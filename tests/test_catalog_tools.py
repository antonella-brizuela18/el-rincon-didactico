from unittest.mock import Mock
from sqlalchemy import select
from app.models import Product
from test_store import app, client, login
from test_drive import mock_drive


def test_modal_preserves_validation_and_only_imports_file(client, mock_drive):
    login(client)
    page=client.get('/admin/productos/nuevo?modal=1&drive_file=pdf')
    assert b'<form' in page.data and b'<html' not in page.data
    assert b'name="drive_file" value="pdf"' in page.data
    assert b'value="Juego"' not in page.data
    error=client.post('/admin/productos/nuevo',data={'price':'NaN'},headers={'X-Product-Modal':'1'})
    assert error.status_code==422 and error.json['error']
    result=client.post('/admin/productos/nuevo',data=dict(title='Completo', description='Propuesta', category='Lenguaje',kind='digital',price='3000',drive_file='pdf',published='on'),headers={'X-Product-Modal':'1'})
    assert result.json=={'saved':True}


def test_drive_picker_is_private_and_scoped(client, mock_drive):
    assert client.get('/admin/drive/archivos').status_code==302
    login(client)
    result=client.get('/admin/drive/archivos')
    assert result.json['files'][0]['kind']=='folder'
    assert any(f['id']=='doc' and f['kind']=='resource' for f in result.json['files'])
    assert client.get('/admin/drive/archivos?folder=outside').status_code==422


def test_examples_created_once_and_never_published(app,client):
    assert client.post('/admin/productos/ejemplos').status_code==302
    login(client)
    for _ in range(2): assert client.post('/admin/productos/ejemplos').status_code==302
    with app.extensions['sessions']() as db:
        examples=db.scalars(select(Product).where(Product.id>3)).all()
        assert len(examples)==6
        assert all(not p.published and p.image and not p.digital_file for p in examples)
    public=client.get('/catalogo')
    assert b'Mi primer abecedario' not in public.data


def test_integrations_never_render_secrets(app,client,monkeypatch):
    assert client.get('/admin/integraciones').status_code==302
    app.config.update(MP_ACCESS_TOKEN='private-mp-token',MP_WEBHOOK_SECRET='private-webhook',MP_COLLECTOR_ID='123',SITE_URL='https://example.test')
    login(client)
    page=client.get('/admin/integraciones')
    assert b'8000' in page.data and b'private-mp-token' not in page.data and b'private-webhook' not in page.data
    from app import catalog_tools
    call=Mock(return_value={'id':123})
    monkeypatch.setattr(catalog_tools,'mp_request',call)
    result=client.post('/admin/integraciones/verificar',data={'service':'mp'},follow_redirects=True)
    assert 'cuenta vendedora verificadas' in result.text
    call.assert_called_once_with('GET','/users/me')


def test_direct_product_shipping_uses_server_product_not_client_dimensions(app,client,monkeypatch):
    import app.shipping as shipping
    call=Mock(return_value=dict(rates=[dict(name='Clásico',delivery='Domicilio',cents=10000)],test=True))
    monkeypatch.setattr(shipping,'quote',call)
    result=client.post('/envios/cotizar',data={'postal_code':'1425','product_id':'2','quantity':'2','weight':'1'})
    assert result.status_code==200 and result.json['origin']=='8000' and result.json['preparation_days']==10
    rows,destination=call.call_args.args
    assert rows[0][0].id==2 and rows[0][1]==2 and destination=='1425'
    with client.session_transaction() as state: state.pop('shipping_last',None)
    assert client.post('/envios/cotizar',data={'postal_code':'1425','product_id':'3'}).status_code==400

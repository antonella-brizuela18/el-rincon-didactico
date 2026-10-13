from unittest.mock import Mock
import requests
from sqlalchemy import select
from app.models import Base, OrderContact, MailOutbox, Parcel, Product
from app.studio import StoreSetting, VisitEvent, DEFAULTS
from test_store import app, client, login, place_order, latest_order

def test_physical_requires_whatsapp_and_preserves_contact(app, client):
    client.post('/carrito/agregar/2')
    client.get('/pedido/nuevo')
    with client.session_transaction() as state: key=state['checkout_key']
    fields=dict(checkout_key=key,name='Cliente Test',email='client@example.test')
    assert client.post('/pedido/nuevo',data=fields).location.endswith('/pedido/nuevo')
    assert latest_order(app) is None
    response=client.post('/pedido/nuevo',data=dict(fields,whatsapp='+54 9 291 509-0223',postal_code='8000'))
    assert '/pedido/' in response.location
    with app.extensions['sessions']() as db:
        contact=db.get(OrderContact,latest_order(app).id)
        assert contact.whatsapp=='5492915090223' and contact.postal_code=='8000'
    login(client)
    assert 'https://wa.me/5492915090223' in client.get('/admin/pedidos/1').text

def test_zero_stock_is_orderable_and_init_db_is_repeatable(app, client):
    with app.extensions['sessions']() as db:
        db.get(Product,2).stock=0;db.commit()
    response,_=place_order(client,2)
    assert latest_order(app).total_cents==200000
    assert 'PreOrder' in client.get('/producto/2').text
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code==0
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code==0
    assert client.get(response.location).status_code==200

def test_payment_unlocks_status_and_mail_exactly_once(app,client):
    app.config['SITE_URL']='https://example.test'
    response,_=place_order(client)
    order=latest_order(app)
    path=response.location.replace('http://localhost','')
    assert client.get(path+'/estado').json=={'status':'pending'}
    assert 'no-store' in client.get(path+'/estado').headers['Cache-Control']
    assert client.get(path+'/descarga/'+str(order.items[0].id)).status_code==403
    login(client)
    endpoint=f'/admin/pedidos/{order.id}/pagar'
    assert client.post(endpoint,data={'verified':'on','reference':'bank'}).status_code==302
    assert client.get(path+'/estado').json=={'status':'paid'}
    assert client.get(path+'/descarga/'+str(order.items[0].id)).status_code==200
    assert client.post(endpoint,data={'verified':'on','reference':'bank'}).status_code==409
    with app.extensions['sessions']() as db:
        assert db.query(MailOutbox).filter_by(event_key=f'order:{order.id}:paid').count()==1
    assert client.get('/pedido/not-a-token/estado').status_code==404

def test_physical_payment_mail_does_not_claim_downloads(app,client):
    app.config['SITE_URL']='https://example.test'
    place_order(client,2);login(client)
    client.post('/admin/pedidos/1/pagar',data={'verified':'on','reference':'bank'})
    with app.extensions['sessions']() as db:
        body=db.scalar(select(MailOutbox).where(MailOutbox.event_key=='order:1:paid')).body
        assert '10 días' in body and 'archivos digitales' not in body

def test_consent_remembered_after_session_loss_and_reversible(app,client):
    assert 'id="consent-title"' in client.get('/').text
    response=client.post('/privacidad/medicion',data={'choice':'no','next':'/catalogo'})
    assert response.location=='/catalogo'
    assert 'Max-Age=15552000' in response.headers.get('Set-Cookie')
    client.delete_cookie(app.config['SESSION_COOKIE_NAME'])
    assert 'id="consent-title"' not in client.get('/').text
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==0
    client.post('/privacidad/medicion',data={'choice':'yes'})
    client.get('/')
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==1
    client.post('/privacidad/medicion',data={'choice':'no'})
    client.get('/producto/1')
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==1
    assert client.post('/privacidad/medicion',data={'choice':'no','next':'//evil.test'}).location=='/'
    assert client.post('/privacidad/medicion',data={'choice':'other'}).status_code==400

def test_new_settings_validate_and_render(client):
    login(client)
    values=dict(DEFAULTS,promo_title='Semana de juegos',promo_text='Conocé las novedades',font='classic',default_mode='dark',accent='#112233')
    assert client.post('/admin/configuracion',data=values).status_code==302
    page=client.get('/').text
    assert 'Semana de juegos' in page and 'font-classic' in page
    assert 'data-default-mode="dark"' in page
    assert '#112233' in client.get('/apariencia.css').text
    for change in ({'accent':'red;}'},{'promo_link':'//evil.test'},{'font':'unknown'},{'shipping_origin':'???'}):
        assert client.post('/admin/configuracion',data=dict(values,**change)).status_code==400

def configure_shipping(app):
    app.config.update(MICORREO_USER='test-user',MICORREO_PASSWORD='test-secret',MICORREO_CUSTOMER_ID='123',MICORREO_TEST=True)
    with app.extensions['sessions']() as db:
        db.add(StoreSetting(key='shipping_origin',value='8000'))
        db.add(Parcel(product_id=2,weight=500,height=5,width=20,length=30));db.commit()

def test_shipping_payload_rates_and_no_automatic_charge(app,client,monkeypatch):
    configure_shipping(app)
    client.post('/carrito/agregar/2');client.post('/carrito/agregar/2')
    call=Mock(side_effect=[Mock(json=lambda:{'token':'test-token'}),Mock(json=lambda:{'rates':[{'productName':'Clásico','deliveredType':'D','price':1234.56}],'validTo':'2026-10-14'})])
    monkeypatch.setattr('app.shipping.requests.post',call)
    response=client.post('/envios/cotizar',data={'postal_code':'1000'})
    assert response.status_code==200 and response.json['rates'][0]['cents']==123456
    payload=call.call_args.kwargs['json']
    assert payload['dimensions']==dict(weight=1000,height=10,width=20,length=30)
    assert payload['postalCodeOrigin']=='8000' and payload['postalCodeDestination']=='1000'
    assert 'test-secret' not in response.text
    assert client.post('/envios/cotizar',data={'postal_code':'1000'}).status_code==429
    assert latest_order(app) is None

def test_shipping_unavailable_and_csrf(app,client,monkeypatch):
    client.post('/carrito/agregar/2')
    assert client.post('/envios/cotizar',data={'postal_code':'invalid'}).status_code==400
    assert client.post('/envios/cotizar',data={'postal_code':'1000'}).status_code==422
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/envios/cotizar',data={'postal_code':'1000'}).status_code==400

def test_shipping_timeout_falls_back(app,client,monkeypatch):
    configure_shipping(app);client.post('/carrito/agregar/2')
    monkeypatch.setattr('app.shipping.requests.post',Mock(side_effect=requests.Timeout()))
    response=client.post('/envios/cotizar',data={'postal_code':'1000'})
    assert response.status_code==422 and 'WhatsApp' in response.json['error']

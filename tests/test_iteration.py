import json
from unittest.mock import Mock
from pathlib import Path
import pytest
from app.models import Fulfillment
from deploy.actions import configuration, verify
from test_store import app, client, login, place_order, latest_order

def test_public_revision_and_assets_cache_busting(app,client):
    app.config['APP_REVISION']='a'*40
    result=client.get('/health/ready')
    assert result.json=={'status':'ok','revision':'a'*40}
    assert result.headers['Cache-Control']=='no-store'
    page=client.get('/')
    assert page.headers['X-App-Revision']=='a'*40
    assert 'experience.js?v=' in page.text and 'experience.css?v=' in page.text

def test_catalogue_sorting(client):
    ascending=client.get('/catalogo?orden=price_asc').text
    descending=client.get('/catalogo?orden=price_desc').text
    assert ascending.index('Imprimible de colores')<ascending.index('Juego de tela')
    assert descending.index('Juego de tela')<descending.index('Imprimible de colores')
    assert 'Limpiar filtros' in ascending and 'noindex' in ascending
    assert client.get('/catalogo?orden=invalid').status_code==200

def test_fulfillment_requires_paid_physical_order_and_admin(app,client):
    response,_=place_order(client,2)
    order=latest_order(app)
    endpoint=f'/admin/pedidos/{order.id}/preparacion'
    assert client.post(endpoint,data={'status':'shipped'}).location.endswith('/admin/login')
    login(client)
    assert client.post(endpoint,data={'status':'shipped'}).status_code==409
    client.post(f'/admin/pedidos/{order.id}/pagar',data={'verified':'on','reference':'bank'})
    assert client.post(endpoint,data={'status':'shipped','tracking':'AR123456'}).status_code==302
    page=client.get(response.location).text
    assert 'Enviado' in page and 'AR123456' in page
    assert 'Guardar preparación' not in page
    assert 'Guardar preparación' in client.get(f'/admin/pedidos/{order.id}').text
    assert client.post(endpoint,data={'status':'bad'}).status_code==400
    assert client.post(endpoint,data={'status':'shipped','tracking':'<script>'}).status_code==400
    with app.extensions['sessions']() as db:
        assert db.query(Fulfillment).count()==1
        assert db.get(Fulfillment,order.id).tracking=='AR123456'

def test_fulfillment_digital_rejected_and_csrf(app,client):
    place_order(client);login(client)
    client.post('/admin/pedidos/1/pagar',data={'verified':'on','reference':'bank'})
    assert client.post('/admin/pedidos/1/preparacion',data={'status':'shipped'}).status_code==409
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/admin/pedidos/1/preparacion',data={'status':'shipped'}).status_code==400

def deployment_config():
    return dict(ALWAYS_SSH_KEY='fake-key',ALWAYS_KNOWN_HOSTS='fake-host',ALWAYS_ACCOUNT='elrincondidactico',ALWAYS_HOST='ssh-elrincondidactico.alwaysdata.net',ALWAYS_PROJECT='/home/elrincondidactico/el-rincon-didactico',ALWAYS_PYTHON='/home/elrincondidactico/venv/bin/python',ALWAYS_URL='https://elrincondidactico.alwaysdata.net',DEPLOY_SHA='b'*40)

def test_deployment_configuration_refuses_missing_and_unexpected_destinations():
    with pytest.raises(ValueError,match='Falta configurar'): configuration({})
    config=deployment_config()
    assert configuration(config)==config
    for key,value in [('DEPLOY_SHA','main;evil'),('ALWAYS_PROJECT','/home/elrincondidactico/../other'),('ALWAYS_HOST','evil.test'),('ALWAYS_URL','http://evil.test')]:
        with pytest.raises(ValueError): configuration(dict(config,**{key:value}))

def test_deploy_verification_refuses_old_healthy_site(monkeypatch):
    response=Mock()
    response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.read=Mock(return_value=json.dumps({'status':'ok','revision':'a'*40}).encode())
    monkeypatch.setattr('deploy.actions.urlopen',Mock(return_value=response))
    assert verify('https://example.test','b'*40,attempts=1,pause=lambda _:None) is False

def test_deploy_verification_accepts_matching_site_only(monkeypatch):
    health=Mock();health.__enter__=Mock(return_value=health);health.__exit__=Mock(return_value=False)
    health.read=Mock(return_value=json.dumps({'status':'ok','revision':'b'*40}).encode())
    page=Mock();page.__enter__=Mock(return_value=page);page.__exit__=Mock(return_value=False)
    page.read=Mock(return_value=b'<button class="mode-toggle"></button><script src="experience.js?v=123"></script>')
    page.headers={'X-App-Revision':'b'*40}
    monkeypatch.setattr('deploy.actions.urlopen',Mock(side_effect=[health,page]))
    assert verify('https://example.test','b'*40,attempts=1,pause=lambda _:None) is True

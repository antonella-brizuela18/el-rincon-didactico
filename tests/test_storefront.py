import json
import re
from sqlalchemy import select
from app.models import Product,Order
from app.studio import VisitEvent
from test_store import app,client

JSON={'Accept':'application/json'}

def test_catalog_api_filters_paginates_and_never_exposes_private_files(app,client):
    data=client.get('/api/catalogo',headers=JSON).json
    assert data['total']==2 and len(data['products'])==2
    assert 'original.pdf' not in json.dumps(data) and 'Borrador' not in json.dumps(data)
    assert client.get('/api/producto/3').status_code==404
    assert client.get('/api/catalogo?tipo=digital').json['total']==1
    assert client.get('/api/catalogo?q=%25').json['total']==0
    with app.extensions['sessions']() as db:
        db.add_all([Product(title=f'Extra {n}',description='Test',category='Juego',kind='physical',price_cents=100,published=True) for n in range(52)])
        db.commit()
    first=client.get('/api/catalogo?orden=price_asc').json
    second=client.get('/api/catalogo?orden=price_asc&pagina=3').json
    assert len(first['products'])==24 and len(second['products'])==6
    assert not {p['id'] for p in first['products']} & {p['id'] for p in second['products']}


def test_json_cart_and_checkout_keep_server_validation_and_idempotency(app,client):
    added=client.post('/carrito/agregar/1',headers=JSON)
    assert added.status_code==200 and added.json['total']==123456
    assert client.get('/api/carrito').json['items'][0]['quantity']==1
    quote=client.get('/pedido/nuevo',headers=JSON).json
    assert quote['checkout_key'] and quote['methods'][0][0]=='transfer'
    fields={'checkout_key':quote['checkout_key'],'name':'Cliente Test','email':'client@example.test','payment_method':'transfer','price':'1'}
    result=client.post('/pedido/nuevo',headers=JSON,data=fields)
    assert result.json['redirect'].split('/pedido/')[1] != 'nuevo'
    duplicate=client.post('/pedido/nuevo',headers=JSON,data=fields)
    assert duplicate.json['redirect']==result.json['redirect']
    assert client.get('/api/carrito').json['items']==[]
    with app.extensions['sessions']() as db:
        orders=db.scalars(select(Order)).all()
        assert len(orders)==1 and orders[0].total_cents==123456


def test_json_checkout_rejects_changed_price_and_has_no_store(app,client):
    client.post('/carrito/agregar/1',headers=JSON)
    key=client.get('/pedido/nuevo',headers=JSON).json['checkout_key']
    with app.extensions['sessions']() as db:
        db.get(Product,1).price_cents=999999;db.commit()
    response=client.post('/pedido/nuevo',headers=JSON,data={'checkout_key':key,'name':'Cliente Test','email':'client@example.test'})
    assert 'precio cambió' in ' '.join(response.json['messages'])
    assert response.headers['Cache-Control']=='private, no-store'
    with app.extensions['sessions']() as db: assert db.scalars(select(Order)).all()==[]


def test_csrf_required_for_json_cart_and_measurement(app,client):
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/carrito/agregar/1',headers=JSON).status_code==400
    token=client.get('/api/carrito').json['csrf']
    assert client.post('/carrito/agregar/1',headers=dict(JSON,**{'X-CSRFToken':token})).status_code==200
    assert client.post('/api/evento',json={'kind':'product','id':1}).status_code==400


def test_spa_events_respect_consent_dnt_and_public_products(app,client):
    assert client.post('/api/evento',json={'kind':'product','id':3}).status_code==404
    client.post('/api/evento',json={'kind':'product','id':1})
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==0
    client.post('/privacidad/medicion',data={'choice':'yes'})
    client.post('/api/evento',json={'kind':'product','id':1},headers={'DNT':'1'})
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==0
    client.post('/api/evento',json={'kind':'product','id':1})
    client.post('/api/evento',json={'kind':'product','id':1})
    with app.extensions['sessions']() as db:
        events=db.query(VisitEvent).all()
        assert len(events)==1 and events[0].kind=='product' and events[0].product_id==1


def test_bootstrap_has_no_operator_email_or_payment_instructions(client):
    response=client.get('/')
    if 'rincon-bootstrap' not in response.text: return # fully working fallback before frontend build
    payload=json.loads(re.search(r'<script id="rincon-bootstrap"[^>]*>(.*?)</script>',response.text,re.S).group(1))
    assert 'payment_instructions' not in payload['store'] and 'order_email' not in payload['store']
    assert 'original.pdf' not in json.dumps(payload)
    assert 'experience.js' not in response.text


def test_public_assets_compress_but_csrf_html_and_json_do_not(client):
    import gzip
    raw=client.get('/ui.css')
    compressed=client.get('/ui.css',headers={'Accept-Encoding':'gzip'})
    assert compressed.headers['Content-Encoding']=='gzip'
    assert gzip.decompress(compressed.data)==raw.data
    assert len(compressed.data)<len(raw.data)/2
    assert 'Accept-Encoding' in compressed.headers['Vary']
    assert client.get('/ui.css',headers={'Accept-Encoding':'gzip;q=0'}).headers.get('Content-Encoding') is None
    for path in ['/','/api/carrito']:
        assert client.get(path,headers={'Accept-Encoding':'gzip'}).headers.get('Content-Encoding') is None

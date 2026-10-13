from sqlalchemy import select
from app.models import OrderPayment
from app.studio import StoreSetting, DEFAULTS
from test_store import app,client,login,place_order,latest_order
from test_payments import enable_mp,headers,payment


def put(app,**values):
    with app.extensions['sessions']() as db:
        for key,value in values.items():
            row=db.get(StoreSetting,key)
            if row:row.value=value
            else:db.add(StoreSetting(key=key,value=value))
        db.commit()


def fields(client,**values):
    client.get('/pedido/nuevo')
    with client.session_transaction() as state:key=state['checkout_key']
    return dict(checkout_key=key,name='Cliente Test',email='client@example.test',**values)


def test_buy_now_preserves_cart_and_next_step(client):
    client.post('/carrito/agregar/2')
    response=client.post('/carrito/agregar/1',data={'intent':'buy_now'})
    assert response.location.endswith('/pedido/nuevo')
    with client.session_transaction() as state:assert state['cart']=={'1':1,'2':1}
    assert 'Crear pedido y continuar al pago' in client.get('/pedido/nuevo').text
    assert 'Comprar ahora' in client.get('/producto/1').text
    assert 'Agregar al carrito +' in client.get('/catalogo').text


def test_selected_transfer_snapshot_survives_settings_changes(app,client):
    put(app,payment_instructions='Alias original',transfer_mode='on')
    client.post('/carrito/agregar/1')
    response=client.post('/pedido/nuevo',data=fields(client,payment_method='transfer'))
    assert latest_order(app).status=='pending'
    put(app,payment_instructions='Alias nuevo',transfer_mode='off')
    assert 'Alias original' in client.get(response.location).text
    assert 'Alias nuevo' not in client.get(response.location).text
    assert client.post(response.location+'/pagar').status_code==409
    with app.extensions['sessions']() as db:assert db.get(OrderPayment,latest_order(app).id).method=='transfer'


def test_invalid_or_disabled_method_never_creates_order(app,client):
    client.post('/carrito/agregar/1')
    response=client.post('/pedido/nuevo',data=fields(client,payment_method='mp'))
    assert response.status_code==302 and latest_order(app) is None
    put(app,checkout_enabled='0')
    assert client.get('/pedido/nuevo').status_code==503
    assert client.post('/pedido/nuevo',data={'payment_method':'transfer'}).status_code==503


def test_mp_disabled_blocks_new_orders_but_accepts_existing_webhook(app,client,monkeypatch):
    enable_mp(app)
    response,key=place_order(client)
    order=latest_order(app)
    put(app,mp_mode='off')
    monkeypatch.setattr('app.routes.mp_request',lambda *a,**kw:payment(order))
    assert client.post('/pagos/mercadopago/webhook?data.id=456',headers=headers(app)).status_code==200
    assert latest_order(app).status=='paid'
    assert client.get(response.location).status_code==200


def test_transfer_cannot_be_silently_paid_by_mp_webhook(app,client,monkeypatch):
    enable_mp(app)
    client.post('/carrito/agregar/1')
    client.post('/pedido/nuevo',data=fields(client,payment_method='transfer'))
    order=latest_order(app)
    monkeypatch.setattr('app.routes.mp_request',lambda *a,**kw:payment(order))
    response=client.post('/pagos/mercadopago/webhook?data.id=456',headers=headers(app))
    assert response.json['status']=='payment-method-review-required'
    assert latest_order(app).status=='pending'


def test_admin_payment_validation_and_public_contact(app,client):
    login(client)
    for change in [{'whatsapp_number':'javascript:alert(1)'},{'preparation_days':'0'},{'transfer_mode':'on','payment_instructions':''},{'mp_mode':'on'},{'transfer_mode':'unexpected'}]:
        assert client.post('/admin/configuracion',data=dict(DEFAULTS,**change)).status_code==400
    values=dict(DEFAULTS,payment_instructions='Banco y alias',transfer_mode='on',whatsapp_number='5492915111111',preparation_days='15')
    assert client.post('/admin/configuracion',data=values).status_code==302
    page=client.get('/producto/2').text
    assert '15 días' in page and 'https://wa.me/5492915111111' in page
    assert 'test-only' not in client.get('/admin/configuracion').text


def test_sorting_and_snapshot_schema_idempotent(app,client):
    html=client.get('/catalogo?orden=price_desc').text
    assert html.index('Juego de tela')<html.index('Imprimible de colores')
    assert client.get('/catalogo?orden=garbage').status_code==200
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code==0
    assert app.test_cli_runner().invoke(args=['init-db']).exit_code==0

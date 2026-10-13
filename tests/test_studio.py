from datetime import timedelta
from sqlalchemy import select
from app.models import MailOutbox, Order, now
from app.studio import StoreSetting, VisitEvent, DEFAULTS
from test_store import app, client, login, place_order, latest_order


def test_navigation_and_seo(client, app):
    app.config['SITE_URL']='https://example.test'
    home=client.get('/').text
    catalog=client.get('/catalogo').text
    assert '/catalogo#catalogo' not in home+catalog
    assert 'Ideas que hacen crecer' in home and 'Ideas que hacen crecer' not in catalog
    assert 'https://example.test/catalogo' in catalog
    assert 'Borrador' not in client.get('/sitemap.xml').text
    assert '/producto/1' in client.get('/sitemap.xml').text
    assert '/producto/3' not in client.get('/sitemap.xml').text
    assert 'noindex' in client.get('/admin/login').headers['X-Robots-Tag']
    assert 'schema.org/Product' in client.get('/producto/1').text


def test_admin_settings_validate_escape_and_persist(client):
    assert client.get('/admin/configuracion').status_code==302
    login(client)
    invalid=dict(DEFAULTS,theme='bad',instagram='javascript:evil')
    assert client.post('/admin/configuracion',data=invalid).status_code==400
    valid=dict(DEFAULTS,hero_title='<script>alert(1)</script>',theme='lavender',order_email='owner@example.test')
    assert client.post('/admin/configuracion',data=valid).status_code==302
    page=client.get('/').text
    assert '&lt;script&gt;' in page and 'theme-lavender' in page
    assert '<script>alert' not in page


def test_analytics_requires_consent_and_excludes_admin_and_dnt(app,client):
    client.get('/')
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==0
    client.post('/privacidad/medicion',data={'choice':'yes'})
    client.get('/')
    client.get('/')
    client.get('/producto/1',headers={'DNT':'1'})
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==1
    client.get('/producto/1')
    login(client)
    client.get('/producto/2')
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==2


def test_order_funnel_owner_mail_and_dashboard(app,client):
    app.config['SITE_URL']='https://example.test'
    with app.extensions['sessions']() as db:
        db.add(StoreSetting(key='order_email',value='owner@example.test'));db.commit()
    client.post('/privacidad/medicion',data={'choice':'yes'})
    client.get('/producto/1')
    response,key=place_order(client)
    client.post('/pedido/nuevo',data={'checkout_key':key})
    with app.extensions['sessions']() as db:
        assert db.query(MailOutbox).count()==2
        assert db.query(VisitEvent).filter_by(kind='order').count()==1
        event=db.scalar(select(VisitEvent).where(VisitEvent.kind=='order'))
        assert event.order_id==latest_order(app).id
    login(client)
    client.post(f'/admin/pedidos/{latest_order(app).id}/pagar',data={'verified':'on','reference':'bank'})
    report=client.get('/admin/estadisticas').text
    assert '100.0%' in report and 'Con pago confirmado' in report
    with app.extensions['sessions']() as db: assert db.query(MailOutbox).count()==4
    assert client.get('/admin/correos').status_code==200


def test_disable_and_expire_analytics(app,client):
    client.post('/privacidad/medicion',data={'choice':'yes'})
    client.get('/')
    client.post('/privacidad/medicion',data={'choice':'no'})
    client.get('/producto/1')
    with app.extensions['sessions']() as db:
        assert db.query(VisitEvent).count()==1
        db.add(VisitEvent(visit='old',kind='visit',created_at=now()-timedelta(days=181)));db.commit()
    assert app.test_cli_runner().invoke(args=['prune-analytics']).exit_code==0
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).count()==1


def test_settings_and_retry_csrf(client,app):
    login(client)
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/admin/configuracion',data=DEFAULTS).status_code==400
    assert client.post('/admin/correos/1/reintentar').status_code==400


def test_failed_cart_not_counted(app,client):
    client.post('/privacidad/medicion',data={'choice':'yes'})
    client.post('/carrito/agregar/2')
    client.post('/carrito/agregar/2')
    client.post('/carrito/agregar/2')
    with app.extensions['sessions']() as db: assert db.query(VisitEvent).filter_by(kind='cart').count()==1

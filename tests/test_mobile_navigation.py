import re
from test_store import app,client,login


def test_bundle_is_fingerprinted_and_private_pages_are_not_cached(app,client):
    html=client.get('/').text
    path=re.search(r'href="([^"]*ui.css[^\"]*)"',html).group(1)
    css=client.get(path)
    assert css.status_code==200 and 'immutable' in css.headers['Cache-Control']
    assert css.mimetype=='text/css'
    assert 'safe-area-inset-bottom' in css.text and 'admin-access' in css.text
    assert client.get(path,headers={'If-None-Match':css.headers['ETag']}).status_code==304
    assert client.get('/ui.css').headers['Cache-Control']=='no-cache'
    assert client.get('/carrito').headers['Cache-Control']=='no-store'
    script=re.search(r'src="([^"]*experience.js[^\"]*)"',html).group(1)
    assert 'immutable' in client.get(script).headers['Cache-Control']
    assert 'immutable' not in client.get('/static/experience.js?v=invalid').headers['Cache-Control']


def test_spa_pages_keep_server_routes_and_security(app,client):
    for path in ['/','/catalogo','/producto/1','/carrito','/admin/login']:
        html=client.get(path,headers={'X-Rincon-Navigation':'1'}).text
        assert 'name="rincon-app"' in html and 'name="rincon-revision"' in html
        assert '<main' in html and '<title>' in html
        assert 'aria-label="Ingresar a administración"' in html
    login(client)
    assert client.get('/admin/configuracion',headers={'X-Rincon-Navigation':'1'}).status_code==200
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/carrito/agregar/1',headers={'X-Rincon-Navigation':'1'}).status_code==400
    assert client.post('/admin/configuracion',headers={'X-Rincon-Navigation':'1'}).status_code==400

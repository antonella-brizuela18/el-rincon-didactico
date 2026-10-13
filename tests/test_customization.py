import io
from PIL import Image
from sqlalchemy import select
from werkzeug.datastructures import MultiDict
from app.studio import DEFAULTS, StoreSetting
from test_store import app, client, login

def fields(**overrides):
    return dict(DEFAULTS,**overrides)

def test_customization_persists_escapes_and_normalizes_contact(client):
    login(client)
    values=fields(brand_name='<script>marca</script>',whatsapp_number='+54 9 291 509-0223',story_title='Nuestra historia',grid_columns='4',card_style='square',hero_layout='compact')
    assert client.post('/admin/configuracion',data=values).status_code==302
    page=client.get('/').text
    assert '&lt;script&gt;marca&lt;/script&gt;' in page and '<script>marca' not in page
    assert 'grid-4' in page and 'cards-square' in page and 'hero-compact' in page
    assert 'Nuestra historia' in page and 'https://wa.me/5492915090223?' in page
    assert 'whatsapp-icon' in page
    for changes in ({'whatsapp_number':'javascript:alert(1)'},{'grid_columns':'20'},{'card_style':'evil'},{'brand_name':''}):
        assert client.post('/admin/configuracion',data=fields(**changes)).status_code==400

def test_section_toggles_and_legacy_forms(client):
    login(client)
    values=fields(show_story='0',show_faq='0',show_categories='0',show_benefits='0')
    assert client.post('/admin/configuracion',data=values).status_code==302
    page=client.get('/').text
    assert 'class="story"' not in page and 'faq-title' not in page and 'category-section' not in page
    # A form left open from a previous version must preserve newer settings.
    legacy={key:value for key,value in fields().items() if key not in __import__('app.customization',fromlist=['DEFAULTS']).DEFAULTS}
    assert client.post('/admin/configuracion',data=legacy).status_code==302
    assert 'class="story"' not in client.get('/').text

def test_uploaded_brand_assets_are_normalized_and_can_be_removed(app,client):
    login(client)
    photo=io.BytesIO();Image.new('RGB',(80,80),'pink').save(photo,'PNG');content=photo.getvalue()
    values=fields(logo_image=(io.BytesIO(content),'logo.png'),hero_image=(io.BytesIO(content),'hero.png'))
    assert client.post('/admin/configuracion',data=values,content_type='multipart/form-data').status_code==302
    with app.extensions['sessions']() as db:
        filename=db.get(StoreSetting,'hero_image').value
        assert filename.endswith('.jpg') and len(filename)==36
    assert 'hero-photo' in client.get('/').text
    assert client.get('/imagenes/'+filename).status_code==200
    assert client.post('/admin/configuracion',data=fields(remove_hero_image='1',remove_logo_image='1')).status_code==302
    assert 'hero-photo' not in client.get('/').text
    assert client.post('/admin/configuracion',data=fields(hero_image=(io.BytesIO(b'<svg/>'),'evil.svg')),content_type='multipart/form-data').status_code==400

def test_asset_references_cannot_be_forged(client):
    login(client)
    assert client.post('/admin/configuracion',data=fields(hero_image='../../secret',logo_image='evil')).status_code==302
    assert '../../secret' not in client.get('/').text

def test_featured_selection_does_not_hide_full_catalogue(client):
    login(client)
    values=MultiDict(fields());values.setlist('featured_ids',['2'])
    assert client.post('/admin/configuracion',data=values).status_code==302
    page=client.get('/').text.split('<main')[1].split('</main>')[0]
    assert 'Elegidos para vos' in page and 'Juego de tela' in page and 'Imprimible de colores' not in page
    assert 'Imprimible de colores' in client.get('/catalogo').text
    values.setlist('featured_ids',['3']) # Draft must never leak even if selected by hand.
    assert client.post('/admin/configuracion',data=values).status_code==302
    assert 'Borrador oculto' not in client.get('/').text
    values.setlist('featured_ids',['1']*9)
    assert client.post('/admin/configuracion',data=values).status_code==400

def test_product_specific_contact_and_quick_buy(client):
    page=client.get('/producto/1').text
    assert 'Consultar por este recurso' in page and 'Imprimible+de+colores' in page
    assert 'Agregar Imprimible de colores al carrito' in client.get('/').text

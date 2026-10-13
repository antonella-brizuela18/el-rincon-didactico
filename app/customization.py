"""Validated presentation choices; never accepts executable HTML or CSS."""
import re
from urllib.parse import urlencode

DEFAULTS = dict(brand_name='El Rincón Didáctico',brand_tagline='Ideas pequeñas. Descubrimientos enormes.',location='Bahía Blanca, Argentina',
                logo_image='',hero_image='',hero_eyebrow='Un rincón hecho de ideas y amor',hero_cta='Explorar recursos',hero_note='Para docentes, familias y pequeñas grandes mentes.',
                hero_layout='spacious',card_style='soft',image_fit='contain',grid_columns='3',header_sticky='0',show_categories='1',show_story='1',show_faq='1',show_benefits='1',
                story_title='Una idea pequeña puede ser el comienzo de algo enorme.',story_text='Un espacio pensado para docentes y familias que creen en el juego como una forma de descubrir el mundo.',
                whatsapp_number='5492915090223',whatsapp_label='WhatsApp',whatsapp_message='Hola, quisiera consultar sobre los recursos de El Rincón Didáctico.',featured_ids='')
LIMITS=dict(brand_name=60,brand_tagline=120,location=80,hero_eyebrow=80,hero_cta=40,hero_note=140,story_title=120,story_text=350,whatsapp_label=24,whatsapp_message=200,whatsapp_number=25,
            hero_layout=15,card_style=12,image_fit=10,grid_columns=1,header_sticky=1,show_categories=1,show_story=1,show_faq=1,show_benefits=1)
CHOICES=dict(hero_layout=('spacious','compact'),card_style=('soft','square','round'),image_fit=('contain','cover'),grid_columns=('2','3','4'))
TOGGLES=('header_sticky','show_categories','show_story','show_faq','show_benefits')

def read_values(form, current):
    values={k:current.get(k,v) for k,v in DEFAULTS.items()}
    for key in LIMITS:
        if key in form: values[key]=form[key].strip()
    for key in TOGGLES:
        if form.get('customization_version')=='1' or key in form:
            values[key]='1' if form.get(key)=='1' else '0'
    values['whatsapp_number']=re.sub(r'[\s()+-]','',values['whatsapp_number'])
    if 'featured_ids' in form:
        selected=[item for item in form.getlist('featured_ids') if item]
        # Legacy dictionary submissions can contain the empty setting.
        if len(selected)>8 or any(not re.fullmatch(r'[1-9][0-9]{0,8}',item) for item in selected):
            raise ValueError('Elegí hasta ocho recursos destacados.')
        values['featured_ids']=','.join(dict.fromkeys(selected))
    if any(len(values[k])>limit for k,limit in LIMITS.items()):
        raise ValueError('Hay textos de personalización que exceden su límite.')
    if any(values[k] not in choices for k,choices in CHOICES.items()):
        raise ValueError('Elegí una presentación y una grilla válidas.')
    if not re.fullmatch(r'[1-9][0-9]{9,14}',values['whatsapp_number']):
        raise ValueError('El WhatsApp debe incluir código de país, por ejemplo +5492915090223.')
    if not all(values[k] for k in ('brand_name','hero_cta','whatsapp_label')):
        raise ValueError('Completá el nombre de marca y los textos de los botones.')
    return values

def save_assets(files, form, values):
    from app.routes import save_image
    for key in ('logo_image','hero_image'):
        if form.get('remove_'+key)=='1': values[key]=''
        upload=files.get(key)
        if upload and upload.filename: values[key]=save_image(upload)

def whatsapp_url(values, message=None):
    return 'https://wa.me/'+values['whatsapp_number']+'?'+urlencode({'text':values['whatsapp_message'] if message is None else message})

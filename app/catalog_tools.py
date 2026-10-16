"""Operator-only catalog examples and connection diagnostics; never expose secrets."""
import secrets
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from PIL import Image, ImageDraw
from sqlalchemy import select
from app.routes import admin_required, db
from app.models import Product
from app import drive
from app.payments import mp_ready, mp_request, PaymentError

catalog_tools = Blueprint('catalog_tools', __name__)

EXAMPLES = [
    ('Colores para descubrir', 'Exploración y colores', 'Sala de 2 y 3', 'digital', 350000,
     'Propuesta de ejemplo: tarjetas de colores y consignas para buscar objetos, clasificar y conversar. Definí cantidad de tarjetas, tamaño de impresión y adjuntá tu PDF antes de publicar.'),
    ('Mi primer abecedario', 'Lenguaje', 'Sala de 5 y primer ciclo', 'digital', 450000,
     'Propuesta de ejemplo: letras y palabras cercanas para acompañar los primeros encuentros con la escritura. Completá las actividades incluidas y adjuntá el archivo final.'),
    ('Contamos jugando', 'Matemática', 'Sala de 4 y 5', 'digital', 400000,
     'Propuesta de ejemplo: asociación de números y cantidades del 1 al 10. Revisá consignas, cantidad de piezas y nivel sugerido; agregá tu material descargable.'),
    ('Un rincón de emociones', 'Emociones', 'Nivel inicial', 'digital', 500000,
     'Propuesta de ejemplo: tarjetas para reconocer emociones y abrir conversaciones en el aula o en casa. Detallá el contenido y adjuntá tu PDF de venta.'),
    ('Memotest de animales', 'Juegos de mesa', 'Desde 3 años', 'physical', 1200000,
     'Propuesta de ejemplo: juego de pares con animales para ejercitar la observación y la memoria. Definí materiales, tamaño y cantidad de piezas. Elaboración a pedido: aproximadamente 10 días desde el pago, más el traslado. Envío a coordinar por WhatsApp.'),
    ('Kit de juego simbólico', 'Juego simbólico', 'Desde 3 años', 'physical', 1800000,
     'Propuesta de ejemplo: materiales para inventar historias y acompañar el juego cotidiano. Detallá qué incluye, medidas y cuidados. Elaboración a pedido: aproximadamente 10 días desde el pago, más el traslado. Envío a coordinar por WhatsApp.'),
]

def create_samples():
    from app.studio import StoreSetting
    # Lock one existing operator row to serialize simultaneous clicks on PostgreSQL.
    from app.models import Admin
    db().scalar(select(Admin).order_by(Admin.id).limit(1).with_for_update())
    if db().get(StoreSetting, 'catalog_examples_v1'):
        return False
    palette = ['#f5dce7','#e2e8c4','#e5ddf3','#f7dfbb','#dceceb','#eed9df']
    for index, (title, category, age, kind, price, description) in enumerate(EXAMPLES):
        image = Image.new('RGB', (900, 900), palette[index])
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((130,140,770,760),radius=45,fill='#fffdf7',outline='#614353',width=4)
        for i in range(3):
            draw.ellipse((230+i*150,270,340+i*150,380),fill=palette[(index+i+1)%6])
        draw.rectangle((250,470,650,495),fill='#614353')
        draw.rectangle((310,530,590,544),fill=palette[index])
        draw.text((390,640),'EJEMPLO',fill='#614353',font_size=26)
        filename=secrets.token_hex(16)+'.jpg'
        image.save(Path(current_app.config['STORAGE_DIR'])/'images'/filename,quality=85)
        db().add(Product(title=title, category=category, age=age, kind=kind, price_cents=price,
                         description=description, stock=0, published=False, image=filename))
    db().add(StoreSetting(key='catalog_examples_v1',value='created'))
    db().commit()
    return True

@catalog_tools.post('/admin/productos/ejemplos')
@admin_required
def samples():
    flash('Creamos seis borradores de ejemplo. Revisá los precios y completá los archivos antes de publicarlos.' if create_samples() else 'Los ejemplos ya fueron creados. Encontralos en Mis recursos → Borradores.')
    return redirect(url_for('main.admin',visibilidad='draft')+'#mis-recursos')

@catalog_tools.get('/admin/integraciones')
@admin_required
def integrations():
    from app.studio import settings
    config=current_app.config
    return render_template('integrations.html', mp_connected=mp_ready(), mp_live=config['MP_LIVE_MODE'],
                           shipping_connected=all(config.get(k) for k in ('MICORREO_USER','MICORREO_PASSWORD','MICORREO_CUSTOMER_ID')),
                           shipping_test=config['MICORREO_TEST'], drive_connected=drive.configured(),
                           origin=settings()['shipping_origin'], site_url=config['SITE_URL'])

@catalog_tools.post('/admin/integraciones/verificar')
@admin_required
def verify():
    service=request.form.get('service')
    if service=='mp':
        try:
            if not mp_ready(): raise PaymentError()
            profile=mp_request('GET','/users/me')
            if str(profile.get('id'))!=str(current_app.config['MP_COLLECTOR_ID']):
                flash('Mercado Pago respondió, pero el ID de vendedor no coincide. Revisá la cuenta configurada.')
            else: flash('Mercado Pago: credencial y cuenta vendedora verificadas. Falta validar el webhook mediante un pago de prueba.')
        except PaymentError:
            flash('No pudimos verificar Mercado Pago. Revisá la credencial privada, el ID de vendedor y la conexión.')
    elif service=='drive':
        try:
            drive.list_folder()
            flash('Drive: acceso de lectura a la carpeta verificado.')
        except drive.DriveError as error: flash(str(error))
    else:
        flash('Elegí una conexión válida.')
    return redirect(url_for('catalog_tools.integrations'))

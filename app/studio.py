"""Store presentation settings, first-party consented analytics and operator tools."""
import json
import re
import secrets
from datetime import timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from flask import Blueprint, Response, abort, current_app, g, redirect, render_template, request, session, url_for, flash
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError
from app.models import Base, Product, Order, MailOutbox, now
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.routes import db, admin_required

studio = Blueprint('studio', __name__)

class StoreSetting(Base):
    __tablename__ = 'store_settings'
    key = Column(String(60), primary_key=True)
    value = Column(Text, nullable=False)

class VisitEvent(Base):
    __tablename__ = 'visit_events'
    id = Column(Integer, primary_key=True)
    visit = Column(String(48), nullable=False, index=True)
    kind = Column(String(30), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    order_id = Column(Integer, ForeignKey('orders.id'))
    created_at = Column(DateTime, nullable=False, default=now, index=True)

DEFAULTS = dict(hero_title='Ideas que hacen crecer la imaginación.', hero_text='Materiales didácticos y recursos para transformar los momentos de cada día en pequeñas aventuras de aprendizaje.', announcement='Creado con amor para aprender jugando', theme='floral', contact_email='', order_email='', instagram='elrincondidactico_', seo_description='Materiales didácticos e imprimibles para docentes y familias. El Rincón Didáctico, desde Bahía Blanca: juego, creatividad y aprendizaje.', analytics_enabled='1')
DEFAULTS.update(payment_instructions='', transfer_mode='auto', mp_mode='auto', checkout_enabled='1', whatsapp='5492915090223', preparation_days='10', delivery_note='El envío se coordina por WhatsApp y se abona por separado. Podés consultar su estimación antes de confirmar.', font='editorial', default_mode='system', promo_title='', promo_text='', promo_link='/catalogo', promo_label='Ver recursos', accent='#345b32', shipping_origin='')

@studio.before_app_request
def restore_consent():
    choice = request.cookies.get('rincon_measurement')
    if choice in ('yes','no'):
        session['analytics_consent'] = choice=='yes'

def settings():
    if 'store_settings' not in g:
        values = DEFAULTS.copy()
        values['contact_email'] = current_app.config.get('CONTACT_EMAIL', '')
        values['payment_instructions'] = current_app.config.get('PAYMENT_INSTRUCTIONS', '')
        with current_app.extensions['sessions']() as connection:
            values.update({row.key:row.value for row in connection.scalars(select(StoreSetting)) if row.key in DEFAULTS})
        g.store_settings = values
    return g.store_settings

@studio.app_context_processor
def context():
    private = request.path.startswith(('/admin', '/pedido', '/carrito'))
    canonical = current_app.config['SITE_URL'] + request.path
    if request.endpoint == 'main.catalog' and request.args.get('pagina', type=int) and request.args.get('pagina', type=int)>1:
        canonical += '?pagina='+str(request.args.get('pagina', type=int))
    from app.payments import payment_methods, mp_ready
    smtp_ready=all(current_app.config.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'))
    return dict(payment_methods=payment_methods, mp_ready=mp_ready(), smtp_ready=smtp_ready, store=settings(), is_admin=request.path.startswith('/admin') and bool(session.get('admin_id')), private_page=private, canonical=canonical, seo_noindex=private or bool(request.args.get('q') or request.args.get('categoria') or request.args.get('tipo')))

@studio.post('/privacidad/medicion')
def consent():
    choice = request.form.get('choice')
    if choice not in ('yes','no'): abort(400)
    session['analytics_consent'] = choice == 'yes'
    session.pop('analytics_visit', None)
    target = request.form.get('next', '/')
    if not target.startswith('/') or target.startswith('//') or '\\' in target or any(ord(c)<32 for c in target): target='/'
    response = redirect(target)
    response.set_cookie('rincon_measurement', choice, max_age=180*86400, secure=current_app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
    return response

@studio.after_app_request
def measure(response):
    if request.path.startswith(('/admin', '/pedido', '/carrito')) or response.status_code>=400:
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    events = {'main.home':'visit', 'main.catalog':'catalog', 'main.product_detail':'product', 'main.add_to_cart':'cart', 'main.checkout':'checkout'}
    kind = events.get(request.endpoint)
    if not kind or response.status_code>=400 or session.get('admin_id') or not session.get('analytics_consent') or request.headers.get('DNT')=='1' or request.headers.get('Sec-GPC')=='1':
        return response
    if settings()['analytics_enabled']!='1':
        return response
    if request.method=='POST':
        kind = getattr(g, 'analytics_event', None)
    elif response.status_code!=200:
        return response
    if not kind:
        return response
    stamp = now().timestamp()
    if stamp-session.get('analytics_last', 0)>1800:
        session['analytics_visit'] = secrets.token_hex(20)
    visit = session.setdefault('analytics_visit', secrets.token_hex(20))
    session['analytics_last'] = stamp
    try:
        with current_app.extensions['sessions']() as connection:
            # Each funnel step counts once per visit/product/order, independent of refreshes.
            values = dict(visit=visit, kind=kind, product_id=(request.view_args or {}).get('identifier'), order_id=getattr(g, 'analytics_order', None))
            if not connection.scalar(select(VisitEvent.id).filter_by(**values).limit(1)):
                connection.add(VisitEvent(**values))
                connection.commit()
    except SQLAlchemyError:
        current_app.logger.warning('Analytics write failed; customer response preserved')
    return response

@studio.get('/apariencia.css')
def appearance():
    accent = settings()['accent']
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent): accent=DEFAULTS['accent']
    # Validated CSS value, separate resource compatible with strict CSP.
    channels=[int(accent[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
    luminance=sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
    foreground='#000' if luminance>.179 else '#fff'
    return Response(':root{--brand-accent:'+accent+';--accent-ink:'+foreground+'}', mimetype='text/css', headers={'Cache-Control':'no-cache'})

@studio.get('/privacidad')
def privacy():
    return render_template('privacy.html')

@studio.route('/admin/configuracion', methods=['GET','POST'])
@admin_required
def configuration():
    if request.method=='POST':
        values={key:request.form.get(key,'').strip() for key in DEFAULTS}
        limits=dict(payment_instructions=4000,transfer_mode=10,mp_mode=10,checkout_enabled=1,whatsapp=15,preparation_days=3,delivery_note=400,font=20,default_mode=10,promo_title=100,promo_text=250,promo_link=200,promo_label=40,accent=7,shipping_origin=8,hero_title=100,hero_text=350,announcement=140,theme=20,contact_email=254,order_email=254,instagram=30,seo_description=180,analytics_enabled=1)
        error = any(len(values[k])>limit for k,limit in limits.items())
        error |= values['transfer_mode'] not in ('auto','on','off') or values['mp_mode'] not in ('auto','on','off')
        error |= bool(values['whatsapp']) and not bool(re.fullmatch(r'[1-9][0-9]{9,14}',values['whatsapp']))
        error |= not bool(re.fullmatch(r'[0-9]{1,3}',values['preparation_days'])) or not 1<=int(values['preparation_days'] or '0')<=120
        error |= values['transfer_mode']=='on' and not values['payment_instructions']
        from app.payments import mp_ready
        error |= values['mp_mode']=='on' and not mp_ready()
        values['checkout_enabled']='1' if values['checkout_enabled']=='1' else '0'
        error |= values['font'] not in ('editorial','rounded','classic')
        error |= values['default_mode'] not in ('system','light','dark')
        error |= not bool(re.fullmatch(r'#[0-9a-fA-F]{6}', values['accent']))
        values['shipping_origin']=values['shipping_origin'].upper()
        error |= bool(values['shipping_origin']) and not bool(re.fullmatch(r'(?:[0-9]{4}|[A-Z][0-9]{4}[A-Z]{3})',values['shipping_origin']))
        error |= not bool(re.fullmatch(r'/[a-zA-Z0-9/_?=&%#.-]*',values['promo_link'])) or values['promo_link'].startswith('//')
        error |= values['theme'] not in ('floral','lavender','sunshine')
        error |= not bool(re.fullmatch(r'[a-zA-Z0-9_.]{1,30}',values['instagram']))
        error |= any(values[k] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',values[k]) for k in ('contact_email','order_email'))
        error |= not values['hero_title'] or not values['seo_description']
        if error:
            flash('Revisá los campos: título y descripción obligatorios, correos válidos y textos dentro de sus límites.')
            return render_template('settings.html', values=values),400
        values['analytics_enabled']='1' if values['analytics_enabled']=='1' else '0'
        for key,value in values.items():
            row=db().get(StoreSetting,key)
            if row: row.value=value
            else: db().add(StoreSetting(key=key,value=value))
        db().commit()
        flash('Configuración guardada. Los cambios ya se ven en tu tienda.')
        return redirect(url_for('studio.configuration'))
    return render_template('settings.html',values=settings())

@studio.get('/admin/estadisticas')
@admin_required
def analytics():
    days=request.args.get('dias',30,type=int)
    if days not in (7,30,90): days=30
    since=now()-timedelta(days=days)
    # Cohort denominator includes visits that enter directly on a product or checkout.
    cohort=select(VisitEvent.visit).group_by(VisitEvent.visit).having(func.min(VisitEvent.created_at)>=since)
    scope=(VisitEvent.visit.in_(cohort),)
    visitors=db().scalar(select(func.count(func.distinct(VisitEvent.visit))).where(*scope)) or 0
    steps=[]
    for kind,label in [('product','Vieron un recurso'),('cart','Agregaron al carrito'),('checkout','Iniciaron el pedido'),('order','Crearon un pedido')]:
        count=db().scalar(select(func.count(func.distinct(VisitEvent.visit))).where(*scope,VisitEvent.kind==kind)) or 0
        steps.append((label,count,round(count/visitors*100,1) if visitors else 0))
    paid_visits=db().scalar(select(func.count(func.distinct(VisitEvent.visit))).join(Order,Order.id==VisitEvent.order_id).where(*scope,Order.status=='paid')) or 0
    steps.append(('Con pago confirmado',paid_visits,round(paid_visits/visitors*100,1) if visitors else 0))
    orders=db().scalar(select(func.count(Order.id)).where(Order.created_at>=since)) or 0
    revenue=db().scalar(select(func.sum(Order.total_cents)).where(Order.status=='paid',Order.paid_at>=since)) or 0
    top=db().execute(select(Product.title,func.count(func.distinct(VisitEvent.visit))).join(VisitEvent,VisitEvent.product_id==Product.id).where(VisitEvent.kind=='product',VisitEvent.created_at>=since).group_by(Product.id,Product.title).order_by(func.count(func.distinct(VisitEvent.visit)).desc()).limit(10)).all()
    daily=db().execute(select(func.date(VisitEvent.created_at),func.count(func.distinct(VisitEvent.visit))).where(VisitEvent.created_at>=since).group_by(func.date(VisitEvent.created_at)).order_by(func.date(VisitEvent.created_at))).all()
    return render_template('analytics.html',days=days,visitors=visitors,steps=steps,orders=orders,revenue=revenue,top=top,daily=daily)

@studio.get('/admin/correos')
@admin_required
def mail():
    rows=db().scalars(select(MailOutbox).order_by(MailOutbox.id.desc()).limit(100)).all()
    ready=all(current_app.config.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'))
    return render_template('mail.html',rows=rows,ready=ready)

@studio.post('/admin/correos/<int:identifier>/reintentar')
@admin_required
def retry_mail(identifier):
    row=db().get(MailOutbox,identifier)
    if not row: abort(404)
    if row.sent_at is None:
        row.attempts=0
        db().commit()
        flash('Correo habilitado para el próximo envío automático.')
    return redirect(url_for('studio.mail'))

@studio.get('/sitemap.xml')
def sitemap():
    root=Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    paths=['/','/catalogo']+[url_for('main.product_detail',identifier=p) for p in db().scalars(select(Product.id).where(Product.published.is_(True)))]
    for path in paths:
        SubElement(SubElement(root,'url'),'loc').text=current_app.config['SITE_URL']+path
    return Response(tostring(root,encoding='utf-8',xml_declaration=True),mimetype='application/xml')

@studio.get('/robots.txt')
def robots():
    return Response('User-agent: *\nDisallow: /admin\nDisallow: /pedido\nDisallow: /carrito\nSitemap: '+current_app.config['SITE_URL']+'/sitemap.xml\n',mimetype='text/plain')

def register(app):
    app.register_blueprint(studio)
    @app.cli.command('prune-analytics')
    def prune():
        """Remove anonymous measurement events older than 180 days."""
        import click
        with app.extensions['sessions']() as connection:
            connection.execute(delete(VisitEvent).where(VisitEvent.created_at<now()-timedelta(days=180)))
            connection.commit()
        click.echo('Mediciones antiguas eliminadas.')


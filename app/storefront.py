"""Public JSON contracts. Orders still use the existing transactional checkout."""
import json
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, session, url_for, g, get_flashed_messages
from flask_wtf.csrf import generate_csrf
from sqlalchemy import select, func
from app.models import Product
from app.routes import db, cart_rows
from app.studio import settings
from app.customization import whatsapp_url
api=Blueprint('storefront',__name__)

def product_data(p):
    return dict(id=p.id,title=p.title,description=p.description,category=p.category,age=p.age,kind=p.kind,price=p.price_cents,image=url_for('main.image',filename=p.image) if p.image else None)

def catalogue():
    query=select(Product).where(Product.published.is_(True))
    q=request.args.get('q','').strip()[:100]
    category=request.args.get('categoria','')[:80]
    kind=request.args.get('tipo','')
    if q: query=query.where(Product.title.icontains(q,autoescape=True)|Product.description.icontains(q,autoescape=True))
    if category: query=query.where(Product.category==category)
    if kind in ('digital','physical'): query=query.where(Product.kind==kind)
    total=db().scalar(select(func.count()).select_from(query.subquery()))
    sorting={'recent':(Product.created_at.desc(),Product.id.desc()),'price_asc':(Product.price_cents.asc(),Product.id.asc()),'price_desc':(Product.price_cents.desc(),Product.id.asc()),'title':(Product.title.asc(),Product.id.asc())}
    page=max(1,min(request.args.get('pagina',1,type=int) or 1,max(1,(total+23)//24)))
    products=db().scalars(query.order_by(*sorting.get(request.args.get('orden'),sorting['recent'])).offset((page-1)*24).limit(24)).all()
    return dict(products=[product_data(p) for p in products],total=total,page=page,pages=max(1,(total+23)//24))

def cart_data():
    rows=cart_rows()
    refreshed={str(p.id):min(q,10) if p.kind=='physical' else 1 for p,q in rows}
    if session.get('cart',{})!=refreshed:
        session['cart']=refreshed
        session.pop('checkout_key',None)
    return dict(items=[dict(product=product_data(p),quantity=refreshed[str(p.id)]) for p,q in rows],total=sum(p.price_cents*refreshed[str(p.id)] for p,q in rows))

@api.get('/api/catalogo')
def catalog_api():
    return jsonify(catalogue())

@api.get('/api/producto/<int:identifier>')
def product_api(identifier):
    p=db().get(Product,identifier)
    if not p or not p.published: return jsonify(error='Este recurso ya no está disponible.'),404
    return jsonify(product_data(p))

@api.get('/api/carrito')
def cart_api():
    return jsonify(**cart_data(),csrf=generate_csrf())

@api.after_request
def private_json(response):
    response.headers['Cache-Control']='private, no-store'
    response.headers['X-Robots-Tag']='noindex, nofollow'
    return response

@api.post('/api/evento')
def event():
    value=request.get_json(silent=True) or {}
    kind=value.get('kind')
    if kind not in ('visit','catalog','product','checkout'): return jsonify(error='Evento inválido.'),400
    identifier=value.get('id')
    if kind=='product':
        if not isinstance(identifier,int): return jsonify(error='Recurso inválido.'),400
        product=db().get(Product,identifier)
        if not product or not product.published: return jsonify(error='Recurso inválido.'),404
        request.view_args['identifier']=identifier
    g.analytics_event=kind
    return jsonify(ok=True)

def register(app):
    app.register_blueprint(api)
    @app.after_request
    def json_mutations(response):
        endpoints=('main.add_to_cart','main.remove_from_cart','main.update_cart_quantity','main.checkout')
        if request.accept_mimetypes.best=='application/json' and request.endpoint in endpoints:
            if response.status_code in (302,303):
                target=response.headers['Location']
                messages=get_flashed_messages()
                payload=dict(redirect=target,messages=messages)
                if request.endpoint!='main.checkout': payload.update(cart_data())
                response=jsonify(payload)
            elif response.mimetype=='text/html':
                response=jsonify(error='No pudimos validar la solicitud. Volvé a abrir el formulario.'),response.status_code
                response=app.make_response(response)
            response.headers['Cache-Control']='private, no-store'
        return response
    @app.context_processor
    def frontend_context():
        # No build means fully functional HTML fallback (CLI/test/first installation).
        manifest=Path(app.static_folder)/'storefront/.vite/manifest.json'
        enabled=request.endpoint in ('main.home','main.catalog','main.product_detail','main.cart','main.checkout') and request.method=='GET' and manifest.is_file() and (request.endpoint!='main.checkout' or getattr(g,'react_checkout',False))
        if not enabled: return dict(react_storefront=False)
        entry=json.loads(manifest.read_text())['src/main.tsx']
        options=settings()
        public={key:value for key,value in options.items() if key not in ('order_email','payment_instructions','shipping_origin')}
        featured_ids=[int(value) for value in options['featured_ids'].split(',') if value.isdigit()]
        featured=[product_data(p) for p in db().scalars(select(Product).where(Product.published.is_(True),Product.id.in_(featured_ids)))] if featured_ids else []
        data=dict(featured=featured,store=public,csrf=generate_csrf(),cart=cart_data(),catalog=catalogue(),categories=db().scalars(select(Product.category).where(Product.published.is_(True)).distinct().order_by(Product.category)).all(),whatsapp=whatsapp_url(options),consent=session.get('analytics_consent'),admin=bool(session.get('admin_id')),revision=app.config['APP_REVISION'])
        if request.endpoint=='main.checkout':
            from app.payments import payment_methods
            data['checkout']=dict(**data['cart'],checkout_key=session['checkout_key'],methods=payment_methods(any(i['product']['kind']=='physical' for i in data['cart']['items'])))
        if request.endpoint=='main.product_detail':
            data['product']=product_data(db().get(Product,request.view_args['identifier']))
        return dict(react_storefront=True,frontend_data=data,frontend_script='storefront/'+entry['file'],frontend_css=['storefront/'+name for name in entry.get('css',[])])

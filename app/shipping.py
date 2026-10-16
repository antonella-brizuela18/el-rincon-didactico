"""MiCorreo quotations only. Dispatch and payment remain with the operator."""
from decimal import Decimal, InvalidOperation
import re
import requests
from flask import Blueprint, current_app, jsonify, request, session
from app.models import Parcel, Product
from app.routes import cart_rows, db
from app.studio import settings

shipping = Blueprint('shipping', __name__)

class ShippingError(Exception):
    pass

def quote(rows, destination):
    config = current_app.config
    if not all(config.get(k) for k in ('MICORREO_USER','MICORREO_PASSWORD','MICORREO_CUSTOMER_ID')):
        raise ShippingError('El envío se cotiza por WhatsApp mientras conectamos MiCorreo.')
    origin = settings()['shipping_origin']
    if not re.fullmatch(r'(?:[0-9]{4}|[A-Z][0-9]{4}[A-Z]{3})', origin):
        raise ShippingError('Falta configurar el código postal de origen. Coordinaremos por WhatsApp.')
    parcels = []
    for product, quantity in rows:
        if product.kind != 'physical': continue
        parcel = db().get(Parcel, product.id)
        if not parcel:
            raise ShippingError('Este material necesita una cotización personalizada. Coordinaremos por WhatsApp.')
        parcels.extend([parcel]*quantity)
    if not parcels:
        raise ShippingError('Los recursos digitales no requieren envío.')
    # Conservative stacked bounding box; the operator verifies final packaging.
    dimensions = dict(weight=sum(p.weight for p in parcels), height=sum(p.height for p in parcels), width=max(p.width for p in parcels), length=max(p.length for p in parcels))
    if dimensions['weight']>25000 or max(dimensions[k] for k in ('height','width','length'))>150:
        raise ShippingError('El pedido requiere más de un paquete. Coordinaremos el envío por WhatsApp.')
    base = 'https://apitest.correoargentino.com.ar/micorreo/v1' if config['MICORREO_TEST'] else 'https://api.correoargentino.com.ar/micorreo/v1'
    try:
        auth = requests.post(base+'/token', auth=(config['MICORREO_USER'],config['MICORREO_PASSWORD']), timeout=10)
        auth.raise_for_status()
        token = auth.json()['token']
        response = requests.post(base+'/rates', headers={'Authorization':'Bearer '+token}, json=dict(customerId=config['MICORREO_CUSTOMER_ID'], postalCodeOrigin=origin, postalCodeDestination=destination, dimensions=dimensions), timeout=15)
        response.raise_for_status()
        payload = response.json()
        rates = []
        for row in payload['rates']:
            price = Decimal(str(row['price']))
            if not price.is_finite() or price<=0 or price>10000000 or row['deliveredType'] not in ('D','S'): raise ValueError()
            rates.append(dict(name=str(row['productName'])[:100], delivery='Domicilio' if row['deliveredType']=='D' else 'Sucursal', cents=int(price*100)))
        if not rates: raise ValueError()
        return dict(rates=rates, valid_to=str(payload.get('validTo',''))[:50], test=config['MICORREO_TEST'])
    except (requests.RequestException, ValueError, KeyError, TypeError, InvalidOperation):
        raise ShippingError('MiCorreo no pudo cotizar ahora. Podés continuar y coordinar el envío por WhatsApp.') from None

@shipping.post('/envios/cotizar')
def rates():
    from app.models import now
    stamp = now().timestamp()
    if stamp-session.get('shipping_last',0)<15:
        return jsonify(error='Esperá unos segundos antes de volver a cotizar.'),429
    destination = request.form.get('postal_code','').strip().upper()
    if not re.fullmatch(r'(?:[0-9]{4}|[A-Z][0-9]{4}[A-Z]{3})',destination):
        return jsonify(error='Ingresá un código postal argentino válido.'),400
    session['shipping_last'] = stamp
    try:
        if request.form.get('product_id'):
            product=db().get(Product,request.form.get('product_id',type=int))
            quantity=request.form.get('quantity',1,type=int)
            if not product or not product.published or product.kind!='physical' or quantity is None or not 1<=quantity<=10:
                return jsonify(error='Elegí un material físico publicado y entre 1 y 10 unidades.'),400
            rows=[(product,quantity)]
        else:
            rows=cart_rows()
        result=quote(rows,destination)
        result.update(origin=settings()['shipping_origin'],preparation_days=int(settings()['preparation_days']))
        return jsonify(result)
    except ShippingError as error:
        return jsonify(error=str(error)),422

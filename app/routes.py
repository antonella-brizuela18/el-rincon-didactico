"""Catalogue, administration and payment-gated fulfilment."""
import hashlib
import hmac
import io
import re
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, send_from_directory, session, url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import Admin, LoginAttempt, Order, OrderItem, Product, now
from app import csrf
from app.payments import PaymentError, mp_configured, mp_request, valid_signature
from app.notifications import enqueue_mail
from app import drive
main = Blueprint("main", __name__)
DUMMY_HASH = generate_password_hash("not-an-account-password")

def db():
    if "db" not in g:
        g.db = current_app.extensions["sessions"]()
    return g.db

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id") or not db().get(Admin, session["admin_id"]):
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)
    return wrapped

def signer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="customer-order-v1")

def order_link(order):
    return url_for("main.order_detail", token=signer().dumps(order.checkout_key), _external=True)

def customer_order(token):
    try:
        key = signer().loads(token, max_age=30*86400)
    except (BadSignature, SignatureExpired):
        abort(404)
    order = db().scalar(select(Order).where(Order.checkout_key==key))
    if not order:
        abort(404)
    return order

def cart_rows(lock=False):
    rows = []
    for identifier, quantity in sorted(session.get("cart", {}).items(), key=lambda entry:int(entry[0])):
        query = select(Product).where(Product.id==int(identifier), Product.published.is_(True))
        if lock:
            query = query.with_for_update()
        product = db().scalar(query)
        if product:
            rows.append((product, quantity))
    return rows

@main.app_context_processor
def shared_context():
    def pagination_url(endpoint, parameter, page, anchor=""):
        allowed = {"q","categoria","tipo","recurso","visibilidad","pedido","estado","recursos_pagina","pedidos_pagina"}
        arguments = {key:value[:100] for key,value in request.args.items() if key in allowed and value}
        arguments[parameter] = page
        return url_for(endpoint, _anchor=anchor, **arguments)
    return {"cart_count":sum(session.get("cart", {}).values()), "order_link":order_link,
            "mp_configured":mp_configured(), "pagination_url":pagination_url}


def paginate(query, name="pagina", per_page=24):
    total = db().scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    pages = max(1, (total+per_page-1)//per_page)
    page = min(pages, max(1, request.args.get(name, 1, type=int) or 1))
    rows = db().scalars(query.offset((page-1)*per_page).limit(per_page)).all()
    return rows, {"total":total, "page":page, "pages":pages}

@main.get("/")
def home():
    return catalogue_page(True)

@main.get("/catalogo")
def catalog():
    return catalogue_page(False)

def catalogue_page(is_home):
    query = select(Product).where(Product.published.is_(True))
    search = request.args.get("q", "").strip()[:100]
    category = request.args.get("categoria", "").strip()[:80]
    kind = request.args.get("tipo", "")
    if search:
        query = query.where(Product.title.icontains(search, autoescape=True) | Product.description.icontains(search, autoescape=True))
    if category:
        query = query.where(Product.category==category)
    if kind in ("digital", "physical"):
        query = query.where(Product.kind==kind)
    products, pagination = paginate(query.order_by(Product.created_at.desc(), Product.id.desc()))
    categories = db().scalars(select(Product.category).where(Product.published.is_(True)).distinct().order_by(Product.category)).all()
    return render_template("index.html", products=products, categories=categories, search=search, category=category, kind=kind, pagination=pagination, is_home=is_home)

@main.get("/producto/<int:identifier>")
def product_detail(identifier):
    product = db().get(Product, identifier)
    if not product or not product.published:
        abort(404)
    return render_template("product.html", product=product)

@main.get("/imagenes/<filename>")
def image(filename):
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", filename):
        abort(404)
    return send_from_directory(Path(current_app.config["STORAGE_DIR"])/"images", filename)

@main.post("/carrito/agregar/<int:identifier>")
def add_to_cart(identifier):
    product = db().get(Product, identifier)
    if not product or not product.published:
        abort(404)
    cart = session.get("cart", {}).copy()
    if len(cart)>=20 and str(identifier) not in cart:
        flash("El carrito admite hasta 20 recursos diferentes.")
        return redirect(url_for("main.cart"))
    quantity = 1 if product.kind=="digital" else min(cart.get(str(identifier), 0)+1, 10)
    if product.kind=="physical" and quantity>product.stock:
        flash("No hay más unidades disponibles.")
    else:
        cart[str(identifier)] = quantity
        session["cart"] = cart
        g.analytics_event = "cart"
        session.pop("checkout_key", None)
    return redirect(url_for("main.cart"))

@main.post("/carrito/quitar/<int:identifier>")
def remove_from_cart(identifier):
    cart = session.get("cart", {}).copy()
    cart.pop(str(identifier), None)
    session["cart"] = cart
    session.pop("checkout_key", None)
    return redirect(url_for("main.cart"))

@main.get("/carrito")
def cart():
    rows = cart_rows()
    current = session.get("cart", {})
    refreshed = {str(p.id):min(q, p.stock, 10) if p.kind=="physical" else 1 for p,q in rows if p.kind=="digital" or p.stock>0}
    if current != refreshed:
        session["cart"] = refreshed
        session.pop("checkout_key", None)
        flash("Actualizamos tu carrito porque cambió la disponibilidad de un recurso.")
        rows = cart_rows()
    return render_template("cart.html", rows=rows, total=sum(p.price_cents*q for p,q in rows))


@main.post("/carrito/cantidad/<int:identifier>")
def update_cart_quantity(identifier):
    product = db().get(Product, identifier)
    cart = session.get("cart", {}).copy()
    if str(identifier) not in cart or not product or not product.published:
        abort(404)
    try:
        quantity = int(request.form.get("quantity", ""))
    except ValueError:
        abort(400)
    limit = min(10, product.stock) if product.kind=="physical" else 1
    if not 1 <= quantity <= limit:
        flash("La cantidad debe respetar el stock disponible; los recursos digitales se compran una sola vez.")
    else:
        cart[str(identifier)] = quantity
        session["cart"] = cart
        session.pop("checkout_key", None)
    return redirect(url_for("main.cart"))

@main.route("/pedido/nuevo", methods=["GET", "POST"])
def checkout():
    if not current_app.config["PAYMENT_INSTRUCTIONS"] and not mp_configured():
        return render_template("message.html", title="Estamos preparando las compras", message="Los recursos se pueden explorar. Pronto habilitaremos los pedidos."), 503
    if request.method=="GET":
        session.setdefault("checkout_key", secrets.token_hex(24))
        rows = cart_rows()
        if not rows:
            return redirect(url_for("main.cart"))
        session["checkout_quote"] = {str(p.id):[p.price_cents,q] for p,q in rows}
        return render_template("checkout.html", rows=rows, total=sum(p.price_cents*q for p,q in rows), checkout_key=session["checkout_key"])
    key = request.form.get("checkout_key", "")
    if not key or not hmac.compare_digest(key, session.get("checkout_key", "")):
        abort(400)
    existing = db().scalar(select(Order).where(Order.checkout_key==key))
    if existing:
        return redirect(order_link(existing))
    name = request.form.get("name", "").strip()[:120]
    email = request.form.get("email", "").strip().lower()[:254]
    notes = request.form.get("notes", "").strip()[:1000]
    if len(name)<2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("Ingresá tu nombre y un correo válido.")
        return redirect(url_for("main.checkout"))
    rows = cart_rows(lock=True)
    if not rows or len(rows)!=len(session.get("cart", {})):
        db().rollback()
        flash("El catálogo cambió. Revisá el carrito antes de continuar.")
        return redirect(url_for("main.cart"))
    for product, quantity in rows:
        if product.kind=="physical" and product.stock<quantity:
            db().rollback()
            flash("Un material se quedó sin stock. Revisá el carrito.")
            return redirect(url_for("main.cart"))
    if session.get("checkout_quote") != {str(p.id):[p.price_cents,q] for p,q in rows}:
        db().rollback()
        flash("Un precio cambió. Revisá el total actualizado antes de confirmar.")
        return redirect(url_for("main.checkout"))
    if any(p.kind=="physical" for p,q in rows) and not current_app.config["PAYMENT_INSTRUCTIONS"]:
        db().rollback()
        flash("Las compras de materiales físicos todavía no están habilitadas.")
        return redirect(url_for("main.cart"))
    order = Order(checkout_key=key, customer_name=name, email=email, notes=notes, total_cents=sum(p.price_cents*q for p,q in rows))
    for product, quantity in rows:
        order.items.append(OrderItem(product_id=product.id, title=product.title, kind=product.kind, unit_cents=product.price_cents, quantity=quantity, digital_file=product.digital_file))
        if product.kind=="physical":
            product.stock -= quantity
    db().add(order)
    try:
        db().flush()
        enqueue_mail(db(), order, "created")
        g.analytics_event = "order"
        g.analytics_order = order.id
        db().commit()
    except IntegrityError:
        db().rollback()
        order = db().scalar(select(Order).where(Order.checkout_key==key))
        if not order:
            raise
    session["cart"] = {}
    return redirect(order_link(order))

@main.get("/pedido/<token>")
def order_detail(token):
    order = customer_order(token)
    return render_template("order.html", order=order, token=token, can_download=order.status=="paid" and bool(order.paid_at) and order.paid_at>=now()-timedelta(days=7))

@main.get("/pedido/<token>/descarga/<int:item_id>")
def download(token, item_id):
    order = customer_order(token)
    if order.status!="paid" or not order.paid_at or order.paid_at<now()-timedelta(days=7):
        abort(403)
    item = next((item for item in order.items if item.id==item_id), None)
    if not item or item.kind!="digital" or not item.digital_file:
        abort(404)
    response = send_from_directory(Path(current_app.config["STORAGE_DIR"])/"private", item.digital_file, as_attachment=True, download_name=f"recurso-{item.product_id}{Path(item.digital_file).suffix}")
    response.headers["Cache-Control"] = "private, no-store"
    return response


@main.post("/pedido/<token>/pagar")
def pay_with_mp(token):
    order = customer_order(token)
    if not mp_configured() or order.status!="pending" or any(item.kind=="physical" for item in order.items):
        abort(409)
    order = db().scalar(select(Order).where(Order.id==order.id).with_for_update().execution_options(populate_existing=True))
    if order.status!="pending":
        abort(409)
    if not order.preference_url:
        site = current_app.config["SITE_URL"]
        back = site+url_for("main.order_detail", token=token)
        try:
            preference = mp_request("POST", "/checkout/preferences", {
                "items":[{"id":str(item.product_id), "title":item.title, "quantity":item.quantity, "currency_id":"ARS", "unit_price":item.unit_cents/100} for item in order.items],
                "external_reference":order.checkout_key,
                "notification_url":site+url_for("main.mp_webhook"),
                "back_urls":{"success":back, "pending":back, "failure":back},
                "auto_return":"approved",
            }, key=order.checkout_key)
            from urllib.parse import urlparse
            payment_url = preference.get("init_point", "")
            parsed = urlparse(payment_url)
            if parsed.scheme!="https" or parsed.hostname not in ("www.mercadopago.com", "www.mercadopago.com.ar"):
                raise PaymentError()
            order.preference_url = payment_url
            db().commit()
        except PaymentError:
            db().rollback()
            flash("No pudimos abrir Mercado Pago. Tu pedido quedó guardado; intentá nuevamente.")
            return redirect(url_for("main.order_detail", token=token))
    return redirect(order.preference_url, code=303)


@main.post("/pagos/mercadopago/webhook")
@csrf.exempt
def mp_webhook():
    if not mp_configured():
        abort(503)
    payment_id = request.args.get("data.id", "")
    if not valid_signature(payment_id, request.headers.get("x-request-id", ""), request.headers.get("x-signature", "")):
        abort(401)
    try:
        payment = mp_request("GET", "/v1/payments/"+payment_id)
    except PaymentError:
        abort(503)
    order = db().scalar(select(Order).where(Order.checkout_key==payment.get("external_reference", "")).with_for_update())
    if not order:
        return jsonify(status="ignored")
    try:
        amount = Decimal(str(payment.get("transaction_amount")))
        correct_amount = amount.is_finite() and amount==Decimal(order.total_cents)/100
    except InvalidOperation:
        correct_amount = False
    valid = (correct_amount and str(payment.get("id"))==payment_id and payment.get("currency_id")=="ARS"
             and str(payment.get("collector_id"))==str(current_app.config["MP_COLLECTOR_ID"])
             and payment.get("live_mode") is current_app.config["MP_LIVE_MODE"])
    if not valid:
        abort(400)
    if payment.get("status") in ("refunded", "charged_back") and order.payment_id==payment_id:
        order.status = "refunded"
    elif payment.get("status")=="approved":
        if order.payment_id and order.payment_id!=payment_id:
            return jsonify(status="duplicate-payment-review-required")
        if order.status=="paid" and not order.payment_id:
            return jsonify(status="manual-payment-review-required")
        if order.status not in ("pending", "cancelled", "paid") or any(item.kind=="physical" for item in order.items):
            return jsonify(status="manual-review-required")
        order.status, order.payment_id = "paid", payment_id
        order.payment_reference = "Mercado Pago #"+payment_id
        order.paid_at = order.paid_at or now()
        enqueue_mail(db(), order, "paid")
    db().commit()
    return jsonify(status="ok")

@main.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method=="POST":
        email = request.form.get("email", "").strip().lower()[:254]
        identity = hashlib.sha256(email.encode()).hexdigest()
        recent = now()-timedelta(minutes=15)
        db().query(LoginAttempt).filter(LoginAttempt.created_at<recent).delete()
        count = db().query(LoginAttempt).filter(LoginAttempt.identity==identity).count()
        if count>=5:
            db().commit()
            return render_template("message.html", title="Esperá unos minutos", message="Demasiados intentos de acceso. Volvé a intentar en 15 minutos."), 429
        admin = db().scalar(select(Admin).where(Admin.email==email))
        valid = check_password_hash(admin.password_hash if admin else DUMMY_HASH, request.form.get("password", ""))
        if admin and valid:
            db().query(LoginAttempt).filter(LoginAttempt.identity==identity).delete()
            db().commit()
            session.clear()
            session["admin_id"] = admin.id
            session.permanent = True
            return redirect(url_for("main.admin"))
        db().add(LoginAttempt(identity=identity))
        db().commit()
        flash("Correo o contraseña incorrectos.")
    return render_template("login.html")

@main.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("main.home"))

@main.get("/admin")
@admin_required
def admin():
    resource_q = request.args.get("recurso", "").strip()[:100]
    visibility = request.args.get("visibilidad", "")
    order_q = request.args.get("pedido", "").strip()[:100]
    status = request.args.get("estado", "")
    products_query = select(Product)
    if resource_q:
        products_query = products_query.where(Product.title.icontains(resource_q, autoescape=True) | Product.category.icontains(resource_q, autoescape=True))
    if visibility in ("published", "draft"):
        products_query = products_query.where(Product.published.is_(visibility=="published"))
    orders_query = select(Order)
    if order_q:
        matching = Order.customer_name.icontains(order_q, autoescape=True) | Order.email.icontains(order_q, autoescape=True)
        if order_q.isdigit() and len(order_q)<10:
            matching = matching | (Order.id==int(order_q))
        orders_query = orders_query.where(matching)
    if status in ("pending", "paid", "cancelled", "refunded"):
        orders_query = orders_query.where(Order.status==status)
    products, product_pages = paginate(products_query.order_by(Product.id.desc()), "recursos_pagina", 20)
    orders, order_pages = paginate(orders_query.order_by(Order.id.desc()), "pedidos_pagina", 20)
    stats = {
        "products":db().scalar(select(func.count()).select_from(Product)),
        "published":db().scalar(select(func.count()).select_from(Product).where(Product.published.is_(True))),
        "pending":db().scalar(select(func.count()).select_from(Order).where(Order.status=="pending")),
    }
    return render_template("admin.html", products=products, orders=orders, stats=stats,
                           product_pages=product_pages, order_pages=order_pages,
                           resource_q=resource_q, visibility=visibility, order_q=order_q, status=status)


@main.get("/admin/drive")
@admin_required
def drive_browser():
    product_id=request.args.get("producto", type=int)
    if product_id and not db().get(Product, product_id):
        abort(404)
    folder=request.args.get("carpeta", "")
    search=request.args.get("buscar", "").strip()[:100]
    token=request.args.get("pagina", "")
    files=[]
    info=None
    next_token=""
    error=""
    if drive.configured():
        try:
            info,files,next_token=drive.list_folder(folder, token, search)
        except drive.DriveError as problem:
            error=str(problem)
    return render_template("drive.html", files=files, folder=info, search=search,
                           next_token=next_token, error=error, configured=drive.configured(),
                           root_folder=current_app.config["GOOGLE_DRIVE_FOLDER_ID"], product_id=product_id,
                           resource_mimes=drive.RESOURCE_MIMES, image_mimes=drive.IMAGE_MIMES, folder_mime=drive.FOLDER_MIME)


@main.get("/admin/productos/<int:identifier>/vista-previa")
@admin_required
def preview_product(identifier):
    product = db().get(Product, identifier)
    if not product:
        abort(404)
    return render_template("product.html", product=product, preview=True)


@main.post("/admin/productos/<int:identifier>/<action>")
@admin_required
def publish_product(identifier, action):
    product = db().scalar(select(Product).where(Product.id==identifier).with_for_update())
    if not product:
        abort(404)
    if action=="publicar":
        if product.kind=="digital" and (not product.digital_file or not (Path(current_app.config["STORAGE_DIR"])/"private"/product.digital_file).is_file()):
            flash("Adjuntá un archivo digital disponible antes de publicar este recurso.")
            return redirect(url_for("main.edit_product", identifier=identifier))
        product.published = True
    elif action=="ocultar":
        product.published = False
    else:
        abort(400)
    db().commit()
    flash("Recurso publicado." if product.published else "Recurso ocultado; los pedidos anteriores conservan sus archivos.")
    return redirect(url_for("main.admin"))

def save_image(upload):
    try:
        content = upload.read()
        if len(content)>5*1024*1024:
            raise ValueError("La imagen debe pesar menos de 5 MB.")
        with Image.open(io.BytesIO(content)) as picture:
            if picture.format not in ("JPEG", "PNG", "WEBP") or picture.width*picture.height>20_000_000:
                raise ValueError("Usá JPG, PNG o WebP de hasta 20 megapíxeles.")
            picture.thumbnail((1400, 1400))
            filename = f"{secrets.token_hex(16)}.jpg"
            picture.convert("RGB").save(Path(current_app.config["STORAGE_DIR"])/"images"/filename, "JPEG", quality=85)
            return filename
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("El archivo de imagen no es válido.") from error

def save_digital(upload):
    extension = Path(upload.filename).suffix.lower()
    content = upload.read()
    if extension not in (".pdf", ".zip") or not content or (extension==".pdf" and not content.startswith(b"%PDF-")) or (extension==".zip" and not content.startswith(b"PK\x03\x04")):
        raise ValueError("El recurso descargable debe ser un PDF o ZIP válido.")
    filename = secrets.token_hex(16)+extension
    (Path(current_app.config["STORAGE_DIR"])/"private"/filename).write_bytes(content)
    return filename

@main.route("/admin/productos/nuevo", methods=["GET", "POST"])
@main.route("/admin/productos/<int:identifier>", methods=["GET", "POST"])
@admin_required
def edit_product(identifier=None):
    product = db().get(Product, identifier) if identifier else Product(published=False, kind="digital", stock=0)
    if product is None:
        abort(404)
    drive_file_id=(request.form if request.method=="POST" else request.args).get("drive_file", "")
    drive_image_id=(request.form if request.method=="POST" else request.args).get("drive_image", "")
    selected_file=None
    selected_image=None
    if request.method=="GET":
        try:
            if drive_file_id:
                selected_file=drive.permitted_metadata(drive_file_id)
                if selected_file.get("mimeType") not in drive.RESOURCE_MIMES:
                    raise drive.DriveError("Ese archivo no puede usarse como recurso descargable.")
                if not identifier:
                    product.title=Path(selected_file["name"]).stem[:160]
                    product.category="Recursos didácticos"
            if drive_image_id:
                selected_image=drive.permitted_metadata(drive_image_id)
                if selected_image.get("mimeType") not in drive.IMAGE_MIMES:
                    raise drive.DriveError("Ese archivo no puede usarse como portada.")
        except drive.DriveError as problem:
            flash(str(problem))
            return redirect(url_for("main.drive_browser", producto=identifier))
    if request.method=="POST":
        try:
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "").strip()
            kind = request.form.get("kind", "digital")
            price = Decimal(request.form.get("price", "").replace(",", "."))
            stock = int(request.form.get("stock", "0") or "0")
            if not title or len(title)>160 or not description or len(description)>10000 or not category or len(category)>80:
                raise ValueError("Completá título, descripción y categoría dentro de los límites indicados.")
            if kind not in ("digital", "physical") or not price.is_finite() or price<=0 or price>Decimal("9999999.99") or price.as_tuple().exponent < -2 or not 0<=stock<=100000:
                raise ValueError("Revisá el tipo, precio (hasta dos decimales) y stock.")
            product.title, product.description, product.category, product.kind = title, description, category, kind
            product.age = request.form.get("age", "").strip()[:80]
            product.price_cents, product.stock = int(price*100), stock
            if request.files.get("image") and request.files["image"].filename:
                if drive_image_id:
                    raise ValueError("Elegí una portada desde tu equipo o Drive, no ambas.")
                product.image = save_image(request.files["image"])
            elif drive_image_id:
                upload,selected_image=drive.download(drive_image_id, image=True)
                product.image=save_image(upload)
            if request.files.get("digital_file") and request.files["digital_file"].filename:
                if drive_file_id:
                    raise ValueError("Elegí un recurso desde tu equipo o Drive, no ambos.")
                product.digital_file = save_digital(request.files["digital_file"])
            elif drive_file_id:
                if kind!="digital":
                    raise ValueError("El archivo de Drive se usa en recursos digitales.")
                upload,selected_file=drive.download(drive_file_id)
                product.digital_file=save_digital(upload)
            product.published = request.form.get("published")=="on"
            if product.published and kind=="digital" and (not product.digital_file or not (Path(current_app.config["STORAGE_DIR"])/"private"/product.digital_file).is_file()):
                raise ValueError("Adjuntá el recurso digital antes de publicarlo.")
            db().add(product)
            db().commit()
            flash("Recurso guardado.")
            return redirect(url_for("main.admin"))
        except (ValueError, InvalidOperation, drive.DriveError) as error:
            db().rollback()
            flash(str(error) if isinstance(error, (ValueError,drive.DriveError)) else "Ingresá un precio válido.")
    return render_template("edit_product.html", product=product, drive_file_id=drive_file_id,
                           drive_image_id=drive_image_id, selected_file=selected_file, selected_image=selected_image)

@main.get("/admin/pedidos/<int:identifier>")
@admin_required
def admin_order(identifier):
    order = db().get(Order, identifier)
    if not order:
        abort(404)
    return render_template("admin_order.html", order=order)

@main.post("/admin/pedidos/<int:identifier>/<action>")
@admin_required
def order_action(identifier, action):
    order = db().scalar(select(Order).where(Order.id==identifier).with_for_update())
    if not order:
        abort(404)
    if action=="pagar" and order.status=="pending":
        reference = request.form.get("reference", "").strip()[:200]
        if not reference or request.form.get("verified")!="on":
            flash("Verificá el cobro e ingresá la referencia antes de habilitar las descargas.")
            return redirect(url_for("main.admin_order", identifier=identifier))
        order.status, order.paid_at = "paid", now()
        order.payment_reference, order.confirmed_by = reference, session["admin_id"]
        enqueue_mail(db(), order, "paid")
    elif action=="cancelar" and order.status=="pending":
        for item in sorted(order.items, key=lambda item:item.product_id):
            if item.kind=="physical":
                product = db().scalar(select(Product).where(Product.id==item.product_id).with_for_update())
                if product:
                    product.stock += item.quantity
        order.status = "cancelled"
    else:
        abort(409)
    db().commit()
    flash("Pedido actualizado.")
    return redirect(url_for("main.admin_order", identifier=identifier))

@main.get("/health")
def health():
    return jsonify(status="ok", service="el-rincon-didactico")

@main.get("/health/ready")
def readiness():
    try:
        db().execute(text("SELECT 1"))
        db().scalar(select(Product.id).limit(1))
    except SQLAlchemyError:
        db().rollback()
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")

@main.app_errorhandler(413)
def too_large(error):
    return render_template("message.html", title="El archivo es demasiado grande", message="El formulario admite hasta 20 MB en total."), 413

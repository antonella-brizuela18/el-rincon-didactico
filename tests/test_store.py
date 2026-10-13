import io
import re
from datetime import timedelta
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.models import Admin, Base, Order, Product, now


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True, "SECRET_KEY": "tests-only-secret",
        "DATABASE_URL": f"sqlite:///{tmp_path/'test.db'}",
        "STORAGE_DIR": str(tmp_path/'storage'), "SESSION_COOKIE_SECURE": False,
        "WTF_CSRF_ENABLED": False, "PAYMENT_INSTRUCTIONS": "Transferencia de prueba.",
    })
    Base.metadata.create_all(application.extensions["database"])
    with application.extensions["sessions"]() as db:
        db.add(Admin(email="admin@example.test", password_hash=generate_password_hash("test-password-123")))
        db.add_all([
            Product(title="Imprimible de colores", description="Para explorar los colores.", category="Colores", age="Sala de 3", kind="digital", price_cents=123456, published=True, digital_file="original.pdf"),
            Product(title="Juego de tela", description="Material físico", category="Juego", kind="physical", price_cents=200000, published=True, stock=2),
            Product(title="Borrador oculto", description="No publicado", category="Colores", kind="digital", price_cents=1000, published=False),
        ])
        db.commit()
    (tmp_path/'storage'/'private'/'original.pdf').write_bytes(b"%PDF-1.4\nprivate-resource")
    yield application
    application.extensions["database"].dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client):
    return client.post("/admin/login", data={"email":"admin@example.test", "password":"test-password-123"})


def place_order(client, product=1):
    client.post(f"/carrito/agregar/{product}")
    client.get("/pedido/nuevo")
    with client.session_transaction() as state:
        key = state["checkout_key"]
    response = client.post("/pedido/nuevo", data={"checkout_key":key, "name":"Cliente Test", "email":"client@example.test", "price": "1", "whatsapp":"+5492915090223"})
    return response, key


def latest_order(app):
    with app.extensions["sessions"]() as db:
        return db.scalar(select(Order).order_by(Order.id.desc()))


def test_catalogue_filters_and_hidden_products(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b"Imprimible de colores" in page.data
    assert b"Borrador oculto" not in page.data
    assert b"Juego de tela" not in client.get("/?tipo=digital").data
    assert b"Juego de tela" not in client.get("/?categoria=Colores").data
    assert b"Imprimible de colores" not in client.get("/?q=%25").data
    assert client.get("/producto/3").status_code == 404
    assert client.post("/carrito/agregar/3").status_code == 404


def test_health_checks(app, client):
    assert client.get("/health").json["status"] == "ok"
    assert client.get("/health/ready").status_code == 200
    Base.metadata.drop_all(app.extensions["database"])
    assert client.get("/health/ready").status_code == 503


def test_admin_requires_login(client):
    for path in ("/admin", "/admin/productos/nuevo", "/admin/pedidos/1"):
        assert client.get(path).status_code == 302
    assert client.post("/admin/productos/nuevo", data={}).status_code == 302


def test_admin_login_logout(client):
    assert login(client).status_code == 302
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/productos/1").status_code == 200
    client.post("/admin/logout")
    assert client.get("/admin").status_code == 302


def test_login_rate_limit_is_shared(app, client):
    for unused in range(5):
        assert client.post("/admin/login", data={"email":"admin@example.test", "password":"wrong"}).status_code == 200
    fresh_client = app.test_client()
    assert login(fresh_client).status_code == 429


def test_csrf_required(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/carrito/agregar/1").status_code == 400
    assert client.post("/admin/login", data={}).status_code == 400
    page = client.get("/admin/login")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    assert client.post("/admin/login", data={"email":"admin@example.test", "password":"test-password-123", "csrf_token":token}).status_code == 302


def test_cart_digital_quantity_and_physical_made_to_order(client):
    for unused in range(3):
        client.post("/carrito/agregar/1")
        client.post("/carrito/agregar/2")
    with client.session_transaction() as state:
        assert state["cart"] == {"1":1, "2":3}
    client.post("/carrito/quitar/1")
    assert "Imprimible de colores" not in client.get("/carrito").text.split("<main")[1].split("</main>")[0]


def test_checkout_price_is_server_owned_and_retries_do_not_duplicate(app, client):
    response, key = place_order(client)
    assert response.status_code == 302
    assert client.get(response.location).status_code == 200
    order = latest_order(app)
    assert order.total_cents == 123456
    assert order.status == "pending"
    second = client.post("/pedido/nuevo", data={"checkout_key":key, "name":"Changed", "email":"changed@example.test"})
    # Signed URLs can differ when retries fall in another second; the order identity must match.
    from app.routes import signer
    with app.app_context():
        assert signer().loads(second.location.rsplit("/", 1)[1]) == key
    assert client.get(second.location).status_code == 200
    with app.extensions["sessions"]() as db:
        assert db.query(Order).count() == 1


def test_hidden_product_during_checkout_is_not_silently_omitted(app, client):
    client.post("/carrito/agregar/1")
    client.get("/pedido/nuevo")
    with client.session_transaction() as state:
        key = state["checkout_key"]
    with app.extensions["sessions"]() as db:
        db.get(Product, 1).published = False
        db.commit()
    response = client.post("/pedido/nuevo", data={"checkout_key":key, "name":"Client", "email":"client@example.test"})
    assert response.status_code == 302
    assert response.location.endswith("/carrito")
    assert latest_order(app) is None


def test_no_orders_until_payment_instructions_are_configured(app, client):
    app.config["PAYMENT_INSTRUCTIONS"] = ""
    assert client.get("/pedido/nuevo").status_code == 503
    assert client.post("/pedido/nuevo").status_code == 503
    assert latest_order(app) is None


def test_download_payment_gate_and_token_isolation(app, client):
    response, unused = place_order(client)
    order = latest_order(app)
    download = response.location + f"/descarga/{order.items[0].id}"
    assert client.get(download).status_code == 403
    assert client.get("/pedido/invalid").status_code == 404
    assert client.get("/static/original.pdf").status_code == 404
    login(client)
    assert client.get(f"/admin/pedidos/{order.id}").status_code == 200
    client.post(f"/admin/pedidos/{order.id}/pagar", data={"reference":"verified-ref"})
    assert client.get(download).status_code == 403
    client.post(f"/admin/pedidos/{order.id}/pagar", data={"reference":"verified-ref", "verified":"on"})
    downloaded = client.get(download)
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"%PDF-")
    assert downloaded.headers["Cache-Control"] == "private, no-store"
    assert client.get(response.location + "/descarga/9999").status_code == 404
    with app.extensions["sessions"]() as db:
        db.get(Order, order.id).paid_at = now()-timedelta(days=8)
        db.commit()
    assert client.get(download).status_code == 403


def test_made_to_order_cancellation_exactly_once(app, client):
    response, unused = place_order(client, product=2)
    order = latest_order(app)
    with app.extensions["sessions"]() as db:
        assert db.get(Product, 2).stock == 2
    login(client)
    assert client.post(f"/admin/pedidos/{order.id}/cancelar").status_code == 302
    assert client.post(f"/admin/pedidos/{order.id}/cancelar").status_code == 409
    with app.extensions["sessions"]() as db:
        assert db.get(Product, 2).stock == 2


def test_product_edit_upload_validation_and_publication(client):
    login(client)
    data = {"title":"Nuevo recurso", "description":"Descripción", "category":"Prueba", "kind":"digital", "price":"100,25", "stock":"0", "published":"on"}
    response = client.post("/admin/productos/nuevo", data=data)
    assert response.status_code == 200
    assert b"Nuevo recurso" not in client.get("/").data
    data["digital_file"] = (io.BytesIO(b"<script>bad</script>"), "false.pdf")
    assert client.post("/admin/productos/nuevo", data=data).status_code == 200
    data["digital_file"] = (io.BytesIO(b"%PDF-1.4\nresource"), "real.pdf")
    picture = io.BytesIO()
    Image.new("RGB", (16,16), "green").save(picture, "PNG")
    picture.seek(0)
    data["image"] = (picture, "../../cover.png")
    assert client.post("/admin/productos/nuevo", data=data).status_code == 302
    assert b"Nuevo recurso" in client.get("/").data


@pytest.mark.parametrize("price", ["-1", "nan", "Infinity", "0", "1.234", "10000000"])
def test_invalid_prices_cannot_be_saved(client, price):
    login(client)
    response = client.post("/admin/productos/nuevo", data={"title":"Invalid", "description":"desc", "category":"test", "kind":"physical", "price":price, "stock":"1"})
    assert response.status_code == 200
    assert b"Invalid" not in client.get("/").data


def test_checkout_key_tampering_and_email_validation(client):
    client.post("/carrito/agregar/1")
    client.get("/pedido/nuevo")
    assert client.post("/pedido/nuevo", data={"checkout_key":"tampered"}).status_code == 400
    with client.session_transaction() as state:
        key = state["checkout_key"]
    response = client.post("/pedido/nuevo", data={"checkout_key":key, "name":"OK", "email":"not-email"})
    assert response.location.endswith("/pedido/nuevo")


def test_initial_schema_command_is_idempotent(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db"]).exit_code == 0
    assert runner.invoke(args=["init-db"]).exit_code == 0


def test_headers_and_xss_escaping(app, client):
    with app.extensions["sessions"]() as db:
        db.get(Product, 1).description = "<script>alert('x')</script>"
        db.commit()
    page = client.get("/producto/1")
    assert b"<script>" not in page.data
    assert b"&lt;script&gt;" in page.data
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["Referrer-Policy"] == "same-origin"


def test_https_login_requires_token_and_same_origin_referrer(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/admin/login", base_url="https://localhost")
    assert page.headers["Referrer-Policy"]=="same-origin"
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    data={"email":"admin@example.test", "password":"test-password-123", "csrf_token":token}
    assert client.post("/admin/login", base_url="https://localhost", data=data).status_code==400
    assert client.post("/admin/login", base_url="https://localhost", data=data, headers={"Referer":"https://other.example/login"}).status_code==400
    response=client.post("/admin/login", base_url="https://localhost", data=data, headers={"Referer":"https://localhost/admin/login"})
    assert response.status_code==302
    assert client.get("/admin", base_url="https://localhost").status_code==200
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]


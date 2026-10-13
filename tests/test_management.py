from pathlib import Path

from app.models import Order, Product
from test_store import app, client, latest_order, login, place_order


def test_preview_is_private_and_has_no_buy_form(client):
    assert client.get("/admin/productos/3/vista-previa").status_code==302
    login(client)
    page = client.get("/admin/productos/3/vista-previa")
    assert page.status_code==200
    assert b"Borrador oculto" in page.data
    assert b"Vista previa privada" in page.data
    assert b"/carrito/agregar/" not in page.data
    assert client.get("/producto/3").status_code==404


def test_publication_requires_private_file_and_authentication(app, client):
    assert client.post("/admin/productos/3/publicar").status_code==302
    login(client)
    assert client.post("/admin/productos/3/publicar").location.endswith("/admin/productos/3")
    assert client.get("/producto/3").status_code==404
    with app.extensions["sessions"]() as db:
        db.get(Product, 3).digital_file="draft.pdf"
        db.commit()
    assert client.post("/admin/productos/3/publicar").location.endswith("/admin/productos/3")
    (Path(app.config["STORAGE_DIR"])/"private"/"draft.pdf").write_bytes(b"%PDF-1.4 test")
    assert client.post("/admin/productos/3/publicar").status_code==302
    assert client.get("/producto/3").status_code==200
    assert client.post("/admin/productos/3/ocultar").status_code==302
    assert client.get("/producto/3").status_code==404
    assert client.get("/admin/productos/3/publicar").status_code==405


def test_hide_product_does_not_revoke_paid_order(app, client):
    response, unused=place_order(client)
    order=latest_order(app)
    login(client)
    client.post(f"/admin/pedidos/{order.id}/pagar", data={"reference":"test","verified":"on"})
    client.post("/admin/productos/1/ocultar")
    assert client.get("/producto/1").status_code==404
    assert client.get(response.location+f"/descarga/{order.items[0].id}").status_code==200


def test_quantity_limits_and_checkout_invalidation(client):
    client.post("/carrito/agregar/2")
    client.get("/pedido/nuevo")
    assert client.post("/carrito/cantidad/2", data={"quantity":"2"}).status_code==302
    with client.session_transaction() as state:
        assert state["cart"]["2"]==2
        assert "checkout_key" not in state
    for quantity in ("0","-1","11","100"):
        client.post("/carrito/cantidad/2", data={"quantity":quantity})
        with client.session_transaction() as state:
            assert state["cart"]["2"]==2
    assert client.post("/carrito/cantidad/2", data={"quantity":"abc"}).status_code==400
    client.post("/carrito/agregar/1")
    client.post("/carrito/cantidad/1", data={"quantity":"2"})
    with client.session_transaction() as state:
        assert state["cart"]["1"]==1


def test_cart_removes_hidden_but_keeps_made_to_order_products(app, client):
    client.post("/carrito/agregar/1")
    client.post("/carrito/agregar/2")
    client.get("/pedido/nuevo")
    with app.extensions["sessions"]() as db:
        db.get(Product, 1).published=False
        db.get(Product, 2).stock=0
        db.commit()
    page=client.get("/carrito")
    assert page.status_code==200
    assert b"Actualizamos tu carrito" in page.data
    with client.session_transaction() as state:
        assert state["cart"]=={"2":1}
        assert "checkout_key" not in state


def test_catalogue_pagination_preserves_filters_and_covers_all_results(app, client):
    with app.extensions["sessions"]() as db:
        for index in range(50):
            db.add(Product(title=f"Resource {index:02}",description="Test",category="Pagination",kind="physical",price_cents=100,stock=1,published=True))
        db.commit()
    first=client.get("/catalogo?categoria=Pagination&tipo=physical")
    assert first.status_code==200
    assert b"Resource 49" in first.data
    assert b"Resource 00" not in first.data
    assert b"pagina=2" in first.data and b"categoria=Pagination" in first.data
    second=client.get("/catalogo?categoria=Pagination&tipo=physical&pagina=2")
    assert b"Resource 25" in second.data
    assert b"Resource 49" not in second.data
    last=client.get("/catalogo?categoria=Pagination&pagina=999")
    assert b"Resource 00" in last.data and b"Resource 49" not in last.data


def test_admin_search_and_totals_cover_all_pages(app, client):
    with app.extensions["sessions"]() as db:
        for index in range(55):
            db.add(Order(checkout_key=f"order-{index}",customer_name=f"Buyer {index:02}",email=f"buyer{index}@example.test",status="pending",total_cents=100))
        db.commit()
    login(client)
    page=client.get("/admin")
    assert page.status_code==200
    assert b"<strong>55</strong>" in page.data
    assert b"Buyer 54" in page.data and b"Buyer 00" not in page.data
    assert b"pedidos_pagina=2" in page.data
    filtered=client.get("/admin?pedido=buyer0%40example.test&estado=pending")
    assert b"Buyer 00" in filtered.data and b"Buyer 54" not in filtered.data
    drafts=client.get("/admin?visibilidad=draft")
    assert b"Borrador oculto" in drafts.data
    assert b"Imprimible de colores" not in drafts.data


def test_publication_and_quantity_changes_require_csrf(app, client):
    login(client)
    app.config["WTF_CSRF_ENABLED"]=True
    assert client.post("/admin/productos/1/ocultar").status_code==400
    assert client.post("/carrito/cantidad/2", data={"quantity":"1"}).status_code==400


def test_editor_cannot_publish_a_missing_private_file(app, client):
    login(client)
    with app.extensions["sessions"]() as db:
        db.get(Product, 3).digital_file="missing.pdf"
        db.commit()
    response=client.post("/admin/productos/3", data={"title":"Borrador oculto","description":"Test","category":"Colores","kind":"digital","price":"10","stock":"0","published":"on"})
    assert response.status_code==200
    assert client.get("/producto/3").status_code==404

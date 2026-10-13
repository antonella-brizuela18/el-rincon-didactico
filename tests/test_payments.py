import hashlib
import hmac
import time
from sqlalchemy import select
from app.models import Order
from test_store import app, client, latest_order, login, place_order


def enable_mp(app):
    app.config.update(MP_ACCESS_TOKEN="test-only", MP_WEBHOOK_SECRET="webhook-test-secret",
                      MP_COLLECTOR_ID="123", SITE_URL="https://example.test", MP_LIVE_MODE=False)


def headers(app, payment_id="456", timestamp=None):
    timestamp = str(timestamp or int(time.time()))
    request_id = "test-request"
    manifest = f"id:{payment_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(app.config["MP_WEBHOOK_SECRET"].encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-request-id":request_id, "x-signature":f"ts={timestamp},v1={digest}"}


def payment(order, **overrides):
    payload = {"id":456, "external_reference":order.checkout_key, "transaction_amount":order.total_cents/100,
               "currency_id":"ARS", "collector_id":123, "live_mode":False, "status":"approved"}
    payload.update(overrides)
    return payload


def test_payment_signature_required_and_stale_rejected(app, client):
    enable_mp(app)
    path = "/pagos/mercadopago/webhook?data.id=456"
    assert client.post(path).status_code == 401
    assert client.post(path, headers=headers(app, timestamp=int(time.time())-600)).status_code == 401


def test_validated_webhook_pays_once_and_refund_disables_downloads(app, client, monkeypatch):
    enable_mp(app)
    response, unused = place_order(client)
    order = latest_order(app)
    monkeypatch.setattr("app.routes.mp_request", lambda *a,**kw:payment(order))
    path = "/pagos/mercadopago/webhook?data.id=456"
    assert client.post(path, headers=headers(app)).status_code == 200
    assert latest_order(app).status == "paid"
    paid_at = latest_order(app).paid_at
    assert client.post(path, headers=headers(app)).status_code == 200
    assert latest_order(app).paid_at == paid_at
    assert client.get(response.location+f"/descarga/{order.items[0].id}").status_code == 200
    monkeypatch.setattr("app.routes.mp_request", lambda *a,**kw:payment(order, status="refunded"))
    assert client.post(path, headers=headers(app)).status_code == 200
    assert latest_order(app).status == "refunded"
    assert client.get(response.location).status_code == 200
    assert client.get(response.location+f"/descarga/{order.items[0].id}").status_code == 403


def test_wrong_amount_currency_merchant_and_mode_never_unlock(app, client, monkeypatch):
    enable_mp(app)
    unused, key = place_order(client)
    order = latest_order(app)
    for overrides in ({"transaction_amount":1},{"currency_id":"USD"},{"collector_id":999},{"live_mode":True},{"id":777}):
        monkeypatch.setattr("app.routes.mp_request", lambda *a,**kw:payment(order, **overrides))
        assert client.post("/pagos/mercadopago/webhook?data.id=456", headers=headers(app)).status_code == 400
        assert latest_order(app).status == "pending"


def test_preference_uses_server_snapshot_and_return_does_not_confirm(app, client, monkeypatch):
    enable_mp(app)
    response, unused = place_order(client)
    calls = []
    def fake(method, path, payload=None, **kw):
        calls.append(payload)
        return {"init_point":"https://www.mercadopago.com.ar/checkout/test"}
    monkeypatch.setattr("app.routes.mp_request", fake)
    assert client.post(response.location+"/pagar").status_code == 303
    assert calls[0]["items"][0]["unit_price"] == 1234.56
    assert calls[0]["notification_url"] == "https://example.test/pagos/mercadopago/webhook"
    assert client.post(response.location+"/pagar").status_code == 303
    assert len(calls) == 1
    assert client.get(response.location+"?status=approved&payment_id=456").status_code == 200
    assert latest_order(app).status == "pending"


def test_checkout_price_change_requires_review(app, client):
    client.post("/carrito/agregar/1")
    client.get("/pedido/nuevo")
    with client.session_transaction() as state:
        key = state["checkout_key"]
    from app.models import Product
    with app.extensions["sessions"]() as db:
        db.get(Product, 1).price_cents += 100
        db.commit()
    response = client.post("/pedido/nuevo", data={"checkout_key":key,"name":"Client","email":"client@example.test"})
    assert response.location.endswith("/pedido/nuevo")
    assert latest_order(app) is None

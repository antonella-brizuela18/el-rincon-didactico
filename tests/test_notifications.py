import smtplib
from app.models import MailOutbox
from test_store import app, client, latest_order, login, place_order


def test_receipt_and_paid_emails_are_queued_once(app, client):
    app.config["SITE_URL"] = "https://example.test"
    response, key = place_order(client)
    client.post("/pedido/nuevo", data={"checkout_key":key})
    order = latest_order(app)
    login(client)
    client.post(f"/admin/pedidos/{order.id}/pagar", data={"verified":"on","reference":"test"})
    with app.extensions["sessions"]() as db:
        assert db.query(MailOutbox).count()==2
        assert all(row.recipient=="client@example.test" for row in db.query(MailOutbox))
        assert all("https://example.test/pedido/" in row.body for row in db.query(MailOutbox))


def test_worker_sends_without_duplicates(app, client, monkeypatch):
    app.config.update(SITE_URL="https://example.test",SMTP_HOST="smtp.example.test",SMTP_USER="test",SMTP_PASSWORD="not-real",SMTP_FROM="store@example.test")
    place_order(client)
    sent=[]
    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def login(self, *a): pass
        def send_message(self, message): sent.append(message)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    assert app.test_cli_runner().invoke(args=["send-mail"]).exit_code==0
    assert app.test_cli_runner().invoke(args=["send-mail"]).exit_code==0
    assert len(sent)==1
    assert sent[0]["To"]=="client@example.test"


def test_worker_keeps_failed_mail_for_retry(app, client, monkeypatch):
    app.config.update(SITE_URL="https://example.test",SMTP_HOST="smtp.example.test",SMTP_USER="test",SMTP_PASSWORD="not-real",SMTP_FROM="store@example.test")
    place_order(client)
    def failing(*a, **kw): raise OSError("Simulated offline")
    monkeypatch.setattr(smtplib, "SMTP_SSL", failing)
    assert app.test_cli_runner().invoke(args=["send-mail"]).exit_code!=0
    with app.extensions["sessions"]() as db:
        row=db.query(MailOutbox).one()
        assert row.sent_at is None and row.attempts==1

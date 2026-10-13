"""Transactional email outbox; a scheduled CLI worker performs delivery."""
import smtplib
import ssl
from email.message import EmailMessage
import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select
from app.models import MailOutbox, OrderPayment, now


def enqueue_mail(db, order, event):
    site = current_app.config.get("SITE_URL", "")
    if not site.startswith("https://"):
        return
    event_key = f"order:{order.id}:{event}"
    if db.scalar(select(MailOutbox.id).where(MailOutbox.event_key==event_key)):
        return
    from app.routes import signer
    link = site+"/pedido/"+signer().dumps(order.checkout_key)
    subject = f"El Rincón Didáctico · Pedido #{order.id}"
    body = f"Hola, {order.customer_name}.\n\n"
    if event=="paid":
        body += "Confirmamos tu pago.\n"
        if any(item.kind=="digital" for item in order.items):
            body += "Tus archivos digitales ya están habilitados en el enlace privado, durante 7 días desde la acreditación.\n"
        if any(item.kind=="physical" for item in order.items):
            terms=db.get(OrderPayment,order.id)
            body += (terms.delivery_note if terms else "Tus materiales se preparan a pedido en aproximadamente 10 días, más el tránsito del correo. Coordinaremos la entrega por WhatsApp.")+"\n"
    else:
        body += "Recibimos tu pedido, que queda pendiente de pago.\n"
    body += "\nConsultá los detalles y el estado en tu enlace privado:\n"+link+"\n\nNo compartas este enlace.\nEl Rincón Didáctico"
    db.add(MailOutbox(event_key=event_key, recipient=order.email, subject=subject, body=body))
    from app.studio import settings
    owner = settings()['order_email']
    if owner:
        owner_key = event_key+":owner"
        if not db.scalar(select(MailOutbox.id).where(MailOutbox.event_key==owner_key)):
            detail = "\n".join(f"{item.quantity} × {item.title}" for item in order.items)
            body = f"Pedido #{order.id} · {'Pago confirmado' if event=='paid' else 'Nuevo pedido'}\nCliente: {order.customer_name}\nCorreo: {order.email}\nTotal ARS: {order.total_cents/100:.2f}\n\n{detail}\n\nAdministrar: {site}/admin/pedidos/{order.id}"
            db.add(MailOutbox(event_key=owner_key,recipient=owner,subject=subject,body=body))


@click.command("send-mail")
@with_appcontext
def send_mail_command():
    """Deliver up to 20 queued emails; schedule once per minute."""
    config = current_app.config
    if not all(config.get(key) for key in ("SMTP_HOST","SMTP_USER","SMTP_PASSWORD","SMTP_FROM")):
        raise click.ClickException("Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD y SMTP_FROM.")
    delivered = 0
    with current_app.extensions["sessions"]() as db:
        for unused in range(20):
            row = db.scalar(select(MailOutbox).where(MailOutbox.sent_at.is_(None), MailOutbox.attempts<5).order_by(MailOutbox.id).limit(1).with_for_update(skip_locked=True))
            if not row:
                break
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = config["SMTP_FROM"], row.recipient, row.subject
            message["Message-ID"] = f"<rincon-{row.event_key.replace(':','-')}@{config['SMTP_FROM'].split('@')[-1]}>"
            message.set_content(row.body)
            try:
                connection = smtplib.SMTP_SSL if config["SMTP_SSL"] else smtplib.SMTP
                kwargs = {"timeout":15}
                if config["SMTP_SSL"]:
                    kwargs["context"] = ssl.create_default_context()
                with connection(config["SMTP_HOST"], config["SMTP_PORT"], **kwargs) as server:
                    if not config["SMTP_SSL"]:
                        server.starttls(context=ssl.create_default_context())
                    server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
                    server.send_message(message)
                row.sent_at = now()
                delivered += 1
            except (smtplib.SMTPException, OSError):
                row.attempts += 1
                db.commit()
                raise click.ClickException("No se pudo enviar el correo. Quedó en cola para reintento.")
            db.commit()
    click.echo(f"Correos enviados: {delivered}.")


"""Configuration and secrets stay outside the repository."""
import os
from datetime import timedelta
from pathlib import Path
import click
from flask import Flask, g, render_template
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash

csrf = CSRFProtect()

def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        STORAGE_DIR=os.environ.get("STORAGE_DIR", str(Path(app.instance_path)/"storage")),
        MAX_CONTENT_LENGTH=20*1024*1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1")=="1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        PAYMENT_INSTRUCTIONS=os.environ.get("PAYMENT_INSTRUCTIONS", ""),
        CONTACT_EMAIL=os.environ.get("CONTACT_EMAIL", ""),
        SITE_URL=os.environ.get("SITE_URL", "").rstrip("/"),
        MP_ACCESS_TOKEN=os.environ.get("MP_ACCESS_TOKEN", ""),
        MP_WEBHOOK_SECRET=os.environ.get("MP_WEBHOOK_SECRET", ""),
        MP_COLLECTOR_ID=os.environ.get("MP_COLLECTOR_ID", ""),
        MP_LIVE_MODE=os.environ.get("MP_LIVE_MODE", "0")=="1",
        SMTP_HOST=os.environ.get("SMTP_HOST", ""),
        SMTP_PORT=int(os.environ.get("SMTP_PORT", "465")),
        SMTP_USER=os.environ.get("SMTP_USER", ""),
        SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
        SMTP_FROM=os.environ.get("SMTP_FROM", ""),
        SMTP_SSL=os.environ.get("SMTP_SSL", "1")=="1",
        GOOGLE_DRIVE_FOLDER_ID=os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "1oRYvQe1MuIxy1R-ehYilne_LVIOXKpbl"),
        GOOGLE_DRIVE_CREDENTIALS=os.environ.get("GOOGLE_DRIVE_CREDENTIALS", ""),
        TRUSTED_HOSTS=[host.strip() for host in os.environ.get("TRUSTED_HOSTS", "").split(",") if host.strip()] or None,
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"] or not app.config["DATABASE_URL"]:
        raise RuntimeError("Configure SECRET_KEY y DATABASE_URL antes de iniciar la tienda.")
    url = app.config["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    app.extensions["database"] = engine
    app.extensions["sessions"] = sessionmaker(bind=engine, expire_on_commit=False)
    for directory in ("images", "private"):
        (Path(app.config["STORAGE_DIR"])/directory).mkdir(parents=True, exist_ok=True)
    csrf.init_app(app)

    @app.teardown_appcontext
    def close_database(error=None):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()
        drive_connection = g.pop("drive_session", None)
        if drive_connection is not None:
            drive_connection.close()

    @app.template_filter("money")
    def money(cents):
        return (f"$ {int(cents)/100:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        # HTTPS CSRF validation needs a same-origin Referer; external links must not receive private URLs.
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    from app.models import Admin, Base
    from app.routes import main
    app.register_blueprint(main)
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("message.html", title="Volvé a abrir el formulario", message="No pudimos validar el envío. Recargá la página e intentá otra vez. Si estabas ingresando, abrí nuevamente el acceso de administración."), 400
    from app.notifications import send_mail_command
    app.cli.add_command(send_mail_command)

    @app.cli.command("init-db")
    def init_db():
        """Initial non-destructive schema installation (version 1)."""
        Base.metadata.create_all(engine)
        click.echo("Esquema inicial creado. No modifica ni borra tablas existentes.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt="Correo administrativo")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(email, password):
        if len(password)<12:
            raise click.ClickException("Usá al menos 12 caracteres.")
        email = email.strip().lower()
        with app.extensions["sessions"]() as db:
            if db.query(Admin).filter_by(email=email).first():
                raise click.ClickException("La cuenta ya existe; no se cambió su contraseña.")
            db.add(Admin(email=email, password_hash=generate_password_hash(password)))
            db.commit()
        click.echo("Cuenta administrativa creada.")
    return app

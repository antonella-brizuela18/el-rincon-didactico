"""Interactive setup. Passwords are read privately from the terminal."""
import getpass
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.engine import URL

from deploy.settings import settings_path


def ask(label, default=""):
    value = input(label+(f" [{default}]" if default else "")+": ").strip()
    return value or default


def configure():
    path = settings_path()
    values = json.loads(path.read_text()) if path.is_file() else {}
    print("Los datos privados se guardan fuera del repositorio. No se muestran contraseñas.")
    site = ask("URL HTTPS de la tienda", values.get("SITE_URL", "")).rstrip("/")
    parsed = urlparse(site)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or parsed.port:
        raise SystemExit("Ingresá solo https://tu-dominio, sin ruta ni puerto.")
    if values.get("DATABASE_URL") and ask("¿Conservar la conexión actual a PostgreSQL? (s/n)", "s").lower()=="s":
        database_url = values["DATABASE_URL"]
    else:
        host = ask("Host PostgreSQL", "postgresql-elrincondidactico.alwaysdata.net")
        name = ask("Nombre de la base", "elrincondidactico_tienda")
        user = ask("Usuario PostgreSQL")
        password = getpass.getpass("Contraseña PostgreSQL (no se muestra): ")
        if not all((host,name,user,password)):
            raise SystemExit("Los datos de PostgreSQL son obligatorios.")
        database_url = URL.create("postgresql+psycopg", username=user, password=password, host=host, port=5432, database=name).render_as_string(hide_password=False)
    values.update(
        SECRET_KEY=values.get("SECRET_KEY") or os.environ.get("SECRET_KEY") or secrets.token_urlsafe(48),
        DATABASE_URL=database_url, SITE_URL=site, TRUSTED_HOSTS=parsed.hostname, COOKIE_SECURE="1",
        STORAGE_DIR=values.get("STORAGE_DIR", str(Path.home()/"private-store-storage")),
        CONTACT_EMAIL=ask("Correo público de contacto (opcional)", values.get("CONTACT_EMAIL", "")),
        PAYMENT_INSTRUCTIONS=ask("Indicaciones de transferencia; vacío deja compras deshabilitadas", values.get("PAYMENT_INSTRUCTIONS", "")),
    )
    for key in ("MP_ACCESS_TOKEN","MP_WEBHOOK_SECRET","MP_COLLECTOR_ID","SMTP_HOST","SMTP_USER","SMTP_PASSWORD","SMTP_FROM"):
        values.setdefault(key, "")
    values.setdefault("MP_LIVE_MODE", "0")
    values.setdefault("SMTP_PORT", "465")
    values.setdefault("SMTP_SSL", "1")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name("settings-"+secrets.token_hex(8)+".tmp")
    descriptor = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(values, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)
    print(f"Configuración guardada en {path}. No la compartas ni la subas a GitHub.")


if __name__=="__main__":
    configure()

"""Connect a read-only service account without copying secrets into the repo."""
import json
import os
import secrets
from pathlib import Path
from app.drive import DriveError, valid_id, validated_credentials
from deploy.settings import settings_path


def configure():
    settings_file=settings_path()
    if not settings_file.is_file():
        raise SystemExit("Primero ejecutá python -m deploy.configure.")
    values=json.loads(settings_file.read_text())
    default=str(Path.home()/".config"/"el-rincon-didactico"/"google-drive-service-account.json")
    filename=input(f"Ruta privada del JSON de la cuenta de servicio [{default}]: ").strip() or default
    keyfile=Path(filename).expanduser().resolve()
    checkout=Path(__file__).resolve().parents[1]
    if keyfile.is_relative_to(checkout):
        raise SystemExit("Guardá la credencial fuera del repositorio y del directorio público del sitio.")
    try:
        credentials=validated_credentials(keyfile)
    except DriveError as error:
        raise SystemExit(str(error)) from None
    default_folder=values.get("GOOGLE_DRIVE_FOLDER_ID", "1oRYvQe1MuIxy1R-ehYilne_LVIOXKpbl")
    folder=input(f"ID de la carpeta Drive [{default_folder}]: ").strip() or default_folder
    if not valid_id(folder):
        raise SystemExit("El ID de carpeta no es válido.")
    keyfile.chmod(0o600)
    values.update(GOOGLE_DRIVE_CREDENTIALS=str(keyfile), GOOGLE_DRIVE_FOLDER_ID=folder)
    temporary=settings_file.with_name("settings-"+secrets.token_hex(8)+".tmp")
    descriptor=os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(values,stream,ensure_ascii=False,indent=2)
    temporary.replace(settings_file)
    print("Configuración guardada. Compartí solo la carpeta de recursos como Lector con:")
    print(credentials.service_account_email)
    print("Reiniciá el sitio y abrí Administración → Importar desde Drive.")


if __name__=="__main__":
    configure()

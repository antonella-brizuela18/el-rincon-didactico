"""Private settings shared by WSGI and Flask CLI; never stored in the repo."""
import json
import os
from pathlib import Path


def settings_path():
    return Path(os.environ.get("RINCON_SETTINGS_FILE", str(Path.home()/".config"/"el-rincon-didactico"/"settings.json")))


def load_settings():
    path = settings_path()
    if not path.is_file():
        raise RuntimeError("Falta la configuración privada. Ejecutá python -m deploy.configure.")
    values = json.loads(path.read_text())
    if not isinstance(values, dict) or not all(isinstance(k, str) and isinstance(v, str) for k,v in values.items()):
        raise RuntimeError("La configuración privada debe contener valores de texto.")
    for key, value in values.items():
        os.environ[key] = value
    return values

import importlib.util
import json
from pathlib import Path

from sqlalchemy.engine import make_url

from deploy.configure import configure
from deploy.settings import load_settings


def test_setup_encodes_password_and_keeps_secrets_private(tmp_path, monkeypatch):
    path = tmp_path/"private"/"settings.json"
    monkeypatch.setenv("RINCON_SETTINGS_FILE", str(path))
    answers = iter(["https://store.example.test", "db.example.test", "store", "dbuser", "contact@example.test", "Transferir al alias acordado"])
    monkeypatch.setattr("builtins.input", lambda label:next(answers))
    monkeypatch.setattr("getpass.getpass", lambda label:"test@password:/#")
    configure()
    values = json.loads(path.read_text())
    assert make_url(values["DATABASE_URL"]).password=="test@password:/#"
    assert values["TRUSTED_HOSTS"]=="store.example.test"
    if __import__("os").name != "nt":  # POSIX modes are not Windows ACLs.
        assert path.stat().st_mode & 0o777 == 0o600
    secret = values["SECRET_KEY"]
    answers = iter(["", "s", "", ""])
    monkeypatch.setattr("builtins.input", lambda label:next(answers))
    configure()
    assert json.loads(path.read_text())["SECRET_KEY"]==secret


def test_wsgi_and_cli_share_private_configuration(tmp_path, monkeypatch):
    path = tmp_path/"settings.json"
    path.write_text(json.dumps({"SECRET_KEY":"private-test-only", "DATABASE_URL":f"sqlite:///{tmp_path/'test.db'}", "STORAGE_DIR":str(tmp_path/"storage"), "COOKIE_SECURE":"1", "TRUSTED_HOSTS":"store.example.test"}))
    monkeypatch.setenv("RINCON_SETTINGS_FILE", str(path))
    # Isolate environment mutations made by the loader from other tests.
    for key in json.loads(path.read_text()):
        monkeypatch.setenv(key, "temporary")
    spec = importlib.util.spec_from_file_location("deployment_wsgi_test", Path(__file__).parents[1]/"deploy"/"wsgi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = module.application
    assert app.config["SECRET_KEY"]=="private-test-only"
    assert app.test_cli_runner().invoke(args=["init-db"]).exit_code==0
    assert app.test_client().get("/health/ready", base_url="https://store.example.test").status_code==200
    assert app.test_client().get("/", base_url="https://wrong.example.test").status_code==400
    app.extensions["database"].dispose()

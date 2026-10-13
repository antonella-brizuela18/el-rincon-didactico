import io
from pathlib import Path

import pytest
from PIL import Image

from app import drive
from app.models import Product
from test_store import app, client, login


class Response:
    def __init__(self, value=None, data=b""):
        self.value=value
        self.data=data
        self.closed=False
    def json(self): return self.value
    def iter_content(self, chunk_size):
        for start in range(0,len(self.data),chunk_size):
            yield self.data[start:start+chunk_size]
    def close(self): self.closed=True


@pytest.fixture
def mock_drive(app, monkeypatch):
    app.config.update(GOOGLE_DRIVE_FOLDER_ID="root", GOOGLE_DRIVE_CREDENTIALS="test-credential-not-used")
    picture=io.BytesIO()
    Image.new("RGB",(16,16),"green").save(picture,"PNG")
    items={
        "root":{"id":"root","name":"Recursos","mimeType":drive.FOLDER_MIME,"parents":[]},
        "folder":{"id":"folder","name":"Juegos","mimeType":drive.FOLDER_MIME,"parents":["root"]},
        "pdf":{"id":"pdf","name":"Juego.pdf","mimeType":"application/pdf","parents":["folder"],"size":"20","capabilities":{"canDownload":True}},
        "doc":{"id":"doc","name":"Documento","mimeType":"application/vnd.google-apps.document","parents":["root"]},
        "cover":{"id":"cover","name":"Portada.png","mimeType":"image/png","parents":["root"]},
        "outside":{"id":"outside","name":"Fuera.pdf","mimeType":"application/pdf","parents":[]},
        "huge":{"id":"huge","name":"Grande.pdf","mimeType":"application/pdf","parents":["root"],"size":str(21*1024*1024)},
        "restricted":{"id":"restricted","name":"Restringido.pdf","mimeType":"application/pdf","parents":["root"],"capabilities":{"canDownload":False}},
    }
    calls=[]
    def fake_api(path,params=None,stream=False):
        calls.append((path,params,stream))
        if path=="files":
            return Response({"files":[items["folder"],items["doc"],items["cover"]],"nextPageToken":"next"})
        identifier=path.split("/")[1]
        if stream:
            return Response(data=picture.getvalue() if identifier=="cover" else b"%PDF-1.4\ndrive-resource")
        return Response(items[identifier])
    monkeypatch.setattr(drive,"api_get",fake_api)
    return items,calls


def test_drive_browser_requires_admin_and_explains_missing_configuration(app, client):
    assert client.get("/admin/drive").status_code==302
    login(client)
    page=client.get("/admin/drive")
    assert page.status_code==200
    assert b"Falta conectar tu carpeta" in page.data


def test_browse_subfolders_and_resource_selection(client, mock_drive):
    login(client)
    page=client.get("/admin/drive")
    assert page.status_code==200
    assert b"Documento" in page.data
    assert b"drive_file=doc" in page.data
    assert b"drive_image=cover" in page.data
    assert b"carpeta=folder" in page.data
    assert b"pagina=next" in page.data
    selected=client.get("/admin/productos/nuevo?drive_file=pdf")
    assert selected.status_code==200
    assert b'name="drive_file" value="pdf"' in selected.data
    assert b'value="Juego"' in selected.data


def test_save_imported_pdf_keeps_file_private(app, client, mock_drive):
    login(client)
    response=client.post("/admin/productos/nuevo",data={"title":"Importado de Drive","description":"Un recurso","category":"Juegos","kind":"digital","price":"2000","stock":"0","drive_file":"pdf","published":"on"})
    assert response.status_code==302
    with app.extensions["sessions"]() as db:
        product=db.query(Product).filter_by(title="Importado de Drive").one()
        filename=product.digital_file
        assert product.published and filename.endswith(".pdf")
    assert (Path(app.config["STORAGE_DIR"])/"private"/filename).read_bytes().startswith(b"%PDF-")
    assert client.get("/static/"+filename).status_code==404
    assert b"Importado de Drive" in client.get("/").data


def test_google_document_exports_to_pdf_and_cover_is_normalized(app, client, mock_drive):
    login(client)
    response=client.post("/admin/productos/nuevo",data={"title":"Documento Drive","description":"Un recurso","category":"Juegos","kind":"digital","price":"1500","stock":"0","drive_file":"doc","drive_image":"cover","published":"on"})
    assert response.status_code==302
    with app.extensions["sessions"]() as db:
        product=db.query(Product).filter_by(title="Documento Drive").one()
        assert product.digital_file.endswith(".pdf")
        assert product.image.endswith(".jpg")
    assert any(path=="files/doc/export" and params=={"mimeType":"application/pdf"} for path,params,stream in mock_drive[1])


def test_import_denies_files_outside_root(app, client, mock_drive):
    login(client)
    assert client.get("/admin/productos/nuevo?drive_file=outside").status_code==302
    response=client.post("/admin/productos/nuevo",data={"title":"Must not import","description":"Test","category":"Test","kind":"digital","price":"10","stock":"0","drive_file":"outside"})
    assert response.status_code==200
    assert not any(path=="files/outside" and stream for path,params,stream in mock_drive[1])
    with app.extensions["sessions"]() as db:
        assert db.query(Product).filter_by(title="Must not import").first() is None


def test_file_size_and_google_permissions_enforced(app, mock_drive):
    with app.test_request_context():
        for identifier in ("huge","restricted"):
            with pytest.raises(drive.DriveError):
                drive.download(identifier)
    assert not any(stream for path,params,stream in mock_drive[1])


def test_streaming_size_limit_cannot_be_bypassed(app, mock_drive, monkeypatch):
    mock_drive[0]["huge"]["size"]="1"
    original=drive.api_get
    def fake(path,params=None,stream=False):
        return Response(data=b"x"*(21*1024*1024)) if stream else original(path,params,stream)
    monkeypatch.setattr(drive,"api_get",fake)
    with app.test_request_context():
        with pytest.raises(drive.DriveError):
            drive.download("huge")


def test_drive_publication_requires_csrf(app, client, mock_drive):
    login(client)
    app.config["WTF_CSRF_ENABLED"]=True
    assert client.post("/admin/productos/nuevo",data={"drive_file":"pdf"}).status_code==400


def test_untrusted_credential_endpoint_rejected(tmp_path):
    import json
    path=tmp_path/"key.json"
    path.write_text(json.dumps({"type":"service_account","token_uri":"https://bad.example/token"}))
    with pytest.raises(drive.DriveError):
        drive.validated_credentials(path)

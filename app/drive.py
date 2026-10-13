"""Read-only Drive source, restricted to one folder and its descendants."""
import io
import json
import re
from pathlib import Path

from flask import current_app, g
from werkzeug.datastructures import FileStorage

FOLDER_MIME="application/vnd.google-apps.folder"
PDF_EXPORTS={"application/vnd.google-apps.document", "application/vnd.google-apps.presentation", "application/vnd.google-apps.spreadsheet"}
RESOURCE_MIMES={"application/pdf", "application/zip", "application/x-zip-compressed"} | PDF_EXPORTS
IMAGE_MIMES={"image/jpeg", "image/png", "image/webp"}
SCOPES=["https://www.googleapis.com/auth/drive.readonly"]


class DriveError(Exception):
    pass


def configured():
    return bool(current_app.config.get("GOOGLE_DRIVE_CREDENTIALS") and current_app.config.get("GOOGLE_DRIVE_FOLDER_ID"))


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value) is not None


def validated_credentials(path):
    try:
        from google.auth.exceptions import GoogleAuthError
        from google.oauth2 import service_account
    except ImportError as error:
        raise DriveError("Instalá las dependencias actualizadas de la tienda para habilitar Drive.") from error
    try:
        info=json.loads(Path(path).read_text())
        if info.get("type")!="service_account" or info.get("token_uri")!="https://oauth2.googleapis.com/token" or info.get("universe_domain", "googleapis.com")!="googleapis.com":
            raise ValueError()
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except (OSError, ValueError, TypeError, AttributeError, GoogleAuthError) as error:
        raise DriveError("No pudimos cargar la credencial privada de Google. Revisá su configuración en el servidor.") from error


def connection():
    if not configured():
        raise DriveError("Primero configurá la conexión de la tienda con Drive.")
    if "drive_session" not in g:
        try:
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as error:
            raise DriveError("Instalá las dependencias actualizadas de la tienda para habilitar Drive.") from error
        g.drive_session=AuthorizedSession(validated_credentials(current_app.config["GOOGLE_DRIVE_CREDENTIALS"]), refresh_timeout=15)
    return g.drive_session


def api_get(path, params=None, stream=False):
    transport=connection()
    from google.auth.exceptions import GoogleAuthError
    from requests.exceptions import RequestException
    try:
        response=transport.get("https://www.googleapis.com/drive/v3/"+path, params=params, timeout=(10,30), stream=stream, allow_redirects=False)
        if response.status_code!=200:
            response.close()
            raise DriveError("Google no permitió leer este archivo. Revisá el acceso a la carpeta y que Drive API esté habilitada.")
        return response
    except (RequestException, GoogleAuthError) as error:
        raise DriveError("No pudimos conectar con Google Drive. Intentá nuevamente.") from error


def metadata(identifier):
    if not valid_id(identifier):
        raise DriveError("El identificador de Drive no es válido.")
    cache=g.setdefault("drive_metadata", {})
    if identifier not in cache:
        response=api_get("files/"+identifier, {"fields":"id,name,mimeType,size,parents,trashed,capabilities(canDownload)", "supportsAllDrives":"true"})
        try:
            value=response.json()
            if not isinstance(value,dict) or value.get("id")!=identifier or value.get("trashed"):
                raise DriveError("El archivo ya no está disponible en Drive.")
            cache[identifier]=value
        except ValueError as error:
            raise DriveError("Google devolvió una respuesta no válida.") from error
        finally:
            response.close()
    return cache[identifier]


def permitted_metadata(identifier):
    item=metadata(identifier)
    root=current_app.config["GOOGLE_DRIVE_FOLDER_ID"]
    current=item
    visited=set()
    for unused in range(20):
        if current.get("id")==root:
            return item
        if current["id"] in visited:
            break
        visited.add(current["id"])
        parents=current.get("parents", [])
        if len(parents)!=1:
            break
        current=metadata(parents[0])
    raise DriveError("Solo se pueden importar archivos de la carpeta configurada y sus subcarpetas.")


def list_folder(folder=None, page_token="", search=""):
    identifier=folder or current_app.config["GOOGLE_DRIVE_FOLDER_ID"]
    folder_info=permitted_metadata(identifier)
    if folder_info.get("mimeType")!=FOLDER_MIME:
        raise DriveError("La ubicación elegida no es una carpeta.")
    query=f"'{identifier}' in parents and trashed = false"
    if search:
        escaped=search[:100].replace("\\", "\\\\").replace("'", "\\'")
        query+=" and name contains '"+escaped+"'"
    params={"q":query, "fields":"nextPageToken,files(id,name,mimeType,size)", "pageSize":50,
            "orderBy":"folder,name", "supportsAllDrives":"true", "includeItemsFromAllDrives":"true"}
    if page_token:
        if len(page_token)>2048:
            raise DriveError("La página seleccionada no es válida.")
        params["pageToken"]=page_token
    response=api_get("files", params)
    try:
        result=response.json()
        return folder_info,result.get("files", []),result.get("nextPageToken", "")
    except (ValueError,AttributeError) as error:
        raise DriveError("Google devolvió un listado no válido.") from error
    finally:
        response.close()


def download(identifier, image=False):
    info=permitted_metadata(identifier)
    mime=info.get("mimeType")
    allowed=IMAGE_MIMES if image else RESOURCE_MIMES
    if mime not in allowed:
        raise DriveError("Elegí una imagen JPG/PNG/WebP." if image else "Elegí un PDF, ZIP o documento de Google exportable a PDF.")
    if info.get("capabilities", {}).get("canDownload") is False:
        raise DriveError("Google no permite descargar este archivo.")
    maximum=5*1024*1024 if image else 20*1024*1024
    if int(info.get("size", 0))>maximum:
        raise DriveError("El archivo supera el límite: 5 MB para portadas y 20 MB para recursos.")
    export=mime in PDF_EXPORTS
    filename=info.get("name", "recurso")
    if export:
        response=api_get("files/"+identifier+"/export", {"mimeType":"application/pdf"}, stream=True)
        filename=Path(filename).stem+".pdf"
    else:
        response=api_get("files/"+identifier, {"alt":"media", "supportsAllDrives":"true"}, stream=True)
        if not image:
            filename=Path(filename).stem+(".pdf" if mime=="application/pdf" else ".zip")
    from requests.exceptions import RequestException
    chunks=[]
    size=0
    try:
        for chunk in response.iter_content(chunk_size=65536):
            size+=len(chunk)
            if size>maximum:
                raise DriveError("El archivo supera el límite de importación.")
            chunks.append(chunk)
    except RequestException as error:
        raise DriveError("La descarga se interrumpió. Volvé a intentar.") from error
    finally:
        response.close()
    return FileStorage(stream=io.BytesIO(b"".join(chunks)), filename=filename),info

"""One fingerprinted CSS payload; private pages remain uncached."""
import hashlib
import gzip
from pathlib import Path
from flask import Blueprint, Response, current_app, request
assets=Blueprint('assets',__name__)

@assets.get('/ui.css')
def ui():
    content,version=current_app.extensions['ui_bundle']
    response=Response(content,mimetype='text/css')
    response.set_etag(version)
    response.headers['Cache-Control']='public, max-age=31536000, immutable' if request.args.get('v')==version else 'no-cache'
    return response.make_conditional(request)

def register(app):
    root=Path(app.static_folder)
    content='\n'.join((root/name).read_text() for name in ('style.css','studio.css','experience.css','commerce.css','mobile.css'))
    version=hashlib.sha256(content.encode()).hexdigest()[:16]
    app.extensions['ui_bundle']=(content,version)
    app.extensions['ui_gzip']=gzip.compress(content.encode(),compresslevel=6,mtime=0)
    app.config['UI_VERSION']=version
    app.register_blueprint(assets)

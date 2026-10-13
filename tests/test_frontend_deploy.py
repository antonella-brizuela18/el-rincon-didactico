import base64
import io
import json
import tarfile
import pytest
from deploy.remote import unpack_frontend


def bundle(revision='a'*40,extra=None):
    files={'.build-revision':revision,'.vite/manifest.json':json.dumps({'src/main.tsx':{'file':'assets/main-test.js','css':['assets/main-test.css']}}),'assets/main-test.js':'compiled JS','assets/main-test.css':'compiled CSS'}
    files.update(extra or {})
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as archive:
        for name,content in files.items():
            content=content.encode();entry=tarfile.TarInfo(name);entry.size=len(content);archive.addfile(entry,io.BytesIO(content))
    return base64.b64encode(out.getvalue()).decode()


def test_matching_frontend_artifact_is_usable(tmp_path):
    unpack_frontend(bundle(),tmp_path,'a'*40)
    assert (tmp_path/'assets/main-test.js').read_text()=='compiled JS'


def test_wrong_revision_does_not_deploy(tmp_path):
    with pytest.raises(ValueError,match='otra revisión'): unpack_frontend(bundle(),tmp_path,'b'*40)


def test_frontend_artifact_cannot_write_outside_destination(tmp_path):
    with pytest.raises(ValueError,match='inválido'): unpack_frontend(bundle(extra={'../outside':'forbidden'}),tmp_path,'a'*40)
    assert not (tmp_path.parent/'outside').exists()

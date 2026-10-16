"""Runs on Alwaysdata over SSH. Refuses dirty/divergent checkouts.

Prepares new tables before updating the live checkout. Does not delete files,
reset changes, migrate columns, or modify private JSON/SMTP settings.
"""
import fcntl
import base64
import io
import shutil
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

def run(command, cwd, capture=False, env=None):
    return subprocess.run(command,cwd=cwd,env=env,check=True,text=True,
                          stdout=subprocess.PIPE if capture else None).stdout

def unpack_frontend(encoded, frontend, sha):
    payload=base64.b64decode(encoded,validate=True)
    if len(payload)>5*1024*1024: raise ValueError('Artefacto frontend demasiado grande.')
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as bundle:
        members=bundle.getmembers()
        if sum(member.size for member in members)>10*1024*1024: raise ValueError('Artefacto frontend demasiado grande.')
        for member in members:
            if not member.isfile() or not re.fullmatch(r'(?:assets/[A-Za-z0-9_-]+\.(?:js|css)|\.vite/manifest\.json|\.build-revision)',member.name):
                raise ValueError('Artefacto frontend inválido.')
        bundle.extractall(frontend,filter='data')
    if (frontend/'.build-revision').read_text().strip()!=sha:
        raise ValueError('El frontend corresponde a otra revisión.')
    entry=json.loads((frontend/'.vite/manifest.json').read_text())['src/main.tsx']
    for name in [entry['file'],*entry.get('css',[])]:
        if not re.fullmatch(r'assets/[A-Za-z0-9_-]+\.(?:js|css)',name) or not (frontend/name).is_file():
            raise ValueError('Frontend incompleto.')

def main(sha, directory):
    if not re.fullmatch(r'[a-f0-9]{40}',sha): raise ValueError('Commit inválido')
    project=Path(directory).resolve()
    home=Path.home().resolve()
    if project!=home/'el-rincon-didactico' or not (project/'.git').is_dir():
        raise ValueError('El checkout existente no coincide con el destino esperado.')
    with (home/'.rincon-deploy.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        def git(*args): return run(['git',*args],project,True).strip()
        if git('status','--porcelain'):
            raise ValueError('Hay cambios locales en el servidor. Se conservaron; revisar antes de desplegar.')
        if git('remote','get-url','origin') not in ('https://github.com/antonella-brizuela18/el-rincon-didactico.git','https://github.com/antonella-brizuela18/el-rincon-didactico'):
            raise ValueError('Origen Git inesperado.')
        git('fetch','origin','main')
        if git('rev-parse','origin/main')!=sha:
            raise ValueError('Hay una versión main más nueva. Este despliegue no la reemplazará.')
        previous=git('rev-parse','HEAD')
        git('merge-base','--is-ancestor',previous,sha)
        if git('branch','--list','main'): git('merge-base','--is-ancestor','main',sha)
        # Never print database or mail settings. Stable storage location also during staging.
        private=Path(os.environ.get('RINCON_SETTINGS_FILE',home/'.config/el-rincon-didactico/settings.json'))
        values=json.loads(private.read_text())
        env=os.environ.copy();env.update(values)
        env['RINCON_SETTINGS_FILE']=str(private)
        env.setdefault('STORAGE_DIR',str(project/'instance/storage'))
        with tempfile.TemporaryDirectory(prefix='.rincon-stage-',dir=home) as temp:
            stage=Path(temp)
            archive=stage/'source.tar'
            run(['git','archive','--format=tar','--output='+str(archive),sha],project)
            with tarfile.open(archive) as source: source.extractall(stage,filter='data')
            frontend=stage/'frontend-build'
            frontend.mkdir()
            unpack_frontend(FRONTEND_BUNDLE,frontend,sha)
            run([sys.executable,'-m','pip','install','-r',str(stage/'requirements.txt')],stage)
            run([sys.executable,'-m','flask','--app',str(stage/'deploy/wsgi.py'),'init-db'],stage,env=env)
            run([sys.executable,'-m','flask','--app',str(stage/'deploy/wsgi.py'),'seed-examples'],stage,env=env)
            run([sys.executable,'-m','compileall','-q',str(stage/'app')],stage)
            git('update-ref','refs/deploy/previous',previous)
            git('merge','--ff-only',sha)
            # Keep previous hashed assets so tabs opened before deployment still work.
            destination=project/'app/static/storefront'
            for asset in frontend.rglob('*'):
                if asset.is_file() and asset.name!='manifest.json':
                    target=destination/asset.relative_to(frontend);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(asset,target)
            pending_manifest=frontend/'.vite/manifest.json'
            manifest_dir=destination/'.vite';manifest_dir.mkdir(parents=True,exist_ok=True)
            shutil.copy2(pending_manifest,manifest_dir/'manifest.json.tmp')
            os.replace(manifest_dir/'manifest.json.tmp',manifest_dir/'manifest.json')
        # Fast-forward keeps the historical feature branch ancestry and all data.
        git('merge','--ff-only',sha)
        if git('branch','--list','main'):
            git('switch','main')
            git('merge','--ff-only',sha)
        else:
            git('switch','-c','main',sha)
        marker=project/'.release.tmp';marker.write_text(sha+'\n');os.replace(marker,project/'.release')
        (home/'.rincon-reload').touch()
        print('Código actualizado a '+sha+'. Versión anterior conservada: '+previous)

if __name__=='__main__':
    try: main(sys.argv[1],sys.argv[2])
    except Exception: raise SystemExit('No se pudo preparar el despliegue. Revisar checkout limpio, main, rutas, dependencias y configuración privada.')

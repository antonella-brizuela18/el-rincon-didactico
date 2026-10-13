"""Runs on Alwaysdata over SSH. Refuses dirty/divergent checkouts.

Prepares new tables before updating the live checkout. Does not delete files,
reset changes, migrate columns, or modify private JSON/SMTP settings.
"""
import fcntl
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
            run([sys.executable,'-m','pip','install','-r',str(stage/'requirements.txt')],stage)
            run([sys.executable,'-m','flask','--app',str(stage/'deploy/wsgi.py'),'init-db'],stage,env=env)
            run([sys.executable,'-m','compileall','-q',str(stage/'app')],stage)
        git('update-ref','refs/deploy/previous',previous)
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

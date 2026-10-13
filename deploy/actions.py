"""GitHub runner entry point: SSH upload, restart and exact-version health check.

Only stdlib is used. Credentials live in the ephemeral runner, never in artifacts.
"""
import base64
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

def configuration(environ):
    required=('ALWAYS_SSH_KEY','ALWAYS_KNOWN_HOSTS','ALWAYS_API_KEY','ALWAYS_SITE_ID',
              'ALWAYS_ACCOUNT','ALWAYS_HOST','ALWAYS_PROJECT','ALWAYS_PYTHON','ALWAYS_URL','DEPLOY_SHA')
    missing=[key for key in required if not environ.get(key)]
    if missing:
        raise ValueError('Falta configurar Actions: '+', '.join(missing)+'. Ver deploy/AUTODEPLOY.md.')
    config={key:environ[key] for key in required}
    if not re.fullmatch(r'[0-9a-f]{40}',config['DEPLOY_SHA']): raise ValueError('Commit inválido.')
    if not config['ALWAYS_SITE_ID'].isdigit(): raise ValueError('ID de sitio inválido.')
    if config['ALWAYS_HOST']!='ssh-elrincondidactico.alwaysdata.net' or config['ALWAYS_ACCOUNT']!='elrincondidactico':
        raise ValueError('Destino inesperado.')
    if config['ALWAYS_URL']!='https://elrincondidactico.alwaysdata.net': raise ValueError('URL inesperada.')
    for key in ('ALWAYS_PROJECT','ALWAYS_PYTHON'):
        if not re.fullmatch(r'/home/elrincondidactico/[a-zA-Z0-9_./-]+',config[key]) or '..' in config[key].split('/'):
            raise ValueError('Ruta de despliegue inválida.')
    return config

def verify(url, sha, attempts=24, pause=time.sleep):
    for _ in range(attempts):
        try:
            with urlopen(Request(url+'/health/ready',headers={'Cache-Control':'no-cache'}),timeout=10) as response:
                payload=json.load(response)
            if payload.get('status')=='ok' and payload.get('revision')==sha:
                with urlopen(url+'/',timeout=10) as response:
                    html=response.read().decode()
                    revision=response.headers.get('X-App-Revision')
                if revision==sha and 'mode-toggle' in html and 'experience.js?v=' in html: return True
        except (URLError,ValueError,OSError): pass
        pause(5)
    return False

def main():
    config=configuration(os.environ)
    sha=config['DEPLOY_SHA']
    with tempfile.TemporaryDirectory(prefix='rincon-deploy-') as temp:
        directory=Path(temp)
        key=directory/'key';key.write_text(config['ALWAYS_SSH_KEY'].rstrip()+'\n');key.chmod(0o600)
        hosts=directory/'known_hosts';hosts.write_text(config['ALWAYS_KNOWN_HOSTS'].rstrip()+'\n');hosts.chmod(0o600)
        ssh=['ssh','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
             '-o','UserKnownHostsFile='+str(hosts),'-o','ConnectTimeout=15',config['ALWAYS_ACCOUNT']+'@'+config['ALWAYS_HOST']]
        script=Path(__file__).with_name('remote.py').read_text()
        command=shlex.join([config['ALWAYS_PYTHON'],'-',sha,config['ALWAYS_PROJECT']])
        subprocess.run(ssh+[command],input=script,text=True,check=True,timeout=600)
        credentials=base64.b64encode((config['ALWAYS_API_KEY']+' account='+config['ALWAYS_ACCOUNT']+':').encode()).decode()
        restart=Request('https://api.alwaysdata.com/v1/site/'+config['ALWAYS_SITE_ID']+'/restart/',
                        method='POST',data=b'',headers={'Authorization':'Basic '+credentials})
        with urlopen(restart,timeout=30) as response:
            if response.status not in (200,202,204): raise RuntimeError('Alwaysdata no confirmó el reinicio.')
        if not verify(config['ALWAYS_URL'],sha):
            raise RuntimeError('La versión pública no coincide o no está saludable. Revisar el reinicio en Alwaysdata; no se declara éxito.')
    summary='Publicado y verificado: '+sha+'\n'+config['ALWAYS_URL']+'\n'
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out: out.write(summary)
    print(summary)

if __name__=='__main__':
    try: main()
    except (ValueError,RuntimeError) as error: raise SystemExit(str(error))
    except Exception: raise SystemExit('Falló el despliegue. Revisar SSH, permisos y conexión de Alwaysdata; credenciales omitidas.')

"""Interactive SMTP setup. Secrets never go to the repository or stdout."""
import getpass
import json
import os
import re
import tempfile
from deploy.settings import settings_path

def main():
    path=settings_path()
    if not path.exists():
        raise SystemExit('Primero ejecutá python -m deploy.configure.')
    values=json.loads(path.read_text())
    def ask(label,key,default=''):
        return input(f'{label} [{values.get(key,default)}]: ').strip() or values.get(key,default)
    host=ask('Servidor SMTP','SMTP_HOST','smtp-elrincondidactico.alwaysdata.net')
    port=ask('Puerto SMTP (465 SSL / 587 STARTTLS)','SMTP_PORT','465')
    user=ask('Usuario SMTP','SMTP_USER')
    sender=ask('Correo remitente','SMTP_FROM',user)
    password=getpass.getpass('Contraseña SMTP (vacío conserva la anterior): ') or values.get('SMTP_PASSWORD','')
    if port not in ('465','587') or not host or any(c.isspace() for c in host) or not user or not password or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',sender):
        raise SystemExit('Datos incompletos o inválidos; no se guardaron cambios.')
    values.update(SMTP_HOST=host,SMTP_PORT=port,SMTP_USER=user,SMTP_FROM=sender,SMTP_PASSWORD=password,SMTP_SSL='1' if port=='465' else '0')
    descriptor,temp=tempfile.mkstemp(dir=path.parent,prefix='.smtp-')
    try:
        with os.fdopen(descriptor,'w') as handle:
            json.dump(values,handle,ensure_ascii=False,indent=2)
        os.chmod(temp,0o600)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    print('Conexión guardada. Reiniciá el sitio y configurá el destinatario en Administración → Configuración. La entrega todavía debe verificarse.')

if __name__=='__main__': main()

"""Keep payment secrets outside the repo; operator enters them over SSH."""
import getpass
import json
import os
import tempfile
from deploy.settings import settings_path

def main():
    path=settings_path()
    if not path.is_file(): raise SystemExit('Primero ejecutá python -m deploy.configure.')
    values=json.loads(path.read_text())
    print('Conexión con Mercado Pago. No se muestran ni se publican tokens.')
    token=getpass.getpass('Access token (vacío conserva el actual): ') or values.get('MP_ACCESS_TOKEN','')
    webhook=getpass.getpass('Clave secreta del webhook (vacío conserva la actual): ') or values.get('MP_WEBHOOK_SECRET','')
    collector=input('ID de la cuenta vendedora: ').strip() or values.get('MP_COLLECTOR_ID','')
    live=input('¿Credenciales de producción? (s/n, vacío conserva): ').strip().lower()
    if not token or not webhook or not collector.isdigit() or live not in ('s','n',''):
        raise SystemExit('Revisá los datos. No se guardaron cambios.')
    values.update(MP_ACCESS_TOKEN=token,MP_WEBHOOK_SECRET=webhook,MP_COLLECTOR_ID=collector,MP_LIVE_MODE=('1' if live=='s' else '0') if live else values.get('MP_LIVE_MODE','0'))
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.payments-')
    try:
        with os.fdopen(fd,'w') as handle: json.dump(values,handle,ensure_ascii=False,indent=2)
        os.chmod(temp,0o600);os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    print('Conexión guardada. Reiniciá el sitio; revisá Pagos en la configuración del panel. Todavía falta probar un pago real.')

if __name__=='__main__': main()

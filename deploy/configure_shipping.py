"""Configure official MiCorreo API credentials outside the repository."""
import getpass
import json
import os
import tempfile
from deploy.settings import settings_path

def main():
    path=settings_path()
    if not path.exists(): raise SystemExit('Primero ejecutá python -m deploy.configure.')
    values=json.loads(path.read_text())
    user=input('Usuario API de MiCorreo (vacío conserva el anterior): ').strip() or values.get('MICORREO_USER','')
    password=getpass.getpass('Contraseña API de MiCorreo (vacío conserva la anterior): ') or values.get('MICORREO_PASSWORD','')
    customer=input('Customer ID de MiCorreo (vacío conserva el anterior): ').strip() or values.get('MICORREO_CUSTOMER_ID','')
    environment=input('Ambiente: prueba / produccion [prueba]: ').strip() or 'prueba'
    if not all((user,password,customer)) or environment not in ('prueba','produccion'):
        raise SystemExit('Datos incompletos o ambiente inválido. No se guardaron cambios.')
    values.update(MICORREO_USER=user,MICORREO_PASSWORD=password,MICORREO_CUSTOMER_ID=customer,MICORREO_TEST='1' if environment=='prueba' else '0')
    descriptor,temp=tempfile.mkstemp(dir=path.parent,prefix='.shipping-')
    try:
        with os.fdopen(descriptor,'w') as handle: json.dump(values,handle,ensure_ascii=False,indent=2)
        os.chmod(temp,0o600)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    print('Guardado. Reiniciá el sitio y completá origen y medidas en el administrador. Falta validar una cotización real.')

if __name__=='__main__': main()

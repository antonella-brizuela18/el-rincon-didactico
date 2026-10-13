# Main → Alwaysdata

El workflow `Store checks and deploy` corre con cada push. Para `main`, ejecuta
SQLite/PostgreSQL y solo después despliega ese mismo commit. Las demás ramas y
los pull requests ejecutan pruebas sin acceso al servidor. Se puede volver a
ejecutar desde Actions → Run workflow, seleccionando `main`.

## Conexión inicial (una sola vez)

En GitHub → Settings → Secrets and variables → Actions, guardar:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| Secret | `ALWAYSDATA_SSH_KEY` | Clave privada Ed25519 exclusiva para deploy, cuyo público esté autorizado en Alwaysdata. |
| Secret | `ALWAYSDATA_KNOWN_HOSTS` | Línea verificada de known_hosts para `ssh-elrincondidactico.alwaysdata.net`. Comparar el fingerprint con Remote access → SSH/SFTP de Alwaysdata; no usar StrictHostKeyChecking=no. |
| Secret | `ALWAYSDATA_API_KEY` | Token de Alwaysdata autorizado para reiniciar este sitio. |
| Variable | `ALWAYSDATA_SITE_ID` | `1086130`, confirmado en el panel de Alwaysdata. |

El workflow apunta al checkout existente
`/home/elrincondidactico/el-rincon-didactico` y al Python
`/home/elrincondidactico/venv/bin/python`. Antes del primer despliegue verificar
en la configuración del sitio que estas rutas coinciden con las reales.
La aplicación WSGI debe apuntar a `deploy/wsgi.py` del mismo checkout.

Las credenciales no deben ir en el repositorio ni en el chat. El archivo privado
`~/.config/el-rincon-didactico/settings.json` sigue en el servidor. Su SMTP, base
de datos y clave de sesión no se reemplazan.

## Qué hace

1. Espera pruebas satisfactorias, y serializa despliegues sin interrumpir uno activo.
2. Verifica la clave del servidor SSH, el origen del repo y que el checkout esté
   limpio. Rechaza ramas divergentes o commits superados por un push más reciente.
3. Prepara una copia temporal del commit probado. Instala dependencias y ejecuta
   `init-db` en ella antes de actualizar el código del sitio. Solo crea tablas
   nuevas; no borra productos, pedidos, recursos ni ajustes privados.
4. Conserva la referencia anterior en `refs/deploy/previous`, avanza a `main`
   por fast-forward y escribe `.release` con el commit instalado.
5. Reinicia únicamente el sitio configurado mediante la API oficial de Alwaysdata.
6. Comprueba `/health/ready` y la portada: exige respuesta saludable, el mismo
   commit y los recursos de interfaz nuevos. Si no coinciden, Actions falla.

La aplicación versiona CSS/JS mediante hashes de contenido para evitar que una
actualización siga mostrando archivos guardados por el navegador. El panel de
administración muestra el commit instalado; el código del commit es público,
no incluye información de pedidos ni configuración.

El despliegue actualiza el checkout existente: no es un cambio atómico de releases.
Si falla la instalación de dependencias, el código aún no se ha cambiado, aunque
el virtualenv puede haber recibido paquetes nuevos. Si falla el reinicio o la
verificación final, revisar Alwaysdata y reejecutar el workflow. No se realiza un
rollback de base de datos ni se promete una recuperación automática.

## Diagnóstico

- “Falta configurar Actions”: completar los tres secrets y la variable.
- “Hay cambios locales”: revisarlos y conservarlos antes de desplegar; el script
  no ejecuta reset/clean ni descarta trabajo del servidor.
- “Hay una versión main más nueva”: reejecutar el último workflow de main.
- Fallo SSH: revisar usuario, clave autorizada y fingerprint.
- Versión pública distinta: revisar las rutas WSGI/virtualenv y el reinicio del sitio.

Referencias oficiales:
- https://help.alwaysdata.com/en/docs/development/api/
- https://help.alwaysdata.com/en/docs/web-hosting/remote-access/ssh/
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments

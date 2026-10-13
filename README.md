# El Rincón Didáctico

Tienda Python/Flask para Alwaysdata y PostgreSQL. Conserva el proyecto original; no requiere Node ni cambiar de alojamiento.

## Implementado

- Portada responsive, buscador, filtros por categoría y formato; fichas de producto.
- Catálogo paginado con filtros conservados; ya no se ocultan recursos por un límite fijo de resultados.
- Administración con contraseñas hasheadas, sesiones, CSRF y límite de intentos de acceso.
- Productos digitales y físicos, borradores/publicación, precios ARS, stock, fotos normalizadas.
- Vista previa privada de borradores y acciones para publicar/ocultar desde el listado. La publicación digital exige un archivo disponible.
- Carrito y pedidos persistidos con precios calculados en el servidor. Confirmación idempotente.
- Cantidades editables de materiales físicos y actualización del carrito si se oculta un recurso o cambia el stock.
- Administración con filtros, búsqueda y paginación de productos/pedidos; los contadores representan toda la tienda.
- Reserva de stock al crear el pedido y devolución al cancelar un pedido pendiente.
- Transferencias con verificación manual, referencia y administrador que acreditó el pago.
- Checkout Pro opcional para pedidos exclusivamente digitales. Notificaciones firmadas, consulta del pago por API y validación de importe, moneda, cuenta receptora y modo de prueba/producción. El retorno del navegador nunca acredita un pago.
- PDF/ZIP privados, enlaces de pedido firmados (30 días), descargas por 7 días desde la acreditación. Las compras conservan la versión del archivo adquirida. Los reembolsos/contracargos de Mercado Pago deshabilitan descargas posteriores.
- Cola transaccional de correos de pedido/pago, con trabajador SMTP y reintentos.
- Salud de proceso en /health y disponibilidad de base/esquema en /health/ready.
- CI con pruebas SQLite y una prueba concurrente de stock sobre PostgreSQL 17.

No incluye productos ficticios ni credenciales preconfiguradas. La cuenta administrativa se crea en el servidor. Los pagos, el correo y el despliegue requieren configuración y pruebas con las cuentas reales antes de abrir la tienda.

## Preparación en Alwaysdata

### Asistente por SSH (alternativa recomendada para esta primera instalación)

Instalar esta rama en una carpeta nueva, por ejemplo ~/apps/el-rincon-didactico. Usar PYTHON_VERSION=3.12 python -m venv .venv, activar el virtualenv e instalar requirements.txt. Alwaysdata utiliza el comando python, no python3.

Desde la raíz del proyecto ejecutar python -m deploy.configure. El asistente pide la URL HTTPS y los datos de PostgreSQL, codifica los caracteres especiales de la contraseña y genera una clave de sesión. Guarda settings.json con permisos 600 en ~/.config/el-rincon-didactico/, fuera del repositorio. Al repetirlo conserva la clave de sesión y puede conservar la conexión existente.

Ejecutar python -m flask --app deploy/wsgi.py init-db y python -m flask --app deploy/wsgi.py create-admin. Para esta alternativa el sitio debe apuntar al archivo deploy/wsgi.py, con el checkout como working directory y su .venv como virtualenv. Ese WSGI carga la misma configuración privada que los comandos de consola.

Para editar después pagos o correo usar un editor local sobre ~/.config/el-rincon-didactico/settings.json. No compartir ese archivo. La tarea de correos debe ejecutar python -m flask --app deploy/wsgi.py send-mail desde el proyecto y con el virtualenv correspondiente. No apuntar la URL del sitio a la carpeta privada de configuración.

### Configuración directa por variables de entorno

1. Confirmar dónde está el checkout existente. El despliegue original documenta:
   - Python WSGI: /home/elrincondidactico/wsgi.py
   - Working directory: /home/elrincondidactico/
   - Virtualenv: /home/elrincondidactico/venv/
   No cambiar estas rutas si la configuración real utiliza otra estructura.
2. Respaldar PostgreSQL y la carpeta de archivos antes de actualizar.
3. Instalar dependencias en el virtualenv: python -m pip install -r requirements.txt
4. Configurar las variables de .env.example en el entorno WSGI y en el entorno de la consola/tareas programadas. La aplicación NO lee archivos .env automáticamente.
5. SECRET_KEY y DATABASE_URL son obligatorias. Configurar SITE_URL y TRUSTED_HOSTS con la dirección real del sitio, HTTPS, COOKIE_SECURE=1 y STORAGE_DIR fuera del directorio público y fuera de app/static.
6. Con esas mismas variables disponibles en la consola, ejecutar:
   - flask --app wsgi init-db
   - flask --app wsgi create-admin
   El comando pide correo y contraseña sin mostrar la contraseña. No pasar la contraseña como argumento ni publicarla.
7. init-db crea el esquema inicial (v1) si no existe; no borra datos ni altera tablas existentes. Los cambios futuros de esquema requerirán una migración versionada, no una nueva ejecución de create_all para modificar columnas.
8. Reiniciar el sitio WSGI y comprobar /health/ready, /admin/login y la portada.
9. Cargar un recurso de prueba, comprobar el pedido, pago y descarga, y después publicar recursos reales.

Mantener la versión anterior desplegada hasta completar las variables y el esquema. No fusionar esta rama en un despliegue automático sin esos pasos.

## Pagos

PAYMENT_INSTRUCTIONS habilita el flujo manual; debe contener datos e indicaciones reales de transferencia. Confirmar desde el panel únicamente después de verificar la acreditación real.

Para Mercado Pago completar MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, MP_COLLECTOR_ID y SITE_URL. Configurar el webhook de pagos en SITE_URL/pagos/mercadopago/webhook. Usar cuentas/credenciales de prueba con MP_LIVE_MODE=0. Validar un pago aprobado, rechazado, pendiente y reembolsado antes de cambiar a credenciales reales y MP_LIVE_MODE=1. No compartir esos secretos en el chat ni en el repositorio.

El botón de Mercado Pago aparece solo para pedidos íntegramente digitales. Los materiales físicos se coordinan por transferencia porque el envío no está incluido. Los pagos duplicados o conflictos con una acreditación manual requieren revisión y devolución desde Mercado Pago; el software no ejecuta reembolsos.

Los pedidos pendientes reservan stock hasta que se cancelan desde el panel; todavía no hay vencimiento automático de reservas. Los archivos antiguos se conservan para pedidos anteriores. No borrarlos manualmente.

## Correos

Configurar SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM y SMTP_SSL. SITE_URL debe ser HTTPS. SMTP_SSL=1 utiliza TLS directo; SMTP_SSL=0 usa STARTTLS obligatorio.

Programar flask --app wsgi send-mail cada minuto en Alwaysdata usando el mismo virtualenv y entorno. Procesa hasta 20 correos por ejecución. Tras cinco fallos un correo requiere revisión de la cola. No se han enviado correos reales durante el desarrollo.

La entrega es al menos una vez: una caída entre la aceptación del SMTP y el registro local puede repetir un mensaje. Los enlaces privados no deben aparecer en logs, analíticas ni repositorios. El encabezado Referrer-Policy impide enviarlos como referencia a Mercado Pago.

## Desarrollo y pruebas

Python 3.12. Crear virtualenv y ejecutar:

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

Para local, definir SECRET_KEY, DATABASE_URL=sqlite:///local.db y COOKIE_SECURE=0. Ejecutar init-db antes de levantar el servidor. PostgreSQL es la base prevista para producción; SQLite no valida los bloqueos concurrentes de stock.

TEST_POSTGRES_URL habilita una prueba que crea y destruye solamente un esquema temporal propio. CI la ejecuta sobre un servicio de PostgreSQL 17.

## Límites de esta entrega

No se ha conectado el alojamiento ni probado un pago o correo real. Faltan la configuración del sitio, credenciales, cuenta administrativa, cron de correos, respaldos y pruebas integrales desplegadas.

La facturación fiscal, cálculo automático de envíos, cambios/devoluciones, integración de Instagram y notificaciones por WhatsApp no están implementados. Antes de vender, completar los datos del emprendimiento y las condiciones comerciales que correspondan. No hay pedidos ni datos de clientes incluidos en este repositorio.

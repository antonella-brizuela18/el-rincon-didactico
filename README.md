# El Rincón Didáctico

Tienda Python/Flask para Alwaysdata y PostgreSQL. Conserva el proyecto original; no requiere Node ni cambiar de alojamiento.

## Implementado

- Portada responsive, buscador, filtros por categoría y formato; fichas de producto.
- Catálogo paginado con filtros conservados; ya no se ocultan recursos por un límite fijo de resultados.
- Administración con contraseñas hasheadas, sesiones, CSRF y límite de intentos de acceso.
- Productos digitales y físicos, borradores/publicación, precios ARS, elaboración a pedido, fotos normalizadas.
- Importación administrativa desde una carpeta privada de Drive y sus subcarpetas: PDF/ZIP, portadas JPG/PNG/WebP y documentos de Google exportados a PDF. Copia privada al guardar; no escribe en Drive ni cambia sus permisos.
- Vista previa privada de borradores y acciones para publicar/ocultar desde el listado. La publicación digital exige un archivo disponible.
- Carrito y pedidos persistidos con precios calculados en el servidor. Confirmación idempotente.
- Cantidades editables de materiales físicos y actualización del carrito si se oculta un recurso.
- Administración con filtros, búsqueda y paginación de productos/pedidos; los contadores representan toda la tienda.
- Materiales físicos hechos a pedido: preparación aproximada de 10 días desde el pago, más tránsito. Sin reservas ni restricciones de stock; hasta 10 unidades por recurso por pedido.
- Transferencias con verificación manual, referencia y administrador que acreditó el pago.
- Checkout Pro opcional para pedidos exclusivamente digitales. Notificaciones firmadas, consulta del pago por API y validación de importe, moneda, cuenta receptora y modo de prueba/producción. El retorno del navegador nunca acredita un pago.
- PDF/ZIP privados, enlaces de pedido firmados (30 días), descargas por 7 días desde la acreditación. Las compras conservan la versión del archivo adquirida. Los reembolsos/contracargos de Mercado Pago deshabilitan descargas posteriores.
- Cola transaccional de correos de pedido/pago, con trabajador SMTP y reintentos.
- Salud de proceso en /health y disponibilidad de base/esquema en /health/ready.
- CI con pruebas SQLite y una prueba de compras concurrentes sobre PostgreSQL 17.

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

No se administra stock. La columna histórica se conserva por compatibilidad pero no limita compras ni se modifica al comprar/cancelar. Los archivos antiguos se conservan para pedidos anteriores. No borrarlos manualmente.

## Correos

Configurar SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM y SMTP_SSL. SITE_URL debe ser HTTPS. SMTP_SSL=1 utiliza TLS directo; SMTP_SSL=0 usa STARTTLS obligatorio.

Programar flask --app wsgi send-mail cada minuto en Alwaysdata usando el mismo virtualenv y entorno. Procesa hasta 20 correos por ejecución. Tras cinco fallos un correo requiere revisión de la cola. No se han enviado correos reales durante el desarrollo.

La entrega es al menos una vez: una caída entre la aceptación del SMTP y el registro local puede repetir un mensaje. Los enlaces privados no deben aparecer en logs, analíticas ni repositorios. El encabezado Referrer-Policy impide enviarlos como referencia a Mercado Pago.

## Importación desde Google Drive

La tienda y el plugin de Drive de ChatGPT tienen conexiones diferentes. La conexión del plugin no entrega sus credenciales a Alwaysdata. La integración del servidor usa una cuenta de servicio de Google con alcance drive.readonly y la carpeta elegida compartida como Lector.

1. En Google Cloud crear o seleccionar un proyecto, habilitar Google Drive API y crear una cuenta de servicio. No necesita roles de edición del proyecto para leer una carpeta que le compartas.
2. Descargar una clave JSON de esa cuenta y guardarla en el servidor en /home/elrincondidactico/.config/el-rincon-didactico/google-drive-service-account.json. Transferirla mediante SFTP/SCP. Nunca subir la clave al repositorio, al catálogo ni al chat.
3. Compartir la carpeta de recursos con el correo de la cuenta de servicio como Lector. No es necesario abrirla a cualquier persona con el enlace. No compartir otras carpetas con esa cuenta si no hace falta.
4. Activar el virtualenv e instalar requirements.txt. Desde el proyecto ejecutar python -m deploy.configure_drive. El asistente valida la credencial, guarda su ruta y el ID de la carpeta en la configuración privada y conserva SECRET_KEY, PostgreSQL y el resto de ajustes. Carpeta inicial: 1oRYvQe1MuIxy1R-ehYilne_LVIOXKpbl.
5. Reiniciar el sitio. En Administración → Importar desde Drive, explorar la carpeta/subcarpetas, elegir el recurso y completar descripción/precio antes de guardar. Para adjuntar luego una portada de Drive, guardar primero el recurso y volver a editarlo.

La tienda verifica que cada archivo pertenece a esa carpeta o a una subcarpeta (hasta 20 niveles). No resuelve accesos directos de Drive. Admite archivos digitales de hasta 20 MB y portadas de hasta 5 MB; la exportación de documentos de Google está además sujeta al límite de 10 MB de su API. Las imágenes se vuelven a codificar y los PDF/ZIP pasan la misma validación que una carga local.

Importar crea una copia independiente: si después cambiás el original de Drive, el producto no se actualiza automáticamente. Seleccionar de nuevo un archivo al editarlo permite importar la nueva versión; los pedidos anteriores conservan su archivo. La descarga del cliente sigue requiriendo pago acreditado y no muestra un enlace público al original de Drive.

La integración se probó con respuestas simuladas de Google. Falta configurar la credencial real y comprobar un archivo real de la carpeta; no se copiaron recursos reales durante el desarrollo.

## Desarrollo y pruebas

Python 3.12. Crear virtualenv y ejecutar:

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

Para local, definir SECRET_KEY, DATABASE_URL=sqlite:///local.db y COOKIE_SECURE=0. Ejecutar init-db antes de levantar el servidor. PostgreSQL es la base prevista para producción; SQLite no valida los bloqueos de filas de PostgreSQL.

TEST_POSTGRES_URL habilita una prueba que crea y destruye solamente un esquema temporal propio. CI la ejecuta sobre un servicio de PostgreSQL 17.

## Límites de esta entrega

No se ha conectado el alojamiento ni probado un pago o correo real. Faltan la configuración del sitio, credenciales, cuenta administrativa, cron de correos, respaldos y pruebas integrales desplegadas.

La facturación fiscal, cambios/devoluciones, publicaciones automáticas en Instagram y notificaciones automáticas por WhatsApp no están implementados. MiCorreo permite estimar envíos; no compra etiquetas ni suma/cobra el envío automáticamente. Antes de vender, completar los datos del emprendimiento y las condiciones comerciales que correspondan. No hay pedidos ni datos de clientes incluidos en este repositorio.

## Rediseño, administración y medición

La portada `/` y el catálogo `/catalogo` ahora tienen navegación y presentación independientes. El panel conserva recursos y pedidos y añade `/admin/estadisticas`, `/admin/correos` y `/admin/configuracion`. La configuración permite elegir tres paletas, textos de portada, contacto, Instagram, descripción SEO y correo receptor de avisos. No admite HTML/CSS arbitrario.

### Actualizar esta versión en Alwaysdata

```bash
cd "$HOME/el-rincon-didactico"
git pull --ff-only origin feat/store-catalog-orders
source "$HOME/venv/bin/activate"
python -m pip install -r requirements.txt
python -m flask --app deploy/wsgi.py init-db
```

Reiniciar el sitio después de `init-db`: esta versión añade las tablas `store_settings` y `visit_events`, sin alterar ni borrar pedidos/productos existentes. La inicialización es idempotente. No arrancar el código nuevo antes de crear estas tablas.

### Correo real

```bash
python -m deploy.configure_mail
```

Ingresar el servidor y credenciales del proveedor de correo. Para un buzón de Alwaysdata, el servidor es `smtp-elrincondidactico.alwaysdata.net`, puerto 465 SSL, usuario = dirección del buzón y contraseña = la del buzón, no la de SSH. También se puede usar otro proveedor SMTP con sus credenciales específicas. El asistente conserva las demás configuraciones, no imprime la contraseña y guarda el archivo privado con permisos 600.

Reiniciar el sitio y completar **Configuración → Recibir avisos de pedidos en**. Se generan avisos para el cliente y para ese destinatario al crear pedidos y al confirmar pagos; no se envían retroactivamente avisos de pedidos anteriores. Los correos al administrador enlazan a la página protegida del pedido, nunca al enlace privado del cliente.

En **Tareas programadas** de Alwaysdata, configurar cada minuto el comando:

```text
/home/elrincondidactico/venv/bin/python -m flask --app /home/elrincondidactico/el-rincon-didactico/deploy/wsgi.py send-mail
```

Configurar además una tarea diaria:

```text
/home/elrincondidactico/venv/bin/python -m flask --app /home/elrincondidactico/el-rincon-didactico/deploy/wsgi.py prune-analytics
```

Comprobar con un pedido de prueba y verificar recepción en ambas casillas; la etiqueta SMTP configurado solo verifica presencia de parámetros. El centro de correos muestra últimos 100 mensajes, enviados, pendientes y agotados (5 fallos); permite reponer intentos luego de corregir el proveedor. La entrega puede repetirse si el proceso se interrumpe luego de que SMTP acepte el mensaje. No se han probado credenciales reales desde el entorno de desarrollo.

### Qué significan las estadísticas

Medición propia, opt-in: no registra actividad hasta que el visitante permite medir en el selector de privacidad. Respeta DNT y GPC y excluye administradores. Una visita se renueva a los 30 minutos de inactividad; no equivale a una persona única. No almacena IP, user-agent, búsquedas, referrers, URLs privadas ni correo en eventos. Las acciones guardadas son catálogo, producto, agregado correcto al carrito, inicio de checkout y pedido creado. Refrescar no multiplica una misma acción de visita/producto/pedido; el conteo del embudo utiliza visitas distintas.

La conversión usa una cohorte de visitas cuyo primer evento conservado está en el período; cada etapa es el porcentaje de esa cohorte que la alcanzó. No impone secuencia lineal. Los pagos se derivan de pedidos realmente pagados de esa cohorte, incluso si se acreditan después del período; los reembolsados dejan de contar. No se infieren pagos a partir de retornos del navegador. Pedidos totales y cobros son indicadores comerciales independientes e incluyen clientes sin consentimiento. Las fechas de reportes son UTC. La limpieza diaria elimina eventos mayores a 180 días. Sin tráfico permitido, se muestran ceros reales.

### SEO

Descripción editable, metadatos sociales, canonical y descripciones por producto, marcado Product/Offer con precio ARS y disponibilidad real, sitemap dinámico de páginas públicas y robots.txt. Admin, carrito y pedidos incluyen `X-Robots-Tag: noindex`; filtros/búsquedas se marcan noindex para evitar variantes indexadas. No se publican opiniones ni calificaciones inventadas. La versión debe desplegarse antes de probar URLs en Search Console y enviar `/sitemap.xml`; el código no verifica propiedad ni promete posiciones. Se necesita contenido original, imágenes reales y revisión editorial de cada producto.


## Actualización: compras a pedido, apariencia y MiCorreo

Continuamos en `feat/store-catalog-orders` con Flask/Jinja. React/TypeScript no aporta una ventaja que justifique reescribir autenticación, formularios y despliegue para estos requisitos. La interacción está aislada en `experience.js` y mantiene los formularios del servidor.

Antes de reiniciar, ejecutar los comandos de actualización anteriores, especialmente `init-db`. Esta entrega añade `order_contacts` y `product_parcels` mediante tablas nuevas; no altera ni borra tablas existentes. Los pedidos históricos siguen siendo accesibles aunque no tengan WhatsApp. Conservar la configuración SMTP existente: no hace falta volver a ejecutar configure_mail.

Al confirmar el pago, el servidor habilita las descargas y encola el aviso en la misma transacción. La página pendiente consulta el estado cada 8 segundos mientras está visible y se actualiza al acreditar. No depende del envío de correo para habilitar archivos. La cola SMTP sigue requiriendo su tarea cada minuto; si SMTP falla, el acceso sigue habilitado. El límite de 7 días de descarga se conserva.

La compra física solicita WhatsApp internacional obligatorio; para compras digitales es opcional. El pedido administrativo incluye el enlace para contactar. Los físicos se preparan en aproximadamente 10 días desde el pago; el plazo de transporte es adicional. Nunca se anuncia entrega total en 10 días.

### Cotización MiCorreo

Documentación oficial: https://www.correoargentino.com.ar/MiCorreo/public/img/pag/apiMiCorreo.pdf

Solicitar a Correo Argentino credenciales API para el ambiente deseado y obtener el `customerId` de la cuenta (endpoint oficial `/users/validate` con la autenticación correspondiente). No confundir contraseña API con SMTP ni pegar secretos en el chat.

Desde el servidor ejecutar `python -m deploy.configure_shipping`. Guarda los datos en la configuración privada, preservando correo y base de datos. También se pueden configurar `MICORREO_USER`, `MICORREO_PASSWORD`, `MICORREO_CUSTOMER_ID`, `MICORREO_TEST` en el entorno. El valor predeterminado es prueba; `0` usa producción. Reiniciar después.

En Administración → Configuración completar el código postal de origen. En cada producto físico completar peso en gramos y las tres medidas en centímetros del paquete embalado. El checkout estima tarifas a domicilio/sucursal al ingresar el código postal. Para varias unidades usa un volumen de apilado conservador (suma de alturas y pesos, máximos de largo/ancho). El paquete final debe verificarse manualmente; si supera los límites o faltan medidas se solicita coordinación por WhatsApp. No se cobra una estimación ni se genera un envío automáticamente. Validar las cotizaciones reales con los paquetes usados antes de activar producción.

### Apariencia y privacidad

Administración permite paleta, tres familias tipográficas con fuentes del dispositivo, acento con texto contrastado, modo inicial claro/oscuro/sistema y banner opcional con título, descripción y enlace interno. El visitante puede cambiar el modo y guardarlo localmente. El banner es informativo: las promociones de precio se editan en los productos. No se permite ejecutar HTML/CSS arbitrario desde configuración.

WhatsApp de consultas: +5492915090223; Instagram usa su icono. Ninguno carga rastreadores ni recursos externos antes de que el visitante abra el enlace.

El aviso de medición aparece abierto desde la primera visita. Aceptar y rechazar se guardan durante 180 días en una cookie propia; puede revocarse desde Privacidad. No se mide antes de aceptar, ni con DNT/GPC. Los eventos asociados a pedidos son seudonimizados y pueden vincularse a una compra: no se anuncian como anónimos. La tarea `prune-analytics` sigue siendo necesaria para eliminar eventos mayores de 180 días.

Marco de referencia: Ley 25.326 y orientación de la AAIP (https://www.argentina.gob.ar/aaip/datospersonales/derechos). Un banner por sí solo no acredita cumplimiento legal. Antes de publicar, identificar al responsable real de la tienda y su contacto, revisar plazos de conservación de compras, registros del hosting y obligaciones aplicables. No se incorporan herramientas publicitarias de terceros.

## Publicación desde main

La rama de producción pasa a ser `main`. El workflow prueba cada cambio y en
main ejecuta el deploy después de las pruebas, con verificación del commit
publicado. Configuración inicial y diagnóstico: [deploy/AUTODEPLOY.md](deploy/AUTODEPLOY.md).
Hasta completar los secrets del servidor, Actions indica la configuración que
falta y el sitio conserva la versión anterior.

El diseño incorpora selector de modo visible en móvil, formatos de catálogo,
orden por precio/nombre, respuestas sobre compras y avisos de preparación.
El administrador muestra la versión desplegada. Los productos físicos pagados
tienen estado manual de preparación/listo/enviado/entregado y código de
seguimiento, visible en el enlace privado del cliente. Esto no cambia el estado
del pago ni envía mensajes de WhatsApp automáticamente.

Esta actualización añade `order_fulfillment`: ejecutar `init-db` antes de
reiniciar; Actions lo hace automáticamente cuando la conexión esté configurada.
La columna histórica de stock sigue sin limitar compras.

## Personalización ampliada

Administración → Configuración permite subir logo y foto de portada, cambiar
nombre/frase/ubicación de marca, textos de portada e historia, espaciado, menú
fijo, estilo de tarjetas, columnas en escritorio y encuadre de fotos. Las
secciones de categorías, beneficios, preguntas frecuentes e historia se pueden
ocultar. La portada admite hasta ocho recursos destacados elegidos entre los
publicados; el catálogo completo conserva todos los productos y sus filtros.

Las imágenes JPG/PNG/WebP se normalizan a JPEG (máximo 5 MB, 20 megapíxeles).
No se aceptan SVG ni archivos ejecutables desde administración. Logo y foto
se pueden quitar para volver a la ilustración floral. Configuraciones abiertas
desde una versión anterior conservan los nuevos ajustes al guardar.

WhatsApp usa el icono de Bootstrap Icons (licencia MIT en
`app/static/bootstrap-icons-LICENSE.txt`), con texto visible en móvil. Número,
texto del botón y mensaje inicial son editables. Las fichas preparan una consulta
con el título del recurso y su URL pública; abrir el enlace no envía el mensaje.
Las tarjetas permiten agregar directamente al carrito mediante formulario CSRF.

Referencias de navegación y catálogo: Aprendo Jugando y DidacTO3D. No se importan
sus productos, textos, promociones, opiniones ni datos de clientes.

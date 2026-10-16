# El Rincón Didáctico

Una biblioteca cálida para docentes y familias. La tienda invita a explorar;
la administración prioriza claridad, lectura y acciones rápidas.

- Conservar los colores, fuentes y secciones editables de la marca. Usar los
  tokens existentes de superficie, texto, líneas y acento en ambos modos.
- Administrar productos mediante grilla visual con búsqueda y visibilidad. Crear y
  editar en un dialog accesible, con página independiente de respaldo.
- Separar presentación, archivos y visibilidad. Drive aporta solamente un
  archivo o portada; nunca inventar descripción, precio ni publicación.
- Mantener los datos del formulario ante errores y al navegar carpetas de
  Drive. Advertir antes de descartar cambios. No publicar un digital sin archivo.
- Usar animaciones breves que ayuden a entender una transición. Respetar
  `prefers-reduced-motion`, foco visible, teclado y contraste en modo oscuro.
- Explicar el envío antes de comprar: origen 8000, paquete embalado, estimación
  para una unidad o carrito completo, preparación de unos 10 días y despacho
  coordinado por WhatsApp. Nunca presentar tarifas de prueba como reales.

Referencias revisadas a partir del post de RoundtableSpace:
[Better Design](https://github.com/marvkr/better-design),
[UI Layouts](https://github.com/ui-layouts/uilayouts) y
[Motion Primitives](https://github.com/ibelick/motion-primitives).
Se usan como referencia de jerarquía, componentes y movimiento; no se instaló
su infraestructura ni se copiaron bloques de código de estos repositorios.

La biblioteca muestra portada, estado, archivo y precio sin entrar al editor.
Archivar retira un recurso del catálogo y conserva pedidos y archivos. Restaurar
siempre vuelve a borrador. Duplicar conserva portada, archivo y paquete, con
publicación desactivada. La tabla de archivados se instala con `init-db` sin
alterar columnas existentes. El despliegue ejecuta `seed-examples` una sola vez
por tienda mediante su marcador persistente; los seis ejemplos son borradores.

Revisión de octubre: tipografía de lectura clara, superficies neutras y un solo
acento de marca. Íconos Lucide con trazo consistente; sin flores decorativas ni
portadas de ejemplo ampliadas en el hero. El hero de respaldo explica formatos
y permite entrar al catálogo. Las fotos y el logo personalizados se conservan.
Las mutaciones del carrito muestran progreso, éxito o error en una notificación
persistente al navegar; el botón accionado cambia de estado. Los filtros anuncian
la actualización sin desplazar al visitante. Guardar en administración muestra
progreso y confirma el resultado al volver a la grilla. Respetar movimiento reducido.

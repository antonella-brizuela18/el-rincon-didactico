# El Rincón Didáctico

Tienda online de recursos didácticos, en desarrollo con Python/Flask para Alwaysdata y PostgreSQL.

## Estado actual

Esta es la estructura inicial: página pública de presentación y ruta de salud `/health`. **Todavía no hay catálogo conectado a la base de datos, panel de administración, pagos ni entrega digital.**

## Requisitos

- Python 3.12 recomendado para el primer despliegue.
- PostgreSQL 17.
- Variables de entorno configuradas en Alwaysdata.

## Desarrollo local

1. Crear y activar un entorno virtual.
2. Instalar dependencias: `python -m pip install -r requirements.txt`.
3. Definir `SECRET_KEY` y, cuando se integre la persistencia, `DATABASE_URL`.
4. Ejecutar en local con Flask en modo desarrollo.

No subir contraseñas, tokens de Mercado Pago, archivos `.env`, datos de clientes ni archivos digitales privados al repositorio.

## Alwaysdata

- Tipo de sitio: Python WSGI.
- Application path: `/home/elrincondidactico/wsgi.py`.
- Working directory: `/home/elrincondidactico/`.
- Virtualenv: `/home/elrincondidactico/venv/` (crear antes de configurarlo).
- No configurar rutas estáticas adicionales: Flask sirve por ahora `app/static/`.

Antes de usar la tienda en producción se deberán implementar y probar autenticación administrativa, modelos y migraciones de base de datos, protección de archivos digitales, confirmación de pagos del lado del servidor y copias de seguridad.

# LaTiburona

Aplicacion de escritorio en Python para gestionar reservas, confirmaciones, torneos y reportes de un servicio deportivo y recreativo en Barranquilla, Colombia.

## Arquitectura

```text
app/
|-- services/
|-- models/
|-- data/
`-- utils/

kivy_ui/
|-- main_app.py
|-- screens/
|-- components/
`-- kv/
```

La logica de negocio sigue viviendo en `app/services`. La nueva interfaz Kivy solo consume esos servicios y no duplica reglas de negocio.

## Requisitos

- Python 3.11 o superior
- `pip`

## Instalacion

```bash
py -3 -m pip install -r requirements.txt
```

## Ejecucion

```bash
py main.py
```

## Backend API local

```bash
py -3 -m uvicorn app.backend.main:app --host 0.0.0.0 --port 10000
```

Documentacion interactiva:

- `http://127.0.0.1:10000/docs`

## Funcionalidades incluidas

- Dashboard Kivy con KPIs, grafico de reservas por hora, insights y recomendaciones
- Registro, edicion, eliminacion y confirmacion de reservas
- Cotizacion inteligente con descuentos y recargos visibles
- Gestion de torneos con participantes y estado
- Exportacion de reservas a CSV y PDF
- Configuracion de tarifas, promociones, reglas de ingreso y sede
- Datos de ejemplo para demostracion
- Backend FastAPI listo para SaaS con JWT, refresh token, roles y PostgreSQL

## Notas

- La base `database.db` se inicializa y reutiliza automaticamente.
- Los archivos exportados se guardan dentro de `exports/`.
- En backend, `DATABASE_URL` usa PostgreSQL cuando esta configurada y cae a SQLite solo para desarrollo local.

## Backend SaaS

El backend ahora soporta:

- autenticacion JWT con `access_token` de 15 minutos
- `refresh_token` de 7 dias
- roles `admin`, `operator` y `client`
- aislamiento de datos por usuario
- PostgreSQL via `DATABASE_URL`

### Variables de entorno

- `DATABASE_URL`: cadena PostgreSQL para produccion o Render
- `LATIBURONA_SECRET_KEY`: clave obligatoria para firmar JWT
- `LATIBURONA_ADMIN_PASSWORD`: password inicial o de reseteo del admin
- `CORS_ORIGINS`: lista separada por comas o `*`
- `LATIBURONA_API_BASE_URL`: URL publica del backend para clientes Kivy

### Endpoints principales

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`
- `POST /auth/logout`
- `GET /analytics/overview`
- `GET /analytics/reservations-by-day`
- `GET /analytics/revenue-by-day`
- `GET /analytics/occupancy-by-court`
- `GET /analytics/peak-hours`
- `GET /analytics/status-breakdown`
- `GET /analytics/top-courts`
- `GET /analytics/weekly-summary`
- `GET /analytics/monthly-summary`
- `GET /dashboard/summary`
- `POST /payments/create`
- `POST /payments/webhook`
- `GET /payments/status/{reservation_id}`
- `POST /payments/refund`
- `POST /public/reserve`
- `GET /public/availability`
- `GET /public/reservation/{token}`
- `GET|POST|PUT|DELETE /reservas`
- `GET|POST|PUT|DELETE /torneos`

## Roadmap versionado

### v1.1 - Persistencia y analitica

Implementado de forma incremental sobre v1.0:

- `DATABASE_URL` sigue siendo la fuente para PostgreSQL en produccion y SQLite queda como fallback local.
- Inicializacion segura con `Base.metadata.create_all()` y migraciones aditivas; no se borran tablas ni datos.
- Nuevas tablas persistentes: `app_settings`, `promotions`, `audit_logs`.
- `canchas` agrega columnas aditivas `tipo`, `is_active`, `created_at`.
- Auditoria basica para crear, actualizar y cancelar reservas.
- Nuevos endpoints analiticos bajo `/analytics/*`.
- `GET /dashboard/summary` conserva compatibilidad y devuelve el resumen enriquecido.
- Dashboard y reportes Kivy consumen metricas enriquecidas cuando el backend remoto esta disponible.
- Exportacion PDF incluye indicadores diarios/semanales y estado confirmado/pendiente.

Notas de migracion:

- Las migraciones son aditivas y se ejecutan al iniciar el backend.
- Si `DATABASE_URL` no existe, se usa SQLite local en `server.db`.
- Para Render con PostgreSQL se requiere `psycopg[binary]`.
- Rollback recomendado: volver al commit anterior y conservar la base; las columnas/tablas nuevas no interfieren con v1.0.

### v1.2 - Pagos y reservas online

Implementado como base segura para Checkout Pro y reservas online:

- Nuevas tablas persistentes: `payment_transactions`, `reservation_public_links`, `reservation_expirations`.
- Estados de reserva soportados: `PENDING_PAYMENT`, `PARTIAL_PAYMENT`, `PAID`, `FAILED`, `CANCELLED`, `REFUNDED`, `EXPIRED`.
- `PaymentServiceAPI` crea preferencias server-side y nunca envia credenciales al cliente.
- `PAYMENT_PROVIDER=mercadopago` usa Checkout Pro; sin proveedor remoto se mantiene modo manual para QA local.
- Webhook idempotente actualiza transaccion y reserva; `approved` convierte la reserva a `PAID`.
- Reservas online: disponibilidad publica, reserva publica con token y vista publica de estado.
- Expiracion automatica libera reservas impagas al vencer `RESERVATION_PAYMENT_TIMEOUT_MINUTES`.
- Prevencion de doble reserva conserva validacion de solapes con buffer y bloquea reservas pendientes de pago.
- Analytics agrega pagos aprobados, pendientes, fallidos, conversion, ticket promedio, cancha mas rentable y horas pico de pago.
- Kivy muestra badges de pago, alertas financieras, checkout para cliente y cuenta regresiva de expiracion.

Variables de entorno:

- `MERCADOPAGO_PUBLIC_KEY`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_WEBHOOK_SECRET` opcional
- `PAYMENT_PROVIDER`
- `PAYMENT_MODE`
- `RESERVATION_PAYMENT_TIMEOUT_MINUTES`

Rollback previsto:

- Volver al commit anterior deja las tablas de pago sin uso y conserva reservas existentes.
- Las reservas con estados v1.2 pueden revertirse operacionalmente a `pendiente`, `confirmada` o `cancelada` si se requiere compatibilidad estricta con v1.1.

### v2.0 - Multi-sede, movil y tiempo real

Fase de arquitectura mayor, requiere rama separada:

- Modelar `organizations`, `locations`, canchas por sede y usuarios asignados por alcance.
- Roles previstos: `super_admin`, `org_admin`, `location_admin`, `operator`, `client`.
- Aislar datos por organizacion/sede antes de exponer selectores UI.
- Agregar capa de eventos y WebSocket para reservas, pagos, torneos y ocupacion en vivo.
- Preparar API movil con payloads livianos, refresh token robusto y revision CORS/seguridad.
- Documentar checklist Android/Buildozer antes de construir APK.

Rollback previsto:

- Introducir multi-sede con columnas nullable y feature flag.
- Mantener la sede actual como organizacion/sede por defecto.

## Despliegue en Render

El backend ya quedo preparado para Render con PostgreSQL usando [render.yaml](/C:/latiburona/render.yaml).

### Variables y base de datos

- `DATABASE_URL`: cadena PostgreSQL provista por Render
- `LATIBURONA_SECRET_KEY`: clave secreta obligatoria para JWT
- `LATIBURONA_ADMIN_PASSWORD`: password del admin inicial
- `CORS_ORIGINS`: lista separada por comas o `*`
- `LATIBURONA_API_BASE_URL`: URL publica del backend para los clientes Kivy

### Flujo recomendado

1. Sube el proyecto a GitHub con `app/`, `kivy_ui/`, `main.py`, `requirements.txt` y `render.yaml`.
2. En Render, crea un Blueprint o un Web Service conectado al repositorio.
3. Usa como build command: `pip install -r requirements.txt`
4. Usa como start command: `uvicorn app.backend.main:app --host 0.0.0.0 --port $PORT --workers 2`
5. Crea o vincula una base Render Postgres y conecta `DATABASE_URL`.
6. Verifica `https://tu-servicio.onrender.com/docs`

### Cliente Kivy

Para clientes Windows y Android, configura la variable de entorno `LATIBURONA_API_BASE_URL` con la URL publica del backend, por ejemplo:

```text
https://latiburona-1.onrender.com
```

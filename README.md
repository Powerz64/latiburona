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
- `GET /dashboard/summary`
- `GET|POST|PUT|DELETE /reservas`
- `GET|POST|PUT|DELETE /torneos`

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
https://latiburona-api.onrender.com
```

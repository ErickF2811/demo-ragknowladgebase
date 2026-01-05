# Vetflow: panel RAG + agenda veterinaria

Panel Flask con:
- Gestor de archivos: sube a Azure Blob (prefijo `file/...`), guarda metadatos en PostgreSQL, genera SAS y envía a n8n.
- Explorador de carpetas (reflejo de Blob): navegación por subcarpetas y drag & drop.
- Agenda: CRUD de citas con vista mensual y APIs para bots/servicios.
- Clientes: gestiona contactos (cedula/pasaporte), notas y citas asociadas (opcional).

## Archivos clave
- `app.py`: arranque de Flask (usa `vetflow.create_app()`).
- `vetflow/`: paquete con config, storage, db, servicios y blueprints (archivos, calendario, salud, UI).
- `templates/index.html`: UI Archivos/Calendario, explorador de carpetas, drag & drop.
- `templates/clientes.html`: UI para **Gestionar clientes** (contactos, notas y citas).
- `static/js/clientes.js`: frontend para crear/buscar/editar clientes.
- `vetflow/routes/clientes.py`: endpoints JSON multi-tenant de clientes.
- `vetflow/services/clientes.py`: lógica DB (clientes, notas, duplicados).
- `schema.sql`: schema core + schema por workspace (`files`, `appointments`, `clients`, `client_notes`).
- `.env.example`: variables requeridas.
- `requirements.txt`: dependencias.

## Variables de entorno
Copia `.env.example` a `.env` y ajusta:
```
AZURE_BLOB_CONN_STR=DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
AZURE_BLOB_CONTAINER=uploads
POSTGRES_DSN=postgresql://admin:admin123@localhost:5432/rag_panel
DB_SCHEMA=vetbot
CORE_SCHEMA=vetflow_core
WORKSPACE_SCHEMA_PREFIX=ws
DEFAULT_OWNER_EMAIL=demo@vetflow.local
DEFAULT_OWNER_NAME=Demo Vetflow
N8N_WEBHOOK_URL=https://tu-n8n/webhook/rag-files
N8N_DELETE_WEBHOOK_URL=https://tu-n8n/webhook/rag-files-deleted
N8N_NEW_WORKSPACE_WEBHOOK_URL=https://tu-n8n/webhook/newWorkpace
EVOLUTION_API_BASE_URL=http://localhost:8080
EVOLUTION_API_KEY=tu-api-key
EVOLUTION_API_INTEGRATION=WHATSAPP-BAILEYS
EVOLUTION_RABBITMQ_ENABLED=1
EVOLUTION_RABBITMQ_EVENTS=CHATS_SET,CHATS_UPDATE,CHATS_UPSERT,CONNECTION_UPDATE,MESSAGES_SET,MESSAGES_UPDATE,MESSAGES_UPSERT,PRESENCE_UPDATE,REMOVE_INSTANCE
API_HOST=0.0.0.0
API_PORT=5000
FLASK_SECRET_KEY=cambia-esta-clave
LOG_LEVEL=INFO
APP_TIMEZONE=UTC
```

## Instalar y correr
```bash
python -m venv .venv
.\.venv\Scripts\activate        # en Windows (o source .venv/bin/activate en Linux/Mac)
pip install -r requirements.txt
psql "POSTGRES_DSN" -f schema.sql   # crea schema vetbot y tablas
python app.py
```
Abre `http://localhost:5000`.

## Flujo de uso (UI)
- Archivos: explora carpetas como en Blob; navega con las filas de carpeta o `[ .. ]`. El drag & drop sube al folder actual. Miniaturas usan SAS temporal. “Enviar a bot” cambia de color según el `status`. El botón “Solicitar borrado” marca el archivo como `deleting` (badge naranja) y dispara el webhook de borrado.
- Calendario: crea/edita/elimina citas; vista mensual con eventos por día y modal de detalle.
- Gestionar clientes: crea/busca/edita clientes (identificación obligatoria), agrega notas y agenda citas; desde Calendario puedes asociar una cita a un cliente (opcional).

## API JSON
Fechas en ISO8601, ejemplo `2025-01-15T10:00:00Z`.

## Workspaces y multi-tenancy
- Tras actualizar el repositorio vuelve a ejecutar `psql "POSTGRES_DSN" -f schema.sql` para asegurarte de que el tipo `vetflow_core.appointment_status`, la función `ensure_workspace_schema` y las tablas globales existen. El script es idempotente.
- El schema `schema.sql` crea `vetflow_core`, las tablas (`app_users`, `workspaces`, `workspace_members`, `workspace_invites`) y la función `vetflow_core.ensure_workspace_schema(schema_name text)` que provisiona las tablas `files`/`appointments` dentro de un schema dedicado por workspace.
- Además, `ensure_workspace_schema` provisiona `clients` y `client_notes` y añade las columnas `appointments.timezone` y `appointments.client_id` (nullable) dentro de cada workspace.
- Cada workspace se asocia a un correo (idealmente Gmail) y genera un schema único `ws_<slug>_<hash>`. El backend invoca `ensure_workspace_schema` automáticamente al crear un workspace para garantizar que existan tablas y tipos.
- Las variables nuevas (`CORE_SCHEMA`, `WORKSPACE_SCHEMA_PREFIX`, `DEFAULT_OWNER_EMAIL`, `DEFAULT_OWNER_NAME`, `CLERK_PUBLISHABLE_KEY`) controlan dónde se guardan los metadatos, cómo se nombran los schemas y qué usuario se usa como fallback cuando la UI no envía cabeceras `X-User-Email` / `X-User-Name`. Al definir `CLERK_PUBLISHABLE_KEY`, el overlay de Clerk protege todo el panel y sincroniza la sesión mediante `POST /session/clerk` antes de mostrar los datos; además, se crea automáticamente un workspace por defecto para ese usuario.
- Desde el panel (ruta `/`) puedes seleccionar workspaces existentes, ver sus métricas (archivos/citas) y abrir un modal para crear más. La sesión recuerda el último workspace elegido y todas las operaciones (archivos, calendario, webhooks) se ejecutan dentro de ese schema. Si invocas la UI con `?email=tu_gmail` (o enviando la cabecera `X-User-Email`), Vetflow te mostrará únicamente los workspaces asociados a esa cuenta.
- Las APIs multi-tenant se consumen con prefijo de workspace: `/w/<schema_name>/api/...` (calendario, archivos, SAS), evitando colisiones de sesión entre workspaces. `schema_name` tiene forma `ws_<slug>_<hash>`.

### Diagrama de arquitectura (creación de workspace)
```mermaid
flowchart LR
    Clerk[Clerk + App Vite] -->|headers X-User-Email/X-User-Name| FlaskVetflow
    subgraph Backend
        FlaskVetflow[Flask Vetflow<br/>/ui + /api]
        Service[Servicio Workspaces]
    end
    FlaskVetflow -->|list/create| Service
    Service -->|DDL| CoreDB[(PostgreSQL<br/>vetflow_core)]
    Service -->|ensure_workspace_schema| WorkspaceDB[(PostgreSQL<br/>schema ws_x)]
    FlaskVetflow -->|CRUD archivos/citas| WorkspaceDB
    FlaskVetflow -->|blob SAS / uploads| Azure[(Azure Blob Storage)]
    FlaskVetflow -->|QR WhatsApp / instancia| Evolution[(Evolution API)]

    classDef infra fill:#f3f4ff,stroke:#7c3aed,color:#1c1233;
    classDef service fill:#fff7ed,stroke:#fb923c,color:#7c2d12;
    class Clerk infra
    class FlaskVetflow,Service service
    class CoreDB,WorkspaceDB infra
    class Azure,Evolution infra
```



### Modelo de datos (ERD)
Cada workspace tiene su propio schema en PostgreSQL (ej. `ws_<slug>_<hash>`). Dentro de ese schema existen las tablas de agenda, archivos y ahora también clientes:

```mermaid
erDiagram
    CLIENTS {
        int id PK
        string full_name
        string id_type
        string id_number
        string phone
        string email
        string address
        string notes
        timestamptz created_at
        timestamptz updated_at
    }

    CLIENT_NOTES {
        int id PK
        int client_id FK
        string body
        timestamptz created_at
    }

    APPOINTMENTS {
        int id PK
        string title
        string description
        timestamptz start_time
        timestamptz end_time
        string timezone
        string status
        int client_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    CLIENTS ||--o{ CLIENT_NOTES : "tiene"
    CLIENTS o|--o{ APPOINTMENTS : "opcional"
```

### Calendario (citas)
- Listar: `GET /w/<schema_name>/api/calendar`
- Obtener una: `GET /w/<schema_name>/api/calendar/<id>`
- Crear: `POST /w/<schema_name>/api/calendar`
  - Opcional: `client_id` para asociar la cita a un cliente (si se omite o es `null`, queda sin cliente).
  En PowerShell:
  ```powershell
  $payload = @{
    title = "Vacuna gato"
    description = "Refuerzo anual"
    start_time = "2025-01-15T10:00:00Z"
    end_time = "2025-01-15T10:30:00Z"
    client_id = 1  # opcional
  } | ConvertTo-Json -Compress

  Invoke-RestMethod -Method Post `
    -Uri "http://localhost:5000/w/demo-vetflow/api/calendar" `
    -Body $payload `
    -ContentType "application/json"
  ```
- Actualizar parcial: `PUT /w/<schema_name>/api/calendar/<id>`
  En PowerShell (comillas escapadas):
  ```powershell
  $payload = @{
    title = "Vacuna gato (ajustada)"
    end_time = "2025-01-15T10:45:00Z"
    client_id = $null  # opcional: quitar asociacion
  } | ConvertTo-Json -Compress

  Invoke-RestMethod -Method Put `
    -Uri "http://localhost:5000/w/demo-vetflow/api/calendar/1" `
    -Body $payload `
    -ContentType "application/json"
  ```
- Eliminar: `DELETE /w/<schema_name>/api/calendar/<id>`

### Clientes (CRM)
- Los clientes viven en la tabla `clients` dentro del schema del workspace.
- Identificación obligatoria:
  - `id_type`: `cedula` o `pasaporte`
  - `id_number`: número/documento
- Duplicados: si intentas crear/editar un cliente con la misma identificación, la API responde `409` con:
  - `{ "error": "cliente_ya_existe", "existing_client_id": <id> }`

**Endpoints (multi-tenant)**
- Listar/buscar: `GET /w/<schema_name>/api/clientes?q=<texto>&limit=200`
- Crear: `POST /w/<schema_name>/api/clientes`
- Obtener: `GET /w/<schema_name>/api/clientes/<client_id>`
- Actualizar: `PUT /w/<schema_name>/api/clientes/<client_id>`
- Agregar nota: `POST /w/<schema_name>/api/clientes/<client_id>/notas`
- Crear cita asociada: `POST /w/<schema_name>/api/clientes/<client_id>/citas` (crea en `appointments` con `client_id`)

**UI**
- Nueva pestaña **Gestionar clientes**: CRUD, notas y citas por cliente.
- En el modal de crear/editar cita del **Calendario** existe el selector **Cliente (opcional)** que guarda `appointments.client_id`.

### UI Calendario (FullCalendar)
- La pestaña **Calendario** usa FullCalendar (vista principal) conectado a los endpoints multi-tenant `/w/<schema_name>/api/calendar`.
- Vista por defecto: semanal (`timeGridWeek`), con scroll vertical habilitado y centrado alrededor de la hora actual.
- Crear/editar: FullCalendar reutiliza los mismos modales/formularios ("cartillas") del panel (`Nueva cita` y editar desde la lista o el evento), incluyendo selector de **Cliente (opcional)**.
- Acciones soportadas:
  - Seleccionar rango en el calendario: abre el modal de creación.
  - Click en evento: abre el modal de edición existente.
  - Drag & drop / resize: actualiza la cita (respeta estados bloqueados como `cancelada`, `completada`, `no_show`).
- Archivos clave:
  - UI: `templates/partials/calendar_tab.html`
  - FullCalendar glue: `static/js/fullcalendar.js`
  - Modales + lógica de citas: `static/js/calendar.js`

### Zona horaria (horas consistentes UI/DB)
- `appointments.start_time/end_time` son `timestamptz`; Postgres guarda el instante y lo muestra según el timezone de la sesión.
- Configura `APP_TIMEZONE` (ej. `America/Bogota`) para que la API devuelva/consuma horas consistentes en ese timezone.
- El frontend envía fechas con offset local para evitar desfaces al guardar/editar.
- Nota: al editar una cita y cambiar solo el `status`, el modal envía solo los campos modificados para evitar que `start_time/end_time` se recalculen y “salten” de hora.
- El backend acepta el header `X-Timezone` (p. ej. `America/Bogota`) para fijar el `TimeZone` de la sesión Postgres por request, evitando saltos al refrescar tras cambios (status/drag/resize).
- Nota UI: los inputs `datetime-local` del modal de creación/edición usan formato local `YYYY-MM-DDTHH:MM`; el panel convierte internamente a ISO con offset para persistir correctamente.

### Archivos
- Eliminar: `DELETE /api/files/<id>` (marca `status=deleting`, notifica `N8N_DELETE_WEBHOOK_URL`; n8n debe borrar y actualizar el estado a `deleted/expired` vía `PUT /api/files/<id>`).
- Actualizar metadatos/status (para n8n o bots): `PUT /api/files/<id>`
  En PowerShell:
  ```powershell
  $payload = @{
    status = "processed"
    tags = @("felino","rx")
    notes = "procesado por bot"
    processed_at = "2025-01-16T12:00:00Z"
  } | ConvertTo-Json -Compress

  Invoke-RestMethod -Method Put `
    -Uri "http://localhost:5000/api/files/1" `
    -Body $payload `
    -ContentType "application/json"
  ```
  Respuesta: JSON con el registro actualizado.

## Integración RAG/n8n
- Configura `N8N_WEBHOOK_URL` (ingesta/procesamiento) y `N8N_DELETE_WEBHOOK_URL` (borrado).
- (Opcional) `N8N_NEW_WORKSPACE_WEBHOOK_URL`: se llama al crear un workspace para que n8n haga aprovisionamiento externo.
  - Si usas n8n en **modo test** (`/webhook-test/...`), el webhook solo responde cuando el workflow está en **Listening for test event** y la URL suele incluir un identificador; si no, verás `404 ... webhook is not registered`.
  - Para producción usa `/webhook/...` con el workflow **activo** (Activated) para que siempre reciba eventos.
- **Cuándo se llama a n8n**
  - **Al subir un archivo** (`POST /upload`): se crea el registro con `status=uploaded` y luego se intenta notificar a n8n con `N8N_WEBHOOK_URL` (best-effort).
  - **Al pulsar "Enviar al bot"** (UI): llama explícitamente a `N8N_WEBHOOK_URL`; si n8n responde `2xx` el panel actualiza el registro a `status=processing`.
  - **Al solicitar borrado** (`POST /files/<id>/delete` o `DELETE /api/files/<id>`): primero marca el registro como `status=deleting` y luego intenta notificar a n8n con `N8N_DELETE_WEBHOOK_URL`.
- **Qué se envía (payload JSON)**
  - Ingesta/proceso: `file_id`, `filename`, `blob_path`, `blob_url`, `folder`, `tags`, `notes`, `status`, `schema`.
  - Borrado: `file_id`, `filename`, `blob_path`, `blob_url`, `container`, `schema`.
  - `schema` es el schema del workspace actual (multi-tenancy); n8n debe devolverlo/usar ese contexto si interactúa con la API del panel.
- **Qué pasa si el webhook falla**
  - Subida (`notify_ingest_webhook`): si el `POST` a n8n falla (timeout/connection/error), **no rompe la subida**; se loguea un warning y el archivo queda en `uploaded`.
  - Enviar al bot (acción explícita): si n8n responde no-`2xx` o hay excepción, la UI muestra error y **no** cambia el `status` a `processing`.
  - Borrado: el panel **siempre** marca `status=deleting` y luego intenta el webhook; si falla, el registro queda como `deleting` y puedes reintentar desde la UI. La API responde `202` indicando "pendiente de webhook n8n".
- **Nota sobre `webhook-test`**
  - Si usas URLs tipo `/webhook-test/...` y n8n responde `404`, el backend intenta automáticamente la variante de producción `/webhook/...` (y añade un mensaje de ayuda en la respuesta/UI).
- **Callback desde n8n al panel**
  - Tras procesar o borrar, n8n debe llamar `PUT /api/files/<id>` para actualizar `status`, `tags`, `notes`, `processed_at` (por ejemplo `processed`, `done`, `deleted`, `expired`).
  - Para descargar el blob, n8n puede usar `blob_path` + una SAS generada por el panel (`GET /file/<id>/sas` o `/w/<schema_name>/file/<id>/sas`).

## Integración WhatsApp (Evolution API)
- Variables:
  - `EVOLUTION_API_BASE_URL`: URL base de Evolution (sin trailing `/`), ejemplo `http://localhost:8080`
  - `EVOLUTION_API_KEY`: API key (header `apikey`)
  - `EVOLUTION_API_INTEGRATION` (opcional): por defecto `WHATSAPP-BAILEYS`
  - `EVOLUTION_RABBITMQ_ENABLED` (opcional): por defecto `1` (habilita RabbitMQ en la creación de instancias)
  - `EVOLUTION_RABBITMQ_EVENTS` (opcional): eventos RabbitMQ (coma-separados). Default:
    - `CHATS_SET, CHATS_UPDATE, CHATS_UPSERT, CONNECTION_UPDATE, MESSAGES_SET, MESSAGES_UPDATE, MESSAGES_UPSERT, PRESENCE_UPDATE, REMOVE_INSTANCE`
- RabbitMQ:
  - La configuración de RabbitMQ se envía dentro de `POST /instance/create` (Evolution) al generar QR.
  - La UI no configura eventos RabbitMQ; se controla con variables de entorno.
- Webhooks WhatsApp:
  - Se removió la configuración automática de webhook (n8n) para WhatsApp; los eventos se consumen vía RabbitMQ.
- UI (pestaña **Integración WhatsApp**):
  - La instancia de Evolution se nombra con el `schema_name` del workspace (ej. `ws_<slug>_<hash>`), para que sea única y coincida con el nombre del schema en PostgreSQL.
  - La UI **solo** consulta estado con `GET /status` (no hace `connect` automático). Se ejecuta 1 vez al abrir la pestaña y cuando pulsas **Actualizar estado**.
  - Si el estado es `open` (o `connected=true`), se oculta el panel de QR y se muestra **Conexión activa** con detalles.
  - Si no está conectado, se muestra el panel de QR (oculto por defecto) y el botón **Generar QR**.
  - Al generar QR se muestra un spinner mientras llega la respuesta.
  - **Cerrar sesión WhatsApp** (modal): solo desconecta cuando el usuario confirma la acción (no se desconecta por recargar/salir del panel).
- Endpoints:
  - `GET /w/<schema_name>/api/whatsapp/status`: valida estado de la instancia (usa endpoints de estado, no llama a `connect` para evitar regenerar QR/alterar sesión). Responde `connected`, `state`, `details`.
  - `GET /w/<schema_name>/api/whatsapp/qr`: asegura instancia + pide QR. Antes de generar, la UI valida estado; si ya está conectado no genera un QR nuevo.
  - `POST /w/<schema_name>/api/whatsapp/logout`: cierra sesión/desconecta la instancia **solo** cuando el usuario pulsa el botón "Cerrar sesión WhatsApp".
- Archivos clave:
  - Backend: `vetflow/services/evolution.py`, `vetflow/routes/whatsapp.py`, `vetflow/config.py`
  - UI/JS: `templates/partials/whatsapp_tab.html`, `static/js/whatsapp.js`
- Logs:
  - `vetflow/services/evolution.py`: logs `INFO/WARNING` para `create_instance`, `connect_qr`, `get_instance_status` (instance, code, state, detalles resumidos).
  - `vetflow/routes/whatsapp.py`: logs `INFO/DEBUG` por request (slug, instance, IP/User-Agent) y resultado (connected/state) para depuración.

### Flujo de integración

```mermaid
sequenceDiagram
    participant User as Usuario
    participant UI as Frontend (JS)
    participant Backend as Flask
    participant Evo as Evolution API
    participant WA as WhatsApp (Móvil)

    User->>UI: Clic "Generar QR"
    UI->>Backend: GET /w/slug/api/whatsapp/qr
    Backend->>Evo: instance/connectionState (Check if connected)
    alt Ya conectado
        Evo-->>Backend: connected: true
        Backend-->>UI: 409 Conflict (Ya conectado)
        UI-->>User: Muestra "Conexión activa"
    else No conectado
        Backend->>Evo: instance/create (Crea instancia)
        Backend->>Evo: instance/connect (Solicita QR)
        Evo-->>Backend: QR Base64
        Backend-->>UI: QR Image
        UI-->>User: Muestra QR
        User->>WA: Escanea QR
        
        Note over UI: La UI no hace polling.\nSolo refresca el estado con GET\n(al abrir la pestaña o con “Actualizar estado”).
    end
```

## Notas
- El contenedor de Blob se crea en caliente si no existe.
- Para SAS se requieren `AccountName` y `AccountKey` en la cadena de conexión.
- Servir siempre vía Flask; abrir el HTML directo mostrará llaves Jinja.
## Frontend Clerk (Vite + ClerkJS)
El subdirectorio `clerk-javascript/` contiene una app Vite (Vanilla JS) que monta el flujo de autenticación de Clerk. Puedes seguir usándola como demo independiente (mantiene el `<iframe>`), pero el panel Flask ya incorpora Clerk de forma nativa mediante `@clerk/clerk-js`, por lo que basta con definir `CLERK_PUBLISHABLE_KEY` en tu `.env` y abrir `http://localhost:5000`.

### Producción: evitar “No se pudo cargar Clerk… dominio no autorizado”
Ese mensaje aparece cuando el **origin** desde donde abres el panel (por ejemplo `https://panel.tudominio.com` o `http://IP:5000`) **no está permitido** por tu instancia de Clerk, o cuando usas una key que no corresponde al ambiente.

Checklist:
1. En Clerk Dashboard selecciona el ambiente **Production** y copia la `CLERK_PUBLISHABLE_KEY` `pk_live_...` (no uses `pk_test_...` en prod).
2. En Clerk Dashboard ve a **Configure → Domains** (o “Domains & URLs”) y agrega el dominio/origin exacto desde el que sirves el panel:
   - Si usas dominio: `https://panel.tudominio.com`
   - Si pruebas con IP/puerto: `http://<tu-ip>:5000` (mejor usar dominio + HTTPS en producción)
3. Asegura que el panel se sirva por el mismo origin que registraste (ideal: HTTPS detrás de Nginx/Traefik/Cloudflare).
4. Si también usas el frontend Vite (`clerk-javascript/`), registra adicionalmente su origin (ej. `http://localhost:5173`) y revisa que `VITE_PANEL_URL` apunte al URL público correcto del panel.

### Producción: `ERR_NAME_NOT_RESOLVED` (clerk.<tu-dominio> no resuelve)
Si en la consola ves errores como:
- `GET https://clerk.<tu-dominio>/v1/environment ... net::ERR_NAME_NOT_RESOLVED`
- `GET https://clerk.<tu-dominio>/v1/client ... net::ERR_NAME_NOT_RESOLVED`

No es un error de tu app: significa que **DNS no puede resolver** `clerk.<tu-dominio>` (el subdominio no existe o no está apuntando).

Cómo solucionarlo:
1. En Clerk Dashboard (ambiente **Production**) ve a **Domains** y revisa tu **Custom domain**.
2. Crea en tu proveedor DNS (Hostinger/Cloudflare/etc.) el/los registros que Clerk te indica (normalmente un **CNAME** para `clerk` apuntando al target de Clerk).
3. Espera la propagación y valida con `nslookup clerk.<tu-dominio>` (o `dig`) hasta que resuelva.
4. Alternativa: si no necesitas custom domain, usa el dominio por defecto que muestra Clerk en **Frontend API URL** (y mantén `CLERK_PUBLISHABLE_KEY=pk_live_...` en prod).

### Configuración y prueba
```bash
cd clerk-javascript
cat <<'EOF' > .env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_cXJrLmFjY291bnRzLmRldiQ
VITE_PANEL_URL=http://localhost:5000
EOF
npm install
npm run dev
```
1. Arranca también el backend Flask (`python app.py`) para que el iframe tenga contenido.
2. Abre `http://localhost:5173`.
3. Clerk renderiza el formulario de inicio de sesión. Tras autenticarse, aparece el encabezado con `<UserButton />` y debajo el panel servido por Flask. Al cerrar sesión se vuelve al formulario.

### Archivos clave
- `clerk-javascript/src/main.js`: inicializa `Clerk`, escucha cambios de sesión y monta el iframe hacia `VITE_PANEL_URL` cuando `clerk.isSignedIn` es `true`.
- `clerk-javascript/src/style.css`: estilos del shell de autenticación/iframe.
- `clerk-javascript/index.html`: entry point que carga `src/main.js`.

### Otros comandos
- `npm run build`: genera `dist/` estático con los assets listos para despliegue.
- `npm run preview`: sirve `dist/` localmente para validación final.

> Cambia la publishable key y la URL del panel según ambiente usando `.env`, `.env.local` o variables de sistema; reinicia `npm run dev` al actualizar valores.

## Actualizaciones recientes de UI/UX y Calendario (Diciembre 2025)

### Calendario y Agenda
- **Indicador de hora actual (Línea Roja):**
  - Implementación robusta con reinserción automática en el DOM.
  - Estilo plano con punto rojo ("flat red dot") alineado al inicio de la columna, similar a Google Calendar.
  - Posicionamiento preciso sobre el ancho total de la columna, ignorando gutters para mejor visibilidad (`z-index: 50`).
- **Alineación y Layout:**
  - Corrección de la cabecera del calendario: alineación horizontal (row) de número y mes ("9 DIC"), eliminando desbordamientos verticales.
  - Ajuste óptico de etiquetas: reducción de gap y alineación de línea base entre número y mes.
  - Solución a desalineación al recargar página: forzado de barra de desplazamiento vertical (`overflow-y: scroll`) para garantizar cálculos de ancho (clientWidth) consistentes.
  - Prevención de desbordamiento horizontal en vista mensual mediante ajuste de `minmax(0, 1fr)` en CSS Grid.
- **Interacciones en Tiempo Real:**
  - Visualización dinámica de la hora de inicio y fin mientras se arrastra o redimensiona una cita (ej. "14:27-16:27").
- **Limpieza visual:**
  - Eliminación de títulos redundantes ("Calendario", "Diciembre de 2025" duplicado) en la barra de herramientas.

### UI/UX General
- **Persistencia de estado:** La pestaña activa (Archivos vs Calendario) se guarda en `localStorage` para mantenerse tras recargas.
- **Menú Lateral (Hamburger):** Lógica de toggle corregida para móviles.
- **Estilos:**
  - Aplicación de Glassmorphism mejorado en el logo y tarjetas.
  - Ajustes de tipografía y espaciado para una apariencia más compacta y moderna.
  - Responsividad mejorada: ocultación de columnas menos relevantes en tablas (mobile) y adaptación de anchos de columna en calendario según dispositivo.

## Docker & Despliegue

### Construcción y Ejecución Local
El proyecto incluye configuración completa para Docker (`Dockerfile` y `docker-compose.yml`).

1. **Requisitos previos**:
   - Tener Docker y Docker Compose instalados.
   - Tener el archivo `.env` configurado en la raíz con las credenciales (Azure, Postgres, etc.).

2. **Levantar servicios (App + DB)**:
   ```bash
   docker-compose up --build
   ```
   - Esto levantará la app en `http://localhost:5000`.
   - Postgres estará disponible en el puerto `5433` (para no chocar con instalaciones locales).
   - La base de datos se inicializa automáticamente con `schema.sql` en el primer arranque.

### Construir y Publicar Imagen (Push)

Para llevar la imagen a un registro (ej. Docker Hub, Azure CR, AWS ECR):

1. **Construir la imagen**:
   ```bash
   # Sintaxis: docker build -t <usuario>/<nombre-imagen>:<tag> .
   docker build -t erifcamp/flow-panel:v1.0.0 .
   ```

2. **Login en el registro**:
   ```bash
   docker login
   ```

3. **Subir la imagen (Push)**:
   ```bash
   docker push erifcamp/flow-panel:latest
   ```

### Variables de Entorno en Docker
Al usar `docker-compose`, las variables se leen automáticamente del archivo `.env`.
Si despliegas solo la imagen (`docker run`), debes pasar las variables manualmente o usar un archivo env:

```bash
docker run -p 5000:5000 --env-file .env miusuario/vetflow-panel:latest
```

### Actualizaciones Diciembre 2025 (Semana 2) - Timezones y Funcionalidad

#### 1. Gestión de Zona Horaria (Timezone)
- **Problema Solucionado:** Las citas se guardaban con la hora "ingenua" o UTC incorrecta, y al visualizarlas se aplicaba un doble desplazamiento horario o se mostraban incorrectamente (ej. citas de las 11:00 aparecían a las 06:00).
- **Implementación:**
  - **Detección Automática:** El frontend (`calendar.js`) detecta automáticamente la zona horaria del navegador (ej. `America/Bogota`) usando `Intl.DateTimeFormat().resolvedOptions().timeZone`.
  - **Envío Explícito:** Al crear o editar una cita, se envía tanto la hora local formateada correctamente (ISO 8601 con offset) como el nombre de la zona horaria.
  - **Persistencia:** Se añadió una columna `timezone` a la tabla `appointments`.
  - **Visualización:** El listado de citas ahora muestra el indicador de zona horaria si está disponible, confirmando al usuario en qué huso horario se registró el evento.

#### 2. Mejora en Eliminación de Citas
- **UX Mejorado:** Se eliminó el uso de formularios tradicionales (`<form>`) para el botón de borrar en las tarjetas individuales. Ahora usa llamadas `fetch` con método `DELETE`, permitiendo una experiencia más fluida sin recargas completas de página.
- **Soporte Multi-Web/Workspace:** Se corrigió la lógica de rutas en el botón de eliminación para respetar el contexto del workspace actual (`/w/<schema_name>/...`), asegurando que la acción se ejecute en el entorno correcto.
- **Acceso Global:** Se expuso la función `deleteEvent` globalmente para permitir su uso seguro desde manejadores `onclick` en el HTML dinámico.

#### 3. Estabilidad Visual
- **Prevención de "Flicker":** Se implementó una clase de utilidad (`opacity-0` + `transition`) para ocultar las horas en formato UTC crudo hasta que el JavaScript las hidrata exitosamente a la hora local del usuario, evitando destellos de información incorrecta.

# Vetflow API (panel RAG + agenda + CRM)

Guia rapida de todas las APIs del panel Flask. Todas aceptan `Content-Type: application/json` salvo que se indique `multipart/form-data`. Formatos de fecha: ISO8601 (`2025-01-15T10:45:00Z`). Puedes enviar `X-Timezone: America/Bogota` para fijar la zona horaria en Postgres.

## Convenciones
- Base URL local: `http://localhost:5000`
- Multi-tenant: prefijo `/w/<schema_name>/api/...` (schema tipo `ws_<slug>_<hash>`). Sin prefijo usa el workspace por defecto (`DB_SCHEMA`).
- Auth:
  - JWT (Clerk o mobile): header `Authorization: Bearer <token>`
  - API key (bots/n8n): header `X-API-Key: <VETFLOW_API_KEY>`
  - Sin auth solo si `CLERK_AUTH_REQUIRED=0`

## Salud y sesion
- `GET /health` -> `{ "status": "ok" }`
- `POST /session/clerk` (`Authorization: Bearer <JWT>`, body opcional `{ "role": "<label>" }`) crea sesion en cookie.
- `DELETE /session/clerk` limpia sesion.

## Workspaces, invitaciones y miembros
- `GET /api/workspaces` (o `/w/<schema>/api/workspaces`): lista workspaces accesibles con stats (`files_count`, `appointments_count`).
- `GET /w/<schema>/api/workspace`: detalles del workspace actual.
- `POST /w/<schema>/api/invites` body `{ "email": "user@example.com", "role": "member|admin", "expires_in_days": 7 }`
- `POST /api/invites/accept` body `{ "code": "<invite_code>", "email": "...", "name": "..." }`
- `POST /w/<schema>/api/members/remove` body `{ "email": "target@example.com" }` (solo owner).
- Formularios UI (no JSON):
  - Crear workspace: `POST /workspaces` campos `workspace_name`, `owner_email`, `owner_name`, `workspace_description`, `workspace_slug` opcional, `theme_color`, `workspace_icon` opcional.
  - Actualizar workspace: `POST /workspaces/<id>/update` (owner).
  - Eliminar workspace: `POST /workspaces/<id>/delete` (owner, requiere frase `eliminar esta area trabajo`).

## Calendario (citas)
Campos: `title` (req), `start_time`, `end_time`, `description`, `status` (`programada|confirmada|completada|cancelada|no_show`), `timezone` (IANA, opcional), `client_id` (opcional).

- `GET /api/calendar/<id>` o `/w/<schema>/api/calendar/<id>`: detalle.
- `POST /api/calendar` o `/w/<schema>/api/calendar`: crear cita.
- `PUT /api/calendar/<id>` o `/w/<schema>/api/calendar/<id>`: update parcial (solo campos enviados).

Body permitido (POST/PUT):
- `title` (string, requerido en POST)
- `description` (string o null)
- `start_time` (ISO8601)
- `end_time` (ISO8601)
- `status` (enum: `programada|confirmada|completada|cancelada|no_show`)
- `timezone` (string IANA, opcional)
- `client_id` (int o null para desasociar)
Ejemplo PowerShell (update):
```powershell
$payload = @{
  title = "Vacuna gato (ajustada)"
  end_time = "2025-01-15T10:45:00Z"
  client_id = $null  # opcional: quitar asociacion
} | ConvertTo-Json -Compress
$headers = @{ "X-API-Key" = "supersecretkey" }
Invoke-RestMethod -Method Put `
  -Uri "http://localhost:5000/w/ws_erick_david_flores_campana_e68c/api/calendar/17" `
  -Headers $headers -Body $payload -ContentType "application/json"
```

## Clientes (CRM)
Identificacion obligatoria: `id_type` (`cedula` o `pasaporte`) + `id_number`. Opcionales: `phone`, `email`, `address`, `notes`, `blacklisted` (bool).
- `GET /w/<schema>/api/clientes?q=<texto>&limit=200` lista/busca.
- `POST /w/<schema>/api/clientes` crea cliente.
- `GET /w/<schema>/api/clientes/<id>` detalle (incluye `notes` y `appointments` si existen).
- `PUT /w/<schema>/api/clientes/<id>` update parcial (error 409 si duplica identificacion).
- `DELETE /w/<schema>/api/clientes/<id>` borra cliente y deja citas con `client_id=NULL`.
- `POST /w/<schema>/api/clientes/<id>/notas` body `{ "body": "texto" }`
- `POST /w/<schema>/api/clientes/<id>/citas` body `{ "title": "...", "start_time": "...", "end_time": "...", "status": "programada", "timezone": "America/Bogota" }`

## Archivos
Estados listados: `uploaded`, `processing`, `active/processed/done/activo`, `deleting/eliminando`, `expired/expirada` (ocultos salvo `include_expired=1`). Estados duros (`deleted`, `eliminado`, `eliminar`) no se muestran.
- `GET /api/files?include_expired=0|1` (o `/w/<schema>/api/files`): lista.
- `POST /upload` (`multipart/form-data`) con `file`[]; opcional `tags` (CSV), `notes`. Crea registro, sube a Blob, deja `status=uploaded` y lanza webhook `N8N_WEBHOOK_URL` (best-effort).
- `GET /file/<id>/sas` (o `/w/<schema>/file/<id>/sas`): `{ "url": "<sas>" }` para descarga segura.
- `PUT /api/files/<id>` (o `/w/<schema>/api/files/<id>`): body parcial con `tags` (lista), `notes`, `status`, `processed_at` (ISO). Devuelve registro actualizado.
- `DELETE /api/files/<id>` (o `/w/<schema>/api/files/<id>`): marca `status=deleting`, retorna 202 y notifica `N8N_DELETE_WEBHOOK_URL` (tiene fallback `/webhook/` si la URL de test da 404).
- `POST /files/<id>/send-to-n8n` (form/UI): reenvia a `N8N_WEBHOOK_URL` y pone `processing` si responde 2xx.

## WhatsApp (Evolution API)
- `GET /w/<schema>/api/whatsapp/status`: estado de instancia (no llama connect).
- `GET /w/<schema>/api/whatsapp/qr`: asegura instancia y devuelve QR base64/data URL; si ya esta conectada -> 409.
- `POST /w/<schema>/api/whatsapp/logout`: cierra sesion.
La instancia se nombra con el `schema_name` del workspace para ser unica por tenant.

## Webhooks n8n / RAG
- Ingesta/proceso (`N8N_WEBHOOK_URL`): payload `{ file_id, filename, blob_path, blob_url, folder, tags, notes, status, schema }`.
- Borrado (`N8N_DELETE_WEBHOOK_URL`): payload `{ file_id, filename, blob_path, blob_url, container, schema }`.
- Calendario (`N8N_CALENDAR_WEBHOOK_URL`): payload `{ event, appointment, workspace, changes, source }`, header opcional `Authorization` configurado en `N8N_CALENDAR_WEBHOOK_AUTH`.
- Callback desde n8n al panel: `PUT /w/<schema>/api/files/<id>` para actualizar `status/tags/notes/processed_at` o `GET /w/<schema>/file/<id>/sas` para descargar. Usa siempre el `schema` recibido para operar en el tenant correcto.

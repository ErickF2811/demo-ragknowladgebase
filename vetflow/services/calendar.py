import base64
import logging
from typing import Any, Dict, List, Optional

import requests
from psycopg import errors

from ..config import config
from ..db import get_db
from ..serializers import row_to_appointment_api
from ..utils import parse_datetime

logger = logging.getLogger(__name__)

STATUS_CHOICES: List[Dict[str, str]] = [
    {"value": "programada", "label": "Programada"},
    {"value": "confirmada", "label": "Confirmada"},
    {"value": "completada", "label": "Completada"},
    {"value": "cancelada", "label": "Cancelada"},
    {"value": "no_show", "label": "No asistio"},
]
STATUS_LABELS = {choice["value"]: choice["label"] for choice in STATUS_CHOICES}
DEFAULT_STATUS = "programada"


def _calendar_webhook_url() -> str:
    return (getattr(config, "N8N_CALENDAR_WEBHOOK_URL", "") or "").strip()


def _calendar_webhook_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    raw_auth = (getattr(config, "N8N_CALENDAR_WEBHOOK_AUTH", "") or "").strip()
    if not raw_auth:
        return headers
    if raw_auth.lower().startswith("basic "):
        headers["Authorization"] = raw_auth
        return headers
    if ":" in raw_auth:
        token = base64.b64encode(raw_auth.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
        return headers
    headers["Authorization"] = raw_auth
    return headers


def _workspace_payload(workspace: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not workspace:
        return None
    return {
        "id": workspace.get("id"),
        "slug": workspace.get("slug"),
        "schema_name": workspace.get("schema_name"),
        "name": workspace.get("name"),
    }


def notify_calendar_webhook(
    event: str,
    appointment: Optional[Dict[str, Any]],
    workspace: Optional[Dict[str, Any]] = None,
    changes: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
) -> None:
    webhook_url = _calendar_webhook_url()
    if not webhook_url:
        return
    payload = {
        "event": event,
        "appointment": appointment,
        "workspace": _workspace_payload(workspace),
        "changes": changes or {},
        "source": source,
    }
    headers = _calendar_webhook_headers()
    used_url = webhook_url
    try:
        res = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        if res.status_code == 404 and "/webhook-test/" in webhook_url:
            alt_url = webhook_url.replace("/webhook-test/", "/webhook/")
            logger.info("Webhook calendario test 404, intentando URL de produccion %s", alt_url)
            res_alt = requests.post(alt_url, json=payload, headers=headers, timeout=10)
            used_url = alt_url
            if 200 <= res_alt.status_code < 300:
                logger.info("Webhook calendario OK code=%s url=%s", res_alt.status_code, alt_url)
            else:
                logger.warning(
                    "Webhook calendario FAIL code=%s url=%s body=%s",
                    res_alt.status_code,
                    alt_url,
                    (res_alt.text or "").strip()[:300],
                )
            return
        if 200 <= res.status_code < 300:
            logger.info("Webhook calendario OK code=%s url=%s", res.status_code, used_url)
        else:
            logger.warning(
                "Webhook calendario FAIL code=%s url=%s body=%s",
                res.status_code,
                used_url,
                (res.text or "").strip()[:300],
            )
    except Exception as ex:
        logger.warning("No se pudo notificar N8N_CALENDAR_WEBHOOK_URL=%s: %s", webhook_url, ex)


def _ensure_timezone_column(conn) -> None:
    """
    Migracion idempotente: en instalaciones antiguas `appointments` no tenia `timezone`.
    """
    try:
        conn.execute("ALTER TABLE IF EXISTS appointments ADD COLUMN IF NOT EXISTS timezone TEXT")
    except Exception:
        pass


def _ensure_client_id_column(conn) -> None:
    """
    Migracion idempotente: soporte para asociar citas a un cliente.
    """
    try:
        conn.execute("ALTER TABLE IF EXISTS appointments ADD COLUMN IF NOT EXISTS client_id INTEGER")
    except Exception:
        pass


def get_status_choices() -> List[Dict[str, str]]:
    return STATUS_CHOICES


def normalize_status(raw: Optional[str]) -> str:
    if not raw:
        return DEFAULT_STATUS
    value = str(raw).strip().lower()
    if value not in STATUS_LABELS:
        raise ValueError(f"Estado invalido: {raw}")
    return value


def list_appointments() -> List[Dict[str, Any]]:
    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        rows = conn.execute("SELECT * FROM appointments ORDER BY start_time DESC").fetchall()
    return [row_to_appointment_api(r) for r in rows]


def list_upcoming_appointments() -> List[Dict[str, Any]]:
    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        rows = conn.execute(
            "SELECT * FROM appointments WHERE GREATEST(start_time, end_time) >= NOW() ORDER BY start_time ASC"
        ).fetchall()
    return [row_to_appointment_api(r) for r in rows]


def create_appointment(
    title: str,
    description: str,
    start_raw: str,
    end_raw: str,
    status_raw: Optional[str] = None,
    timezone: Optional[str] = None,
    client_id: Optional[int] = None,
):
    start_time = parse_datetime(start_raw)
    end_time = parse_datetime(end_raw)
    status = normalize_status(status_raw)
    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        try:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status, timezone, client_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                """,
                (title, description, start_time, end_time, status, timezone, client_id),
            ).fetchone()
        except errors.UndefinedColumn:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                (title, description, start_time, end_time, status),
            ).fetchone()
    return row_to_appointment_api(row)


def update_appointment(
    appointment_id: int,
    title: str,
    description: str,
    start_raw: str,
    end_raw: str,
    status_raw: Optional[str] = None,
    timezone: Optional[str] = None,
    client_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    start_time = parse_datetime(start_raw)
    end_time = parse_datetime(end_raw)
    status = normalize_status(status_raw)
    fields = ["title=%s", "description=%s", "start_time=%s", "end_time=%s", "status=%s", "updated_at=NOW()"]
    values: List[Any] = [title, description, start_time, end_time, status]
    if timezone:
        fields.append("timezone=%s")
        values.append(timezone)
    if client_id is not None:
        fields.append("client_id=%s")
        values.append(client_id)
    values.append(appointment_id)

    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        try:
            row = conn.execute(
                f"""
                UPDATE appointments
                SET {', '.join(fields)}
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                """,
                tuple(values),
            ).fetchone()
        except errors.UndefinedColumn:
            fields_no_extra = [f for f in fields if f not in ("timezone=%s", "client_id=%s")]
            values_no_extra: List[Any] = []
            for idx, field in enumerate(fields):
                if field in ("timezone=%s", "client_id=%s"):
                    continue
                values_no_extra.append(values[idx])
            values_no_extra.append(appointment_id)
            row = conn.execute(
                f"""
                UPDATE appointments
                SET {', '.join(fields_no_extra)}
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                tuple(values_no_extra),
            ).fetchone()
    return row_to_appointment_api(row) if row else None


def delete_appointment(appointment_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        try:
            row = conn.execute(
                """
                DELETE FROM appointments
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                """,
                (appointment_id,),
            ).fetchone()
        except errors.UndefinedColumn:
            row = conn.execute(
                """
                DELETE FROM appointments
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                (appointment_id,),
            ).fetchone()
    return row_to_appointment_api(row) if row else None


def api_list():
    return list_appointments()


def api_get(appointment_id: int):
    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        try:
            row = conn.execute(
                """
                SELECT id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                FROM appointments WHERE id=%s
                """,
                (appointment_id,),
            ).fetchone()
        except errors.UndefinedColumn:
            row = conn.execute(
                """
                SELECT id, title, description, start_time, end_time, status, created_at, updated_at
                FROM appointments WHERE id=%s
                """,
                (appointment_id,),
            ).fetchone()
    if not row:
        raise LookupError("not_found")
    return row_to_appointment_api(row)


def _coerce_client_id(raw: Any):
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except Exception:
        raise ValueError("client_id_invalido")


def api_create(payload: Dict[str, Any]):
    title = payload.get("title")
    start_raw = payload.get("start_time")
    end_raw = payload.get("end_time")
    if not title or not start_raw or not end_raw:
        raise ValueError("title, start_time y end_time son requeridos")

    start_dt = parse_datetime(start_raw)
    end_dt = parse_datetime(end_raw)
    status = normalize_status(payload.get("status"))
    timezone = payload.get("timezone")
    client_id = _coerce_client_id(payload.get("client_id"))

    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        try:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status, timezone, client_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                """,
                (title, payload.get("description"), start_dt, end_dt, status, timezone, client_id),
            ).fetchone()
        except errors.UndefinedColumn:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                (title, payload.get("description"), start_dt, end_dt, status),
            ).fetchone()

    logger.info("Cita creada id=%s title=%s", row["id"], row["title"])
    return row_to_appointment_api(row)


def api_update(appointment_id: int, payload: Dict[str, Any]):
    fields: List[str] = []
    values: List[Any] = []
    if "title" in payload:
        fields.append("title=%s")
        values.append(payload["title"])
    if "description" in payload:
        fields.append("description=%s")
        values.append(payload["description"])
    if "start_time" in payload:
        values.append(parse_datetime(payload["start_time"]))
        fields.append("start_time=%s")
    if "end_time" in payload:
        values.append(parse_datetime(payload["end_time"]))
        fields.append("end_time=%s")
    if "status" in payload:
        values.append(normalize_status(payload["status"]))
        fields.append("status=%s")
    if "timezone" in payload:
        values.append(payload["timezone"])
        fields.append("timezone=%s")
    if "client_id" in payload:
        values.append(_coerce_client_id(payload.get("client_id")))
        fields.append("client_id=%s")

    if not fields:
        logger.warning("Update calendario sin cambios id=%s payload=%s", appointment_id, payload)
        raise ValueError("sin cambios")

    values.append(appointment_id)
    with get_db() as conn:
        _ensure_timezone_column(conn)
        _ensure_client_id_column(conn)
        try:
            row = conn.execute(
                f"""
                UPDATE appointments
                SET {', '.join(fields)}, updated_at=NOW()
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                """,
                tuple(values),
            ).fetchone()
        except errors.UndefinedColumn:
            fields_no_extra = [f for f in fields if f not in ("timezone=%s", "client_id=%s")]
            values_no_extra: List[Any] = []
            for idx, field in enumerate(fields):
                if field in ("timezone=%s", "client_id=%s"):
                    continue
                values_no_extra.append(values[idx])
            values_no_extra.append(appointment_id)
            row = conn.execute(
                f"""
                UPDATE appointments
                SET {', '.join(fields_no_extra)}, updated_at=NOW()
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                tuple(values_no_extra),
            ).fetchone()
    if not row:
        raise LookupError("not_found")
    logger.info("Cita actualizada id=%s", appointment_id)
    return row_to_appointment_api(row)


def api_delete(appointment_id: int):
    row = delete_appointment(appointment_id)
    if not row:
        raise LookupError("not_found")
    logger.info("Cita eliminada id=%s", appointment_id)
    return {"deleted": row.get("id"), "appointment": row}

import logging
from typing import Any, Dict, List, Optional

from psycopg import errors

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


def _ensure_timezone_column(conn) -> None:
    """
    Migración idempotente: en instalaciones antiguas `appointments` no tenía `timezone`.
    """
    try:
        conn.execute("ALTER TABLE IF EXISTS appointments ADD COLUMN IF NOT EXISTS timezone TEXT")
    except Exception:
        # No romper flujos por migración best-effort
        pass


def get_status_choices() -> List[Dict[str, str]]:
    return STATUS_CHOICES


def normalize_status(raw: Optional[str]) -> str:
    if not raw:
        return DEFAULT_STATUS
    value = str(raw).strip().lower()
    if value not in STATUS_LABELS:
        raise ValueError(f"Estado inválido: {raw}")
    return value


def list_appointments() -> List[Dict[str, Any]]:
    with get_db() as conn:
        _ensure_timezone_column(conn)
        rows = conn.execute(
            "SELECT * FROM appointments ORDER BY start_time DESC"
        ).fetchall()
    return [row_to_appointment_api(r) for r in rows]


def create_appointment(title: str, description: str, start_raw: str, end_raw: str, status_raw: Optional[str] = None, timezone: Optional[str] = None):
    start_time = parse_datetime(start_raw)
    end_time = parse_datetime(end_raw)
    status = normalize_status(status_raw)
    with get_db() as conn:
        _ensure_timezone_column(conn)
        conn.execute(
            """
            INSERT INTO appointments (title, description, start_time, end_time, status, timezone)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (title, description, start_time, end_time, status, timezone),
        )


def update_appointment(
    appointment_id: int, title: str, description: str, start_raw: str, end_raw: str, status_raw: Optional[str] = None, timezone: Optional[str] = None
) -> bool:
    start_time = parse_datetime(start_raw)
    end_time = parse_datetime(end_raw)
    status = normalize_status(status_raw)
    fields = ["title=%s", "description=%s", "start_time=%s", "end_time=%s", "status=%s", "updated_at=NOW()"]
    values = [title, description, start_time, end_time, status]
    if timezone:
        fields.append("timezone=%s")
        values.append(timezone)
    
    values.append(appointment_id)
    
    with get_db() as conn:
        _ensure_timezone_column(conn)
        updated = conn.execute(
            f"""
            UPDATE appointments
            SET {', '.join(fields)}
            WHERE id=%s
            """,
            tuple(values),
        ).rowcount
    return bool(updated)


def delete_appointment(appointment_id: int) -> bool:
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM appointments WHERE id=%s", (appointment_id,)
        ).rowcount
    return bool(deleted)


def api_list():
    return list_appointments()


def api_get(appointment_id: int):
    with get_db() as conn:
        _ensure_timezone_column(conn)
        try:
            row = conn.execute(
                """
                SELECT id, title, description, start_time, end_time, status, timezone, created_at, updated_at
                FROM appointments WHERE id=%s
                """,
                (appointment_id,),
            ).fetchone()
        except errors.UndefinedColumn:
            # Instalaciones antiguas: responder sin timezone
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
    with get_db() as conn:
        _ensure_timezone_column(conn)
        try:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status, timezone)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, timezone, created_at, updated_at
                """,
                (title, payload.get("description"), start_dt, end_dt, status, timezone),
            ).fetchone()
        except errors.UndefinedColumn:
            # Fallback por si el ALTER falló por permisos/otra razón
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
    fields = []
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

    if not fields:
        logger.warning("Update calendario sin cambios id=%s payload=%s", appointment_id, payload)
        raise ValueError("sin cambios")

    values.append(appointment_id)
    with get_db() as conn:
        _ensure_timezone_column(conn)
        try:
            row = conn.execute(
                f"""
                UPDATE appointments
                SET {', '.join(fields)}, updated_at=NOW()
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, timezone, created_at, updated_at
                """,
                tuple(values),
            ).fetchone()
        except errors.UndefinedColumn:
            # Si timezone no existe, quitar ese campo del update/returning
            fields_no_tz = [f for f in fields if f != "timezone=%s"]
            values_no_tz = []
            for i, f in enumerate(fields):
                if f == "timezone=%s":
                    continue
                values_no_tz.append(values[i])
            values_no_tz.append(appointment_id)
            row = conn.execute(
                f"""
                UPDATE appointments
                SET {', '.join(fields_no_tz)}, updated_at=NOW()
                WHERE id=%s
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                tuple(values_no_tz),
            ).fetchone()
    if not row:
        raise LookupError("not_found")
    logger.info("Cita actualizada id=%s", appointment_id)
    return row_to_appointment_api(row)


def api_delete(appointment_id: int):
    with get_db() as conn:
        deleted = conn.execute(
            "DELETE FROM appointments WHERE id=%s RETURNING id", (appointment_id,)
        ).fetchone()
    if not deleted:
        raise LookupError("not_found")
    logger.info("Cita eliminada id=%s", appointment_id)
    return {"deleted": appointment_id}

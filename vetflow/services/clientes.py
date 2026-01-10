import logging
import unicodedata
from typing import Any, Dict, List, Optional

from psycopg import errors

from ..db import get_db
from ..utils import parse_datetime

logger = logging.getLogger(__name__)


class DuplicateClientError(ValueError):
    def __init__(self, existing_client_id: int):
        super().__init__("cliente_ya_existe")
        self.existing_client_id = existing_client_id


def _normalize_id_type(raw: Any) -> str:
    value = (str(raw) if raw is not None else "").strip()
    if not value:
        raise ValueError("id_type_requerido")
    value = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode("ascii")
    normalized = value.strip().lower()
    if normalized not in ("cedula", "pasaporte"):
        raise ValueError("id_type_invalido")
    return normalized


def _normalize_id_number(raw: Any) -> str:
    value = (str(raw) if raw is not None else "").strip()
    if not value:
        raise ValueError("id_number_requerido")
    return value


def _ensure_clients_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            id_type TEXT NOT NULL,
            id_number TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            notes TEXT,
            blacklisted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    conn.execute("ALTER TABLE IF EXISTS clients ADD COLUMN IF NOT EXISTS id_type TEXT")
    conn.execute("ALTER TABLE IF EXISTS clients ADD COLUMN IF NOT EXISTS id_number TEXT")
    conn.execute("ALTER TABLE IF EXISTS clients ADD COLUMN IF NOT EXISTS blacklisted BOOLEAN DEFAULT FALSE")
    conn.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE clients
            ADD CONSTRAINT clients_identification_required
            CHECK (
                coalesce(id_type, '') IN ('cedula', 'pasaporte')
                AND btrim(coalesce(id_number, '')) <> ''
            )
            NOT VALID;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS client_notes (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    conn.execute("ALTER TABLE IF EXISTS appointments ADD COLUMN IF NOT EXISTS client_id INTEGER")


def _find_existing_client_id(conn, id_type: str, id_number: str, exclude_client_id: Optional[int] = None):
    params: List[Any] = [id_type, id_number]
    sql = "SELECT id FROM clients WHERE id_type=%s AND lower(id_number)=lower(%s)"
    if exclude_client_id is not None:
        sql += " AND id <> %s"
        params.append(exclude_client_id)
    row = conn.execute(sql + " LIMIT 1", tuple(params)).fetchone()
    return row["id"] if row else None


def _parse_blacklisted(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    value = str(raw).strip().lower()
    return value in ("1", "true", "yes", "on", "si")


def list_clients(query: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    limit = max(1, min(int(limit or 200), 500))
    with get_db() as conn:
        _ensure_clients_tables(conn)
        if q:
            like = f"%{q.lower()}%"
            rows = conn.execute(
                """
                SELECT id, full_name, id_type, id_number, phone, email, address, notes, blacklisted, created_at, updated_at
                FROM clients
                WHERE lower(full_name) LIKE %s
                   OR lower(coalesce(phone, '')) LIKE %s
                   OR lower(coalesce(email, '')) LIKE %s
                   OR lower(coalesce(id_number, '')) LIKE %s
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (like, like, like, like, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, full_name, id_type, id_number, phone, email, address, notes, blacklisted, created_at, updated_at
                FROM clients
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_client(client_id: int) -> Dict[str, Any]:
    with get_db() as conn:
        _ensure_clients_tables(conn)
        row = conn.execute(
            """
            SELECT id, full_name, id_type, id_number, phone, email, address, notes, blacklisted, created_at, updated_at
            FROM clients
            WHERE id=%s
            """,
            (client_id,),
        ).fetchone()
        if not row:
            raise LookupError("not_found")

        notes_rows = conn.execute(
            """
            SELECT id, client_id, body, created_at
            FROM client_notes
            WHERE client_id=%s
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (client_id,),
        ).fetchall()

        appointments = []
        try:
            appointments = conn.execute(
                """
                SELECT id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                FROM appointments
                WHERE client_id=%s
                ORDER BY start_time DESC
                LIMIT 200
                """,
                (client_id,),
            ).fetchall()
        except errors.UndefinedColumn:
            appointments = []

    return {
        "client": dict(row),
        "notes": [dict(r) for r in notes_rows],
        "appointments": [dict(r) for r in appointments],
    }


def create_client(payload: Dict[str, Any]) -> Dict[str, Any]:
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise ValueError("full_name_requerido")
    id_type = _normalize_id_type(payload.get("id_type"))
    id_number = _normalize_id_number(payload.get("id_number"))
    phone = (payload.get("phone") or "").strip() or None
    email = (payload.get("email") or "").strip() or None
    address = (payload.get("address") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    blacklisted = _parse_blacklisted(payload.get("blacklisted"))
    with get_db() as conn:
        _ensure_clients_tables(conn)
        existing_id = _find_existing_client_id(conn, id_type, id_number)
        if existing_id:
            raise DuplicateClientError(existing_id)
        row = conn.execute(
            """
            INSERT INTO clients (full_name, id_type, id_number, phone, email, address, notes, blacklisted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, full_name, id_type, id_number, phone, email, address, notes, blacklisted, created_at, updated_at
            """,
            (full_name, id_type, id_number, phone, email, address, notes, blacklisted),
        ).fetchone()
    return dict(row)


def update_client(client_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    with get_db() as conn:
        _ensure_clients_tables(conn)
        current = conn.execute(
            """
            SELECT id, full_name, id_type, id_number, phone, email, address, notes, blacklisted, created_at, updated_at
            FROM clients
            WHERE id=%s
            """,
            (client_id,),
        ).fetchone()
        if not current:
            raise LookupError("not_found")

        effective_id_type = current.get("id_type")
        effective_id_number = current.get("id_number")
        if "id_type" in payload:
            effective_id_type = _normalize_id_type(payload.get("id_type"))
        if "id_number" in payload:
            effective_id_number = _normalize_id_number(payload.get("id_number"))

        # Si el cliente es antiguo/incompleto, obligar a completarlo en cualquier edicion.
        if not effective_id_type or not str(effective_id_type).strip():
            raise ValueError("id_type_requerido")
        if not effective_id_number or not str(effective_id_number).strip():
            raise ValueError("id_number_requerido")

        if "id_type" in payload or "id_number" in payload:
            existing_id = _find_existing_client_id(
                conn,
                str(effective_id_type),
                str(effective_id_number),
                exclude_client_id=client_id,
            )
            if existing_id:
                raise DuplicateClientError(existing_id)

        fields: List[str] = []
        values: List[Any] = []
        for key in ("full_name", "phone", "email", "address", "notes"):
            if key not in payload:
                continue
            if key == "full_name":
                value = (payload.get(key) or "").strip()
                if not value:
                    raise ValueError("full_name_requerido")
            else:
                value = (payload.get(key) or "").strip() or None
            fields.append(f"{key}=%s")
            values.append(value)

        if "id_type" in payload:
            fields.append("id_type=%s")
            values.append(effective_id_type)
        if "id_number" in payload:
            fields.append("id_number=%s")
            values.append(effective_id_number)
        if "blacklisted" in payload:
            fields.append("blacklisted=%s")
            values.append(_parse_blacklisted(payload.get("blacklisted")))

        if not fields:
            raise ValueError("sin_cambios")

        values.append(client_id)
        row = conn.execute(
            f"""
            UPDATE clients
            SET {', '.join(fields)}, updated_at=NOW()
            WHERE id=%s
            RETURNING id, full_name, id_type, id_number, phone, email, address, notes, blacklisted, created_at, updated_at
            """,
            tuple(values),
        ).fetchone()
        if not row:
            raise LookupError("not_found")
    return dict(row)


def delete_client(client_id: int) -> None:
    with get_db() as conn:
        _ensure_clients_tables(conn)
        exists = conn.execute("SELECT 1 FROM clients WHERE id=%s", (client_id,)).fetchone()
        if not exists:
            raise LookupError("not_found")
        try:
            conn.execute("UPDATE appointments SET client_id=NULL WHERE client_id=%s", (client_id,))
        except errors.UndefinedColumn:
            pass
        conn.execute("DELETE FROM clients WHERE id=%s", (client_id,))


def add_note(client_id: int, body: str) -> Dict[str, Any]:
    text = (body or "").strip()
    if not text:
        raise ValueError("nota_vacia")
    with get_db() as conn:
        _ensure_clients_tables(conn)
        exists = conn.execute("SELECT 1 FROM clients WHERE id=%s", (client_id,)).fetchone()
        if not exists:
            raise LookupError("not_found")
        row = conn.execute(
            """
            INSERT INTO client_notes (client_id, body)
            VALUES (%s, %s)
            RETURNING id, client_id, body, created_at
            """,
            (client_id, text),
        ).fetchone()
        conn.execute("UPDATE clients SET updated_at=NOW() WHERE id=%s", (client_id,))
    return dict(row)


def create_appointment_for_client(client_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("title_requerido")
    start_raw = payload.get("start_time")
    end_raw = payload.get("end_time")
    if not start_raw or not end_raw:
        raise ValueError("start_time_y_end_time_requeridos")
    status = (payload.get("status") or "").strip() or "programada"
    timezone = (payload.get("timezone") or "").strip() or None
    description = (payload.get("description") or "").strip() or None
    start_dt = parse_datetime(start_raw)
    end_dt = parse_datetime(end_raw)

    with get_db() as conn:
        _ensure_clients_tables(conn)
        exists = conn.execute("SELECT 1 FROM clients WHERE id=%s", (client_id,)).fetchone()
        if not exists:
            raise LookupError("not_found")

        try:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status, timezone, client_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, timezone, client_id, created_at, updated_at
                """,
                (title, description, start_dt, end_dt, status, timezone, client_id),
            ).fetchone()
        except errors.UndefinedColumn:
            row = conn.execute(
                """
                INSERT INTO appointments (title, description, start_time, end_time, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, description, start_time, end_time, status, created_at, updated_at
                """,
                (title, description, start_dt, end_dt, status),
            ).fetchone()

        conn.execute("UPDATE clients SET updated_at=NOW() WHERE id=%s", (client_id,))

    return dict(row)

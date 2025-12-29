import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import g
from werkzeug.utils import secure_filename

from ..config import config
from ..db import get_db
from ..serializers import row_to_file
from ..storage import generate_sas_url, upload_blob
from ..utils import parse_datetime

logger = logging.getLogger(__name__)
REMOVED_STATUSES = ("expired", "expirada", "deleted", "eliminado", "eliminar")


def list_files(include_expired: bool = False):
    query = "SELECT * FROM files"
    params: List[Any] = []
    if not include_expired:
        placeholders = " AND ".join(["status IS DISTINCT FROM %s"] * len(REMOVED_STATUSES))
        query += f" WHERE {placeholders}"
        params.extend(REMOVED_STATUSES)
    query += " ORDER BY created_at DESC"
    with get_db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [row_to_file(r) for r in rows]


def create_file(
    uploaded,
    tags_list: Optional[List[str]],
    notes: Optional[str],
    size_bytes: Optional[int],
):
    filename = secure_filename(uploaded.filename) or "file"
    base_prefix = "file"
    blob_name = f"{base_prefix}/{uuid.uuid4().hex}-{filename}"

    blob_url = upload_blob(blob_name, uploaded.stream, uploaded.mimetype)
    thumbnail_url = blob_url if (uploaded.mimetype or "").startswith("image/") else None

    with get_db() as conn:
        row = conn.execute(
            """
            INSERT INTO files (filename, blob_path, blob_url, thumbnail_url, mime_type, size_bytes, tags, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'uploaded')
            RETURNING id, filename, blob_path, blob_url, thumbnail_url, mime_type, size_bytes, tags, notes, status, created_at, updated_at
            """,
            (filename, blob_name, blob_url, thumbnail_url, uploaded.mimetype, size_bytes, tags_list, notes),
        ).fetchone()
    logger.info("Metadata guardada en files id=%s nombre=%s", row["id"], filename)
    return row_to_file(row)


def notify_ingest_webhook(file_info: Dict[str, Any]):
    if not config.N8N_WEBHOOK_URL:
        return
    payload = {
        "file_id": file_info["id"],
        "filename": file_info["filename"],
        "blob_path": file_info["blob_path"],
        "tags": file_info.get("tags") or [],
        "notes": file_info.get("notes"),
        "schema": getattr(g, "workspace_schema", config.DB_SCHEMA),
    }
    try:
        requests.post(config.N8N_WEBHOOK_URL, json=payload, timeout=5)
        logger.info("Webhook n8n enviado para file_id=%s", file_info["id"])
    except Exception:
        logger.warning("No se pudo notificar a n8n para file_id=%s", file_info["id"])


def get_file(file_id: int):
    with get_db() as conn:
        return conn.execute("SELECT * FROM files WHERE id=%s", (file_id,)).fetchone()


def _extract_webhook_message(res: requests.Response) -> str:
    try:
        data = res.json()
        if isinstance(data, dict):
            if data.get("message"):
                return str(data.get("message"))
            if data.get("msg"):
                return str(data.get("msg"))
    except Exception:
        pass
    text = (res.text or "").strip()
    # recorta para evitar log gigante
    return text[:300] if text else ""


def delete_file(file_id: int) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    row = get_file(file_id)
    if not row:
        return False, "not_found", None, None

    blob_path = row["blob_path"]
    filename = row.get("filename") if "filename" in row else None
    blob_url = row.get("blob_url") if "blob_url" in row else None
    webhook_msg: Optional[str] = None

    current_schema = getattr(g, "workspace_schema", config.DB_SCHEMA)

    with get_db() as conn:
        conn.execute(
            """
            UPDATE files
            SET status=%s, updated_at=NOW()
            WHERE id=%s
            """,
            ("deleting", file_id),
        )
    logger.info("Archivo marcado como eliminando id=%s", file_id)

    if config.N8N_DELETE_WEBHOOK_URL:
        used_url = config.N8N_DELETE_WEBHOOK_URL
        try:
            res = requests.post(
                used_url,
                json={
                    "file_id": file_id,
                    "blob_path": blob_path,
                    "blob_url": blob_url,
                    "container": config.AZURE_BLOB_CONTAINER,
                    "filename": filename,
                    "schema": current_schema,
                },
                timeout=5,
            )
            webhook_msg = _extract_webhook_message(res)
            # Fallback: si la URL de test no existe, intentar la de produccion
            if res.status_code == 404 and "/webhook-test/" in used_url:
                if not webhook_msg:
                    webhook_msg = (
                        "Webhook 404 en modo test; pulsa Listen/Execute en n8n o usa la URL de produccion."
                    )
                alt_url = used_url.replace("/webhook-test/", "/webhook/")
                logger.info("Webhook delete test 404, intentando URL de produccion %s", alt_url)
                try:
                    res_alt = requests.post(
                        alt_url,
                        json={
                            "file_id": file_id,
                            "blob_path": blob_path,
                            "blob_url": blob_url,
                            "container": config.AZURE_BLOB_CONTAINER,
                            "filename": filename,
                            "schema": current_schema,
                        },
                        timeout=5,
                    )
                    webhook_msg = _extract_webhook_message(res_alt)
                    res = res_alt
                    used_url = alt_url
                    if res_alt.status_code == 404 and not webhook_msg:
                        webhook_msg = "Webhook 404 en produccion; revisa la ruta /webhook/rag-files-deleted."
                except Exception as ex_alt:
                    logger.warning("Fallo intento webhook delete en produccion: %s", ex_alt)

            if 200 <= res.status_code < 300:
                logger.info(
                    "Webhook de eliminacion enviado file_id=%s code=%s url=%s body=%s",
                    file_id,
                    res.status_code,
                    used_url,
                    webhook_msg or res.text,
                )
            else:
                logger.warning(
                    "Webhook de eliminacion respondio code=%s url=%s body=%s",
                    res.status_code,
                    used_url,
                    webhook_msg or res.text,
                )
        except Exception as ex:
            logger.warning(
                "No se pudo notificar eliminacion a n8n file_id=%s: %s", file_id, ex
            )

    return True, None, blob_path, webhook_msg


def send_to_n8n(file_id: int) -> Tuple[bool, str]:
    if not config.N8N_WEBHOOK_URL:
        return False, "Configura N8N_WEBHOOK_URL"

    row = get_file(file_id)
    if not row:
        return False, "Archivo no encontrado"

    file_obj = row_to_file(row)
    payload = {
        "file_id": row["id"],
        "filename": file_obj["filename"],
        "blob_path": file_obj["blob_path"],
        "blob_url": file_obj.get("blob_url"),
        "folder": file_obj.get("folder"),
        "tags": file_obj.get("tags") or [],
        "notes": file_obj.get("notes"),
        "status": file_obj.get("status"),
        "schema": getattr(g, "workspace_schema", config.DB_SCHEMA),
    }

    try:
        res = requests.post(config.N8N_WEBHOOK_URL, json=payload, timeout=10)
        used_url = config.N8N_WEBHOOK_URL

        if res.status_code == 404 and "/webhook-test/" in config.N8N_WEBHOOK_URL:
            alt_url = config.N8N_WEBHOOK_URL.replace("/webhook-test/", "/webhook/")
            logger.info("Webhook test 404, intentando URL de produccion %s", alt_url)
            try:
                res = requests.post(alt_url, json=payload, timeout=10)
                used_url = alt_url
            except Exception as ex_alt:
                logger.warning("Fallo intento con URL de produccion: %s", ex_alt)

        if 200 <= res.status_code < 300:
            with get_db() as conn:
                conn.execute(
                    "UPDATE files SET status=%s, updated_at=NOW() WHERE id=%s",
                    ("processing", file_id),
                )
            logger.info(
                "Webhook n8n OK file_id=%s status=%s code=%s url=%s",
                file_id,
                row.get("status"),
                res.status_code,
                used_url,
            )
            return True, "Enviado a n8n"

        hint = ""
        if "/webhook-test/" in used_url and res.status_code == 404:
            hint = " (modo test: pulsa Execute/Listen y usa la URL de test, o usa la URL de produccion)"
        logger.warning(
            "Webhook n8n fallo file_id=%s code=%s body=%s url=%s",
            file_id,
            res.status_code,
            res.text,
            used_url,
        )
        return False, f"n8n respondio {res.status_code}: {res.text}{hint}"
    except Exception as ex:
        logger.exception("Error enviando a n8n file_id=%s", file_id)
        return False, f"Error enviando a n8n: {ex}"


def sas_for_file(file_id: int) -> str:
    row = get_file(file_id)
    if not row:
        raise LookupError("No encontrado")
    return generate_sas_url(row["blob_path"])


def update_file_metadata(file_id: int, payload: Dict[str, Any]):
    fields = []
    values: List[Any] = []

    if "tags" in payload:
        fields.append("tags=%s")
        values.append(payload["tags"])
    if "notes" in payload:
        fields.append("notes=%s")
        values.append(payload["notes"])
    if "status" in payload:
        fields.append("status=%s")
        values.append(payload["status"])
    if "processed_at" in payload:
        try:
            values.append(parse_datetime(payload["processed_at"]))
            fields.append("processed_at=%s")
        except ValueError as ex:
            raise ValueError(str(ex)) from ex

    if not fields:
        raise ValueError("sin cambios")

    values.append(file_id)
    with get_db() as conn:
        row = conn.execute(
            f"""
            UPDATE files
            SET {', '.join(fields)}, updated_at=NOW()
            WHERE id=%s
            RETURNING id, filename, blob_path, blob_url, thumbnail_url, mime_type, size_bytes, tags, notes, status, processed_at, created_at, updated_at
            """,
            tuple(values),
        ).fetchone()
    if not row:
        raise LookupError("not_found")
    return row_to_file(row)

def row_to_file(row: dict):
    blob_path = row["blob_path"]
    folder = "/".join(blob_path.split("/")[:-1]) if "/" in blob_path else ""
    return {
        "id": row["id"],
        "filename": row["filename"],
        "blob_path": blob_path,
        "folder": folder,
        "blob_url": row.get("blob_url"),
        "thumbnail_url": row.get("thumbnail_url"),
        "mime_type": row.get("mime_type"),
        "size_bytes": row.get("size_bytes"),
        "tags": row.get("tags") or [],
        "notes": row.get("notes"),
        "status": row.get("status"),
        "processed_at": row.get("processed_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def row_to_appointment(row: dict):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "status": row.get("status"),
    }


def row_to_appointment_api(row: dict):
    # Serializa citas en ISO para consumo por APIs/bots.
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "start_time": _iso_datetime(row.get("start_time")),
        "end_time": _iso_datetime(row.get("end_time")),
        "status": row.get("status"),
        "timezone": row.get("timezone"),
        "client_id": row.get("client_id"),
        "created_at": _iso_datetime(row.get("created_at")),
        "updated_at": _iso_datetime(row.get("updated_at")),
    }
from datetime import timezone


def _iso_datetime(value):
    """
    Serializa datetimes garantizando que incluyan zona horaria.
    Si el datetime viene naive (sin tzinfo), se asume UTC para evitar desfaces en el frontend.
    """
    if not value:
        return None
    try:
        dt = value
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return str(value)

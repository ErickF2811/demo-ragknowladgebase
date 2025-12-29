import re
from datetime import datetime, timezone
from typing import Optional

from werkzeug.utils import secure_filename


def parse_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as ex:
        raise ValueError(f"Fecha invalida: {value}") from ex


def sanitize_folder_path(raw: Optional[str]) -> str:
    """
    Sanitiza una ruta de carpeta asegurando que coincida con la jerarquia de Blob Storage.
    - Separa por / o \
    - Aplica secure_filename a cada segmento
    - Recompone usando /
    """
    if not raw:
        return ""
    parts = []
    for chunk in raw.replace("\\", "/").split("/"):
        cleaned = secure_filename(chunk.strip())
        if cleaned:
            parts.append(cleaned)
    return "/".join(parts)


_slug_regex = re.compile(r"[^a-z0-9]+")


def slugify(value: Optional[str], fallback: str = "workspace") -> str:
    """
    Convierte un nombre arbitrario a slug URL-safe.
    """
    if not value:
        return fallback
    slug = _slug_regex.sub("-", value.lower()).strip("-")
    return slug or fallback

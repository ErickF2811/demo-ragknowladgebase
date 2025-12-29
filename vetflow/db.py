import logging
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from flask import g, request

from .config import config

logger = logging.getLogger(__name__)


def _resolve_schema(explicit_schema: Optional[str] = None) -> str:
    if explicit_schema:
        return explicit_schema
    try:
        workspace_schema = getattr(g, "workspace_schema", None)
        if workspace_schema:
            return workspace_schema
    except RuntimeError:
        pass
    return config.DB_SCHEMA


def get_db(schema: Optional[str] = None):
    if not config.POSTGRES_DSN:
        raise RuntimeError("Falta POSTGRES_DSN")
    target_schema = _resolve_schema(schema)
    logger.debug("Conectando a Postgres usando schema %s", target_schema)
    tz = (getattr(config, "APP_TIMEZONE", None) or "UTC").strip() or "UTC"
    try:
        header_tz = (request.headers.get("X-Timezone") or "").strip()
        # Validación simple para evitar inyección en options; acepta zonas tipo "America/Bogota"
        if header_tz and 1 <= len(header_tz) <= 64 and all(
            c.isalnum() or c in ("/", "_", "+", "-", ".") for c in header_tz
        ):
            tz = header_tz
    except RuntimeError:
        # fuera de contexto de request
        pass
    return psycopg.connect(
        config.POSTGRES_DSN,
        row_factory=dict_row,
        options=f"-c search_path={target_schema} -c TimeZone={tz}",
    )

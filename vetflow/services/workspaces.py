import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from psycopg import errors, sql

from ..bootstrap import ensure_core_bootstrap
from ..config import config
from ..db import get_db
from ..utils import slugify

logger = logging.getLogger(__name__)


def _json_safe(value):
    if isinstance(value, datetime):
        # Enviar en ISO8601 para webhooks/JSON
        return value.isoformat()
    return value


def _normalize_email(value: str) -> str:
    if not value:
        raise ValueError("Email requerido")
    return value.strip().lower()


def _unique_slug(base: str, conn) -> str:
    slug = base
    suffix = 2
    while True:
        row = conn.execute("SELECT 1 FROM workspaces WHERE slug=%s", (slug,)).fetchone()
        if not row:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _generate_schema_name(slug: str, conn) -> str:
    slug_fragment = slug.replace("-", "_")
    prefix = config.WORKSPACE_SCHEMA_PREFIX or "ws"
    while True:
        candidate = f"{prefix}_{slug_fragment}_{secrets.token_hex(2)}"
        row = conn.execute(
            "SELECT 1 FROM workspaces WHERE schema_name=%s",
            (candidate,),
        ).fetchone()
        if not row:
            return candidate


def ensure_user(email: str, display_name: Optional[str] = None, clerk_id: Optional[str] = None):
    normalized = _normalize_email(email)
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            INSERT INTO app_users (email, display_name, clerk_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE
            SET
                display_name = COALESCE(EXCLUDED.display_name, app_users.display_name),
                clerk_id = COALESCE(EXCLUDED.clerk_id, app_users.clerk_id)
            RETURNING id::text, email, display_name
            """,
            (normalized, display_name, clerk_id),
        ).fetchone()
    return dict(row)


def _workspace_stats(schema_name: str) -> Dict[str, int]:
    stats = {"files_count": 0, "appointments_count": 0}
    try:
        with get_db(schema=schema_name) as conn:
            files_row = conn.execute("SELECT COUNT(*) AS total FROM files").fetchone()
            appt_row = conn.execute("SELECT COUNT(*) AS total FROM appointments").fetchone()
            stats["files_count"] = files_row["total"] if files_row else 0
            stats["appointments_count"] = appt_row["total"] if appt_row else 0
    except Exception as ex:
        logger.warning("No se pudieron calcular estadisticas para schema %s: %s", schema_name, ex)
    return stats


def _fetch_all_workspaces(conn):
    return conn.execute(
        """
        SELECT
            w.id::text,
            w.name,
            w.slug,
            w.schema_name,
            w.description,
            w.theme_color,
            w.icon_url,
            u.email AS owner_email,
            u.display_name AS owner_name,
            w.created_at,
            w.updated_at
        FROM workspaces w
        JOIN app_users u ON u.id = w.owner_id
        ORDER BY w.created_at ASC
        """
    ).fetchall()


def _fetch_user_workspaces(conn, user_id: str):
    return conn.execute(
        """
        SELECT
            w.id::text,
            w.name,
            w.slug,
            w.schema_name,
            w.description,
            w.theme_color,
            w.icon_url,
            owner.email AS owner_email,
            owner.display_name AS owner_name,
            wm.role AS member_role,
            w.created_at,
            w.updated_at
        FROM workspace_members wm
        JOIN workspaces w ON w.id = wm.workspace_id
        JOIN app_users owner ON owner.id = w.owner_id
        WHERE wm.user_id = %s
        ORDER BY w.created_at ASC
        """,
        (user_id,),
    ).fetchall()


def list_workspaces(
    include_stats: bool = False,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
) -> List[Dict]:
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        try:
            if user_email:
                user = ensure_user(user_email, user_name)
                rows = _fetch_user_workspaces(conn, user["id"])
            else:
                rows = _fetch_all_workspaces(conn)
        except errors.UndefinedTable:
            ensure_core_bootstrap()
            if user_email:
                user = ensure_user(user_email, user_name)
                rows = _fetch_user_workspaces(conn, user["id"])
            else:
                rows = _fetch_all_workspaces(conn)
    items = [dict(r) for r in rows]
    if include_stats:
        for item in items:
            item.update(_workspace_stats(item["schema_name"]))
    return items


def get_workspace(workspace_id: str) -> Optional[Dict]:
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            SELECT
                w.id::text,
                w.name,
                w.slug,
                w.schema_name,
                w.description,
                w.theme_color,
                w.icon_url,
                u.email AS owner_email,
                u.display_name AS owner_name,
                w.created_at,
                w.updated_at
            FROM workspaces w
            JOIN app_users u ON u.id = w.owner_id
            WHERE w.id = %s
            """,
            (workspace_id,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item.update(_workspace_stats(item["schema_name"]))
    return item


def get_workspace_by_slug(slug: str) -> Optional[Dict]:
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            SELECT
                w.id::text,
                w.name,
                w.slug,
                w.schema_name,
                w.description,
                w.theme_color,
                w.icon_url,
                u.email AS owner_email,
                u.display_name AS owner_name,
                w.created_at,
                w.updated_at
            FROM workspaces w
            JOIN app_users u ON u.id = w.owner_id
            WHERE w.slug = %s
            """,
            (slug,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item.update(_workspace_stats(item["schema_name"]))
    return item


def get_workspace_by_key(key: str) -> Optional[Dict]:
    """
    Resuelve un workspace por:
    - slug (ej: veterinaria1)
    - schema_name (ej: ws_veterinaria1_dfb7)

    Esto permite usar URLs canónicas que incluyan el identificador/hash del workspace.
    """
    key = (key or "").strip()
    if not key:
        return None

    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            SELECT
                w.id::text,
                w.name,
                w.slug,
                w.schema_name,
                w.description,
                w.theme_color,
                w.icon_url,
                u.email AS owner_email,
                u.display_name AS owner_name,
                w.created_at,
                w.updated_at
            FROM workspaces w
            JOIN app_users u ON u.id = w.owner_id
            WHERE w.slug = %s OR w.schema_name = %s
            LIMIT 1
            """,
            (key, key),
        ).fetchone()

    if not row:
        return None
    item = dict(row)
    item.update(_workspace_stats(item["schema_name"]))
    return item


def list_members(workspace_id: str) -> List[Dict]:
    """
    Devuelve miembros de un workspace con rol y datos de usuario.
    """
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        rows = conn.execute(
            """
            SELECT
                wm.workspace_id::text,
                wm.role,
                wm.joined_at,
                u.id::text AS user_id,
                u.email,
                u.display_name,
                u.avatar_url
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s
            ORDER BY wm.role = 'owner' DESC, wm.role = 'admin' DESC, u.email ASC
            """,
            (workspace_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_member_role(workspace_id: str, email: str) -> Optional[str]:
    if not email:
        return None
    ensure_core_bootstrap()
    normalized = _normalize_email(email)
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            SELECT wm.role
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s AND u.email = %s
            """,
            (workspace_id, normalized),
        ).fetchone()
    return row["role"] if row else None




def list_members(workspace_id: str) -> List[Dict]:
    """
    Devuelve miembros de un workspace con rol y datos de usuario.
    """
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        rows = conn.execute(
            """
            SELECT
                wm.workspace_id::text,
                wm.role,
                wm.joined_at,
                u.id::text AS user_id,
                u.email,
                u.display_name,
                u.avatar_url
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s
            ORDER BY wm.role = 'owner' DESC, wm.role = 'admin' DESC, u.email ASC
            """,
            (workspace_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_member_role(workspace_id: str, email: str) -> Optional[str]:
    if not email:
        return None
    ensure_core_bootstrap()
    normalized = _normalize_email(email)
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            SELECT wm.role
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s AND u.email = %s
            """,
            (workspace_id, normalized),
        ).fetchone()
    return row["role"] if row else None


def create_workspace(
    name: str,
    owner_email: str,
    owner_name: Optional[str] = None,
    description: Optional[str] = None,
    slug_hint: Optional[str] = None,
    theme_color: Optional[str] = None,
    icon_url: Optional[str] = None,
) -> Dict:
    if not name:
        raise ValueError("Nombre requerido")
    ensure_core_bootstrap()
    owner = ensure_user(owner_email, owner_name)
    slug_value = slugify(slug_hint) if slug_hint else ""
    if slug_value:
        base_slug = slug_value
        explicit_slug = True
    else:
        slug_source = name or owner_email
        base_slug = slugify(slug_source) or slugify(owner_email.split("@")[0])
        if not base_slug:
            base_slug = secrets.token_hex(3)
        explicit_slug = False

    with get_db(schema=config.CORE_SCHEMA) as conn:
        if explicit_slug:
            slug = base_slug
            existing = conn.execute("SELECT 1 FROM workspaces WHERE slug=%s", (slug,)).fetchone()
            if existing:
                raise ValueError("El URL solicitado ya existe, prueba otro.")
        else:
            slug = _unique_slug(base_slug, conn)
        schema_name = _generate_schema_name(slug, conn)
        workspace = conn.execute(
            """
            INSERT INTO workspaces (name, slug, schema_name, description, owner_id, theme_color, icon_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING
                id::text,
                name,
                slug,
                schema_name,
                description,
                theme_color,
                icon_url,
                owner_id,
                created_at,
                updated_at
            """,
            (name, slug, schema_name, description, owner["id"], theme_color or '#6c47ff', icon_url),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT (workspace_id, user_id) DO NOTHING
            """,
            (workspace["id"], owner["id"]),
        )
        conn.execute("SELECT vetflow_core.ensure_workspace_schema(%s)", (schema_name,))

    result = dict(workspace)
    result["owner_email"] = owner["email"]
    result["owner_name"] = owner.get("display_name")
    result.update(_workspace_stats(result["schema_name"]))

    webhook_url = (getattr(config, "N8N_NEW_WORKSPACE_WEBHOOK_URL", "") or "").strip()
    if webhook_url:
        payload = {
            "event": "workspace_created",
            "workspace": {
                "id": result.get("id"),
                "name": result.get("name"),
                "slug": result.get("slug"),
                "schema_name": result.get("schema_name"),
                "description": result.get("description"),
                "theme_color": result.get("theme_color"),
                "owner_email": result.get("owner_email"),
                "owner_name": result.get("owner_name"),
                "created_at": _json_safe(result.get("created_at")),
            },
        }
        try:
            logger.info("Notificando webhook workspace_created url=%s schema=%s", webhook_url, result.get("schema_name"))
            res = requests.post(webhook_url, json=payload, timeout=10)
            if 200 <= res.status_code < 300:
                logger.info("Webhook workspace_created OK code=%s", res.status_code)
            else:
                logger.warning(
                    "Webhook workspace_created FAIL code=%s body=%s",
                    res.status_code,
                    (res.text or "").strip()[:300],
                )
        except Exception as ex:
            logger.warning("No se pudo notificar N8N_NEW_WORKSPACE_WEBHOOK_URL=%s: %s", webhook_url, ex)
    return result


def update_workspace(
    workspace_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    theme_color: Optional[str] = None,
    icon_url: Optional[str] = None,
) -> Dict:
    """
    Actualiza los datos basicos de un workspace.
    """
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        # Build update query dynamically
        fields = []
        values = []
        if name is not None:
            fields.append("name = %s")
            values.append(name.strip())
        if description is not None:
            fields.append("description = %s")
            values.append(description.strip())
        if theme_color is not None:
            fields.append("theme_color = %s")
            values.append(theme_color.strip())
        if icon_url is not None:
            fields.append("icon_url = %s")
            values.append(icon_url.strip())
        
        if not fields:
            # Nothing to update, return current state
            return get_workspace(workspace_id) or {}

        values.append(workspace_id)
        query = f"""
            UPDATE workspaces
            SET {', '.join(fields)}, updated_at = NOW()
            WHERE id = %s
            RETURNING
                id::text,
                name,
                slug,
                schema_name,
                description,
                theme_color,
                icon_url,
                owner_id,
                created_at,
                updated_at
        """
        row = conn.execute(query, tuple(values)).fetchone()
        if not row:
            raise LookupError("workspace_not_found")
        
        updated = dict(row)
        # Fetch stats to keep return shape consistent
        updated.update(_workspace_stats(updated["schema_name"]))
        
        # Get owner info
        owner_row = conn.execute("SELECT email, display_name FROM app_users WHERE id=%s", (updated["owner_id"],)).fetchone()
        if owner_row:
            updated["owner_email"] = owner_row["email"]
            updated["owner_name"] = owner_row["display_name"]

    return updated


def create_invite(
    workspace_id: str,
    email: str,
    invited_by_email: Optional[str] = None,
    invited_by_name: Optional[str] = None,
    expires_in_days: Optional[int] = None,
) -> Dict:
    """
    Crea una invitacion (con codigo unico) para un workspace concreto.
    - Si el email ya es miembro: ValueError("already_member")
    - Si existe una invitacion vigente para ese email: devuelve la existente.
    """
    normalized_email = _normalize_email(email)
    ensure_core_bootstrap()

    inviter_id = None
    if invited_by_email:
        inviter = ensure_user(invited_by_email, invited_by_name)
        inviter_id = inviter["id"]

    with get_db(schema=config.CORE_SCHEMA) as conn:
        ws = conn.execute(
            "SELECT id::text, slug FROM workspaces WHERE id = %s",
            (workspace_id,),
        ).fetchone()
        if not ws:
            raise LookupError("workspace_not_found")

        member_exists = conn.execute(
            """
            SELECT 1
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s AND u.email = %s
            """,
            (workspace_id, normalized_email),
        ).fetchone()
        if member_exists:
            raise ValueError("already_member")

        now = datetime.now(timezone.utc)
        existing = conn.execute(
            """
            SELECT id::text, workspace_id::text, email, invite_code, expires_at, accepted_at, created_at
            FROM workspace_invites
            WHERE workspace_id = %s
              AND email = %s
              AND accepted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (workspace_id, normalized_email),
        ).fetchone()
        if existing and (existing["expires_at"] is None or existing["expires_at"] > now):
            return dict(existing)

        expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

        for _ in range(5):
            invite_code = secrets.token_urlsafe(6)
            row = conn.execute(
                """
                INSERT INTO workspace_invites (workspace_id, email, invite_code, invited_by, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (invite_code) DO NOTHING
                RETURNING id::text, workspace_id::text, email, invite_code, expires_at, accepted_at, created_at
                """,
                (workspace_id, normalized_email, invite_code, inviter_id, expires_at),
            ).fetchone()
            if row:
                return dict(row)

    raise RuntimeError("No se pudo generar codigo de invitacion")


def accept_invite(invite_code: str, email: str, display_name: Optional[str] = None) -> Dict:
    """
    Acepta una invitacion y agrega al usuario como miembro.
    - Valida expiracion, codigo y que el correo coincida.
    - Si ya es miembro, solo marca accepted_at.
    """
    if not invite_code:
        raise ValueError("code_requerido")
    normalized_email = _normalize_email(email)
    ensure_core_bootstrap()
    now = datetime.now(timezone.utc)

    with get_db(schema=config.CORE_SCHEMA) as conn:
        invite_row = conn.execute(
            """
            SELECT
                wi.id::text,
                wi.workspace_id::text,
                wi.email,
                wi.invite_code,
                wi.expires_at,
                wi.accepted_at,
                wi.created_at,
                w.slug,
                w.schema_name,
                w.name AS workspace_name
            FROM workspace_invites wi
            JOIN workspaces w ON w.id = wi.workspace_id
            WHERE wi.invite_code = %s
            """,
            (invite_code,),
        ).fetchone()

        if not invite_row:
            raise LookupError("invite_not_found")

        invite_email = (invite_row["email"] or "").strip().lower()
        if invite_email != normalized_email:
            raise ValueError("email_mismatch")

        expires_at = invite_row["expires_at"]
        if expires_at and expires_at < now:
            raise ValueError("invite_expired")

        user = ensure_user(normalized_email, display_name)

        member_exists = conn.execute(
            """
            SELECT 1
            FROM workspace_members wm
            WHERE wm.workspace_id = %s AND wm.user_id = %s
            """,
            (invite_row["workspace_id"], user["id"]),
        ).fetchone()

        if not member_exists:
            conn.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role)
                VALUES (%s, %s, 'member')
                ON CONFLICT (workspace_id, user_id) DO NOTHING
                """,
                (invite_row["workspace_id"], user["id"]),
            )

        updated_invite = conn.execute(
            """
            UPDATE workspace_invites
            SET accepted_at = %s
            WHERE id = %s
            RETURNING id::text, workspace_id::text, email, invite_code, expires_at, accepted_at, created_at
            """,
            (now, invite_row["id"]),
        ).fetchone()

    return {
        "workspace": {
            "id": invite_row["workspace_id"],
            "slug": invite_row["slug"],
            "schema_name": invite_row["schema_name"],
            "name": invite_row["workspace_name"],
        },
        "invite": dict(updated_invite) if updated_invite else dict(invite_row),
        "user": user,
    }


def ensure_default_workspace_for_user(email: str, display_name: Optional[str] = None) -> Optional[Dict]:
    if not email:
        return None
    ensure_core_bootstrap()
    owner = ensure_user(email, display_name)
    with get_db(schema=config.CORE_SCHEMA) as conn:
        existing = conn.execute(
            """
            SELECT w.id::text
            FROM workspace_members wm
            JOIN workspaces w ON w.id = wm.workspace_id
            WHERE wm.user_id = %s
            LIMIT 1
            """,
            (owner["id"],),
        ).fetchone()

    if existing:
        return get_workspace(existing["id"])

    if not config.AUTO_CREATE_DEFAULT_WORKSPACE:
        return None

    default_name = display_name or email.split("@")[0].title()
    description = f"Workspace inicial para {email}"
    logger.info("Creando workspace por defecto para %s", email)
    return create_workspace(default_name, email, display_name, description)


def delete_workspace(workspace_id: str, drop_schema: bool = True) -> Optional[Dict]:
    """
    Elimina el workspace del schema core y opcionalmente elimina el schema dedicado.
    Devuelve el workspace eliminado o None si no existe.
    """
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        row = conn.execute(
            """
            SELECT id::text, slug, schema_name, name
            FROM workspaces
            WHERE id = %s
            """,
            (workspace_id,),
        ).fetchone()
        if not row:
            return None

        conn.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))

    deleted = dict(row)

    if drop_schema:
        prefix = config.WORKSPACE_SCHEMA_PREFIX or "ws"
        schema_name = deleted["schema_name"]
        # Solo permitimos borrar schemas que sigan el prefijo configurado
        if schema_name and schema_name.startswith(f"{prefix}_"):
            try:
                with get_db(schema=config.DB_SCHEMA) as conn:
                    conn.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name))
                    )
            except Exception as ex:
                logger.warning("No se pudo eliminar schema %s: %s", schema_name, ex)
        else:
            logger.warning("Schema %s no coincide con prefijo %s, se omite DROP", schema_name, prefix)

    return deleted


def remove_member(workspace_id: str, target_email: str, acting_email: str) -> Dict:
    """
    Elimina a un miembro. Solo owner puede hacerlo. No elimina owners.
    """
    ensure_core_bootstrap()
    if not acting_email:
        raise PermissionError("acting_email_requerido")
    if not target_email:
        raise ValueError("email_requerido")

    normalized_target = _normalize_email(target_email)
    normalized_actor = _normalize_email(acting_email)

    with get_db(schema=config.CORE_SCHEMA) as conn:
        actor_row = conn.execute(
            """
            SELECT wm.role
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s AND u.email = %s
            """,
            (workspace_id, normalized_actor),
        ).fetchone()
        if not actor_row or actor_row["role"] != "owner":
            raise PermissionError("solo_owner")

        target_row = conn.execute(
            """
            SELECT wm.role, wm.user_id::text, u.email, u.display_name
            FROM workspace_members wm
            JOIN app_users u ON u.id = wm.user_id
            WHERE wm.workspace_id = %s AND u.email = %s
            """,
            (workspace_id, normalized_target),
        ).fetchone()
        if not target_row:
            raise LookupError("miembro_no_encontrado")
        if target_row["role"] == "owner":
            raise ValueError("no_se_puede_remover_owner")

        conn.execute(
            "DELETE FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
            (workspace_id, target_row["user_id"]),
        )

    return dict(target_row)


def update_workspace(workspace_id: str, name: str = None, description: str = None, theme_color: str = None, icon_url: str = None):
    """
    Actualiza detalles del workspace.
    """
    ensure_core_bootstrap()
    with get_db(schema=config.CORE_SCHEMA) as conn:
        # Update dynamically
        updates = []
        params = []
        if name:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if theme_color:
            updates.append("theme_color = %s")
            params.append(theme_color)
        if icon_url:
            updates.append("icon_url = %s")
            params.append(icon_url)

        if not updates:
            return None

        params.append(workspace_id)
        workspace = conn.execute(
            f"UPDATE workspaces SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s RETURNING *",
            tuple(params)
        ).fetchone()
        return dict(workspace) if workspace else None

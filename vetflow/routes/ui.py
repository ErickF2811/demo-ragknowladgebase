from typing import Optional

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    session,
    flash,
    redirect,
    url_for,
    g,
    make_response,
)

from ..config import config
from ..auth import (
    AuthError,
    is_auth_required,
    is_service_api_key_valid,
    resolve_user_from_token,
    require_authenticated_request,
)
from ..services.calendar import get_status_choices, list_appointments, list_upcoming_appointments, STATUS_LABELS
from ..services.files import list_files
from ..services.workspaces import (
    create_workspace,
    ensure_default_workspace_for_user,
    get_workspace_by_key,
    list_workspaces,
    list_members,
    get_member_role,
    delete_workspace,
    create_invite,
    accept_invite,
    remove_member,
)

ui_bp = Blueprint("ui", __name__)


def _select_workspace(workspaces, requested_id):
    if requested_id:
        for ws in workspaces:
            if ws["id"] == requested_id:
                return ws
    return workspaces[0] if workspaces else None


def _select_workspace_by_slug(workspaces, slug):
    if slug:
        for ws in workspaces:
            if ws.get("schema_name") == slug or ws.get("slug") == slug:
                return ws
    return None


def set_workspace_context(workspace):
    if not workspace:
        return
    session["workspace_id"] = workspace["id"]
    session["workspace_schema"] = workspace["schema_name"]
    g.workspace_schema = workspace["schema_name"]
    g.workspace_id = workspace["id"]


def ensure_workspace_from_slug(slug: str):
    if not slug:
        return None
    workspace = get_workspace_by_key(slug)
    if not workspace:
        return None

    if is_auth_required() and not is_service_api_key_valid():
        user_email, _ = _resolve_current_user()
        if not user_email:
            return None
        role = get_member_role(workspace["id"], user_email)
        if not role:
            return None
        # Guardar rol de membership para UI (no es autorizacion adicional; es solo display)
        session["current_membership_role"] = role

    set_workspace_context(workspace)
    return workspace


def _resolve_current_user():
    email = session.get("current_user_email")
    name = session.get("current_user_name")
    if getattr(config, "CLERK_AUTH_REQUIRED", False):
        return email, name
    header_email = request.headers.get("X-User-Email")
    header_name = request.headers.get("X-User-Name")
    qs_email = request.args.get("email")
    qs_name = request.args.get("name")

    if header_email:
        email = header_email
    elif qs_email:
        email = qs_email

    if header_name:
        name = header_name
    elif qs_name:
        name = qs_name

    if email:
        email = email.strip()
        session["current_user_email"] = email
    if name:
        name = name.strip()
        session["current_user_name"] = name
    return email, name


def _render_dashboard(workspace_slug: Optional[str] = None):
    user_email, user_name = _resolve_current_user()
    workspaces = (
        list_workspaces(include_stats=True, user_email=user_email, user_name=user_name) if user_email else []
    )

    if not workspaces and user_email:
        target_workspace = ensure_default_workspace_for_user(user_email, user_name)
        if target_workspace:
            workspaces = list_workspaces(include_stats=True, user_email=user_email, user_name=user_name)
            if not workspaces:
                workspaces = [target_workspace]
                
            # Opcional: Flash solo si es nuevo (ej. created_at reciente)
            # Por simplicidad, no enviamos flash si ya existía.

    requested_id = request.args.get("workspace") or session.get("workspace_id")
    current_workspace = None
    if workspace_slug:
        current_workspace = _select_workspace_by_slug(workspaces, workspace_slug)
    if not current_workspace:
        current_workspace = _select_workspace(workspaces, requested_id)

    files = []
    appointments = []
    upcoming_appointments = []
    members = []
    membership_role = None
    if current_workspace:
        set_workspace_context(current_workspace)
        files = list_files()
        appointments = list_appointments()
        upcoming_appointments = list_upcoming_appointments()
        members = list_members(current_workspace["id"])
        if user_email:
            membership_role = get_member_role(current_workspace["id"], user_email)
    else:
        session.pop("workspace_id", None)
        session.pop("workspace_schema", None)

    return render_template(
        "index.html",
        files=files,
        appointments=appointments,
        appointments_upcoming=upcoming_appointments,
        appointment_statuses=get_status_choices(),
        appointment_status_labels=STATUS_LABELS,
        workspaces=workspaces,
        current_workspace=current_workspace,
        current_user_email=user_email,
        current_user_name=user_name,
        current_membership_role=membership_role,
        workspace_members=members,
    )


@ui_bp.route("/", methods=["GET"])
def index():
    return _render_dashboard()


@ui_bp.route("/w/<slug>", methods=["GET"])
def workspace_by_slug(slug: str):
    workspace = ensure_workspace_from_slug(slug)
    if not workspace:
        flash("Workspace no encontrado", "danger")
        return redirect(url_for("ui.index"))

    # URL canónica: usar schema_name (ej: ws_<slug>_<hash>) para incluir el id/hash del workspace.
    canonical = workspace.get("schema_name")
    if canonical and slug != canonical:
        return redirect(url_for("ui.workspace_by_slug", slug=canonical))
    return _render_dashboard(workspace_slug=slug)


@ui_bp.route("/workspaces", methods=["POST"])
def create_workspace_route():
    try:
        require_authenticated_request()
    except AuthError as ex:
        flash(str(ex), "danger")
        return redirect(url_for("ui.index"))
    name = (request.form.get("workspace_name") or "").strip()
    owner_email = (request.form.get("owner_email") or "").strip()
    owner_name = (request.form.get("owner_name") or "").strip() or None
    description = (request.form.get("workspace_description") or "").strip() or None
    slug_hint = (request.form.get("workspace_slug") or "").strip() or None

    if is_auth_required():
        session_email, session_name = _resolve_current_user()
        owner_email = session_email or owner_email
        owner_name = session_name or owner_name

    if not owner_email:
        fallback_email, fallback_name = _resolve_current_user()
        owner_email = owner_email or fallback_email
        owner_name = owner_name or fallback_name

    if not name or not owner_email:
        flash("Nombre y correo son obligatorios", "danger")
        return redirect(url_for("ui.index"))

    try:
        workspace = create_workspace(name, owner_email, owner_name, description, slug_hint=slug_hint)
        flash(f"Workspace {workspace['name']} creado", "success")
        return redirect(url_for("ui.workspace_by_slug", slug=workspace["slug"]))
    except ValueError as ve:
        flash(str(ve), "danger")
        return redirect(url_for("ui.index"))
    except Exception as ex:
        flash(f"No se pudo crear el workspace: {ex}", "danger")
        return redirect(url_for("ui.index"))


@ui_bp.route("/workspaces/<workspace_id>/delete", methods=["POST"])
@ui_bp.route("/workspaces/delete", methods=["POST"])
def delete_workspace_route(workspace_id: str = None):
    try:
        require_authenticated_request()
    except AuthError as ex:
        flash(str(ex), "danger")
        return redirect(url_for("ui.index"))
    target_id = workspace_id or request.form.get("workspace_id")
    if not target_id:
        flash("Selecciona un workspace para eliminar.", "warning")
        return redirect(url_for("ui.index"))
    user_email, _ = _resolve_current_user()
    role = get_member_role(target_id, user_email) if user_email else None
    if role != "owner":
        flash("Solo el owner puede eliminar este workspace.", "danger")
        return redirect(url_for("ui.index"))

    # Validación extra: frase de confirmación
    phrase = (request.form.get("confirmation_phrase") or "").strip().lower()
    if phrase != "eliminar esta area trabajo":
        flash("Debes escribir la frase exacta para confirmar.", "danger")
        return redirect(url_for("ui.index"))

    deleted = delete_workspace(target_id)
    if not deleted:
        flash("Workspace no encontrado", "warning")
        return redirect(url_for("ui.index"))

    # Si el workspace eliminado era el actual, limpiar contexto
    if session.get("workspace_id") == target_id:
        session.pop("workspace_id", None)
        session.pop("workspace_schema", None)
        g.workspace_id = None
        g.workspace_schema = None

    flash(f"Workspace {deleted.get('name') or deleted.get('slug')} eliminado", "success")
    return redirect(url_for("ui.index"))


@ui_bp.route("/w/<slug>/api/invites", methods=["POST"])
def create_invite_api(slug: str):
    try:
        require_authenticated_request()
    except AuthError as ex:
        return jsonify({"error": ex.code, "message": str(ex)}), ex.status_code
    workspace = ensure_workspace_from_slug(slug)
    if not workspace:
        return jsonify({"error": "workspace_not_found"}), 404

    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    expires_raw = payload.get("expires_in_days")
    expires_in_days = None
    if expires_raw is not None and expires_raw != "":
        try:
            expires_in_days = int(expires_raw)
        except Exception:
            return jsonify({"error": "expires_in_days_invalido"}), 400
        if expires_in_days < 0:
            expires_in_days = None

    inviter_email, inviter_name = _resolve_current_user()

    if not email:
        return jsonify({"error": "email_requerido"}), 400

    try:
        invite = create_invite(
            workspace["id"],
            email,
            invited_by_email=inviter_email,
            invited_by_name=inviter_name,
            expires_in_days=expires_in_days,
        )
        return (
            jsonify(
                {
                    "invite": invite,
                    "workspace": {
                        "id": workspace["id"],
                        "slug": workspace["slug"],
                        "name": workspace["name"],
                    },
                }
            ),
            201,
        )
    except ValueError as ex:
        message = str(ex)
        status = 400
        if message == "already_member":
            status = 409
            message = "El usuario ya es miembro de este workspace."
        return jsonify({"error": message}), status
    except LookupError:
        return jsonify({"error": "workspace_not_found"}), 404
    except Exception as ex:
        return jsonify({"error": f"no_se_pudo_crear: {ex}"}), 500


@ui_bp.route("/session/clerk", methods=["POST", "OPTIONS", "DELETE"], provide_automatic_options=False)
def set_clerk_session():
    if request.method == "OPTIONS":
        return make_response("", 204)
    if request.method == "DELETE":
        for key in [
            "current_user_email",
            "current_user_name",
            "current_user_role",
            "current_user_clerk_id",
            "current_membership_role",
            "workspace_id",
            "workspace_schema",
        ]:
            session.pop(key, None)
        return jsonify({"ok": True})

    auth_header = request.headers.get("Authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return jsonify({"error": "token_requerido"}), 401

    try:
        identity = resolve_user_from_token(token)
    except AuthError as ex:
        return jsonify({"error": ex.code, "message": str(ex)}), ex.status_code

    payload = request.get_json(silent=True) or {}
    role = (payload.get("role") or "").strip() or None

    email = identity["email"]
    name = identity.get("name")
    clerk_id = identity.get("clerk_id")

    session["current_user_email"] = email
    session["current_user_name"] = name
    session["current_user_clerk_id"] = clerk_id
    if role:
        session["current_user_role"] = role
    else:
        session.setdefault("current_user_role", "Miembro")

    ensure_default_workspace_for_user(email, name)
    return jsonify({"ok": True})


@ui_bp.route("/api/invites/accept", methods=["POST"])
def accept_invite_api():
    try:
        require_authenticated_request()
    except AuthError as ex:
        return jsonify({"error": ex.code, "message": str(ex)}), ex.status_code
    payload = request.get_json(silent=True) or {}
    code = (payload.get("code") or "").strip()
    email = (payload.get("email") or "").strip()
    name = (payload.get("name") or "").strip() or None

    if is_auth_required():
        session_email, session_name = _resolve_current_user()
        if session_email:
            if email and email.strip().lower() != session_email.strip().lower():
                return jsonify({"error": "email_no_coincide_con_sesion"}), 403
            email = session_email
        if session_name and not name:
            name = session_name

    # Fallback al usuario actual si no envian email
    if not email:
        email, name = _resolve_current_user()

    if not code or not email:
        return jsonify({"error": "code_y_email_requeridos"}), 400

    try:
        result = accept_invite(code, email, name)
        # Actualizar sesion y contexto de workspace
        session["current_user_email"] = result["user"]["email"]
        if name:
            session["current_user_name"] = name
        else:
            session["current_user_name"] = result["user"].get("display_name")
        set_workspace_context(result["workspace"])
        return jsonify(result)
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError as ex:
        return jsonify({"error": str(ex)}), 404
    except Exception as ex:
        return jsonify({"error": f"no_se_pudo_aceptar: {ex}"}), 500


@ui_bp.route("/w/<slug>/api/members/remove", methods=["POST"])
def remove_member_api(slug: str):
    try:
        require_authenticated_request()
    except AuthError as ex:
        return jsonify({"error": ex.code, "message": str(ex)}), ex.status_code
    workspace = ensure_workspace_from_slug(slug)
    if not workspace:
        return jsonify({"error": "workspace_not_found"}), 404
    payload = request.get_json(silent=True) or {}
    target_email = (payload.get("email") or "").strip()
    acting_email, _ = _resolve_current_user()
    try:
        removed = remove_member(workspace["id"], target_email, acting_email)
        return jsonify({"removed": removed})
    except PermissionError as ex:
        return jsonify({"error": str(ex)}), 403
    except LookupError as ex:
        return jsonify({"error": str(ex)}), 404
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except Exception as ex:
        return jsonify({"error": f"no_se_puede_remover: {ex}"}), 500

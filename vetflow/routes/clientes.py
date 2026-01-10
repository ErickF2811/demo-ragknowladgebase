import logging

from flask import Blueprint, jsonify, request

from ..auth import AuthError, require_authenticated_request
from ..services import clientes as clientes_service
from .ui import ensure_workspace_from_slug

logger = logging.getLogger(__name__)

clientes_bp = Blueprint("clientes", __name__)


@clientes_bp.before_request
def _auth_guard():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        require_authenticated_request()
    except AuthError as ex:
        return jsonify({"error": ex.code, "message": str(ex)}), ex.status_code


def _json():
    return request.get_json(silent=True) or {}


@clientes_bp.route("/w/<slug>/api/clientes", methods=["GET"])
def api_clientes_list(slug: str):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    q = request.args.get("q")
    limit = request.args.get("limit") or 200
    try:
        limit_int = int(limit)
    except Exception:
        limit_int = 200
    items = clientes_service.list_clients(q, limit=limit_int)
    return jsonify({"clients": items})


@clientes_bp.route("/w/<slug>/api/clientes", methods=["POST"])
def api_clientes_create(slug: str):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload = _json()
    try:
        row = clientes_service.create_client(payload)
        return jsonify({"client": row}), 201
    except clientes_service.DuplicateClientError as ex:
        return jsonify({"error": "cliente_ya_existe", "existing_client_id": ex.existing_client_id}), 409
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except Exception as ex:
        logger.exception("Error creando cliente slug=%s", slug)
        return jsonify({"error": f"error_interno: {ex}"}), 500


@clientes_bp.route("/w/<slug>/api/clientes/<int:client_id>", methods=["GET"])
def api_clientes_get(slug: str, client_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    try:
        data = clientes_service.get_client(client_id)
        return jsonify(data)
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    except Exception as ex:
        logger.exception("Error obteniendo cliente slug=%s id=%s", slug, client_id)
        return jsonify({"error": f"error_interno: {ex}"}), 500


@clientes_bp.route("/w/<slug>/api/clientes/<int:client_id>", methods=["PUT"])
def api_clientes_update(slug: str, client_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload = _json()
    try:
        row = clientes_service.update_client(client_id, payload)
        return jsonify({"client": row})
    except clientes_service.DuplicateClientError as ex:
        return jsonify({"error": "cliente_ya_existe", "existing_client_id": ex.existing_client_id}), 409
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    except Exception as ex:
        logger.exception("Error actualizando cliente slug=%s id=%s", slug, client_id)
        return jsonify({"error": f"error_interno: {ex}"}), 500


@clientes_bp.route("/w/<slug>/api/clientes/<int:client_id>", methods=["DELETE"])
def api_clientes_delete(slug: str, client_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    try:
        clientes_service.delete_client(client_id)
        return jsonify({"ok": True})
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    except Exception as ex:
        logger.exception("Error eliminando cliente slug=%s id=%s", slug, client_id)
        return jsonify({"error": f"error_interno: {ex}"}), 500


@clientes_bp.route("/w/<slug>/api/clientes/<int:client_id>/notas", methods=["POST"])
def api_clientes_add_note(slug: str, client_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload = _json()
    try:
        note = clientes_service.add_note(client_id, payload.get("body"))
        return jsonify({"note": note}), 201
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    except Exception as ex:
        logger.exception("Error agregando nota slug=%s id=%s", slug, client_id)
        return jsonify({"error": f"error_interno: {ex}"}), 500


@clientes_bp.route("/w/<slug>/api/clientes/<int:client_id>/citas", methods=["POST"])
def api_clientes_create_appt(slug: str, client_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload = _json()
    try:
        appt = clientes_service.create_appointment_for_client(client_id, payload)
        return jsonify({"appointment": appt}), 201
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError:
        return jsonify({"error": "not_found"}), 404
    except Exception as ex:
        logger.exception("Error creando cita slug=%s client_id=%s", slug, client_id)
        return jsonify({"error": f"error_interno: {ex}"}), 500

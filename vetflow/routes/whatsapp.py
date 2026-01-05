import logging

from flask import Blueprint, jsonify, request, session

from ..auth import AuthError, require_authenticated_request
from ..config import config
from ..services.evolution import (
    EvolutionApiError,
    ensure_instance_and_get_qr,
    get_instance_status,
    logout_instance,
)
from .ui import ensure_workspace_from_slug

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.before_request
def _auth_guard():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        require_authenticated_request()
    except AuthError as ex:
        return jsonify({"error": ex.code, "message": str(ex)}), ex.status_code


def _current_workspace_slug_from_session():
    schema = session.get("workspace_schema")
    workspace_id = session.get("workspace_id")
    if not schema or not workspace_id:
        return None
    # No tenemos el slug en session; para UI usamos el endpoint /w/<slug>/...
    return None


@whatsapp_bp.route("/api/whatsapp/qr", methods=["GET"])
def api_whatsapp_qr_current():
    # Mantener este endpoint por si llaman sin /w/<slug>, pero preferimos /w/<slug>/api/...
    return jsonify({"error": "usa /w/<slug>/api/whatsapp/qr"}), 400


@whatsapp_bp.route("/w/<slug>/api/whatsapp/qr", methods=["GET"])
def api_whatsapp_qr(slug: str):
    workspace = ensure_workspace_from_slug(slug)
    if not workspace:
        return jsonify({"error": "workspace_not_found"}), 404

    # Usar el schema real del workspace (ej: ws_<slug>_<hash>) para que Evolution
    # tenga una instancia única por workspace y coincida con lo que ves en la BD.
    instance_name = workspace.get("schema_name") or workspace.get("slug") or slug
    logger.info(
        "WhatsApp QR request slug=%s instance=%s ip=%s ua=%s",
        slug,
        instance_name,
        request.headers.get("X-Forwarded-For") or request.remote_addr,
        (request.headers.get("User-Agent") or "")[:120],
    )
    try:
        result = ensure_instance_and_get_qr(instance_name)

        if result.get("already_connected"):
            logger.info("WhatsApp QR already_connected slug=%s instance=%s", slug, instance_name)
            return jsonify({
                "ok": False,
                "error": "instance_already_connected",
                "message": "La instancia ya está conectada. Refresca el estado."
            }), 409

        logger.info(
            "WhatsApp QR ok slug=%s instance=%s created=%s",
            slug,
            result.get("instance_name"),
            result.get("created"),
        )

        return jsonify(
            {
                "ok": True,
                "instance_name": result["instance_name"],
                "created": result["created"],
                "qr_base64": result["qr_base64"],
                "qr_data_url": result["qr_data_url"],
            }
        )
    except EvolutionApiError as ex:
        logger.warning("WhatsApp QR error slug=%s instance=%s error=%s", slug, instance_name, ex)
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        logger.exception("Error obteniendo QR evolution slug=%s", slug)
        return jsonify({"ok": False, "error": f"error_interno: {ex}"}), 500


@whatsapp_bp.route("/w/<slug>/api/whatsapp/status", methods=["GET"])
def api_whatsapp_status(slug: str):
    workspace = ensure_workspace_from_slug(slug)
    if not workspace:
        return jsonify({"error": "workspace_not_found"}), 404

    instance_name = workspace.get("schema_name") or workspace.get("slug") or slug
    logger.debug(
        "WhatsApp status request slug=%s instance=%s ip=%s",
        slug,
        instance_name,
        request.headers.get("X-Forwarded-For") or request.remote_addr,
    )
    try:
        status = get_instance_status(instance_name)
        logger.info(
            "WhatsApp status ok slug=%s instance=%s connected=%s state=%s",
            slug,
            instance_name,
            status.get("connected"),
            status.get("state"),
        )
        return jsonify(
            {
                "ok": True,
                "instance_name": instance_name,
                "connected": status.get("connected"),
                "state": status.get("state"),
                "details": status.get("details") or {},
            }
        )
    except EvolutionApiError as ex:
        logger.warning("WhatsApp status error slug=%s instance=%s error=%s", slug, instance_name, ex)
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        logger.exception("Error consultando estado evolution slug=%s", slug)
        return jsonify({"ok": False, "error": f"error_interno: {ex}"}), 500


@whatsapp_bp.route("/w/<slug>/api/whatsapp/logout", methods=["POST"])
def api_whatsapp_logout(slug: str):
    workspace = ensure_workspace_from_slug(slug)
    if not workspace:
        return jsonify({"error": "workspace_not_found"}), 404

    instance_name = workspace.get("schema_name") or workspace.get("slug") or slug
    logger.info(
        "WhatsApp logout request slug=%s instance=%s ip=%s",
        slug,
        instance_name,
        request.headers.get("X-Forwarded-For") or request.remote_addr,
    )
    try:
        result = logout_instance(instance_name)
        return jsonify({"ok": True, "instance_name": instance_name, "result": result})
    except EvolutionApiError as ex:
        logger.warning("WhatsApp logout error slug=%s instance=%s error=%s", slug, instance_name, ex)
        return jsonify({"ok": False, "error": str(ex)}), 400
    except Exception as ex:
        logger.exception("Error logout evolution slug=%s", slug)
        return jsonify({"ok": False, "error": f"error_interno: {ex}"}), 500


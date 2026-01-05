import json
import logging
from flask import Blueprint, flash, jsonify, redirect, request, url_for

from ..services import calendar as calendar_service
from .ui import ensure_workspace_from_slug

calendar_bp = Blueprint("calendar", __name__)
logger = logging.getLogger(__name__)


def _parse_payload():
    """
    Intenta parsear el body en varios modos (JSON, raw, form) y devuelve (payload, fuente).
    Permite solicitudes desde cmd/PowerShell que a veces mandan comillas simples.
    """
    payload = request.get_json(silent=True)
    if payload:
        return payload, "request.get_json"

    raw = (request.get_data(as_text=True) or "").strip()
    if raw:
        try:
            return json.loads(raw), "json.loads(raw)"
        except Exception:
            if "'" in raw and '"' not in raw:
                try:
                    return json.loads(raw.replace("'", '"')), "json.loads(raw single->double)"
                except Exception:
                    logger.warning("No se pudo parsear JSON con single quotes body=%s", raw)
            else:
                logger.warning("No se pudo parsear JSON body=%s", raw)

    form_payload = request.form.to_dict() or {}
    if form_payload:
        return form_payload, "form"
    return {}, "empty"


@calendar_bp.route("/calendar", methods=["POST"])
def create_calendar():
    title = request.form.get("title")
    description = request.form.get("description")
    start_raw = request.form.get("start_time")
    end_raw = request.form.get("end_time")
    status_raw = request.form.get("status")
    timezone_raw = request.form.get("timezone")
    client_id_raw = request.form.get("client_id")
    client_id = None
    if client_id_raw not in (None, ""):
        try:
            client_id = int(client_id_raw)
        except Exception:
            flash("Cliente invalido", "danger")
            return redirect(url_for("ui.index"))

    if not title or not start_raw or not end_raw:
        flash("Titulo, inicio y fin son obligatorios", "danger")
        return redirect(url_for("ui.index"))

    try:
        calendar_service.create_appointment(title, description, start_raw, end_raw, status_raw, timezone_raw, client_id)
    except ValueError as ex:
        flash(str(ex), "danger")
        return redirect(url_for("ui.index"))

    flash("Cita creada", "success")
    return redirect(url_for("ui.index"))


@calendar_bp.route("/calendar/<int:appointment_id>/update", methods=["POST"])
def update_calendar(appointment_id: int):
    title = request.form.get("title")
    description = request.form.get("description")
    start_raw = request.form.get("start_time")
    end_raw = request.form.get("end_time")
    status_raw = request.form.get("status")
    timezone_raw = request.form.get("timezone")
    client_id_raw = request.form.get("client_id")
    client_id = None
    if client_id_raw not in (None, ""):
        try:
            client_id = int(client_id_raw)
        except Exception:
            flash("Cliente invalido", "danger")
            return redirect(url_for("ui.index"))
    try:
        updated = calendar_service.update_appointment(
            appointment_id, title, description, start_raw, end_raw, status_raw, timezone_raw, client_id
        )
    except ValueError as ex:
        flash(str(ex), "danger")
        return redirect(url_for("ui.index"))
    if updated:
        flash("Cita actualizada", "success")
    else:
        flash("Cita no encontrada", "danger")
    return redirect(url_for("ui.index"))


@calendar_bp.route("/calendar/<int:appointment_id>/delete", methods=["POST"])
def delete_calendar(appointment_id: int):
    deleted = calendar_service.delete_appointment(appointment_id)
    if deleted:
        flash("Cita eliminada", "success")
    else:
        flash("Cita no encontrada", "danger")
    return redirect(url_for("ui.index"))


# --- API JSON para agentes/IA ---


@calendar_bp.route("/api/calendar", methods=["GET"])
def api_calendar_list():
    return jsonify(calendar_service.api_list())

@calendar_bp.route("/w/<slug>/api/calendar", methods=["GET"])
def api_calendar_list_ws(slug: str):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    return jsonify(calendar_service.api_list())


@calendar_bp.route("/api/calendar/<int:appointment_id>", methods=["GET"])
def api_calendar_get(appointment_id: int):
    try:
        return jsonify(calendar_service.api_get(appointment_id))
    except LookupError:
        return jsonify({"error": "not_found"}), 404


@calendar_bp.route("/w/<slug>/api/calendar/<int:appointment_id>", methods=["GET"])
def api_calendar_get_ws(slug: str, appointment_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    try:
        return jsonify(calendar_service.api_get(appointment_id))
    except LookupError:
        return jsonify({"error": "not_found"}), 404


@calendar_bp.route("/api/calendar", methods=["POST"])
def api_calendar_create():
    payload, source = _parse_payload()
    logger.info("API calendar create source=%s payload=%s", source, payload)
    try:
        row = calendar_service.api_create(payload)
        return jsonify(row), 201
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400


@calendar_bp.route("/w/<slug>/api/calendar", methods=["POST"])
def api_calendar_create_ws(slug: str):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload, source = _parse_payload()
    logger.info("API calendar create slug=%s source=%s payload=%s", slug, source, payload)
    try:
        row = calendar_service.api_create(payload)
        return jsonify(row), 201
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400


@calendar_bp.route("/api/calendar/<int:appointment_id>", methods=["PUT"])
def api_calendar_update(appointment_id: int):
    payload, source = _parse_payload()
    logger.info("API calendar update id=%s source=%s payload=%s", appointment_id, source, payload)
    try:
        row = calendar_service.api_update(appointment_id, payload)
        return jsonify(row)
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError:
        return jsonify({"error": "not_found"}), 404


@calendar_bp.route("/w/<slug>/api/calendar/<int:appointment_id>", methods=["PUT"])
def api_calendar_update_ws(slug: str, appointment_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload, source = _parse_payload()
    logger.info("API calendar update slug=%s id=%s source=%s payload=%s", slug, appointment_id, source, payload)
    try:
        row = calendar_service.api_update(appointment_id, payload)
        return jsonify(row)
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError:
        return jsonify({"error": "not_found"}), 404


@calendar_bp.route("/api/calendar/<int:appointment_id>", methods=["DELETE"])
def api_calendar_delete(appointment_id: int):
    try:
        return jsonify(calendar_service.api_delete(appointment_id))
    except LookupError:
        return jsonify({"error": "not_found"}), 404


@calendar_bp.route("/w/<slug>/api/calendar/<int:appointment_id>", methods=["DELETE"])
def api_calendar_delete_ws(slug: str, appointment_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    try:
        return jsonify(calendar_service.api_delete(appointment_id))
    except LookupError:
        return jsonify({"error": "not_found"}), 404

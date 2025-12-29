import logging
from flask import Blueprint, jsonify, redirect, request, flash, url_for

from ..services.files import (
    create_file,
    delete_file,
    notify_ingest_webhook,
    sas_for_file,
    send_to_n8n,
    update_file_metadata,
)
from .ui import ensure_workspace_from_slug

logger = logging.getLogger(__name__)

files_bp = Blueprint("files", __name__)


@files_bp.route("/upload", methods=["POST"])
def upload_file():
    uploaded_files = [f for f in request.files.getlist("file") if f and f.filename]
    if not uploaded_files:
        flash("Selecciona al menos un archivo", "danger")
        return redirect(url_for("ui.index"))

    tags_raw = request.form.get("tags")
    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else None
    notes = request.form.get("notes")

    successes = 0
    errors = []
    for item in uploaded_files:
        try:
            file_info = create_file(
                item,
                tags_list,
                notes,
                item.content_length or request.content_length,
            )
            notify_ingest_webhook(file_info)
            successes += 1
        except Exception as ex:
            logger.exception("Error subiendo a Blob/DB para %s", getattr(item, "filename", "archivo"))
            errors.append(f"{getattr(item, 'filename', 'archivo')}: {ex}")

    if successes:
        plural = "Archivo" if successes == 1 else "Archivos"
        flash(f"{plural} cargado(s): {successes}", "success")
    if errors:
        flash("Errores subiendo: " + "; ".join(errors), "danger")
    return redirect(url_for("ui.index"))


@files_bp.route("/file/<int:file_id>/sas")
def file_sas(file_id: int):
    try:
        sas_url = sas_for_file(file_id)
        return jsonify({"url": sas_url})
    except LookupError:
        return jsonify({"error": "No encontrado"}), 404
    except Exception as ex:
        return jsonify({"error": f"No se pudo generar SAS: {ex}"}), 500


@files_bp.route("/w/<slug>/file/<int:file_id>/sas")
def file_sas_ws(slug: str, file_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    try:
        sas_url = sas_for_file(file_id)
        return jsonify({"url": sas_url})
    except LookupError:
        return jsonify({"error": "No encontrado"}), 404
    except Exception as ex:
        return jsonify({"error": f"No se pudo generar SAS: {ex}"}), 500


@files_bp.route("/files/<int:file_id>/delete", methods=["POST"])
def delete_file_route(file_id: int):
    ok, err, _, webhook_msg = delete_file(file_id)
    if not ok:
        flash("Archivo no encontrado", "danger")
        return redirect(url_for("ui.index"))
    if webhook_msg:
        flash(f"Eliminacion enviada a n8n: {webhook_msg}", "warning")
    else:
        flash("Archivo marcado como eliminando y notificado a n8n", "warning")
    return redirect(url_for("ui.index"))


@files_bp.route("/api/files/<int:file_id>", methods=["DELETE"])
def api_delete_file(file_id: int):
    ok, err, blob_path, webhook_msg = delete_file(file_id)
    if not ok:
        return jsonify({"error": err}), 404
    return (
        jsonify(
            {
                "deleted": file_id,
                "blob_path": blob_path,
                "status": "deleting",
                "webhook_message": webhook_msg,
                "message": "Eliminacion solicitada; pendiente de webhook n8n",
            }
        ),
        202,
    )

@files_bp.route("/w/<slug>/api/files/<int:file_id>", methods=["DELETE"])
def api_delete_file_ws(slug: str, file_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    ok, err, blob_path, webhook_msg = delete_file(file_id)
    if not ok:
        return jsonify({"error": err}), 404
    return (
        jsonify(
            {
                "deleted": file_id,
                "blob_path": blob_path,
                "status": "deleting",
                "webhook_message": webhook_msg,
                "message": "Eliminacion solicitada; pendiente de webhook n8n",
            }
        ),
        202,
    )


@files_bp.route("/files/<int:file_id>/send-to-n8n", methods=["POST"])
def send_to_n8n_route(file_id: int):
    ok, message = send_to_n8n(file_id)
    if ok:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for("ui.index"))


@files_bp.route("/api/files/<int:file_id>", methods=["PUT"])
def api_update_file(file_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    try:
        row = update_file_metadata(file_id, payload)
        return jsonify(row)
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError as ex:
        return jsonify({"error": str(ex)}), 404


@files_bp.route("/w/<slug>/api/files/<int:file_id>", methods=["PUT"])
def api_update_file_ws(slug: str, file_id: int):
    if not ensure_workspace_from_slug(slug):
        return jsonify({"error": "workspace_not_found"}), 404
    payload = request.get_json(force=True, silent=True) or {}
    try:
        row = update_file_metadata(file_id, payload)
        return jsonify(row)
    except ValueError as ex:
        return jsonify({"error": str(ex)}), 400
    except LookupError as ex:
        return jsonify({"error": str(ex)}), 404

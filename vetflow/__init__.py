import logging
from pathlib import Path

from flask import Flask, g, session, request

from .config import config
from .routes.calendar import calendar_bp
from .routes.files import files_bp
from .routes.health import health_bp
from .routes.ui import ui_bp
from .routes.whatsapp import whatsapp_bp


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def create_app() -> Flask:
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )
    app.secret_key = config.SECRET_KEY

    app.register_blueprint(ui_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(whatsapp_bp)

    @app.context_processor
    def inject_globals():
        return {
            "clerk_publishable_key": config.CLERK_PUBLISHABLE_KEY,
            "current_user_name": session.get("current_user_name"),
            "current_user_role": session.get("current_user_role", "Invitado"),
        }

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        allow_any = not config.CORS_ALLOWED_ORIGINS
        if origin and (allow_any or origin in config.CORS_ALLOWED_ORIGINS):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        return response

    @app.before_request
    def _load_workspace_context():
        workspace_schema = session.get("workspace_schema")
        workspace_id = session.get("workspace_id")
        if workspace_schema:
            g.workspace_schema = workspace_schema
        if workspace_id:
            g.workspace_id = workspace_id

    return app

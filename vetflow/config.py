import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self) -> None:
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.AZURE_BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONN_STR", "")
        self.AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "uploads")
        self.POSTGRES_DSN = os.getenv("POSTGRES_DSN", "")
        self.N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
        self.N8N_DELETE_WEBHOOK_URL = os.getenv("N8N_DELETE_WEBHOOK_URL", "")
        self.N8N_NEW_WORKSPACE_WEBHOOK_URL = os.getenv("N8N_NEW_WORKSPACE_WEBHOOK_URL", "")
        self.EVOLUTION_API_BASE_URL = os.getenv("EVOLUTION_API_BASE_URL", "")
        self.EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
        # En Evolution Manager el "Channel" se muestra como "Baileys"
        self.EVOLUTION_API_INTEGRATION = os.getenv("EVOLUTION_API_INTEGRATION", "Baileys")
        rabbitmq_enabled = os.getenv("EVOLUTION_RABBITMQ_ENABLED", "1").lower().strip()
        self.EVOLUTION_RABBITMQ_ENABLED = rabbitmq_enabled in ("1", "true", "yes", "on")
        rabbitmq_events_raw = os.getenv("EVOLUTION_RABBITMQ_EVENTS", "").strip()
        self.EVOLUTION_RABBITMQ_EVENTS = [e.strip() for e in rabbitmq_events_raw.split(",") if e.strip()] if rabbitmq_events_raw else []
        self.DB_SCHEMA = os.getenv("DB_SCHEMA", "vetbot")
        self.CORE_SCHEMA = os.getenv("CORE_SCHEMA", "vetflow_core")
        self.WORKSPACE_SCHEMA_PREFIX = os.getenv("WORKSPACE_SCHEMA_PREFIX", "ws")
        self.DEFAULT_OWNER_EMAIL = os.getenv("DEFAULT_OWNER_EMAIL", "demo@vetflow.local")
        self.DEFAULT_OWNER_NAME = os.getenv("DEFAULT_OWNER_NAME", "Demo Vetflow")
        clerk_key = os.getenv("CLERK_PUBLISHABLE_KEY")
        if not clerk_key:
            clerk_key = os.getenv("VITE_CLERK_PUBLISHABLE_KEY", "")
        self.CLERK_PUBLISHABLE_KEY = clerk_key
        self.CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "")
        self.CLERK_ISSUER = os.getenv("CLERK_ISSUER", "")
        self.CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "")
        auth_required_default = "1" if self.CLERK_PUBLISHABLE_KEY else "0"
        auth_required_raw = os.getenv("CLERK_AUTH_REQUIRED", auth_required_default).lower().strip()
        self.CLERK_AUTH_REQUIRED = auth_required_raw in ("1", "true", "yes", "on")
        self.VETFLOW_API_KEY = os.getenv("VETFLOW_API_KEY", "")
        cors_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
        self.CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_raw.split(",") if o.strip()]
        self.API_HOST = os.getenv("API_HOST", "0.0.0.0")
        self.API_PORT = int(os.getenv("API_PORT", 5000))
        self.SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret")
        self.APP_TIMEZONE = os.getenv("APP_TIMEZONE", "UTC")
        auto_workspace = os.getenv("AUTO_CREATE_DEFAULT_WORKSPACE", "0").lower()
        self.AUTO_CREATE_DEFAULT_WORKSPACE = auto_workspace in ("1", "true", "yes", "on")


config = Config()

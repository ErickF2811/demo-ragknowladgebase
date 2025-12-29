
import os
from vetflow.db import get_db
from vetflow.config import config
from vetflow.bootstrap import ensure_core_bootstrap

# Force loading env vars if not loaded? 
# Assuming environment is set or .env file is present.
# We'll use the existing app context if needed or just connect.

print(f"Connecting to DB: {config.POSTGRES_DSN}")
ensure_core_bootstrap()

with open("debug_output.txt", "w", encoding="utf-8") as f:
    with get_db(schema=config.CORE_SCHEMA) as conn:
        f.write("--- USERS ---\n")
        users = conn.execute("SELECT * FROM app_users").fetchall()
        for u in users:
            f.write(str(dict(u)) + "\n")

        f.write("\n--- WORKSPACES ---\n")
        workspaces = conn.execute("SELECT * FROM workspaces").fetchall()
        for w in workspaces:
            f.write(str(dict(w)) + "\n")

        f.write("\n--- MEMBERS ---\n")
        members = conn.execute("SELECT * FROM workspace_members").fetchall()
        for m in members:
            f.write(str(dict(m)) + "\n")

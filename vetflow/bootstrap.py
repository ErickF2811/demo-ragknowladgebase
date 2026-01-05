import logging

import psycopg

from .config import config

logger = logging.getLogger(__name__)
_CORE_INITIALIZED = False


def _core_sql_statements():
    schema = config.CORE_SCHEMA
    return [
        'CREATE EXTENSION IF NOT EXISTS "pgcrypto";',
        f"CREATE SCHEMA IF NOT EXISTS {schema};",
        f"SET search_path TO {schema};",
        """
        CREATE TABLE IF NOT EXISTS app_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clerk_id TEXT UNIQUE,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS workspace_membership_roles (
            role TEXT PRIMARY KEY,
            description TEXT
        );
        """,
        """
        INSERT INTO workspace_membership_roles (role, description) VALUES
            ('owner', 'Control total del workspace'),
            ('admin', 'Gestiona miembros y flujos'),
            ('member', 'Acceso regular a archivos y agenda')
        ON CONFLICT (role) DO NOTHING;
        """,
        """
        DO $$
        BEGIN
            CREATE TYPE appointment_status AS ENUM (
                'programada','confirmada','completada','cancelada','no_show'
            );
        EXCEPTION
            WHEN duplicate_object THEN
                NULL;
        END$$;
        """,
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            schema_name TEXT NOT NULL UNIQUE,
            description TEXT,
            theme_color TEXT DEFAULT '#6c47ff',
            icon_url TEXT,
            owner_id UUID NOT NULL REFERENCES app_users(id),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member' REFERENCES workspace_membership_roles(role),
            joined_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (workspace_id, user_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS workspace_invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            invite_code TEXT NOT NULL UNIQUE,
            invited_by UUID REFERENCES app_users(id),
            expires_at TIMESTAMPTZ,
            accepted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        f"""
        CREATE OR REPLACE FUNCTION {schema}.ensure_workspace_schema(p_schema TEXT)
        RETURNS VOID AS $$
        DECLARE
            clean_schema TEXT := regexp_replace(btrim(p_schema), '\\s+', '_', 'g');
        BEGIN
            IF clean_schema IS NULL OR clean_schema = '' THEN
                RAISE EXCEPTION 'Nombre de schema invalido';
            END IF;

            EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', clean_schema);
            EXECUTE format('SET LOCAL search_path TO %I, {schema}, public', clean_schema);

            EXECUTE $files$
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    blob_path TEXT NOT NULL,
                    blob_url TEXT,
                    thumbnail_url TEXT,
                    mime_type TEXT,
                    size_bytes BIGINT,
                    tags TEXT[],
                    notes TEXT,
                    status TEXT DEFAULT 'uploaded',
                    processed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            $files$;

            EXECUTE $appts$
                CREATE TABLE IF NOT EXISTS appointments (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TIMESTAMPTZ NOT NULL,
                    end_time TIMESTAMPTZ NOT NULL,
                    timezone TEXT,
                    client_id INTEGER,
                    status appointment_status NOT NULL DEFAULT 'programada',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            $appts$;

            EXECUTE $clients$
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    id_type TEXT NOT NULL,
                    id_number TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    address TEXT,
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            $clients$;

            EXECUTE $client_notes$
                CREATE TABLE IF NOT EXISTS client_notes (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    body TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            $client_notes$;

            -- Migraciones idempotentes para schemas antiguos
            EXECUTE 'ALTER TABLE IF EXISTS appointments ADD COLUMN IF NOT EXISTS timezone TEXT';
            EXECUTE 'ALTER TABLE IF EXISTS appointments ADD COLUMN IF NOT EXISTS client_id INTEGER';
            EXECUTE 'CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, full_name TEXT NOT NULL, id_type TEXT NOT NULL, id_number TEXT NOT NULL, phone TEXT, email TEXT, address TEXT, notes TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())';
            EXECUTE 'CREATE TABLE IF NOT EXISTS client_notes (id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE, body TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())';
            EXECUTE 'ALTER TABLE IF EXISTS clients ADD COLUMN IF NOT EXISTS id_type TEXT';
            EXECUTE 'ALTER TABLE IF EXISTS clients ADD COLUMN IF NOT EXISTS id_number TEXT';
            BEGIN
                EXECUTE 'ALTER TABLE clients ADD CONSTRAINT clients_identification_required CHECK (coalesce(id_type, '''') IN (''cedula'', ''pasaporte'') AND btrim(coalesce(id_number, '''')) <> '''') NOT VALID';
            EXCEPTION
                WHEN duplicate_object THEN NULL;
                WHEN undefined_table THEN NULL;
                WHEN undefined_column THEN NULL;
            END;
            BEGIN
                EXECUTE 'ALTER TABLE appointments ADD CONSTRAINT appointments_client_id_fkey FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL';
            EXCEPTION
                WHEN duplicate_object THEN NULL;
                WHEN undefined_table THEN NULL;
                WHEN undefined_column THEN NULL;
            END;
        END;
        $$ LANGUAGE plpgsql;
        """,
    ]


def ensure_core_bootstrap():
    global _CORE_INITIALIZED
    if _CORE_INITIALIZED:
        return
    if not config.POSTGRES_DSN:
        raise RuntimeError("Config POSTGRES_DSN requerido para inicializar workspaces")
    logger.info("Inicializando schema central de workspaces si no existe")
    statements = _core_sql_statements()
    with psycopg.connect(config.POSTGRES_DSN) as conn:
        conn.execute("SET search_path TO public;")
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    _CORE_INITIALIZED = True

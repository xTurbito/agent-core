"""Crea/actualiza tablas propias de memoria y metricas del agente."""

import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.settings import settings


MIGRATIONS = [
    (
        1,
        """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;

        CREATE TABLE IF NOT EXISTS agent_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS contact_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source TEXT NOT NULL,
            external_contact_id TEXT,
            phone TEXT,
            email TEXT,
            name TEXT,
            summary TEXT,
            important_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS contact_profiles_external_contact_uidx
            ON contact_profiles(source, external_contact_id)
            WHERE external_contact_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS contact_profiles_phone_idx
            ON contact_profiles(phone)
            WHERE phone IS NOT NULL;

        CREATE INDEX IF NOT EXISTS contact_profiles_email_idx
            ON contact_profiles(email)
            WHERE email IS NOT NULL;
        """,
    ),
    (
        3,
        """
        CREATE TABLE IF NOT EXISTS conversation_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source TEXT NOT NULL,
            external_conversation_id TEXT,
            contact_profile_id UUID REFERENCES contact_profiles(id) ON DELETE SET NULL,
            session_id TEXT NOT NULL,
            status TEXT,
            last_intent TEXT,
            summary TEXT,
            important_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS conversation_profiles_session_uidx
            ON conversation_profiles(session_id);

        CREATE UNIQUE INDEX IF NOT EXISTS conversation_profiles_external_conversation_uidx
            ON conversation_profiles(source, external_conversation_id)
            WHERE external_conversation_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS conversation_profiles_contact_idx
            ON conversation_profiles(contact_profile_id);
        """,
    ),
    (
        4,
        """
        CREATE TABLE IF NOT EXISTS usage_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            source TEXT NOT NULL,
            session_id TEXT,
            external_contact_id TEXT,
            external_conversation_id TEXT,
            status TEXT,
            reason TEXT,
            message_length INTEGER,
            response_length INTEGER,
            latency_ms INTEGER,
            usage_metadata JSONB,
            response_metadata JSONB,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX IF NOT EXISTS usage_logs_timestamp_idx
            ON usage_logs(timestamp);

        CREATE INDEX IF NOT EXISTS usage_logs_session_idx
            ON usage_logs(session_id)
            WHERE session_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS usage_logs_source_status_idx
            ON usage_logs(source, status);
        """,
    ),
    (
        5,
        """
        ALTER TABLE conversation_profiles
            ADD COLUMN IF NOT EXISTS qualification_score INTEGER,
            ADD COLUMN IF NOT EXISTS qualification_label TEXT,
            ADD COLUMN IF NOT EXISTS handoff_recommended BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS handoff_reason TEXT;

        CREATE INDEX IF NOT EXISTS conversation_profiles_handoff_idx
            ON conversation_profiles(handoff_recommended, qualification_score DESC);
        """,
    ),
]


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para configurar la base del agente")

    with psycopg.connect(settings.postgres_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(MIGRATIONS[0][1])
            cur.execute("SELECT version FROM agent_schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

            for version, sql in MIGRATIONS:
                if version in applied:
                    continue

                cur.execute(sql)
                cur.execute(
                    "INSERT INTO agent_schema_migrations (version) VALUES (%s)",
                    (version,),
                )
                print(f"Migracion aplicada: {version}")

    print("Base de datos de la app configurada correctamente.")


if __name__ == "__main__":
    main()

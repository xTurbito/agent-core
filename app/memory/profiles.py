"""Memoria de negocio generica para contactos y conversaciones."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from core.settings import settings


@dataclass(frozen=True)
class ContactProfile:
    id: UUID
    source: str
    external_contact_id: str | None
    phone: str | None
    email: str | None
    name: str | None
    summary: str | None
    important_data: dict[str, Any]
    preferences: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ConversationProfile:
    id: UUID
    source: str
    external_conversation_id: str | None
    contact_profile_id: UUID | None
    session_id: str
    status: str | None
    last_intent: str | None
    summary: str | None
    qualification_score: int | None
    qualification_label: str | None
    handoff_recommended: bool
    handoff_reason: str | None
    important_data: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


def get_or_create_contact_profile(
    *,
    source: str,
    external_contact_id: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ContactProfile:
    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para usar perfiles")

    with psycopg.connect(settings.postgres_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            existing = _find_contact(
                cur,
                source=source,
                external_contact_id=external_contact_id,
                phone=phone,
                email=email,
            )
            if existing:
                cur.execute(
                    """
                    UPDATE contact_profiles
                    SET
                        external_contact_id = COALESCE(external_contact_id, %(external_contact_id)s),
                        phone = COALESCE(phone, %(phone)s),
                        email = COALESCE(email, %(email)s),
                        name = COALESCE(%(name)s, name),
                        metadata = metadata || %(metadata)s,
                        updated_at = now()
                    WHERE id = %(id)s
                    RETURNING *
                    """,
                    {
                        "id": existing["id"],
                        "external_contact_id": external_contact_id,
                        "phone": phone,
                        "email": email,
                        "name": name,
                        "metadata": Jsonb(metadata or {}),
                    },
                )
                row = cur.fetchone()
            else:
                cur.execute(
                    """
                    INSERT INTO contact_profiles (
                        source,
                        external_contact_id,
                        phone,
                        email,
                        name,
                        metadata
                    )
                    VALUES (
                        %(source)s,
                        %(external_contact_id)s,
                        %(phone)s,
                        %(email)s,
                        %(name)s,
                        %(metadata)s
                    )
                    RETURNING *
                    """,
                    {
                        "source": source,
                        "external_contact_id": external_contact_id,
                        "phone": phone,
                        "email": email,
                        "name": name,
                        "metadata": Jsonb(metadata or {}),
                    },
                )
                row = cur.fetchone()

    return _contact_from_row(row)


def get_or_create_conversation_profile(
    *,
    source: str,
    session_id: str,
    external_conversation_id: str | None = None,
    contact_profile_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConversationProfile:
    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para usar perfiles")

    with psycopg.connect(settings.postgres_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_profiles (
                    source,
                    external_conversation_id,
                    contact_profile_id,
                    session_id,
                    metadata
                )
                VALUES (
                    %(source)s,
                    %(external_conversation_id)s,
                    %(contact_profile_id)s,
                    %(session_id)s,
                    %(metadata)s
                )
                ON CONFLICT (session_id)
                DO UPDATE SET
                    external_conversation_id = COALESCE(
                        conversation_profiles.external_conversation_id,
                        EXCLUDED.external_conversation_id
                    ),
                    contact_profile_id = COALESCE(
                        conversation_profiles.contact_profile_id,
                        EXCLUDED.contact_profile_id
                    ),
                    metadata = conversation_profiles.metadata || EXCLUDED.metadata,
                    updated_at = now()
                RETURNING *
                """,
                {
                    "source": source,
                    "external_conversation_id": external_conversation_id,
                    "contact_profile_id": contact_profile_id,
                    "session_id": session_id,
                    "metadata": Jsonb(metadata or {}),
                },
            )
            row = cur.fetchone()

    return _conversation_from_row(row)


def update_conversation_profile(
    *,
    session_id: str,
    status: str | None = None,
    last_intent: str | None = None,
    summary: str | None = None,
    qualification_score: int | None = None,
    qualification_label: str | None = None,
    handoff_recommended: bool | None = None,
    handoff_reason: str | None = None,
    important_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConversationProfile | None:
    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para usar perfiles")

    with psycopg.connect(settings.postgres_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversation_profiles
                SET
                    status = COALESCE(%(status)s, status),
                    last_intent = COALESCE(%(last_intent)s, last_intent),
                    summary = COALESCE(%(summary)s, summary),
                    qualification_score = COALESCE(%(qualification_score)s, qualification_score),
                    qualification_label = COALESCE(%(qualification_label)s, qualification_label),
                    handoff_recommended = COALESCE(%(handoff_recommended)s, handoff_recommended),
                    handoff_reason = COALESCE(%(handoff_reason)s, handoff_reason),
                    important_data = important_data || %(important_data)s,
                    metadata = metadata || %(metadata)s,
                    updated_at = now()
                WHERE session_id = %(session_id)s
                RETURNING *
                """,
                {
                    "session_id": session_id,
                    "status": status,
                    "last_intent": last_intent,
                    "summary": summary,
                    "qualification_score": qualification_score,
                    "qualification_label": qualification_label,
                    "handoff_recommended": handoff_recommended,
                    "handoff_reason": handoff_reason,
                    "important_data": Jsonb(important_data or {}),
                    "metadata": Jsonb(metadata or {}),
                },
            )
            row = cur.fetchone()

    if not row:
        return None

    return _conversation_from_row(row)


def get_conversation_profile(session_id: str) -> ConversationProfile | None:
    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para usar perfiles")

    with psycopg.connect(settings.postgres_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM conversation_profiles
                WHERE session_id = %(session_id)s
                LIMIT 1
                """,
                {"session_id": session_id},
            )
            row = cur.fetchone()

    if not row:
        return None

    return _conversation_from_row(row)


def get_contact_profile_by_id(contact_profile_id: UUID) -> ContactProfile | None:
    if not settings.postgres_url:
        raise ValueError("POSTGRES_URL es requerido para usar perfiles")

    with psycopg.connect(settings.postgres_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM contact_profiles
                WHERE id = %(id)s
                LIMIT 1
                """,
                {"id": contact_profile_id},
            )
            row = cur.fetchone()

    if not row:
        return None

    return _contact_from_row(row)


def _find_contact(
    cur,
    *,
    source: str,
    external_contact_id: str | None,
    phone: str | None,
    email: str | None,
) -> dict[str, Any] | None:
    if external_contact_id:
        cur.execute(
            """
            SELECT *
            FROM contact_profiles
            WHERE source = %(source)s AND external_contact_id = %(external_contact_id)s
            LIMIT 1
            """,
            {"source": source, "external_contact_id": external_contact_id},
        )
        row = cur.fetchone()
        if row:
            return row

    if phone:
        cur.execute(
            """
            SELECT *
            FROM contact_profiles
            WHERE phone = %(phone)s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            {"phone": phone},
        )
        row = cur.fetchone()
        if row:
            return row

    if email:
        cur.execute(
            """
            SELECT *
            FROM contact_profiles
            WHERE email = %(email)s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            {"email": email},
        )
        row = cur.fetchone()
        if row:
            return row

    return None


def _contact_from_row(row: dict[str, Any]) -> ContactProfile:
    return ContactProfile(
        id=row["id"],
        source=row["source"],
        external_contact_id=row["external_contact_id"],
        phone=row["phone"],
        email=row["email"],
        name=row["name"],
        summary=row["summary"],
        important_data=row["important_data"],
        preferences=row["preferences"],
        metadata=row["metadata"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _conversation_from_row(row: dict[str, Any]) -> ConversationProfile:
    return ConversationProfile(
        id=row["id"],
        source=row["source"],
        external_conversation_id=row["external_conversation_id"],
        contact_profile_id=row["contact_profile_id"],
        session_id=row["session_id"],
        status=row["status"],
        last_intent=row["last_intent"],
        summary=row["summary"],
        qualification_score=row["qualification_score"],
        qualification_label=row["qualification_label"],
        handoff_recommended=row["handoff_recommended"],
        handoff_reason=row["handoff_reason"],
        important_data=row["important_data"],
        metadata=row["metadata"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

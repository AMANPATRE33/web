"""Audit trail for privileged mutations.

Two properties matter more than the schema here:

1. **Same transaction.** ``record()`` only adds to the session; it never
   commits. If the surrounding transaction rolls back, so does the audit row -
   which is correct, because the change it describes did not happen. A separate
   connection that committed independently would produce audit entries for
   changes that were rolled back, which is worse than no audit at all.

2. **Redaction.** A snapshot of an entity is taken before the change, so it must
   never contain a secret, a password hash, or a payment signature. Anything
   matching a sensitive key is replaced rather than filtered later, because a
   filter that is applied "in the log pipeline" is one config change away from
   leaking.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.engagement import AuditLog
from app.models.identity import Profile

logger = get_logger(__name__)

#: Substrings that mark a value as sensitive. Matched case-insensitively
#: against the *key*, which is why the set includes fragments rather than only
#: exact names ("access_token" contains "token").
_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "signature",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "private",
    "credential",
    "otp",
    "cvv",
    "card",
)

#: Never snapshot these at all: they are large, volatile, or meaningless in an
#: audit diff.
_SKIP_KEYS = frozenset({"password_hash", "hashed_password", "gateway_payload"})

_MAX_STRING = 512


def _redact(value: Any, depth: int = 0) -> Any:
    """Return a JSON-safe, secret-free representation of ``value``."""
    if depth > 6:
        return "<truncated: too deep>"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            lowered = key_str.lower()
            if key_str in _SKIP_KEYS:
                continue
            if any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS):
                out[key_str] = "[redacted]"
            else:
                out[key_str] = _redact(item, depth + 1)
        return out
    if isinstance(value, list | tuple | set):
        return [_redact(item, depth + 1) for item in list(value)[:50]]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str):
        return value[:_MAX_STRING]
    if isinstance(value, int | float | bool | type(None)):
        return value
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return str(value)[:_MAX_STRING]


def _snapshot(entity: Any) -> dict[str, Any] | None:
    """Extract a redacted dict of a mapped entity's column values."""
    if entity is None:
        return None
    state = getattr(entity, "__dict__", None)
    if not state:
        return None
    data: dict[str, Any] = {}
    for key, value in state.items():
        if key.startswith("_"):
            continue
        # Skip unloaded relationships: touching them would raise or trigger IO.
        if hasattr(value, "metadata") and hasattr(value, "key"):
            continue
        data[key] = value
    return _redact(data)


async def record(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor: Profile | None = None,
    actor_label: str | None = None,
    before: Any = None,
    after: Any = None,
    request: Any = None,
    extra: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an audit row to the current transaction.

    Args:
        action: dotted verb, e.g. ``order.status_change`` or ``product.update``.
        entity_type: table or domain noun, e.g. ``order``.
        entity_id: string id of the affected entity.
        actor: the staff or customer profile responsible, if known.
        actor_label: overrides ``actor`` with a system label such as
            ``"worker:aggregate_sales_daily"``.
        before: entity state before the change (passed to ``session.refresh``
            semantics - use the ORM object).
        after: entity state after the change.
        request: the FastAPI ``Request``, used to capture IP and user agent.
    """
    payload_before = _snapshot(before)
    payload_after = _snapshot(after)
    if extra:
        merged = _redact({**(payload_after or {}), **extra})
    else:
        merged = payload_after

    ip_address = None
    user_agent = None
    request_id = None
    if request is not None:
        request_id = getattr(getattr(request, "state", None), "request_id", None)
        user_agent = (request.headers.get("user-agent") or "")[:400] or None
        # Trust the platform proxy's forwarded header, which is what a client
        # cannot be allowed to set directly.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()[:64]
        elif request.client:
            ip_address = request.client.host[:64]

    log = AuditLog(
        actor_profile_id=actor.id if actor is not None else None,
        actor_label=actor_label or ("staff" if actor is not None else "system"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=payload_before,
        after=merged,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    session.add(log)
    await session.flush()

    logger.info(
        "audit_recorded",
        action=action,
        entity_type=entity_type,
        entity_id=log.entity_id,
        actor=str(actor.id) if actor is not None else (actor_label or "system"),
    )
    return log


async def record_status_change(
    session: AsyncSession,
    *,
    order: Any,
    from_status: str,
    to_status: str,
    actor: Profile | None = None,
    note: str | None = None,
    request: Any = None,
) -> AuditLog:
    """Convenience wrapper for the most common audited action."""
    return await record(
        session,
        action="order.status_change",
        entity_type="order",
        entity_id=str(order.id),
        actor=actor,
        before={"status": from_status},
        after={"status": to_status, "note": note} if note else {"status": to_status},
        request=request,
    )

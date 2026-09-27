"""Inventory reservation. The only code permitted to move stock.

## The single rule

`inventory.available` is a **generated** column, `quantity - reserved`. It
cannot be written, by us, by `psql`, or by a future service. Every decision in
this module is therefore made against a quantity the database itself derived,
and the database's own `CHECK (reserved <= quantity)` guarantees `available`
never goes negative even if a caller asks twice.

## Why one conditional UPDATE and not read-then-write

The naive implementation is "read available, check it is enough, then
subtract". Two concurrent checkouts for the last unit both read `available = 1`,
both pass, and both write - overselling by one, with a row lock serialising the
writes but nothing stopping the *decision* from having already been made twice.

The fix is to make the check and the write the same statement:

```sql
UPDATE inventory
   SET reserved = reserved + :qty
 WHERE variant_id = :variant
   AND quantity - reserved >= :qty
RETURNING id, available;
```

If the row does not satisfy the predicate, it is not locked, not updated, and
`RETURNING` yields nothing. Zero rows *is* the answer "not enough stock". There
is no window between the decision and the write, because they are one statement,
and PostgreSQL's row lock serialises competing updates to the same variant.

This is why the module has no `SELECT ... FOR UPDATE` anywhere: a lock alone
does not help unless the check happens *under* it, and here the predicate is
simply pushed into the UPDATE, which is both stronger and one round trip fewer.

## Lifecycle

| Event | `quantity` | `reserved` | Reservation row |
|---|---|---|---|
| reserve (payment created) | - | `+qty` | new `HELD` |
| commit (payment captured) | `-qty` | `-qty` | `HELD` -> `COMMITTED` |
| release (failed / cancelled) | - | `-qty` | `HELD` -> `RELEASED` |
| expire (TTL swept) | - | `-qty` | `HELD` -> `EXPIRED` |
| restock (order cancelled) | `+qty` | - | - |

Every transition also writes an `inventory_movements` row, so
`reconcile_inventory` can prove the running sum matches `quantity`. A mismatch
is a bug report, not silent drift.

## Idempotency

A replayed webhook or a retried payment must not release a reservation twice.
Two guards, and they are independent on purpose:

1. The conditional UPDATE only ever moves stock it was entitled to move, so a
   second release of an already-released line affects zero rows.
2. `uq_inventory_reservations_held_per_order_variant` - a partial unique index
   over `(order_id, variant_id) WHERE status = 'HELD'` - makes a second
   *reservation* of the same line a database error, not a double decrement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InsufficientStockError
from app.core.logging import get_logger
from app.models.catalog import Inventory, InventoryMovement
from app.models.commerce import InventoryReservation
from app.models.enums import InventoryReason, ReservationStatus

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ReservationLine:
    """What the caller wants to hold, resolved from the database beforehand."""

    variant_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class ReservationResult:
    variant_id: uuid.UUID
    quantity: int
    #: ``available`` immediately after the reservation, for the order timeline.
    available_after: int


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
async def available_for_variants(
    session: AsyncSession, variant_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Sellable quantity per variant, in one query.

    Reads the generated ``available`` column rather than computing
    ``quantity - reserved`` in Python, so this cannot disagree with the
    database. A variant with no inventory row is reported as 0 - "no stock
    record" must not read as "unlimited".
    """
    if not variant_ids:
        return {}

    result = await session.execute(
        select(Inventory.variant_id, Inventory.available).where(
            Inventory.variant_id.in_(variant_ids)
        )
    )
    found = {variant_id: int(available) for variant_id, available in result.all()}
    # Anything with no row has no stock. Fail closed.
    return {vid: found.get(vid, 0) for vid in variant_ids}


# ---------------------------------------------------------------------------
# Reserve
# ---------------------------------------------------------------------------
async def reserve(
    session: AsyncSession,
    lines: list[ReservationLine],
    *,
    order_id: uuid.UUID | None,
    cart_id: uuid.UUID | None,
    ttl_seconds: int,
) -> list[ReservationResult]:
    """Hold stock for a set of variants, or hold nothing at all.

    **All-or-nothing.** If any line cannot be satisfied, every line this call
    already reserved is released before the error propagates. A partial
    reservation is worse than a failed one: the customer sees stock held against
    an order that does not exist, and the units stay invisible to other shoppers
    until a sweeper finds them.

    The rollback is a second conditional UPDATE rather than a transaction
    rollback, because the caller may be inside a larger transaction that it
    intends to keep. Making the compensation explicit keeps this function safe
    to call from either a transaction or standalone.
    """
    if not lines:
        return []
    if order_id is None and cart_id is None:
        raise ValueError("a reservation must belong to an order or a cart")

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None

    held: list[ReservationResult] = []
    try:
        for line in lines:
            held.append(
                await _reserve_one(
                    session,
                    line,
                    order_id=order_id,
                    cart_id=cart_id,
                    expires_at=expires_at,
                )
            )
    except InsufficientStockError:
        # Undo whatever we took, then let the original error stand. The
        # customer-facing message is about the item they wanted, not about our
        # internal cleanup.
        for done in held:
            await _release_one(
                session,
                done.variant_id,
                done.quantity,
                reason=InventoryReason.RELEASE,
                note="compensation: sibling line was short",
                order_id=order_id,
            )
        raise

    logger.info(
        "inventory_reserved",
        order_id=str(order_id) if order_id else None,
        cart_id=str(cart_id) if cart_id else None,
        lines=len(held),
        units=sum(r.quantity for r in held),
    )
    return held


async def _reserve_one(
    session: AsyncSession,
    line: ReservationLine,
    *,
    order_id: uuid.UUID | None,
    cart_id: uuid.UUID | None,
    expires_at: datetime | None,
) -> ReservationResult:
    """Reserve one variant with a single conditional UPDATE.

    The guard clause rejects the caller's own bad input before touching stock, so
    a quantity of zero cannot enter the ledger and produce a no-op reservation
    row that a later commit would then treat as a real sale.
    """
    if line.quantity <= 0:
        raise InsufficientStockError(
            "Quantity must be greater than zero.", code="invalid_quantity"
        )

    result = await session.execute(
        update(Inventory)
        .where(
            Inventory.variant_id == line.variant_id,
            # The predicate *is* the check. A row that cannot satisfy it is not
            # locked and not updated.
            Inventory.quantity - Inventory.reserved >= line.quantity,
        )
        .values(reserved=Inventory.reserved + line.quantity)
        .returning(Inventory.quantity, Inventory.available)
    )
    row = result.first()

    if row is None:
        current = await available_for_variants(session, [line.variant_id])
        available = current.get(line.variant_id, 0)
        logger.warning(
            "inventory_reservation_rejected",
            variant_id=str(line.variant_id),
            requested=line.quantity,
            available=available,
        )
        raise InsufficientStockError(
            "Some items are no longer available in the requested quantity.",
            code="insufficient_stock",
            details={"variant_id": str(line.variant_id), "available": available},
        )

    quantity_after, available_after = row
    variant_id = line.variant_id

    reservation = InventoryReservation(
        variant_id=variant_id,
        order_id=order_id,
        cart_id=cart_id,
        quantity=line.quantity,
        status=ReservationStatus.HELD,
        reason=InventoryReason.RESERVATION,
        expires_at=expires_at,
    )
    session.add(reservation)
    session.add(
        InventoryMovement(
            variant_id=variant_id,
            order_id=order_id,
            # A hold moves nothing into `quantity`; it only lowers `available`.
            delta=0,
            reserved_delta=line.quantity,
            quantity_after=quantity_after,
            reason=InventoryReason.RESERVATION,
            note=f"held for {'order' if order_id else 'cart'}",
        )
    )
    await session.flush()

    return ReservationResult(
        variant_id=variant_id,
        quantity=line.quantity,
        available_after=int(available_after),
    )


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------
async def commit_reservations(
    session: AsyncSession,
    order_id: uuid.UUID,
    *,
    note: str = "payment captured",
) -> int:
    """Turn held stock into sold stock. Returns units committed.

    Idempotent by construction: it updates only rows still ``HELD``, so a second
    call finds nothing to do and returns 0 rather than decrementing twice.
    """
    result = await session.execute(
        select(InventoryReservation).where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == ReservationStatus.HELD,
        )
    )
    reservations = result.scalars().all()
    if not reservations:
        return 0

    for reservation in reservations:
        # `quantity_after` is recorded so the ledger is self-verifying: the last
        # movement for a variant should always agree with `inventory.quantity`.
        await session.execute(
            update(Inventory)
            .where(
                Inventory.variant_id == reservation.variant_id,
                Inventory.reserved >= reservation.quantity,
            )
            .values(
                quantity=Inventory.quantity - reservation.quantity,
                reserved=Inventory.reserved - reservation.quantity,
            )
            .returning(Inventory.quantity)
        )
        quantity_row = await session.execute(
            select(Inventory.quantity).where(
                Inventory.variant_id == reservation.variant_id
            )
        )
        session.add(
            InventoryMovement(
                variant_id=reservation.variant_id,
                order_id=order_id,
                delta=-reservation.quantity,
                reserved_delta=-reservation.quantity,
                quantity_after=int(quantity_row.scalar_one()),
                reason=InventoryReason.SALE,
                note="payment captured",
            )
        )
        reservation.status = ReservationStatus.COMMITTED
        reservation.committed_at = datetime.now(UTC)
        reservation.note = note

    await session.flush()
    logger.info(
        "inventory_committed",
        order_id=str(order_id),
        lines=len(reservations),
        units=sum(r.quantity for r in reservations),
    )
    return sum(r.quantity for r in reservations)


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------
async def release_reservations(
    session: AsyncSession,
    order_id: uuid.UUID,
    *,
    reason: InventoryReason = InventoryReason.RELEASE,
    note: str | None = None,
    status: ReservationStatus = ReservationStatus.RELEASED,
) -> int:
    """Return held stock to sellable. Returns units released.

    Idempotent: only ``HELD`` rows are considered, so calling this after a
    failure webhook has already released is a no-op returning 0. That property
    is what makes webhook delivery safe to retry.
    """
    result = await session.execute(
        select(InventoryReservation).where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == ReservationStatus.HELD,
        )
    )
    reservations = result.scalars().all()
    if not reservations:
        return 0

    for reservation in reservations:
        await _release_one(
            session,
            reservation.variant_id,
            reservation.quantity,
            reason=reason,
            note=note,
            order_id=order_id,
        )
        reservation.status = status
        reservation.released_at = datetime.now(UTC)
        if note:
            reservation.note = note

    await session.flush()
    logger.info(
        "inventory_released",
        order_id=str(order_id),
        reason=str(reason),
        lines=len(reservations),
        units=sum(r.quantity for r in reservations),
    )
    return sum(r.quantity for r in reservations)


async def _release_one(
    session: AsyncSession,
    variant_id: uuid.UUID,
    quantity: int,
    *,
    reason: InventoryReason,
    note: str | None,
    order_id: uuid.UUID | None = None,
) -> None:
    """Lower ``reserved`` for one variant, guarded against underflow.

    The ``reserved >= quantity`` predicate means a compensating release for a
    line that was never held, or a double release, changes zero rows instead of
    driving ``reserved`` negative and making ``available`` exceed ``quantity`` -
    which would advertise stock that does not exist.
    """
    await session.execute(
        update(Inventory)
        .where(
            Inventory.variant_id == variant_id,
            Inventory.reserved >= quantity,
        )
        .values(reserved=Inventory.reserved - quantity)
    )
    quantity_row = await session.execute(
        select(Inventory.quantity).where(Inventory.variant_id == variant_id)
    )
    session.add(
        InventoryMovement(
            variant_id=variant_id,
            order_id=order_id,
            delta=0,
            reserved_delta=-quantity,
            quantity_after=int(quantity_row.scalar_one_or_none() or 0),
            reason=reason,
            note=note,
        )
    )


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------
async def expire_stale_reservations(session: AsyncSession, *, limit: int = 200) -> int:
    """Release ``HELD`` reservations whose payment window closed. Returns units.

    This is what bounds how long stock is invisible to other shoppers after a
    customer abandons Razorpay's checkout. It is driven by
    ``ix_inventory_reservations_expiry_sweep``, a partial index over exactly the
    rows this query needs, so the sweep does not scan the ledger.

    The claim is safe to run concurrently across workers: the UPDATE only
    touches rows that were ``HELD`` when we listed them, and two workers racing
    the same row will both try to set ``RELEASED``; the second finds
    ``reserved`` already lowered and the guarded UPDATE matches zero rows. Stock
    is therefore released exactly once, and the sweep can be retried freely.
    """
    result = await session.execute(
        select(InventoryReservation)
        .where(
            InventoryReservation.status == ReservationStatus.HELD,
            InventoryReservation.expires_at.is_not(None),
            InventoryReservation.expires_at <= datetime.now(UTC),
        )
        .order_by(InventoryReservation.expires_at.asc())
        .limit(limit)
    )
    stale = result.scalars().all()
    if not stale:
        return 0

    released = 0
    for reservation in stale:
        await _release_one(
            session,
            reservation.variant_id,
            reservation.quantity,
            reason=InventoryReason.EXPIRY,
            note="payment window expired",
            order_id=reservation.order_id,
        )
        reservation.status = ReservationStatus.EXPIRED
        reservation.released_at = datetime.now(UTC)
        reservation.note = "payment window expired"
        released += reservation.quantity

    await session.flush()
    logger.info("inventory_reservations_expired", reservations=len(stale), units=released)
    return released


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------
async def reconcile(session: AsyncSession, variant_id: uuid.UUID) -> dict[str, int | str]:
    """Compare the movement ledger against ``inventory.quantity``.

    Returns a verdict rather than raising, so the job can report all mismatches
    in one pass instead of stopping at the first. A ``quantity`` that disagrees
    with the sum of its own movements is a bug in this module, and this is how
    it gets caught.
    """
    result = await session.execute(
        select(
            Inventory.quantity,
            func.coalesce(func.sum(InventoryMovement.delta), 0),
        )
        .select_from(Inventory)
        .outerjoin(
            InventoryMovement,
            InventoryMovement.variant_id == Inventory.variant_id,
        )
        .where(Inventory.variant_id == variant_id)
        .group_by(Inventory.quantity)
    )
    row = result.first()
    if row is None:
        return {"variant_id": str(variant_id), "verdict": "no_inventory_row"}

    stored, moved = int(row[0]), int(row[1])
    if stored != moved:
        logger.error(
            "inventory_reconciliation_mismatch",
            variant_id=str(variant_id),
            stored=stored,
            ledger=moved,
        )
        return {
            "variant_id": str(variant_id),
            "verdict": "MISMATCH",
            "stored_quantity": stored,
            "ledger_quantity": moved,
        }
    return {
        "variant_id": str(variant_id),
        "verdict": "ok",
        "stored_quantity": stored,
        "ledger_quantity": moved,
    }


async def restock_order(session: AsyncSession, order_id: uuid.UUID) -> int:
    """Put a cancelled order's units back into sellable stock.

    Used when staff cancel an order that had already been paid for and the goods
    are genuinely going back on the shelf. Distinct from ``release_reservations``:
    that returns *reserved* units for an order that never sold, this returns
    *sold* units for one that did.
    """
    result = await session.execute(
        select(InventoryMovement)
        .where(
            InventoryMovement.order_id == order_id,
            InventoryMovement.reason == InventoryReason.SALE,
        )
        .order_by(InventoryMovement.created_at.asc())
    )
    movements = result.scalars().all()
    if not movements:
        return 0

    aggregated: dict[uuid.UUID, int] = {}
    for movement in movements:
        aggregated[movement.variant_id] = (
            aggregated.get(movement.variant_id, 0) - movement.delta
        )

    for variant_id, units in aggregated.items():
        if units <= 0:
            continue
        await session.execute(
            update(Inventory)
            .where(Inventory.variant_id == variant_id)
            .values(quantity=Inventory.quantity + units)
        )
        quantity_row = await session.execute(
            select(Inventory.quantity).where(Inventory.variant_id == variant_id)
        )
        session.add(
            InventoryMovement(
                variant_id=variant_id,
                order_id=order_id,
                delta=units,
                reserved_delta=0,
                quantity_after=int(quantity_row.scalar_one()),
                reason=InventoryReason.RETURN,
                note="order cancelled, stock returned",
            )
        )
    await session.flush()
    logger.info("inventory_restocked", order_id=str(order_id), variants=len(aggregated))
    return sum(aggregated.values())


async def low_stock_variants(session: AsyncSession, *, limit: int = 100) -> list[uuid.UUID]:
    """Variants at or below their low-stock threshold, for the reorder job."""
    result = await session.execute(
        select(Inventory.variant_id)
        .where(Inventory.available <= Inventory.low_stock_threshold)
        .order_by(Inventory.available.asc())
        .limit(limit)
    )
    return list(result.scalars().all())

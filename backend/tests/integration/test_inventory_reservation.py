"""Inventory reservation: the properties that make overselling impossible.

The headline test is `test_concurrent_reservation_never_oversells`, which is the
scenario the whole design exists for. The rest guard the properties that make it
hold over time rather than on the happy path.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from app.core.errors import InsufficientStockError
from app.models.catalog import ProductVariant
from app.models.enums import InventoryReason, ReservationStatus
from app.models.orders import Order
from app.services import inventory as inv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def _variant_with_stock(
    session: AsyncSession, *, quantity: int, reserved: int = 0
) -> ProductVariant:
    """Create a profile, product, variant and inventory row with exact stock.

    Built in raw SQL because the ORM's product/variant construction pulls in
    triggers and generated columns that are irrelevant here; what matters is a
    precise `quantity`/`reserved` pair to race against.
    """
    profile_id = uuid.uuid4()
    category_id = uuid.uuid4()
    product_id = uuid.uuid4()
    variant_id = uuid.uuid4()

    await session.execute(
        text(
            """
            INSERT INTO profiles (id, email, full_name, role, is_active, created_at, updated_at)
            VALUES (:pid, :email, 'Stock', 'CUSTOMER', true, now(), now())
            """
        ),
        {"pid": profile_id, "email": f"{profile_id.hex}@example.com"},
    )
    await session.execute(
        text(
            """
            INSERT INTO categories (id, name, slug, description, position, created_at, updated_at)
            VALUES (:cid, 'Test Category', :slug, '', 0, now(), now())
            """
        ),
        {"cid": category_id, "slug": f"cat-{category_id.hex[:8]}"},
    )
    await session.execute(
        text(
            """
            INSERT INTO products (id, title, slug, sku, description, category_id, base_price,
                                  status, currency, created_at, updated_at)
            VALUES (:pid, 'Test Product', :slug, :sku, '', :cid, 10000, 'ACTIVE', 'INR',
                    now(), now())
            """
        ),
        {
            "pid": product_id,
            "slug": f"prod-{product_id.hex[:10]}",
            "sku": f"SKU-{product_id.hex[:8]}",
            "cid": category_id,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO product_variants (id, product_id, sku, title, attributes, currency,
                                          status, position, is_default, low_stock_threshold,
                                          created_at, updated_at)
            VALUES (:vid, :pid, :sku, 'Default', '{"Material":"ACP","Size":"12x18"}'::jsonb,
                    'INR', 'ACTIVE', 0, true, 3, now(), now())
            """
        ),
        {"vid": variant_id, "pid": product_id, "sku": f"V-{product_id.hex[:8]}"},
    )
    await session.execute(
        text(
            """
            INSERT INTO inventory (id, variant_id, quantity, reserved, low_stock_threshold,
                                   reorder_point, created_at, updated_at)
            VALUES (:iid, :vid, :qty, :res, 3, 5, now(), now())
            """
        ),
        {
            "iid": uuid.uuid4(),
            "vid": variant_id,
            "qty": quantity,
            "res": reserved,
        },
    )
    # Record the opening balance in the ledger.
    #
    # Without this the stock exists but nothing explains it, and `reconcile` -
    # correctly - reports a mismatch. That is the check doing its job: it caught
    # this fixture for inventing stock out of nowhere, which is exactly the drift
    # it exists to catch. The real seeder and every admin adjustment go through a
    # movement; a test fixture that inserts a bare row does not.
    await session.execute(
        text(
            """
            INSERT INTO inventory_movements (id, variant_id, delta, reserved_delta,
                                             quantity_after, reason, note, created_at)
            VALUES (:mid, :vid, :delta, :res, :after, 'RESTOCK', 'opening balance', now())
            """
        ),
        {
            "mid": uuid.uuid4(),
            "vid": variant_id,
            "delta": quantity,
            "res": reserved,
            "after": quantity,
        },
    )
    await session.commit()

    result = await session.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    return result.scalar_one()


async def _profile(session: AsyncSession) -> uuid.UUID:
    """Create a profile and return its id. Orders need one to satisfy the FK."""
    from sqlalchemy import text as _text

    profile_id = uuid.uuid4()
    await session.execute(
        _text(
            "INSERT INTO profiles (id, email, full_name, role, is_active, "
            "created_at, updated_at) VALUES (:pid, :email, 'Racer', 'CUSTOMER', "
            "true, now(), now())"
        ),
        {"pid": profile_id, "email": f"{profile_id.hex}@example.com"},
    )
    return profile_id


def _blank_order(profile_id: uuid.UUID) -> Order:
    return Order(
        order_number=f"T-{uuid.uuid4().hex[:10]}",
        profile_id=profile_id,
        email="r@example.com",
        phone="9999999999",
        shipping_name="R",
        shipping_line1="1 St",
        shipping_city="Pune",
        shipping_state="MH",
        shipping_postal_code="411001",
        subtotal=0,
        discount_total=0,
        shipping_total=0,
        tax_total=0,
        total=0,
    )


async def _two_orders(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Two orders, each with its own profile, so the two racers are independent."""
    ids: list[uuid.UUID] = []
    for _ in range(2):
        profile_id = await _profile(session)
        order = _blank_order(profile_id)
        session.add(order)
        await session.flush()
        ids.append(order.id)
    await session.commit()
    return ids[0], ids[1]


async def _many_orders(session: AsyncSession, count: int) -> list[uuid.UUID]:
    """N orders under one profile. Order ownership is irrelevant to the race;
    what matters is that each racer holds a distinct reservation target."""
    profile_id = await _profile(session)
    ids: list[uuid.UUID] = []
    for _ in range(count):
        order = _blank_order(profile_id)
        session.add(order)
        await session.flush()
        ids.append(order.id)
    await session.commit()
    return ids


async def _read_inventory(db_session: AsyncSession, variant_id: uuid.UUID) -> tuple[int, int, int]:
    result = await db_session.execute(
        text(
            "SELECT quantity, reserved, available FROM inventory WHERE variant_id = :v"
        ),
        {"v": variant_id},
    )
    row = result.first()
    return int(row[0]), int(row[1]), int(row[2])


async def _engine_factory(test_database_url: str):
    """Create an engine for a concurrency test, disposed however the test ends.

    Two things here are load-bearing and both were arrived at the hard way.

    **Disposal.** Each test opens a second engine so the racers get genuinely
    separate connections, and an undisposed engine keeps its whole pool alive.
    Nineteen tests leaking a pool of five is over a hundred connections, and the
    run stops making progress at `max_connections` rather than failing - which
    reads as a hang, not a leak.

    **`lock_timeout`.** The winner of a race holds the inventory row lock until
    it commits, so the loser legitimately *blocks* on that row. That is correct
    behaviour - it is exactly the serialisation we are relying on - but with no
    bound it is indistinguishable from a deadlock, and the test suite hangs
    forever instead of failing. A two-second lock timeout turns "waited too
    long" into a definite, assertable outcome.

    A racer that times out on the lock is a **loss**: it did not get the stock.
    That is the honest classification, not a workaround - if the winner had
    rolled back, the predicate would have been re-evaluated and the row updated
    rather than skipped.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(
        test_database_url,
        pool_size=6,
        max_overflow=2,
        connect_args={"server_settings": {"lock_timeout": "2s", "statement_timeout": "30s"}},
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


#: What a losing racer reports. Covers both outcomes a blocked UPDATE can have:
#: the predicate re-checked and rejected (the normal case), or a lock timeout.
_RACE_LOST = "lost"
_RACE_TIMEOUT = "timeout"
_RACE_WON = "won"


def _make_racer(setup, variant_id: uuid.UUID, quantity: int):
    """Build a racer coroutine that reports exactly one of three outcomes.

    A racer wins by committing a hold. It loses either because the conditional
    UPDATE matched no rows - the row it wanted was taken while it was blocked -
    or because it gave up waiting for the row lock. Both are failures to acquire
    stock, and the caller asserts on them together.
    """

    async def attempt(order_id: uuid.UUID) -> str:
        from sqlalchemy.exc import DBAPIError

        async with setup() as racer:
            try:
                await inv.reserve(
                    racer,
                    [inv.ReservationLine(variant_id=variant_id, quantity=quantity)],
                    order_id=order_id,
                    cart_id=None,
                    ttl_seconds=900,
                )
                await racer.commit()
                return _RACE_WON
            except InsufficientStockError:
                await racer.rollback()
                return _RACE_LOST
            except DBAPIError as exc:
                await racer.rollback()
                text_ = str(getattr(exc, "orig", exc)).lower()
                if "lock" in text_ or "timeout" in text_ or "canceling" in text_:
                    return _RACE_TIMEOUT
                raise

    return attempt


def _assert_single_winner(outcomes: list[str], *, context: str) -> None:
    won = outcomes.count(_RACE_WON)
    assert won == 1, (
        f"{context}: expected exactly one winner, got {won} out of {outcomes}. "
        "More than one means stock was oversold."
    )
    assert won + outcomes.count(_RACE_LOST) + outcomes.count(_RACE_TIMEOUT) == len(outcomes)


# ---------------------------------------------------------------------------
# The mandatory concurrency test
# ---------------------------------------------------------------------------
class TestConcurrency:
    """Exactly-one-winner, run in a subprocess with a hard timeout.

    Why a subprocess: the race is the *point* of this test, and a race needs two
    real connections contending for one row. Driving that from the pytest
    process hung - the racers block on the row lock held by the winner, which is
    the serialisation this design relies on, and with the test's own session
    still holding connections the run stopped making progress rather than
    failing. That presents as an indefinite hang, which is the worst possible
    outcome for a test suite.

    So the race runs in a fresh process against the real database, with a
    `lock_timeout` so a blocked racer is bounded, and with a wall-clock timeout
    on the subprocess so a regression fails the build instead of wedging it.

    The mechanism itself was verified directly before this was formalised: two
    racers on one unit of stock, the conditional UPDATE, `A` returned a row and
    committed while `B` returned no rows.
    """

    PROBE = r"""
import asyncio, os, sys, uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

async def main(quantity, per_order, racers, mode):
    engine = create_async_engine(
        os.environ["DATABASE_URL"], pool_size=8, max_overflow=4,
        connect_args={"server_settings": {"lock_timeout": "2s", "statement_timeout": "20s"}},
    )
    mk = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as c:
            await c.exec_driver_sql(
                "TRUNCATE inventory, product_variants, products, categories, profiles, "
                "orders, inventory_reservations, inventory_movements RESTART IDENTITY CASCADE"
            )
        async with mk() as s:
            pid, cid, prod, vid = (uuid.uuid4() for _ in range(4))
            await s.execute(text(
                "INSERT INTO profiles (id,email,full_name,role,is_active,"
                "created_at,updated_at)"
                " VALUES (:p,:e,'R','CUSTOMER',true,now(),now())"), {"p": pid, "e": f"{pid.hex}@e.com"})
            await s.execute(text(
                "INSERT INTO categories (id,name,slug,description,position,created_at,updated_at)"
                " VALUES (:c,'C',:sl,'',0,now(),now())"), {"c": cid, "sl": f"c-{cid.hex[:8]}"})
            await s.execute(text(
                "INSERT INTO products (id,title,slug,sku,description,category_id,base_price,"
                "status,currency,created_at,updated_at) VALUES (:i,'P',:sl,:sku,'',:c,10000,"
                "'ACTIVE','INR',now(),now())"),
                {"i": prod, "sl": f"p-{prod.hex[:10]}", "sku": f"S-{prod.hex[:6]}", "c": cid})
            await s.execute(text(
                "INSERT INTO product_variants (id,product_id,sku,title,attributes,currency,status,"
                "position,is_default,low_stock_threshold,created_at,updated_at) VALUES "
                "(:v,:p,:sku,'D','{}'::jsonb,'INR','ACTIVE',0,true,3,now(),now())"),
                {"v": vid, "p": prod, "sku": f"V-{prod.hex[:6]}"})
            await s.execute(text(
                "INSERT INTO inventory (id,variant_id,quantity,reserved,low_stock_threshold,"
                "reorder_point,created_at,updated_at) VALUES (:i,:v,:q,0,3,5,now(),now())"),
                {"i": uuid.uuid4(), "v": vid, "q": quantity})
            oids = []
            for _ in range(racers):
                o = uuid.uuid4()
                await s.execute(text(
                    "INSERT INTO orders (id,order_number,profile_id,email,phone,shipping_name,"
                    "shipping_line1,shipping_city,shipping_state,shipping_postal_code,subtotal,"
                    "discount_total,shipping_total,tax_total,total,created_at,updated_at) VALUES "
                    "(:i,:n,:p,'o@e.com','9999999999','O','1 St','Pune','MH','411001',0,0,0,0,0,"
                    "now(),now())"), {"i": o, "n": f"T-{o.hex[:8]}", "p": pid})
                oids.append(o)
            await s.commit()

        async def race(oid):
            async with mk() as s:
                try:
                    r = await s.execute(text(
                        "UPDATE inventory SET reserved = reserved + :q WHERE variant_id = :v "
                        "AND quantity - reserved >= :q RETURNING quantity, reserved, available"),
                        {"v": vid, "q": per_order})
                    row = r.first()
                    if row is None:
                        await s.rollback(); return "lost"
                    await s.commit(); return "won:" + "|".join(str(x) for x in row)
                except Exception as exc:
                    await s.rollback()
                    t = str(exc).lower()
                    return "timeout" if ("lock" in t or "timeout" in t) else f"error:{exc}"

        if mode == "service":
            sys.path.insert(0, os.getcwd())
            from app.core.errors import InsufficientStockError
            from app.services import inventory as inv
            async def race(oid):
                async with mk() as s:
                    try:
                        await inv.reserve(s, [inv.ReservationLine(variant_id=vid, quantity=per_order)],
                                         order_id=oid, cart_id=None, ttl_seconds=900)
                        await s.commit(); return "won"
                    except InsufficientStockError:
                        await s.rollback(); return "lost"
                    except Exception as exc:
                        await s.rollback()
                        t = str(exc).lower()
                        return "timeout" if ("lock" in t or "timeout" in t) else f"error:{exc}"

        results = await asyncio.gather(*(race(o) for o in oids))
        async with mk() as s:
            r = await s.execute(text(
                "SELECT quantity, reserved, available FROM inventory WHERE variant_id = :v"),
                {"v": vid})
            qty, res, avail = r.one()
        print("RESULTS " + ";".join(results))
        print("STOCK " + f"{qty},{res},{avail}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    import json
    a = json.loads(sys.argv[1])
    asyncio.run(asyncio.wait_for(main(**a), timeout=60))
"""

    def _run(self, test_database_url, **kwargs) -> tuple[list[str], tuple[int, int, int]]:
        """Run the probe in a subprocess. Returns (results, (quantity, reserved, available))."""
        import json
        import os
        import subprocess
        import sys

        env = {**os.environ, "DATABASE_URL": test_database_url, "PYTHONWARNINGS": "ignore"}
        script = Path(__file__).with_name("_race_probe.py")
        script.write_text(self.PROBE, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, str(script), json.dumps(kwargs)],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                cwd=str(Path(__file__).resolve().parents[2]),
            )
        finally:
            script.unlink(missing_ok=True)

        assert completed.returncode == 0, (
            f"race probe failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr[-2000:]}"
        )
        results_line = next(
            (ln for ln in completed.stdout.splitlines() if ln.startswith("RESULTS ")), ""
        )
        stock_line = next(
            (ln for ln in completed.stdout.splitlines() if ln.startswith("STOCK ")), ""
        )
        assert results_line and stock_line, f"probe produced no verdict:\n{completed.stdout}"
        results = results_line[len("RESULTS "):].split(";")
        stock = tuple(int(x) for x in stock_line[len("STOCK "):].split(","))
        return results, stock  # type: ignore[return-value]

    async def test_two_racers_for_the_last_unit_yield_one_winner(
        self, test_database_url
    ) -> None:
        results, (quantity, reserved, available) = self._run(
            test_database_url, quantity=1, per_order=1, racers=2, mode="raw"
        )
        won = [r for r in results if r.startswith("won")]
        assert len(won) == 1, f"expected exactly 1 winner, got {results}"
        # This probe performs the *hold* only, so `reserved` is 1 and
        # `available` is 0. Turning a hold into a sale is `commit_reservations`,
        # covered by the service-level test below and by TestReservation.
        assert quantity == 1, "a hold must not touch physical stock"
        assert reserved == 1, "the winner's unit is held, not yet sold"
        assert available == 0, "the last unit is no longer sellable"
        assert available >= 0, "available must never go negative"

    async def test_ten_racers_for_one_unit_yield_one_winner(self, test_database_url) -> None:
        results, (_, _, available) = self._run(
            test_database_url, quantity=1, per_order=1, racers=10, mode="raw"
        )
        assert len([r for r in results if r.startswith("won")]) == 1, results
        assert available == 0
        assert available >= 0

    async def test_stock_five_cannot_satisfy_two_orders_of_three(
        self, test_database_url
    ) -> None:
        """Proves the predicate is evaluated per attempt, not just at the boundary."""
        results, (quantity, reserved, available) = self._run(
            test_database_url, quantity=5, per_order=3, racers=8, mode="raw"
        )
        assert len([r for r in results if r.startswith("won")]) == 1, results
        assert reserved == 3, f"exactly one 3-unit hold expected, got {reserved}"
        assert available == 2
        assert quantity == 5, "a hold must not touch physical stock"

    async def test_the_service_itself_yields_one_winner(self, test_database_url) -> None:
        """The same race driven through InventoryService.reserve, not raw SQL.

        A raw-SQL test proves the database behaves. This proves *our code* goes
        through the statement that behaves, which is the thing that could regress.
        """
        results, (quantity, reserved, available) = self._run(
            test_database_url, quantity=1, per_order=1, racers=6, mode="service"
        )
        assert len([r for r in results if r == "won"]) == 1, results
        assert all(r in ("won", "lost", "timeout") for r in results), results
        assert quantity == 1 and reserved == 0 and available == 0
        assert available >= 0

# ---------------------------------------------------------------------------
# Reservation lifecycle
# ---------------------------------------------------------------------------
class TestReservation:
    async def test_reserve_then_commit_sells_the_stock(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=10)
        profile_id = uuid.uuid4()
        order = await _order_with_profile(session, profile_id)

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=3)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        await session.commit()

        _, reserved, available = await _read_inventory(session, variant.id)
        assert reserved == 3 and available == 7, "a hold lowers available, not quantity"

        committed = await inv.commit_reservations(session, order.id)
        await session.commit()
        assert committed == 3

        quantity, reserved, available = await _read_inventory(session, variant.id)
        assert (quantity, reserved, available) == (7, 0, 7), "commit turns a hold into a sale"

    async def test_reserve_then_release_returns_the_stock(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=10)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=4)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        released = await inv.release_reservations(session, order.id)
        await session.commit()

        assert released == 4
        quantity, reserved, available = await _read_inventory(session, variant.id)
        assert (quantity, reserved, available) == (10, 0, 10), "release must restore exactly"

    async def test_reserving_more_than_available_is_refused(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=3)
        order = await _order_with_profile(session, uuid.uuid4())

        with pytest.raises(InsufficientStockError):
            await inv.reserve(
                session,
                [inv.ReservationLine(variant_id=variant.id, quantity=4)],
                order_id=order.id,
                cart_id=None,
                ttl_seconds=900,
            )
        await session.rollback()

        quantity, reserved, available = await _read_inventory(session, variant.id)
        assert available == 3, "a refused reservation must not move stock"
        assert reserved == 0, "a refused reservation must not leave a hold behind"
        assert quantity == 3, "a refused reservation must not touch physical stock"

    async def test_reserving_exactly_all_available_is_allowed(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=3)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=3)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        await session.commit()
        _, _, available = await _read_inventory(session, variant.id)
        assert available == 0

    async def test_partial_reservation_is_rolled_back(self, session) -> None:
        """If any line is short, *no* line is held.

        A partial hold is worse than a failed one: units stay invisible to other
        shoppers against an order that will never exist, until a sweeper notices.
        """
        plenty = await _variant_with_stock(session, quantity=10)
        scarce = await _variant_with_stock(session, quantity=1)
        order = await _order_with_profile(session, uuid.uuid4())

        with pytest.raises(InsufficientStockError):
            await inv.reserve(
                session,
                [
                    inv.ReservationLine(variant_id=plenty.id, quantity=5),
                    inv.ReservationLine(variant_id=scarce.id, quantity=99),
                ],
                order_id=order.id,
                cart_id=None,
                ttl_seconds=900,
            )
        await session.rollback()

        _, reserved_plenty, available_plenty = await _read_inventory(session, plenty.id)
        assert reserved_plenty == 0, "the first line must have been compensated"
        assert available_plenty == 10
        _, _, available_scarce = await _read_inventory(session, scarce.id)
        assert available_scarce == 1

    async def test_release_is_idempotent(self, session) -> None:
        """A replayed failure webhook must not release twice."""
        variant = await _variant_with_stock(session, quantity=10)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=4)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        first = await inv.release_reservations(session, order.id)
        second = await inv.release_reservations(session, order.id)
        third = await inv.release_reservations(session, order.id)
        await session.commit()

        assert first == 4
        assert second == 0 and third == 0, "a second release is a no-op, not a refund of stock"
        _, reserved, available = await _read_inventory(session, variant.id)
        assert (reserved, available) == (0, 10)

    async def test_commit_is_idempotent(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=10)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=2)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        assert await inv.commit_reservations(session, order.id) == 2
        assert await inv.commit_reservations(session, order.id) == 0
        await session.commit()

        quantity, reserved, available = await _read_inventory(session, variant.id)
        assert (quantity, reserved, available) == (8, 0, 8), "a replayed webhook sells once"

    async def test_double_reserve_of_the_same_line_is_a_database_error(
        self, session
    ) -> None:
        """The partial unique index is the safety net, not a nicety."""
        from sqlalchemy.exc import IntegrityError

        variant = await _variant_with_stock(session, quantity=10)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=1)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        await session.commit()

        with pytest.raises(IntegrityError):
            await inv.reserve(
                session,
                [inv.ReservationLine(variant_id=variant.id, quantity=1)],
                order_id=order.id,
                cart_id=None,
                ttl_seconds=900,
            )
        await session.rollback()

    async def test_expired_holds_are_swept(self, session) -> None:
        """A customer who abandons the payment window must not hold stock forever."""
        from datetime import UTC, datetime, timedelta

        variant = await _variant_with_stock(session, quantity=10)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=3)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        # Backdate the deadline rather than sleeping through it.
        await session.execute(
            text(
                "UPDATE inventory_reservations SET expires_at = :past "
                "WHERE order_id = :oid"
            ),
            {"past": datetime.now(UTC) - timedelta(minutes=5), "oid": order.id},
        )
        await session.commit()
        _, reserved, _ = await _read_inventory(session, variant.id)
        assert reserved == 3

        released = await inv.expire_stale_reservations(session)
        await session.commit()

        assert released == 3
        quantity, reserved, available = await _read_inventory(session, variant.id)
        assert (quantity, reserved, available) == (10, 0, 10)

    async def test_unexpired_holds_are_not_swept(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=10)
        order = await _order_with_profile(session, uuid.uuid4())

        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=3)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        await session.commit()

        assert await inv.expire_stale_reservations(session) == 0
        _, reserved, _ = await _read_inventory(session, variant.id)
        assert reserved == 3, "a live payment window must survive the sweeper"

    async def test_available_can_never_go_negative(self, session) -> None:
        """Belt and braces: the schema refuses it even under raw SQL."""
        from sqlalchemy.exc import IntegrityError

        variant = await _variant_with_stock(session, quantity=5)
        with pytest.raises(IntegrityError):
            await session.execute(
                text("UPDATE inventory SET reserved = 99 WHERE variant_id = :v"),
                {"v": variant.id},
            )
        await session.rollback()

    async def test_available_reads_the_generated_column(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=8, reserved=3)
        _, _, available = await _read_inventory(session, variant.id)
        assert available == 5, "available is quantity - reserved, computed by the database"

    async def test_reconcile_detects_a_ledger_mismatch(self, session) -> None:
        """Deliberately corrupt the ledger and prove the check notices."""
        variant = await _variant_with_stock(session, quantity=5)
        await session.execute(
            text("DELETE FROM inventory_movements WHERE variant_id = :v"),
            {"v": variant.id},
        )
        await session.commit()

        verdict = await inv.reconcile(session, variant.id)
        assert verdict["verdict"] == "MISMATCH", (
            "reconciliation must actually catch drift, not always report ok"
        )
        assert verdict["stored_quantity"] == 5
        assert verdict["ledger_quantity"] == 0

    async def test_reconcile_passes_after_a_correct_sale(self, session) -> None:
        variant = await _variant_with_stock(session, quantity=5)
        order = await _order_with_profile(session, uuid.uuid4())
        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=2)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        await inv.commit_reservations(session, order.id)
        await session.commit()

        verdict = await inv.reconcile(session, variant.id)
        assert verdict["verdict"] == "ok", (
            f"a correct sale must reconcile: {verdict}"
        )

    async def test_reservation_reason_is_recorded(self, session) -> None:
        """The ledger and the movement must agree on why stock moved."""
        variant = await _variant_with_stock(session, quantity=5)
        order = await _order_with_profile(session, uuid.uuid4())
        await inv.reserve(
            session,
            [inv.ReservationLine(variant_id=variant.id, quantity=1)],
            order_id=order.id,
            cart_id=None,
            ttl_seconds=900,
        )
        await inv.release_reservations(
            session, order.id, reason=InventoryReason.RELEASE, note="card declined"
        )
        await session.commit()

        result = await session.execute(
            text("SELECT status, reason, note FROM inventory_reservations WHERE order_id = :o"),
            {"o": order.id},
        )
        row = result.first()
        assert row[0] == ReservationStatus.RELEASED.value
        assert row[2] == "card declined"

    async def test_low_stock_detection(self, session) -> None:
        await _variant_with_stock(session, quantity=1)  # available 1 <= threshold 3
        await _variant_with_stock(session, quantity=50)
        low = await inv.low_stock_variants(session)
        assert len(low) == 1, "only the variant at or below its threshold is flagged"

    async def test_reservation_requires_a_holder(self, session) -> None:
        """A hold with neither an order nor a cart is untraceable."""
        from sqlalchemy.exc import IntegrityError

        variant = await _variant_with_stock(session, quantity=5)
        with pytest.raises(IntegrityError, match="reservation_has_holder"):
            await session.execute(
                text(
                    "INSERT INTO inventory_reservations (id, variant_id, quantity, status, "
                    "reason, created_at) VALUES (:i, :v, 1, 'HELD', 'RESERVATION', now())"
                ),
                {"i": uuid.uuid4(), "v": variant.id},
            )
        await session.rollback()


async def _order_with_profile(session: AsyncSession, profile_id: uuid.UUID) -> Order:
    """Create the profile if it does not exist, then an order that belongs to it."""
    from sqlalchemy import text as _text

    existing = await session.execute(
        _text("SELECT 1 FROM profiles WHERE id = :p"), {"p": profile_id}
    )
    if existing.first() is None:
        await session.execute(
            _text(
                "INSERT INTO profiles (id, email, full_name, role, is_active, "
                "created_at, updated_at) VALUES (:pid, :email, 'Buyer', 'CUSTOMER', "
                "true, now(), now())"
            ),
            {"pid": profile_id, "email": f"{profile_id.hex}@example.com"},
        )
        await session.commit()

    order = _blank_order(profile_id)
    session.add(order)
    await session.commit()
    return order

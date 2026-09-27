"""database-generated columns, search vector and integrity triggers

Revision ID: 0002_triggers
Revises: a20691d97538
Created: 2026-09-27

What this migration adds, and why it is not expressible in the ORM:

* ``products.search_vector`` - a weighted tsvector maintained by a BEFORE
  trigger. Weights are a tuning decision that should be reviewable as SQL
  rather than hidden in Python.
* ``products.price_min`` / ``price_max`` - maintained by triggers on
  ``product_variants``. A generated column cannot span two tables, and a
  listing page needs "from Rs.X" to be correct the instant a variant price
  changes. A stale floor price is a customer-facing bug.
* ``categories.path`` - materialised ancestor chain, so a whole subtree is
  fetched with one indexed predicate instead of a recursive CTE per request.
* ``updated_at`` - set by a trigger, not by the ORM. SQLAlchemy's ``onupdate``
  only fires for ORM writes, so a maintenance script or a future service doing
  raw SQL would silently leave stale timestamps.

Implementation note: every ``op.execute`` below carries exactly ONE statement.
asyncpg sends parameterless ``op.execute`` calls as prepared statements, and a
prepared statement cannot contain multiple commands - passing a whole function
body fails with "cannot insert multiple commands into a prepared statement".
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_triggers"
down_revision: str | None = "f93d8a27effa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FN_SET_UPDATED_AT = """
CREATE OR REPLACE FUNCTION fn_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$
"""

_FN_SEARCH_VECTOR = """
CREATE OR REPLACE FUNCTION fn_products_search_vector() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Weight A: the words a shopper actually types.
    -- Weight B: brand and SKU, which people paste from an invoice.
    -- Weight C: body copy - good for "noise cancelling" style queries, too
    --           diluted to rank on its own.
    NEW.search_vector :=
           setweight(
               to_tsvector('english',
                   coalesce(NEW.title, '') || ' ' ||
                   coalesce(NEW.subtitle, '') || ' ' ||
                   coalesce(NEW.short_description, '')),
               'A')
        || setweight(
               to_tsvector('english',
                   coalesce(NEW.brand, '') || ' ' || coalesce(NEW.sku, '')),
               'B')
        || setweight(
               to_tsvector('english', coalesce(NEW.description, '')),
               'C');
    RETURN NEW;
END;
$$
"""

_FN_SYNC_PRICE_RANGE = """
CREATE OR REPLACE FUNCTION fn_sync_product_price_range(p_product_id uuid)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_base bigint;
    v_min  bigint;
    v_max  bigint;
BEGIN
    SELECT base_price INTO v_base FROM products WHERE id = p_product_id;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Only purchasable variants set the advertised floor. A discontinued
    -- colourway at a lower price must not advertise "from Rs.1,299" for a
    -- product nobody can buy at that price.
    SELECT min(COALESCE(v.price_override, v_base)),
           max(COALESCE(v.price_override, v_base))
      INTO v_min, v_max
      FROM product_variants v
     WHERE v.product_id = p_product_id
       AND v.status = 'ACTIVE';

    UPDATE products
       SET price_min = v_min,
           price_max = v_max
     WHERE id = p_product_id
       AND (price_min IS DISTINCT FROM v_min OR price_max IS DISTINCT FROM v_max);
END;
$$
"""

_FN_VARIANT_PRICE_RANGE = """
CREATE OR REPLACE FUNCTION fn_product_variants_price_range() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM fn_sync_product_price_range(OLD.product_id);
        RETURN OLD;
    END IF;

    PERFORM fn_sync_product_price_range(NEW.product_id);

    -- A variant moved between products: the old product's range is now stale.
    IF TG_OP = 'UPDATE' AND OLD.product_id IS DISTINCT FROM NEW.product_id THEN
        PERFORM fn_sync_product_price_range(OLD.product_id);
    END IF;
    RETURN NEW;
END;
$$
"""

_FN_PRODUCT_BASE_PRICE_RANGE = """
CREATE OR REPLACE FUNCTION fn_products_base_price_range() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.base_price IS DISTINCT FROM OLD.base_price THEN
        PERFORM fn_sync_product_price_range(NEW.id);
    END IF;
    RETURN NEW;
END;
$$
"""

_FN_CATEGORY_PATH = """
CREATE OR REPLACE FUNCTION fn_sync_category_path() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_parent_path text;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path := '';
        RETURN NEW;
    END IF;

    SELECT coalesce(parent.path, '') INTO v_parent_path
      FROM categories parent
     WHERE parent.id = NEW.parent_id;

    IF v_parent_path IS NULL THEN
        -- Parent is being created in the same statement, or does not exist.
        -- The FK will reject a genuinely missing parent; leave path empty.
        v_parent_path := '';
    END IF;

    NEW.path := CASE
        WHEN v_parent_path = '' THEN NEW.parent_id::text
        ELSE v_parent_path || ',' || NEW.parent_id::text
    END;

    -- Cycle detection must run here, against the parent's *own* ancestor
    -- chain, immediately after the path is computed and in the same trigger.
    -- Two separate BEFORE triggers would run in alphabetical name order, and
    -- validating against the pre-existing path would let a cycle through.
    --
    -- Comparing against NEW.path would be wrong: NEW.path is by construction
    -- the parent's chain *plus* the parent id, so every legitimate
    -- parent/child insert would look like a cycle.
    IF NEW.parent_id = NEW.id THEN
        RAISE EXCEPTION 'category % cannot be its own parent', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;

    IF v_parent_path <> ''
       AND NEW.id::text = ANY(string_to_array(v_parent_path, ',')) THEN
        RAISE EXCEPTION 'category % would become a descendant of itself', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$
"""

#: Tables carrying an ``updated_at`` column.
_UPDATED_AT_TABLES = (
    "profiles",
    "addresses",
    "categories",
    "products",
    "product_variants",
    "product_images",
    "inventory",
    "carts",
    "cart_items",
    "wishlists",
    "wishlist_items",
    "orders",
    "order_items",
    "payments",
    "refunds",
    "shipping_methods",
    "coupons",
    "reviews",
    "newsletter_subscribers",
    "tags",
)

_TRIGGERS = (
    ("trg_products_search_vector", "products", """
        CREATE TRIGGER trg_products_search_vector
        BEFORE INSERT OR UPDATE OF title, subtitle, brand, sku, short_description, description
        ON products
        FOR EACH ROW EXECUTE FUNCTION fn_products_search_vector()
    """),
    ("trg_product_variants_price_range", "product_variants", """
        CREATE TRIGGER trg_product_variants_price_range
        AFTER INSERT OR UPDATE OF product_id, price_override, status OR DELETE
        ON product_variants
        FOR EACH ROW EXECUTE FUNCTION fn_product_variants_price_range()
    """),
    ("trg_products_base_price_range", "products", """
        CREATE TRIGGER trg_products_base_price_range
        AFTER UPDATE OF base_price ON products
        FOR EACH ROW EXECUTE FUNCTION fn_products_base_price_range()
    """),
    ("trg_categories_path", "categories", """
        CREATE TRIGGER trg_categories_path
        BEFORE INSERT OR UPDATE OF parent_id ON categories
        FOR EACH ROW EXECUTE FUNCTION fn_sync_category_path()
    """),
)


def upgrade() -> None:
    op.execute(_FN_SET_UPDATED_AT)
    for table in _UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at()"
        )

    op.execute(_FN_SEARCH_VECTOR)
    op.execute(_FN_SYNC_PRICE_RANGE)
    op.execute(_FN_VARIANT_PRICE_RANGE)
    op.execute(_FN_PRODUCT_BASE_PRICE_RANGE)
    op.execute(_FN_CATEGORY_PATH)

    for _name, _table, ddl in _TRIGGERS:
        op.execute(ddl)

    # Backfill rows that predate the triggers. On a fresh database both
    # statements touch nothing, so the migration behaves identically whether it
    # runs against an empty schema or a populated one.
    op.execute("UPDATE products SET base_price = base_price")
    op.execute("UPDATE categories SET parent_id = parent_id")


def downgrade() -> None:
    for _name, table, _ddl in _TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {_name} ON {table}")
    for table in _UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.execute("DROP FUNCTION IF EXISTS fn_set_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS fn_products_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS fn_sync_product_price_range(uuid)")
    op.execute("DROP FUNCTION IF EXISTS fn_product_variants_price_range()")
    op.execute("DROP FUNCTION IF EXISTS fn_products_base_price_range()")
    op.execute("DROP FUNCTION IF EXISTS fn_sync_category_path()")

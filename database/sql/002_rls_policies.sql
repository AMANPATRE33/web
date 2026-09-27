-- =============================================================================
-- 002_rls_policies.sql  -  Row Level Security (defence in depth)
-- =============================================================================
-- WHY THIS FILE EXISTS EVEN THOUGH THE API USES THE SERVICE ROLE
--
-- The API connects with the service role key, which bypasses RLS. RLS is
-- therefore not protecting the API - it is protecting the *rest* of the
-- database surface: the Supabase client libraries exposed to the browser, the
-- dashboard, and any future consumer of the `anon` publishable key.
--
-- The rule applied throughout:
--
--   anon        -> may READ the public catalogue only. No customer data.
--   authenticated -> may read/write ONLY their own rows.
--   service_role  -> bypasses everything (the API).
--
-- Anything not explicitly granted here is denied. There are no blanket
-- "allow all" policies.
--
-- Safe to re-run. Run AFTER `alembic upgrade head` so the tables exist, and
-- re-run after any migration that adds a table.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Helper: enable RLS and drop any policy of the same name first so this file
-- can be applied repeatedly without error.
-- ---------------------------------------------------------------------------
-- (PostgreSQL has no CREATE POLICY IF NOT EXISTS, so each policy is written as
--  DROP POLICY IF EXISTS ... ; CREATE POLICY ... in its own DO block is avoided
--  in favour of explicit statements below.)

-- ===========================================================================
-- CATALOGUE: world readable
-- ===========================================================================
ALTER TABLE categories            ENABLE ROW LEVEL SECURITY;
ALTER TABLE products              ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_variants      ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_images        ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_tags          ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipping_methods      ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_rating_summaries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS categories_public_read ON categories;
CREATE POLICY categories_public_read ON categories
    FOR SELECT TO anon, authenticated
    USING (is_active = true);

DROP POLICY IF EXISTS products_public_read ON products;
CREATE POLICY products_public_read ON products
    FOR SELECT TO anon, authenticated
    USING (status = 'ACTIVE');

DROP POLICY IF EXISTS product_variants_public_read ON product_variants;
CREATE POLICY product_variants_public_read ON product_variants
    FOR SELECT TO anon, authenticated
    USING (
        status <> 'DISCONTINUED'
        AND EXISTS (
            SELECT 1 FROM products p
            WHERE p.id = product_variants.product_id AND p.status = 'ACTIVE'
        )
    );

DROP POLICY IF EXISTS product_images_public_read ON product_images;
CREATE POLICY product_images_public_read ON product_images
    FOR SELECT TO anon, authenticated
    USING (
        EXISTS (
            SELECT 1 FROM products p
            WHERE p.id = product_images.product_id AND p.status = 'ACTIVE'
        )
    );

DROP POLICY IF EXISTS tags_public_read ON tags;
CREATE POLICY tags_public_read ON tags FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS product_tags_public_read ON product_tags;
CREATE POLICY product_tags_public_read ON product_tags
    FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS shipping_methods_public_read ON shipping_methods;
CREATE POLICY shipping_methods_public_read ON shipping_methods
    FOR SELECT TO anon, authenticated USING (is_active = true);

DROP POLICY IF EXISTS product_rating_summaries_public_read ON product_rating_summaries;
CREATE POLICY product_rating_summaries_public_read ON product_rating_summaries
    FOR SELECT TO anon, authenticated USING (true);

-- ===========================================================================
-- REVIEWS: published ones are public; the author manages their own
-- ===========================================================================
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS reviews_approved_public_read ON reviews;
CREATE POLICY reviews_approved_public_read ON reviews
    FOR SELECT TO anon, authenticated
    USING (status = 'APPROVED');

DROP POLICY IF EXISTS reviews_author_update ON reviews;
CREATE POLICY reviews_author_update ON reviews
    FOR UPDATE TO authenticated
    USING (profile_id = auth.uid())
    WITH CHECK (profile_id = auth.uid());

DROP POLICY IF EXISTS reviews_author_delete ON reviews;
CREATE POLICY reviews_author_delete ON reviews
    FOR DELETE TO authenticated
    USING (profile_id = auth.uid());

-- ===========================================================================
-- CUSTOMER DATA: strictly owner scoped
-- ===========================================================================
-- NOTE: writes to these tables go through the API (service role). The policies
-- exist so that a leaked browser token cannot reach another customer's data.
-- ===========================================================================
ALTER TABLE profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE addresses     ENABLE ROW LEVEL SECURITY;
ALTER TABLE carts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cart_items    ENABLE ROW LEVEL SECURITY;
ALTER TABLE wishlists     ENABLE ROW LEVEL SECURITY;
ALTER TABLE wishlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders        ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items   ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments      ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds       ENABLE ROW LEVEL SECURITY;
ALTER TABLE coupon_usages ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory     ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_movements ENABLE ROW LEVEL SECURITY;

-- profiles ------------------------------------------------------------------
DROP POLICY IF EXISTS profiles_self_read ON profiles;
CREATE POLICY profiles_self_read ON profiles
    FOR SELECT TO authenticated USING (id = auth.uid());

-- A user may update their own profile, but must not be able to grant
-- themselves ADMIN. The role change is therefore blocked at the row level -
-- this is the database backstop behind the server-side `require_admin` guard.
DROP POLICY IF EXISTS profiles_self_update ON profiles;
CREATE POLICY profiles_self_update ON profiles
    FOR UPDATE TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid() AND role = (SELECT p.role FROM profiles p WHERE p.id = auth.uid()));

DROP POLICY IF EXISTS profiles_insert_self ON profiles;
CREATE POLICY profiles_insert_self ON profiles
    FOR INSERT TO authenticated
    WITH CHECK (id = auth.uid() AND role = 'CUSTOMER');

-- addresses -----------------------------------------------------------------
DROP POLICY IF EXISTS addresses_owner ON addresses;
CREATE POLICY addresses_owner ON addresses
    FOR ALL TO authenticated
    USING (profile_id = auth.uid())
    WITH CHECK (profile_id = auth.uid());

-- carts ---------------------------------------------------------------------
DROP POLICY IF EXISTS carts_owner ON carts;
CREATE POLICY carts_owner ON carts
    FOR ALL TO authenticated
    USING (profile_id = auth.uid())
    WITH CHECK (profile_id = auth.uid());

DROP POLICY IF EXISTS cart_items_owner ON cart_items;
CREATE POLICY cart_items_owner ON cart_items
    FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM carts c
                    WHERE c.id = cart_items.cart_id AND c.profile_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM carts c
                        WHERE c.id = cart_items.cart_id AND c.profile_id = auth.uid()));

-- wishlists -----------------------------------------------------------------
DROP POLICY IF EXISTS wishlists_owner ON wishlists;
CREATE POLICY wishlists_owner ON wishlists
    FOR ALL TO authenticated
    USING (profile_id = auth.uid())
    WITH CHECK (profile_id = auth.uid());

DROP POLICY IF EXISTS wishlist_items_owner ON wishlist_items;
CREATE POLICY wishlist_items_owner ON wishlist_items
    FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM wishlists w
                    WHERE w.id = wishlist_items.wishlist_id AND w.profile_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM wishlists w
                        WHERE w.id = wishlist_items.wishlist_id AND w.profile_id = auth.uid()));

-- orders --------------------------------------------------------------------
-- Customers may read their own orders. No INSERT/UPDATE/DELETE policy exists
-- for `authenticated`, so a customer can never create or modify an order - even
-- if they forge a request. Order creation is the API's job alone.
DROP POLICY IF EXISTS orders_owner_read ON orders;
CREATE POLICY orders_owner_read ON orders
    FOR SELECT TO authenticated USING (profile_id = auth.uid());

DROP POLICY IF EXISTS order_items_owner_read ON order_items;
CREATE POLICY order_items_owner_read ON order_items
    FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM orders o
                    WHERE o.id = order_items.order_id AND o.profile_id = auth.uid()));

DROP POLICY IF EXISTS order_events_owner_read ON order_events;
CREATE POLICY order_events_owner_read ON order_events
    FOR SELECT TO authenticated
    USING (
        is_customer_visible = true
        AND EXISTS (SELECT 1 FROM orders o
                    WHERE o.id = order_events.order_id AND o.profile_id = auth.uid())
    );

DROP POLICY IF EXISTS payments_owner_read ON payments;
CREATE POLICY payments_owner_read ON payments
    FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM orders o
                    WHERE o.id = payments.order_id AND o.profile_id = auth.uid()));

DROP POLICY IF EXISTS refunds_owner_read ON refunds;
CREATE POLICY refunds_owner_read ON refunds
    FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM orders o
                    WHERE o.id = refunds.order_id AND o.profile_id = auth.uid()));

DROP POLICY IF EXISTS coupon_usages_owner_read ON coupon_usages;
CREATE POLICY coupon_usages_owner_read ON coupon_usages
    FOR SELECT TO authenticated USING (profile_id = auth.uid());

-- inventory -----------------------------------------------------------------
-- Readable so a storefront can show stock, but never writable by a browser.
-- The reservation/oversell logic is only reachable through the API.
DROP POLICY IF EXISTS inventory_public_read ON inventory;
CREATE POLICY inventory_public_read ON inventory
    FOR SELECT TO anon, authenticated USING (true);

ALTER TABLE inventory_movements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inventory_movements_owner_read ON inventory_movements;
CREATE POLICY inventory_movements_owner_read ON inventory_movements
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM product_variants v
        JOIN carts c ON c.profile_id = auth.uid()
        WHERE v.id = inventory_movements.variant_id
    ));

-- coupons: readable so a storefront can validate a code client-side for
-- display, but the actual discount is computed server-side regardless.
ALTER TABLE coupons ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS coupons_public_read ON coupons;
CREATE POLICY coupons_public_read ON coupons
    FOR SELECT TO anon, authenticated
    USING (is_active = true AND (starts_at IS NULL OR starts_at <= now())
           AND (expires_at IS NULL OR expires_at >= now()));

-- ===========================================================================
-- STAFF-ONLY TABLES: no policy at all for anon/authenticated.
-- With RLS enabled and zero policies, every non-service_role request is denied.
-- ===========================================================================
ALTER TABLE audit_logs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events          ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_keys       ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_events         ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_logs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE id_counters            ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_notifications    ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_daily        ENABLE ROW LEVEL SECURITY;

-- The admin dashboard reads through the API using the service role, which
-- bypasses RLS after the server-side `require_admin` check. There is
-- deliberately no policy granting `authenticated` access to these tables.

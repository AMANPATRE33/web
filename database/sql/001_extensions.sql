-- =============================================================================
-- 001_extensions.sql  -  Supabase prerequisites
-- =============================================================================
-- Run order: 001 -> 002 -> 003 -> 004, then `alembic upgrade head`.
--
-- 0000_extensions (Alembic) already provisions pgcrypto, citext, pg_trgm and
-- btree_gin. This file only covers the Supabase-specific bits that Alembic must
-- not own, and is safe to re-run.
-- =============================================================================

-- Supabase keeps pgcrypto in the `extensions` schema. The API sets
-- search_path = public, extensions on every connection, so gen_random_uuid()
-- resolves either way. Creating the schema first keeps a brand new project
-- consistent with what the API expects.
CREATE SCHEMA IF NOT EXISTS extensions;

-- Row Level Security is enabled per table in 002_rls_policies.sql, but the
-- table owner (postgres) bypasses RLS by default. That is intentional: the API
-- uses the service role and must be able to read other customers' orders when
-- acting as staff.
--
-- What RLS is actually here for: containing a leaked `anon` / publishable key.
-- Without policies, an anon key can read every table in `public`. With the
-- policies below, an anon key can read the catalogue and nothing else.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO postgres, anon, authenticated;

-- =============================================================================
-- 004_auth_integration.sql  -  tie Supabase Auth to `profiles`
-- =============================================================================
-- Two independent mechanisms guarantee a profile row exists for every
-- authenticated user:
--
--   1. This trigger (database side). Catches users created through the
--      dashboard, the auth admin API, or any future path.
--   2. `ensure_profile()` in app/api/deps.py (application side). Runs on every
--      authenticated request and upserts if the row is somehow missing.
--
-- (2) alone would be sufficient. (1) exists so that a row is present even if a
-- request never reaches the API, and so the two mechanisms can be cross-checked.
--
-- Every statement is guarded by a check for the `auth` schema, which only
-- exists on Supabase. That keeps the file safe to run against a plain
-- PostgreSQL instance (it simply does nothing) and safe to re-run.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'auth') THEN
        RAISE NOTICE 'auth schema not present - skipping profile trigger (not a Supabase project)';
        RETURN;
    END IF;

    -- -------------------------------------------------------------------------
    -- Create the profile automatically on signup
    -- -------------------------------------------------------------------------
    EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.fn_handle_new_user()
    RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    AS $body$
    BEGIN
        -- metadata supplied by the client at sign-up. Only these three fields
        -- are read; anything else the caller puts in raw_user_meta_data is
        -- ignored, so a signup request cannot set `role` or `is_active`.
        INSERT INTO public.profiles (id, email, full_name, phone, role, is_active)
        VALUES (
            NEW.id,
            lower(NEW.email),
            NULLIF(NEW.raw_user_meta_data ->> 'full_name', ''),
            NULLIF(NEW.raw_user_meta_data ->> 'phone', ''),
            'CUSTOMER',
            true
        )
        ON CONFLICT (id) DO NOTHING;
        RETURN NEW;
    END
    $body$;
    $fn$;

    DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
    EXECUTE $trg$
    CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.fn_handle_new_user()
    $trg$;

    -- -------------------------------------------------------------------------
    -- Keep the profile email in step when the user changes theirs
    -- -------------------------------------------------------------------------
    EXECUTE $fn2$
    CREATE OR REPLACE FUNCTION public.fn_handle_user_email_change()
    RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    AS $body2$
    BEGIN
        IF NEW.email IS DISTINCT FROM OLD.email THEN
            UPDATE public.profiles SET email = lower(NEW.email) WHERE id = NEW.id;
        END IF;
        RETURN NEW;
    END
    $body2$;
    $fn2$;

    DROP TRIGGER IF EXISTS on_auth_user_email_changed ON auth.users;
    EXECUTE $trg2$
    CREATE TRIGGER on_auth_user_email_changed
        AFTER UPDATE OF email ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.fn_handle_user_email_change()
    $trg2$;

    -- -------------------------------------------------------------------------
    -- Foreign key to the auth user
    -- -------------------------------------------------------------------------
    -- Declared here rather than in Alembic because the `auth` schema does not
    -- exist on a plain PostgreSQL instance, which would make the migration
    -- chain unrunnable outside Supabase.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_profiles_auth_user'
    ) THEN
        EXECUTE $fk$
        ALTER TABLE public.profiles
            ADD CONSTRAINT fk_profiles_auth_user
            FOREIGN KEY (id) REFERENCES auth.users (id) ON DELETE CASCADE
        $fk$;
    END IF;

    RAISE NOTICE 'Supabase auth integration applied';
END
$$;

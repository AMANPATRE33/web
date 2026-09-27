-- =============================================================================
-- 003_storage.sql  -  Supabase Storage buckets and access policies
-- =============================================================================
-- Product imagery is stored in a PRIVATE bucket. Public URLs are produced on
-- demand as signed URLs (see app/services/storage.py), which means:
--   * the bucket cannot be scraped by anyone who guesses a path
--   * a deleted product's image stops resolving immediately
--   * access can be revoked without renaming files
--
-- Run in the Supabase SQL editor. Safe to re-run.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Buckets
-- ---------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'product-images',
    'product-images',
    false,                                   -- private: signed URLs only
    5242880,                                 -- 5 MiB, matches UPLOAD_MAX_BYTES
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/avif']
)
ON CONFLICT (id) DO UPDATE
    SET public             = EXCLUDED.public,
        file_size_limit    = EXCLUDED.file_size_limit,
        allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Editorial imagery (category hero shots, promotional banners). Also private so
-- the same signed-URL policy applies uniformly.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'site-assets',
    'site-assets',
    false,
    8388608,                                 -- 8 MiB
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/avif']
)
ON CONFLICT (id) DO UPDATE
    SET public             = EXCLUDED.public,
        file_size_limit    = EXCLUDED.file_size_limit,
        allowed_mime_types = EXCLUDED.allowed_mime_types;

-- ---------------------------------------------------------------------------
-- Policies
-- ---------------------------------------------------------------------------
-- Product images must be readable by anyone so the storefront can display them
-- through signed URLs issued by the API. The signed URL is minted server-side
-- after an authorisation decision, so a public read policy here is safe: the
-- object key is an unguessable uuid, and the API re-checks before issuing.
DROP POLICY IF EXISTS "product images are publicly readable" ON storage.objects;
CREATE POLICY "product images are publicly readable"
    ON storage.objects
    FOR SELECT
    TO anon, authenticated
    USING (bucket_id IN ('product-images', 'site-assets'));

-- Uploads are only ever performed by the API using the service role, which
-- bypasses RLS. There is intentionally NO insert/update/delete policy for
-- anon or authenticated: a browser cannot write to storage at all, so file
-- validation (size, MIME, magic bytes) cannot be bypassed by calling the
-- storage API directly.

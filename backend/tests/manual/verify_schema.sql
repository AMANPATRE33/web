-- Structural verification of the migrated schema. Read-only.
\pset pager off

\echo '=== enum types ==='
SELECT t.typname, string_agg(e.enumlabel, ', ' ORDER BY e.enumsortorder) AS values
FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname = 'public'
GROUP BY t.typname ORDER BY t.typname;

\echo ''
\echo '=== generated columns ==='
SELECT table_name, column_name, is_generated, generation_expression
FROM information_schema.columns
WHERE table_schema = 'public' AND is_generated = 'ALWAYS'
ORDER BY table_name, column_name;

\echo ''
\echo '=== partial unique indexes (integrity rules) ==='
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND indexdef LIKE '%UNIQUE%WHERE%'
ORDER BY tablename, indexname;

\echo ''
\echo '=== check constraints ==='
SELECT c.relname AS table_name, con.conname, pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
WHERE con.contype = 'c' AND con.connamespace = 'public'::regnamespace
ORDER BY c.relname, con.conname;

\echo ''
\echo '=== foreign keys ==='
SELECT count(*) AS fk_count FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'public'::regnamespace;

\echo ''
\echo '=== indexes by table ==='
SELECT tablename, count(*) AS index_count
FROM pg_indexes WHERE schemaname = 'public'
GROUP BY tablename ORDER BY tablename;

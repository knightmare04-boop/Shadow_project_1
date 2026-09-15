-- Runs once, on first container init only (docker-entrypoint-initdb.d).
-- Extensions the application and Module 7's query-optimization work depend on.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist; -- exclusion constraints on ranges (fiscal periods)
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy near-duplicate invoice matching (Module 3)

-- WAL archive directory for the backup/restore drill (Module 9) — created here
-- because docker-entrypoint-initdb.d runs as the postgres user with the right perms.

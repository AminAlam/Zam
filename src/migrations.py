"""
Database migrations for Zam.
Run automatically at application startup to keep schema up to date.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Candidate paths to the base schema (same file Postgres' init dir loads on
# a fresh data dir). We re-execute it from the app on every startup so the
# schema is still created when postgres_data carries over from a prior run
# (in which case Postgres skips init scripts entirely).
#
# Two candidates because a wheel install can land src under site-packages
# without bundling the .sql file; the absolute Docker path is the backstop.
_INIT_SQL_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "database", "init.sql"),
    "/app/src/database/init.sql",
]


def _find_init_sql():
    for path in _INIT_SQL_CANDIDATES:
        if os.path.exists(path):
            return path
    return None

# List of migrations in order. Each is a tuple of (version, description, sql)
MIGRATIONS = [
    (1, "Add batch columns to tweet_queue", """
        ALTER TABLE tweet_queue ADD COLUMN IF NOT EXISTS batch_id TEXT;
        ALTER TABLE tweet_queue ADD COLUMN IF NOT EXISTS batch_total INTEGER DEFAULT 1;
        CREATE INDEX IF NOT EXISTS idx_queue_batch_id ON tweet_queue(batch_id);
    """),
    (2, "Add OCR columns to tweet_queue", """
        ALTER TABLE tweet_queue ADD COLUMN IF NOT EXISTS ocr_author TEXT;
        ALTER TABLE tweet_queue ADD COLUMN IF NOT EXISTS ocr_text TEXT;
    """),
    (3, "Add OCR columns to tweets", """
        ALTER TABLE tweets ADD COLUMN IF NOT EXISTS ocr_author TEXT;
        ALTER TABLE tweets ADD COLUMN IF NOT EXISTS ocr_text TEXT;
    """),
    (4, "Add quoted_tweet column to tweet_queue", """
        ALTER TABLE tweet_queue ADD COLUMN IF NOT EXISTS quoted_tweet JSONB;
    """),
]


def _apply_base_schema(db):
    """Apply init.sql to ensure all base tables exist.

    Postgres' docker-entrypoint-initdb.d only runs scripts on a fresh data
    dir. If postgres_data was carried over from an earlier deployment that
    pre-dated tables like tweet_queue, init.sql is silently skipped and the
    versioned migrations below blow up with 'relation does not exist'.
    Running it here, every startup, fixes that — all statements use
    CREATE TABLE IF NOT EXISTS / IF NOT EXISTS guards so re-running is safe.
    """
    path = _find_init_sql()
    if not path:
        logger.warning(
            f"Base schema file not found in any of {_INIT_SQL_CANDIDATES}; skipping"
        )
        return
    with open(path, "r") as fh:
        sql = fh.read()
    if not sql.strip():
        return
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
    logger.info("Base schema ensured (init.sql applied)")


def run_migrations(db):
    """
    Run all pending database migrations.

    Args:
        db: Database instance with get_connection() method
    """
    logger.info("Checking for pending migrations...")

    # Always ensure the base schema exists before versioned migrations run.
    # See _apply_base_schema's docstring for why this is necessary.
    try:
        _apply_base_schema(db)
    except Exception as e:
        logger.error(f"Failed to apply base schema: {e}")
        raise

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Create migrations table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()

            # Get already applied migrations
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}

            # Run pending migrations
            pending = [(v, d, s) for v, d, s in MIGRATIONS if v not in applied]

            if not pending:
                logger.info("Database schema is up to date")
                return

            for version, description, sql in pending:
                logger.info(f"Running migration {version}: {description}")
                try:
                    cursor.execute(sql)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, description) VALUES (%s, %s)",
                        (version, description)
                    )
                    conn.commit()
                    logger.info(f"Migration {version} completed successfully")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration {version} failed: {e}")
                    raise

            logger.info(f"Applied {len(pending)} migration(s)")

    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise

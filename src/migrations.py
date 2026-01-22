"""
Database migrations for Zam.
Run automatically at application startup to keep schema up to date.
"""

import logging

logger = logging.getLogger(__name__)

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
]


def run_migrations(db):
    """
    Run all pending database migrations.
    
    Args:
        db: Database instance with get_connection() method
    """
    logger.info("Checking for pending migrations...")

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

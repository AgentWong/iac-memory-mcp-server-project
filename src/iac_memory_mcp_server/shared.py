"""Shared server instance and database connection.

The database connection requires DATABASE_URL environment variable to be set
to a valid file path. In-memory databases are not supported."""

import logging
import os
import sys
from urllib.parse import urlparse

from .db.connection import DatabaseManager

# Configure module logger
logger = logging.getLogger("iac_memory.shared")

# Add stderr handler if not already present
if not any(
    isinstance(h, logging.StreamHandler) and h.stream == sys.stderr
    for h in logger.handlers
):
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(stderr_handler)
    logger.propagate = False  # Prevent double logging

# Initialize database manager with environment variable or default to data directory
default_db_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "iac_memory.db"
)

# Parse DATABASE_URL if it exists
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("sqlite:///"):
    parsed = urlparse(db_url)
    db_path = parsed.path
else:
    db_path = os.path.abspath(default_db_path)

# Ensure data directory exists
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db = DatabaseManager.get_instance(db_path)


def get_db() -> DatabaseManager:
    """Get the database manager instance and ensure it's initialized."""
    global db
    # Use environment variable if set (for tests)
    db_path = os.getenv("DATABASE_PATH") or os.getenv("MCP_DATABASE_PATH")
    if db_path:
        db = DatabaseManager.get_instance(db_path)
    elif not db or not db.is_initialized():
        db = DatabaseManager.get_instance()
        # Ensure database is properly initialized
        with db.get_connection() as conn:
            # Set required pragmas for reliability and case-insensitive matching
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA case_sensitive_like = OFF") 
            conn.execute("PRAGMA journal_mode = DELETE")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.commit()

            # Verify pragmas were set
            pragmas = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            if not pragmas:
                raise RuntimeError("Failed to enable foreign keys")

            # Clear all tables in a single transaction
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Get all table names dynamically
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()

                # Clear each table
                for (table_name,) in tables:
                    conn.execute(f"DELETE FROM {table_name}")
                conn.commit()
            except:
                conn.rollback()
                raise

            # Verify all tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            # Check for required tables
            required_tables = [
                "schema_version",
                "entities",
                "observations",
                "terraform_providers",
                "terraform_resources",
                "provider_resources",
                "ansible_collections",
                "ansible_modules",
                "entity_relationships",
            ]

            missing_tables = [t for t in required_tables if t not in table_names]
            if missing_tables:
                # Tables missing - need to reinitialize
                db.reset_database()
                # Verify tables were created
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                table_names = [t[0] for t in tables]
                still_missing = [t for t in required_tables if t not in table_names]
                if still_missing:
                    raise RuntimeError(
                        f"Failed to create tables: {', '.join(still_missing)}"
                    )

            # Verify tables again after potential reset
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            if not all(table in table_names for table in required_tables):
                # One more attempt to initialize
                db.reset_database()
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                table_names = [t[0] for t in tables]
                if not all(table in table_names for table in required_tables):
                    raise RuntimeError("Failed to initialize database tables")
    return db

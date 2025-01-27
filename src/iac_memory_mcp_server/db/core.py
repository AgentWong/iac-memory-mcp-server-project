"""Core database operations."""

import logging
import sqlite3
import sys

from .connection import DatabaseError, DatabaseManager, UniqueConstraintError

# Configure module logger
logger = logging.getLogger("iac_memory.db.core")

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


def get_db() -> DatabaseManager:
    """Get the database manager instance."""
    return DatabaseManager.get_instance()


def execute_query(db: DatabaseManager, query: str, params: tuple = ()) -> list:
    """Execute query synchronously with proper error handling."""
    logger.debug(f"Executing query: {query}", extra={"params": params})
    try:
        with db.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            raise UniqueConstraintError(f"Unique constraint violation: {str(e)}")
        raise DatabaseError(f"Integrity error: {str(e)}")
    except sqlite3.Error as e:
        raise DatabaseError(f"Query execution failed: {str(e)}")


def execute_write(db: DatabaseManager, query: str, params: tuple = ()) -> None:
    """Execute write operation synchronously with proper error handling."""
    try:
        with db.get_connection() as conn:
            conn.execute(query, params)
            conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f"Write operation failed: {str(e)}")


def reset_database(db: DatabaseManager) -> None:
    """Drop and recreate all tables - useful for testing."""
    with db.get_connection() as conn:
        # Temporarily disable foreign keys for cleanup
        conn.execute("PRAGMA foreign_keys = OFF")

        # Drop tables in correct order
        conn.executescript(
            """
            DROP TABLE IF EXISTS observations;
            DROP TABLE IF EXISTS entity_relationships; 
            DROP TABLE IF EXISTS entities;
            DROP TABLE IF EXISTS provider_resources;
            DROP TABLE IF EXISTS terraform_resources;
            DROP TABLE IF EXISTS terraform_providers;
            DROP TABLE IF EXISTS ansible_modules;
            DROP TABLE IF EXISTS ansible_collections;
            DROP TABLE IF EXISTS schema_version;
            """
        )

        # Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Reinitialize database
        db._initialized = False
        db._initialize_schema()

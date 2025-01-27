"""Database connection management."""

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Optional

# Configure database logger to inherit from root
db_logger = logging.getLogger("iac_memory.db")


class DatabaseError(Exception):
    """Custom exception for database operations."""

    pass


class UniqueConstraintError(DatabaseError):
    """Raised when a unique constraint is violated."""

    pass


class SchemaError(DatabaseError):
    """Raised when there are schema-related issues."""

    pass


class DatabaseManager:
    """Manages SQLite database connections and operations."""

    _instance: Optional["DatabaseManager"] = None

    def __init__(self, db_path: str | None = None):
        if DatabaseManager._instance is not None:
            raise RuntimeError("Use get_instance() instead")

        self.db_path = db_path or os.getenv("DATABASE_URL")
        if not self.db_path:
            raise DatabaseError("DATABASE_URL environment variable must be set")

        if self.db_path == ":memory:" or self.db_path.startswith("file::memory:"):
            raise DatabaseError("In-memory databases are not supported")

        self._initialized = False
        db_logger.info(f"Connecting to database: {self.db_path}")
        db_logger.debug("Creating database directory if needed")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._initialize_schema()

    def _initialize_schema(self):
        """Initialize database schema."""
        db_logger.info("Initializing database schema")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            schema_path = Path(__file__).parent.parent / "schema.sql"
            if not schema_path.exists():
                raise DatabaseError(f"Schema file not found at {schema_path}")

            with open(schema_path) as f:
                schema_sql = f.read()
                if not schema_sql.strip():
                    raise DatabaseError("Schema file is empty")

                conn.executescript(schema_sql)
                conn.commit()

            self._initialized = True
        finally:
            conn.close()

    @classmethod
    def get_instance(cls, db_path: str | None = None) -> "DatabaseManager":
        """Get or create the DatabaseManager singleton instance."""
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        if cls._instance:
            try:
                with cls._instance.get_connection() as conn:
                    conn.execute("PRAGMA optimize")
                    conn.close()
            except Exception:
                pass
            finally:
                cls._instance = None

    def is_initialized(self) -> bool:
        """Check if database has been initialized."""
        return self._initialized

    def reset_database(self) -> None:
        """Reset database to initial state. Used for testing."""
        db_logger.warning("Resetting database to initial state")
        try:
            with self.get_connection() as conn:
                try:
                    conn.execute("PRAGMA foreign_keys = OFF")
                    conn.execute("BEGIN IMMEDIATE")

                    # Drop all tables in correct dependency order
                    tables = [
                        "observations",
                        "entity_relationships",
                        "provider_resources",
                        "terraform_resources",
                        "ansible_modules",
                        "entities",
                        "terraform_providers",
                        "ansible_collections",
                        "schema_version",
                    ]

                    for table in tables:
                        conn.execute(f"DROP TABLE IF EXISTS {table}")

                    # Reset sequences
                    conn.execute("DELETE FROM sqlite_sequence")
                    conn.execute("PRAGMA foreign_keys = ON")
                    conn.commit()
                except sqlite3.Error as e:
                    conn.rollback()
                    raise DatabaseError(f"Failed to reset database: {str(e)}")

            # Reinitialize schema
            self._initialized = False
            self._initialize_schema()
        except Exception as e:
            raise DatabaseError(f"Failed to reset database: {str(e)}")

    def execute_query(self, query: str, params: tuple = ()) -> list:
        """Execute a read query and return results."""
        db_logger.debug(f"Executing read query: {query}", extra={"params": params})
        with self.get_connection() as conn:
            try:
                return [dict(row) for row in conn.execute(query, params).fetchall()]
            except sqlite3.Error as e:
                raise DatabaseError(f"Query failed: {str(e)}")

    def execute_write(self, query: str, params: tuple = ()) -> str:
        """Execute a write query within a transaction."""
        db_logger.debug(f"Executing write query: {query}", extra={"params": params})
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(query, params)
                conn.commit()
                if query.strip().upper().startswith("INSERT"):
                    db_logger.info(
                        f"Database operation successful: {query}",
                        extra={"params": params},
                    )
                    return cursor.lastrowid
            except sqlite3.Error as e:
                conn.rollback()
                raise DatabaseError(f"Write operation failed: {str(e)}")
            return ""

    def add_terraform_provider(
        self, name: str, version: str, source_url: str, doc_url: str
    ) -> str:
        """Add a new Terraform provider."""
        from .terraform import add_terraform_provider

        return add_terraform_provider(self, name, version, source_url, doc_url)

    def add_terraform_resource(
        self,
        provider_id: str,
        name: str,
        resource_type: str,
        schema: str,
        version: str,
        doc_url: str,
    ) -> str:
        """Add a new Terraform resource."""
        from .terraform import add_terraform_resource

        return add_terraform_resource(
            self, provider_id, name, resource_type, schema, version, doc_url
        )

    def update_provider_version(
        self,
        provider_id: str,
        new_version: str,
        new_source_url: str | None = None,
        new_doc_url: str | None = None,
    ) -> bool:
        """Update a provider's version."""
        try:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Build update query dynamically
                    updates = ["version = ?"]
                    params = [new_version]

                    if new_source_url:
                        updates.append("source_url = ?")
                        params.append(new_source_url)
                    if new_doc_url:
                        updates.append("doc_url = ?")
                        params.append(new_doc_url)

                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(provider_id)  # Add provider_id last

                    query = f"""UPDATE terraform_providers 
                              SET {', '.join(updates)}
                              WHERE id = ?"""

                    cursor = conn.execute(query, tuple(params))
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    raise
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to update provider version: {str(e)}")

    def add_ansible_collection(
        self, name: str, version: str, source_url: str, doc_url: str
    ) -> str:
        """Add a new Ansible collection."""
        from .ansible import add_ansible_collection

        return add_ansible_collection(self, name, version, source_url, doc_url)

    def add_ansible_module(
        self,
        collection_id: str,
        name: str,
        module_type: str,
        schema: str,
        version: str,
        doc_url: str,
    ) -> str:
        """Add a new Ansible module."""
        from .ansible import add_ansible_module

        return add_ansible_module(
            self, collection_id, name, module_type, schema, version, doc_url
        )

    def update_collection_version(
        self,
        collection_id: str,
        new_version: str,
        new_source_url: str = None,
        new_doc_url: str = None,
    ) -> bool:
        """Update a collection's version."""
        from .ansible import update_collection_version

        return update_collection_version(
            self, collection_id, new_version, new_source_url, new_doc_url
        )

    def get_provider_resources(self, provider_id: str) -> list:
        """Get resources for a provider."""
        from .terraform import get_provider_resources

        return get_provider_resources(self, provider_id)

    def get_resource_info(self, resource_id: str) -> dict:
        """Get resource information."""
        from .terraform import get_resource_info

        return get_resource_info(self, resource_id)

    def update_resource_schema(
        self,
        resource_id: str,
        new_schema: str,
        new_version: str | None = None,
        new_doc_url: str | None = None,
    ) -> bool:
        """Update a resource's schema."""
        try:
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Build update query dynamically
                    updates = ["schema = ?"]
                    params = [new_schema]

                    if new_version:
                        updates.append("version = ?")
                        params.append(new_version)
                    if new_doc_url:
                        updates.append("doc_url = ?")
                        params.append(new_doc_url)

                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(resource_id)  # Add resource_id last

                    query = f"""UPDATE terraform_resources 
                              SET {', '.join(updates)}
                              WHERE id = ?"""

                    cursor = conn.execute(query, tuple(params))
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    raise
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to update resource schema: {str(e)}")

    def get_collection_modules(self, collection_id: str) -> list:
        """Get modules for a collection."""
        from .ansible import get_collection_modules

        return get_collection_modules(self, collection_id)

    def get_module_info(self, module_id: str) -> dict:
        """Get module information."""
        from .ansible import get_module_info

        return get_module_info(self, module_id)

    def update_module_version(
        self,
        module_id: str,
        new_schema: str,
        new_version: str = None,
        new_doc_url: str = None,
    ) -> bool:
        """Update a module's version and schema."""
        from .ansible import update_module_version

        return update_module_version(
            self, module_id, new_schema, new_version, new_doc_url
        )

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity by ID."""
        with self.get_connection() as conn:
            try:
                row = conn.execute(
                    "SELECT * FROM entities WHERE id = ?", (entity_id,)
                ).fetchone()
                return dict(row) if row else None
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get entity: {str(e)}")

    def get_entity_relationships(self, entity_id: str) -> list[Dict]:
        """Get relationships for an entity."""
        with self.get_connection() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT e.* FROM entities e
                    JOIN entity_relationships r ON 
                        e.id = r.source_id OR e.id = r.target_id
                    WHERE r.source_id = ? OR r.target_id = ?
                    """,
                    (entity_id, entity_id),
                ).fetchall()
                return [dict(row) for row in rows]
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get entity relationships: {str(e)}")

    @contextmanager
    def get_connection(
        self, timeout: float | None = None
    ) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection using context manager."""
        conn = None
        try:
            # Use immediate mode to prevent writer starvation
            conn = sqlite3.connect(
                self.db_path,
                timeout=timeout
                or 5.0,  # Use provided timeout or 5s default per testing rules
                isolation_level="IMMEDIATE",  # Prevent writer starvation
                check_same_thread=True,  # Enforce thread safety
            )
            conn.row_factory = sqlite3.Row

            # Configure connection with testing-compliant settings
            # Set PRAGMAs before any transactions
            pragmas = [
                ("busy_timeout", "5000"),  # 5 second timeout
                ("journal_mode", "DELETE"),  # Simpler journal mode for testing
                ("synchronous", "NORMAL"),  # Balance between safety and speed
                ("foreign_keys", "ON"),  # Ensure referential integrity
                ("case_sensitive_like", "OFF"),  # Case-insensitive searches
                ("temp_store", "MEMORY"),  # Reduce disk I/O
            ]

            for pragma, value in pragmas:
                conn.execute(f"PRAGMA {pragma} = {value}")
            conn.commit()  # Ensure pragmas are applied

            # Let the caller manage transactions
            try:
                yield conn
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise
        except sqlite3.Error as e:
            if "database is locked" in str(e):
                raise DatabaseError(
                    f"Database is locked (timeout={timeout or 5.0}s). "
                    f"This may indicate too many concurrent connections."
                )
            raise DatabaseError(f"Database error: {str(e)}")
        finally:
            if conn:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                    conn.close()
                except sqlite3.Error:
                    pass  # Already closed or closing

    @contextmanager
    def get_long_running_connection(
        self, timeout: int = 30
    ) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection for long-running operations."""
        conn = None
        try:
            try:
                conn = sqlite3.connect(self.db_path, timeout=float(timeout))
            except sqlite3.OperationalError as e:
                raise DatabaseError(
                    f"Failed to establish long-running connection (timeout={timeout}s): {str(e)}"
                )

            conn.row_factory = sqlite3.Row

            try:
                conn.execute(f"PRAGMA busy_timeout = {timeout * 1000}")
                conn.execute("PRAGMA journal_mode = DELETE")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA case_sensitive_like = OFF")
                conn.execute("PRAGMA temp_store = MEMORY")
                conn.commit()
            except sqlite3.Error as e:
                raise DatabaseError(
                    f"Failed to configure long-running connection: {str(e)}"
                )

            yield conn

        except Exception as e:
            if conn and conn.in_transaction:
                try:
                    conn.rollback()
                except sqlite3.Error as rollback_error:
                    raise DatabaseError(
                        f"Failed to rollback long-running transaction ({str(rollback_error)}) "
                        f"after error: {str(e)}"
                    )
            raise
        finally:
            if conn:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                    conn.close()
                except sqlite3.Error as e:
                    db_logger.warning(
                        f"Failed to cleanup long-running connection: {str(e)}"
                    )

"""Ansible-related database operations."""

import logging
import sqlite3
from typing import Dict, List, Optional

from .connection import DatabaseError, DatabaseManager

# Configure module logger to inherit from root
logger = logging.getLogger("iac_memory.db.ansible")


def add_ansible_collection(
    db: DatabaseManager, name: str, version: str, source_url: str, doc_url: str
) -> str:
    """Add a new Ansible collection."""
    try:
        with db.get_connection() as conn:
            # Set busy timeout before any operations
            conn.execute(
                "PRAGMA busy_timeout = 5000"
            )  # 5 second timeout per testing rules
            conn.execute("BEGIN IMMEDIATE")  # Start transaction
            try:
                cursor = conn.execute(
                    """INSERT INTO ansible_collections
                    (name, version, source_url, doc_url)
                    VALUES (?, ?, ?, ?)""",
                    (name, version, source_url, doc_url),
                )
                collection_id = str(cursor.lastrowid)
                conn.commit()
                return collection_id
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to add Ansible collection: {str(e)}. Operation timed out after 5 seconds."
        )


def get_collection_modules(db: DatabaseManager, collection_identifier: str) -> List[Dict]:
    """Get all modules for a specific Ansible collection.

    Args:
        db: Database manager instance
        collection_identifier: Name or ID of the collection

    Returns:
        List of modules with metadata
    """
    logger.info(
        "Getting collection modules",
        extra={
            "collection_identifier": collection_identifier,
            "operation": "get_collection_modules",
        },
    )

    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout

            # Try to find by ID first, then by name
            modules = conn.execute(
                """SELECT m.*, c.name as collection_name, c.version as collection_version
                FROM ansible_modules m
                JOIN ansible_collections c ON m.collection_id = c.id
                WHERE c.id = ? OR c.name = ?
                ORDER BY m.name""",
                (collection_identifier, collection_identifier),
            ).fetchall()

            return [dict(m) for m in modules]

    except sqlite3.Error as e:
        error_msg = f"Failed to get collection modules: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def update_collection_version(
    db: DatabaseManager,
    collection_id: str,
    new_version: str,
    new_source_url: Optional[str] = None,
    new_doc_url: Optional[str] = None,
) -> bool:
    """Update an Ansible collection's version and optional URLs."""
    try:
        updates = ["version = ?"]
        params = [new_version]

        if new_source_url:
            updates.append("source_url = ?")
            params.append(new_source_url)
        if new_doc_url:
            updates.append("doc_url = ?")
            params.append(new_doc_url)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(collection_id)

        with db.get_connection() as conn:
            # Set busy timeout before any operations
            conn.execute(
                "PRAGMA busy_timeout = 5000"
            )  # 5 second timeout per testing rules
            conn.execute("BEGIN IMMEDIATE")  # Start transaction
            try:
                cursor = conn.execute(
                    f"""UPDATE ansible_collections
                    SET {', '.join(updates)}
                    WHERE id = ?""",
                    tuple(params),
                )
                success = cursor.rowcount > 0
                conn.commit()
                return success
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to update collection version: {str(e)}. "
            f"Operation timed out after 5 seconds."
        )


def add_ansible_module(
    db: DatabaseManager,
    collection_id: str,
    name: str,
    module_type: str,
    schema: str,
    version: str,
    doc_url: str,
) -> str:
    """Add a new Ansible module."""
    try:
        with db.get_connection() as conn:
            # Set busy timeout before any operations
            conn.execute(
                "PRAGMA busy_timeout = 5000"
            )  # 5 second timeout per testing rules
            conn.execute("BEGIN IMMEDIATE")  # Start transaction
            try:
                # Look up collection by ID or name
                collection = conn.execute(
                    """SELECT id FROM ansible_collections
                    WHERE id = ? OR name = ?""",
                    (collection_id, collection_id),
                ).fetchone()

                if not collection:
                    raise DatabaseError(
                        f"Collection '{collection_id}' not found. "
                        f"Operation timed out after 5 seconds."
                    )

                collection_id = collection["id"]  # Ensure we have the numeric ID

                cursor = conn.execute(
                    """INSERT INTO ansible_modules
                    (collection_id, name, type, schema, description, version, doc_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        collection_id,
                        name,
                        module_type,
                        schema,
                        module_type,  # Using type as description for now
                        version,
                        doc_url,
                    ),
                )
                module_id = str(cursor.lastrowid)
                conn.commit()
                return module_id
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        raise DatabaseError(
            f"Failed to add Ansible module: {str(e)}. "
            f"Operation timed out after 5 seconds."
        )


def get_module_info(db: DatabaseManager, module_id: str) -> Optional[Dict]:
    """Get detailed information about an Ansible module."""
    try:
        with db.get_connection() as conn:
            result = conn.execute(
                """SELECT m.*, c.name as collection_name, c.version as collection_version
                FROM ansible_modules m
                JOIN ansible_collections c ON m.collection_id = c.id
                WHERE m.id = ?""",
                (module_id,),
            ).fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get module info: {str(e)}")


def get_module_by_name(
    db: DatabaseManager, collection_name: str, module_name: str
) -> Optional[Dict]:
    """Get module information by collection name and module name."""
    try:
        with db.get_connection() as conn:
            result = conn.execute(
                """SELECT m.*, c.name as collection_name, c.version as collection_version
                FROM ansible_modules m
                JOIN ansible_collections c ON m.collection_id = c.id
                WHERE c.name = ? AND m.name = ?""",
                (collection_name, module_name),
            ).fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get module by name: {str(e)}")


def get_module_compatibility(
    db: DatabaseManager, collection_name: str, module_name: str, version: str
) -> Dict:
    """Check module compatibility across collection versions.

    Args:
        db: Database manager instance
        collection_name: Name of the collection
        module_name: Name of the module
        version: Target version to check compatibility against

    Returns:
        Dict containing compatibility status and any potential issues
    """
    logger.info(
        "Getting module compatibility info",
        extra={
            "collection_name": collection_name,
            "module_name": module_name,
            "version": version,
            "operation": "get_module_compatibility",
        },
    )

    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout

            # Get latest version of the module
            current = conn.execute(
                """
                SELECT m.*, c.name as collection_name, c.version as collection_version
                FROM ansible_modules m
                JOIN ansible_collections c ON m.collection_id = c.id
                WHERE c.name = ? AND m.name = ?
                ORDER BY m.version DESC
                LIMIT 1
                """,
                (collection_name, module_name),
            ).fetchone()

            if not current:
                raise DatabaseError(
                    f"Module '{module_name}' not found in collection '{collection_name}'"
                )

            # Get version history
            history = conn.execute(
                """
                SELECT m.version as module_version,
                       c.version as collection_version,
                       m.schema,
                       c.updated_at as released
                FROM ansible_modules m
                JOIN ansible_collections c ON m.collection_id = c.id
                WHERE c.name = ? AND m.name = ?
                ORDER BY c.updated_at DESC
                """,
                (collection_name, module_name),
            ).fetchall()

            # Check compatibility
            result = {
                "module_name": module_name,
                "collection_name": collection_name,
                "target_version": version,
                "current_version": current["version"],
                "is_compatible": True,
                "compatibility_issues": [],
                "breaking_changes": [],
                "version_history": [],
            }

            # Add version history
            for h in history:
                result["version_history"].append(
                    {
                        "module_version": h["module_version"],
                        "collection_version": h["collection_version"],
                        "released": h["released"],
                    }
                )

            # Compare schemas to detect breaking changes
            target = None
            for h in history:
                if h["collection_version"] == version:
                    target = h
                    break

            if not target:
                result["is_compatible"] = False
                result["compatibility_issues"].append(
                    f"Target version {version} not found in module history"
                )
                return result

            # Basic schema comparison
            try:
                import json

                current_schema = json.loads(current["schema"])
                target_schema = json.loads(target["schema"])

                # Check for required fields in current that weren't required in target
                if "required" in target_schema or "required" in current_schema:
                    current_required = set(current_schema.get("required", []))
                    target_required = set(target_schema.get("required", []))
                    
                    new_required = current_required - target_required
                    if new_required:
                        result["is_compatible"] = False
                        result["breaking_changes"].append(
                            f"Required fields added: {', '.join(new_required)}"
                        )

                # Check for removed properties
                if "properties" in current_schema and "properties" in target_schema:
                    removed_props = set(current_schema["properties"].keys()) - set(
                        target_schema["properties"].keys()
                    )
                    if removed_props:
                        result["breaking_changes"].append(
                            f"Properties removed: {', '.join(removed_props)}"
                        )

                # Add compatibility notes
                if result["breaking_changes"]:
                    result["compatibility_issues"].extend(result["breaking_changes"])
                else:
                    result["compatibility_issues"].append(
                        "No breaking changes detected"
                    )

            except json.JSONDecodeError:
                result["compatibility_issues"].append(
                    "Unable to compare schemas - invalid JSON format"
                )

            return result

    except sqlite3.Error as e:
        error_msg = f"Failed to check module compatibility: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def update_module_version(
    db: DatabaseManager,
    module_id: str,
    new_schema: str,
    new_version: Optional[str] = None,
    new_doc_url: Optional[str] = None,
) -> bool:
    """Update an Ansible module's schema and optional fields."""
    try:
        with db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")  # Start transaction
            try:
                updates = ["schema = ?"]
                params = [new_schema]

                if new_version:
                    updates.append("version = ?")
                    params.append(new_version)
                if new_doc_url:
                    updates.append("doc_url = ?")
                    params.append(new_doc_url)

                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(module_id)

                cursor = conn.execute(
                    f"""UPDATE ansible_modules
                    SET {', '.join(updates)}
                    WHERE id = ?""",
                    tuple(params),
                )
                conn.commit()
                return cursor.rowcount > 0
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update module version: {str(e)}")


def list_ansible_collections(db: DatabaseManager) -> List[Dict]:
    """Get all Ansible collections with basic metadata.

    Args:
        db: Database manager instance

    Returns:
        List of collections with metadata including module counts
    """
    logger.info(
        "Listing Ansible collections", extra={"operation": "list_ansible_collections"}
    )

    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout

            # Get collections with module counts
            collections = conn.execute(
                """
                SELECT
                    c.*,
                    COUNT(m.id) as module_count,
                    MAX(m.updated_at) as latest_module_update
                FROM ansible_collections c
                LEFT JOIN ansible_modules m ON c.id = m.collection_id
                GROUP BY c.id
                ORDER BY c.name
                """
            ).fetchall()

            return [dict(c) for c in collections]

    except sqlite3.Error as e:
        error_msg = f"Failed to list collections: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def get_collection_version_history(
    db: DatabaseManager, collection_name: str
) -> List[Dict]:
    """Get version history for a specific Ansible collection.

    Args:
        db: Database manager instance
        collection_name: Name of the collection

    Returns:
        List of version entries with timestamps and URLs
    """
    logger.info(
        "Getting collection version history",
        extra={
            "collection_name": collection_name,
            "operation": "get_collection_version_history",
        },
    )

    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout

            versions = conn.execute(
                """
                SELECT version, source_url, doc_url, created_at, updated_at
                FROM ansible_collections
                WHERE name = ?
                ORDER BY created_at DESC
                """,
                (collection_name,),
            ).fetchall()

            if not versions:
                raise DatabaseError(f"Collection '{collection_name}' not found")

            return [dict(v) for v in versions]

    except sqlite3.Error as e:
        error_msg = f"Failed to get collection version history: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def get_ansible_collection_info(db: DatabaseManager, collection_name: str) -> Dict:
    """Get comprehensive information about an Ansible collection.

    Args:
        db: Database manager instance
        collection_name: Name of the collection to retrieve

    Returns:
        Dictionary containing collection information including metadata and module count
    """
    logger.info(
        "Getting Ansible collection info",
        extra={
            "collection_name": collection_name,
            "operation": "get_ansible_collection_info",
        },
    )

    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout

            # Get collection info with module count
            result = conn.execute(
                """
                SELECT
                    c.*,
                    COUNT(m.id) as module_count
                FROM ansible_collections c
                LEFT JOIN ansible_modules m ON c.id = m.collection_id
                WHERE c.name = ?
                GROUP BY c.id
                """,
                (collection_name,),
            ).fetchone()

            if not result:
                raise DatabaseError(f"Collection '{collection_name}' not found")

            collection_info = dict(result)

            # Get recent modules
            recent_modules = conn.execute(
                """
                SELECT name, type, version
                FROM ansible_modules
                WHERE collection_id = ?
                ORDER BY updated_at DESC
                LIMIT 5
                """,
                (collection_info["id"],),
            ).fetchall()

            collection_info["recent_modules"] = [dict(m) for m in recent_modules]

            return collection_info

    except sqlite3.Error as e:
        error_msg = f"Failed to get collection info: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)

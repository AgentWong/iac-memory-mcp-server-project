"""Terraform-related database operations."""

import logging
import sqlite3
from typing import Dict, List, Optional

from .connection import DatabaseError, DatabaseManager

# Configure module logger to inherit from root
logger = logging.getLogger("iac_memory.db.terraform")


def add_terraform_provider(
    db: DatabaseManager,
    name: str,
    version: str,
    source_url: str,
    doc_url: str,
) -> str:
    """Add a new Terraform provider with proper error handling."""
    logger.info(
        "Adding Terraform provider",
        extra={"provider_name": name, "version": version, "source_url": source_url},
    )

    try:
        with db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    """INSERT INTO terraform_providers 
                    (name, version, source_url, doc_url, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (name, version, source_url, doc_url),
                )

                conn.commit()
                provider_id = str(cursor.lastrowid)

                logger.info(
                    f"Successfully added provider {name}",
                    extra={"provider_id": provider_id, "provider_name": name},
                )
                return provider_id
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        error_msg = f"Failed to add Terraform provider: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def get_terraform_provider_info(db: DatabaseManager, provider_name: str) -> Dict:
    """Get comprehensive information about a Terraform provider.
    
    Args:
        db: Database manager instance
        provider_name: Name of the provider to retrieve
        
    Returns:
        Dictionary containing provider information including metadata and resource count
    """
    logger.info(
        "Getting Terraform provider info",
        extra={
            "provider_name": provider_name,
            "operation": "get_terraform_provider_info"
        }
    )
    
    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
            
            # Get provider info with resource count
            result = conn.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.version,
                    p.source_url,
                    p.doc_url,
                    p.updated_at,
                    COUNT(r.id) as resource_count,
                    MAX(r.updated_at) as latest_resource_update
                FROM terraform_providers p
                LEFT JOIN terraform_resources r ON p.id = r.provider_id
                WHERE p.name = ?
                GROUP BY p.id, p.name, p.version, p.source_url, p.doc_url, p.updated_at
                """,
                (provider_name,)
            ).fetchone()
            
            if not result:
                raise DatabaseError(f"Provider '{provider_name}' not found")
                
            # Convert row to dict and ensure all necessary fields are present
            provider_info = {
                "id": result["id"],
                "name": result["name"],
                "version": result["version"],
                "source_url": result["source_url"],
                "doc_url": result["doc_url"],
                "updated_at": result["updated_at"],
                "resource_count": result["resource_count"],
                "latest_resource_update": result["latest_resource_update"]
            }
            
            # Get resources associated with this provider
            resources = conn.execute(
                """
                SELECT name, resource_type, version, doc_url
                FROM terraform_resources
                WHERE provider_id = ?
                ORDER BY updated_at DESC
                """,
                (provider_info["id"],)
            ).fetchall()
            
            # Convert resource rows to dicts with explicit field mapping
            provider_info["resources"] = [
                {
                    "name": r["name"],
                    "type": r["resource_type"],
                    "version": r["version"],
                    "doc_url": r["doc_url"]
                } for r in resources
            ]
            
            return provider_info
            
    except sqlite3.Error as e:
        error_msg = f"Failed to get provider info: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)

def get_provider_resources(db: DatabaseManager, provider_id_or_name: str) -> List[Dict]:
    """Get all resources for a specific Terraform provider.

    Args:
        db: Database manager instance
        provider_id_or_name: Either the provider ID or name
    """
    logger.info(
        "Fetching provider resources",
        extra={"provider": provider_id_or_name, "operation": "get_provider_resources"},
    )
    try:
        with db.get_connection() as conn:
            # Try first as ID, then as name if no results
            resources = conn.execute(
                """SELECT r.*, p.name as provider_name, p.version as provider_version,
                          pr.relationship_type, pr.metadata
                   FROM terraform_resources r
                   JOIN terraform_providers p ON r.provider_id = p.id
                   LEFT JOIN provider_resources pr ON r.id = pr.resource_id
                   WHERE p.id = ? OR p.name = ?""",
                (provider_id_or_name, provider_id_or_name),
            ).fetchall()

            # Add debug logging
            logger.debug(f"Found {len(resources)} resources")
            return [dict(r) for r in resources]
    except sqlite3.Error as e:
        error_msg = f"Failed to get provider resources: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def update_provider_version(
    db: DatabaseManager,
    provider_name: str,
    new_version: str,
    new_source_url: Optional[str] = None,
    new_doc_url: Optional[str] = None,
) -> bool:
    """Update a Terraform provider's version and optional URLs."""
    logger.info(
        "Updating provider version",
        extra={
            "provider_name": provider_name,
            "new_version": new_version,
            "has_source_url": bool(new_source_url),
            "has_doc_url": bool(new_doc_url),
            "operation": "update_provider_version",
        },
    )
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
        params.append(provider_name)

        with db.get_connection() as conn:
            cursor = conn.execute(
                f"""UPDATE terraform_providers
                SET {', '.join(updates)}
                WHERE name = ?""",
                tuple(params),
            )
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        error_msg = f"Failed to update provider version: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def add_terraform_resource(
    db: DatabaseManager,
    provider_id: str,
    name: str,
    resource_type: str,
    schema: str,
    version: str,
    doc_url: str,
) -> str:
    """Add a new Terraform resource."""
    logger.info(
        "Adding Terraform resource",
        extra={
            "provider_id": provider_id,
            "resource_name": name,
            "resource_type": resource_type,
            "version": version,
            "operation": "add_terraform_resource",
        },
    )
    try:
        with db.get_connection() as conn:
            # Look up provider by ID or name
            provider = conn.execute(
                """SELECT id FROM terraform_providers 
                WHERE id = ? OR name = ?""",
                (provider_id, provider_id),
            ).fetchone()

            if not provider:
                raise ValueError(f"Provider '{provider_id}' not found")

            provider_id = provider["id"]  # Ensure we have the numeric ID

            conn.execute("BEGIN IMMEDIATE")
            try:
                # Insert resource
                cursor = conn.execute(
                    """INSERT INTO terraform_resources
                    (provider_id, name, resource_type, schema, version, doc_url, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        provider_id,
                        name,
                        resource_type,
                        schema,
                        version,
                        doc_url,
                        f"Terraform {resource_type} resource",
                    ),
                )
                resource_id = cursor.lastrowid

                # Create provider-resource relationship
                provider_info = conn.execute(
                    "SELECT name FROM terraform_providers WHERE id = ?", (provider_id,)
                ).fetchone()

                conn.execute(
                    """INSERT INTO provider_resources
                    (provider_id, resource_id, provider_name, resource_type, 
                     schema_version, doc_url, relationship_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, 'MANAGED', '{}')""",
                    (
                        provider_id,
                        resource_id,
                        provider_info["name"],
                        resource_type,
                        version,
                        doc_url,
                    ),
                )
                conn.commit()
                return str(cursor.lastrowid)
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        error_msg = f"Failed to add Terraform resource: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def get_resource_info(db: DatabaseManager, resource_name: str, provider_name: str = None) -> Optional[Dict]:
    """Get detailed information about a Terraform resource.
    
    Args:
        db: Database manager instance
        resource_name: Name or ID of the resource
        provider_name: Optional provider name to filter by
    """
    logger.info(
        "Fetching resource info",
        extra={
            "resource_name": resource_name,
            "provider_name": provider_name,
            "operation": "get_resource_info"
        },
    )
    try:
        with db.get_connection() as conn:
            if provider_name:
                # Query by resource name and provider name
                result = conn.execute(
                    """SELECT r.*, p.name as provider_name, p.version as provider_version
                    FROM terraform_resources r
                    JOIN terraform_providers p ON r.provider_id = p.id
                    WHERE r.name = ? AND p.name = ?""",
                    (resource_name, provider_name),
                ).fetchone()
            else:
                # Try first as ID, then as name
                result = conn.execute(
                    """SELECT r.*, p.name as provider_name, p.version as provider_version
                    FROM terraform_resources r
                    JOIN terraform_providers p ON r.provider_id = p.id
                    WHERE r.id = ? OR r.name = ?""",
                    (resource_name, resource_name),
                ).fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        error_msg = f"Failed to get resource info: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def update_resource_schema(
    db: DatabaseManager,
    resource_id: str,
    new_schema: str,
    new_version: Optional[str] = None,
    new_doc_url: Optional[str] = None,
) -> bool:
    """Update a Terraform resource's schema and optional fields."""
    logger.info(
        "Updating resource schema",
        extra={
            "resource_id": resource_id,
            "has_new_version": bool(new_version),
            "has_new_doc_url": bool(new_doc_url),
            "operation": "update_resource_schema",
        },
    )
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
        params.append(resource_id)

        with db.get_connection() as conn:
            cursor = conn.execute(
                f"""UPDATE terraform_resources
                SET {', '.join(updates)}
                WHERE id = ?""",
                tuple(params),
            )
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        error_msg = f"Failed to update resource schema: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def check_resource_version_compatibility(
    db: DatabaseManager, provider_name: str, resource_name: str, version: str
) -> Dict:
    """Check resource compatibility across provider versions.

    Args:
        db: Database manager instance
        provider_name: Name of the provider
        resource_name: Name of the resource
        version: Target provider version to check against

    Returns:
        Dictionary containing compatibility status and potential issues
    """
    logger.info(
        "Checking resource version compatibility",
        extra={
            "provider": provider_name,
            "resource": resource_name,
            "target_version": version,
            "operation": "check_resource_version_compatibility",
        },
    )

    try:
        with db.get_connection() as conn:
            # Get resource info for current version
            current = conn.execute(
                """
                SELECT r.*, p.version as provider_version
                FROM terraform_resources r
                JOIN terraform_providers p ON r.provider_id = p.id
                WHERE p.name = ? AND r.name = ?
                ORDER BY p.created_at DESC
                LIMIT 1
                """,
                (provider_name, resource_name),
            ).fetchone()

            if not current:
                raise ValueError(
                    f"Resource {resource_name} not found for provider {provider_name}"
                )

            # Get resource info for target version
            target = conn.execute(
                """
                SELECT r.*, p.version as provider_version
                FROM terraform_resources r
                JOIN terraform_providers p ON r.provider_id = p.id
                WHERE p.name = ? AND r.name = ? AND p.version = ?
                """,
                (provider_name, resource_name, version),
            ).fetchone()

            if not target:
                return {
                    "is_compatible": False,
                    "current_version": current["provider_version"],
                    "target_version": version,
                    "issues": [
                        f"Resource {resource_name} not found in provider version {version}"
                    ],
                }

            # Compare schemas to determine compatibility
            import json

            current_schema = json.loads(current["schema"])
            target_schema = json.loads(target["schema"])

            issues = []

            # Check for removed required fields
            current_required = set(current_schema.get("required", []))
            target_required = set(target_schema.get("required", []))
            removed_required = current_required - target_required
            if removed_required:
                issues.append(
                    f"Required fields removed in target version: {', '.join(removed_required)}"
                )

            # Check for changed field types
            current_props = current_schema.get("properties", {})
            target_props = target_schema.get("properties", {})

            for field, props in current_props.items():
                if field in target_props:
                    if props.get("type") != target_props[field].get("type"):
                        issues.append(
                            f"Field type changed for '{field}': "
                            f"{props.get('type')} -> {target_props[field].get('type')}"
                        )

            return {
                "is_compatible": len(issues) == 0,
                "current_version": current["provider_version"],
                "target_version": version,
                "issues": issues if issues else ["No compatibility issues found"],
            }

    except sqlite3.Error as e:
        error_msg = f"Failed to check resource compatibility: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)


def get_provider_version_history(db: DatabaseManager, provider_name: str) -> List[Dict]:
    """Get version history for a specific Terraform provider.

    Args:
        db: Database manager instance
        provider_name: Name of the provider

    Returns:
        List of version entries with timestamps and URLs
    """
    logger.info(
        "Getting provider version history",
        extra={
            "provider_name": provider_name,
            "operation": "get_provider_version_history",
        },
    )

    try:
        with db.get_connection() as conn:
            versions = conn.execute(
                """
                SELECT version, source_url, doc_url, created_at, updated_at
                FROM terraform_providers
                WHERE name = ?
                ORDER BY created_at DESC
                """,
                (provider_name,),
            ).fetchall()

            # Add debug logging
            logger.debug(f"Found {len(versions)} versions for provider {provider_name}")
            return [dict(v) for v in versions]

    except sqlite3.Error as e:
        error_msg = f"Failed to get provider version history: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(error_msg)

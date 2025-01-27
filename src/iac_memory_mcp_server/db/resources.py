"""Resource-related database operations.

This module provides functions for accessing IaC resources through the existing tables
(terraform_providers, ansible_collections, etc) rather than through a dedicated 
resources table.
"""

import logging
from typing import Dict, List

from .connection import DatabaseManager

# Configure module logger to inherit from root
logger = logging.getLogger("iac_memory.db.resources")


def get_terraform_providers(db: DatabaseManager) -> List[Dict[str, str]]:
    """Get all Terraform providers with their metadata."""
    with db.get_connection() as conn:
        return conn.execute(
            """
            SELECT 
                p.id,
                p.name,
                p.version,
                p.source_url,
                p.doc_url,
                p.updated_at,
                COUNT(r.id) as resource_count
            FROM terraform_providers p
            LEFT JOIN terraform_resources r ON p.id = r.provider_id
            GROUP BY p.id
            ORDER BY p.name
            """
        ).fetchall()


def get_entities(db: DatabaseManager) -> List[Dict[str, str]]:
    """Get all entities with their latest observations."""
    with db.get_connection() as conn:
        return conn.execute(
            """
            SELECT 
                e.id,
                e.name,
                e.type,
                e.created_at,
                e.updated_at,
                o.content as latest_observation,
                COUNT(r.source_id) as relationship_count
            FROM entities e
            LEFT JOIN observations o ON e.id = o.entity_id 
                AND o.created_at = (
                    SELECT MAX(created_at) 
                    FROM observations 
                    WHERE entity_id = e.id
                )
            LEFT JOIN entity_relationships r ON e.id = r.source_id
            GROUP BY e.id
            ORDER BY e.name
            """
        ).fetchall()


def get_entity_relationships(
    db: DatabaseManager, entity_id: int
) -> List[Dict[str, str]]:
    """Get all relationships for a specific entity."""
    with db.get_connection() as conn:
        return conn.execute(
            """
            SELECT 
                r.source_id,
                r.target_id,
                r.relationship_type,
                r.metadata,
                r.created_at,
                e1.name as source_name,
                e1.type as source_type,
                e2.name as target_name,
                e2.type as target_type
            FROM entity_relationships r
            JOIN entities e1 ON r.source_id = e1.id
            JOIN entities e2 ON r.target_id = e2.id
            WHERE r.source_id = ? OR r.target_id = ?
            ORDER BY r.created_at DESC
            """,
            (entity_id, entity_id),
        ).fetchall()


def get_terraform_resources(db: DatabaseManager) -> List[Dict[str, str]]:
    """Get all Terraform resources with their provider info."""
    with db.get_connection() as conn:
        return conn.execute(
            """
            SELECT 
                r.name,
                r.version,
                r.resource_type,
                r.schema,
                r.doc_url,
                p.name as provider_name,
                p.version as provider_version,
                pr.relationship_type,
                pr.metadata
            FROM terraform_resources r
            JOIN provider_resources pr ON r.id = pr.resource_id
            JOIN terraform_providers p ON pr.provider_id = p.id
            ORDER BY p.name, r.name
        """
        ).fetchall()


def get_ansible_collections(db: DatabaseManager) -> List[Dict[str, str]]:
    """Get all Ansible collections with their metadata."""
    with db.get_connection() as conn:
        return conn.execute(
            """
            SELECT 
                c.id,
                c.name,
                c.version,
                c.source_url,
                c.doc_url,
                c.updated_at,
                COUNT(m.id) as module_count
            FROM ansible_collections c
            LEFT JOIN ansible_modules m ON c.id = m.collection_id
            GROUP BY c.id
            ORDER BY c.name
            """
        ).fetchall()


def get_ansible_modules(db: DatabaseManager) -> List[Dict[str, str]]:
    """Get all Ansible modules with their collection info."""
    with db.get_connection() as conn:
        return conn.execute(
            """
            SELECT 
                m.name as module_name,
                m.version as module_version,
                m.doc_url as module_doc_url,
                c.name as collection_name,
                c.version as collection_version
            FROM ansible_modules m
            JOIN ansible_collections c ON m.collection_id = c.id
            ORDER BY c.name, m.name
        """
        ).fetchall()

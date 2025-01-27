"""Entity-related database operations."""

import logging
import sqlite3
import sys
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from .connection import DatabaseError, DatabaseManager

# Configure module logger
logger = logging.getLogger("iac_memory.db.entities")

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


async def create_entity(db: DatabaseManager, name: str, entity_type: str) -> str:
    """Create a new entity."""
    logger.info(f"Creating entity: {name} of type: {entity_type}")
    try:
        with db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    """INSERT INTO entities (name, type) 
                    VALUES (?, ?) RETURNING id""",
                    (name, entity_type),
                )
                entity_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"Successfully created entity: {name} with id: {entity_id}")
                return entity_id
            except Exception:
                conn.rollback()
                raise
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to create entity: {str(e)}")


def update_entity(db: DatabaseManager, entity_id: str, updates: Dict) -> bool:
    """Update an existing entity."""
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = tuple(updates.values()) + (entity_id,)
    query = f"UPDATE entities SET {set_clause} WHERE id = ?"
    try:
        with db.get_connection() as conn:
            cursor = conn.execute(query, values)
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Update failed: {str(e)}")


def delete_entity(db: DatabaseManager, entity_id: str) -> bool:
    """Delete an entity and its related observations."""
    try:
        with db.get_connection() as conn:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("DELETE FROM observations WHERE entity_id = ?", (entity_id,))
            cursor = conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            affected = cursor.rowcount > 0
            conn.commit()
            return affected
    except sqlite3.Error as e:
        raise DatabaseError(f"Delete failed: {str(e)}")


def get_entity(db: DatabaseManager, entity_id: str) -> Optional[Dict]:
    """Get an entity by ID with its observations."""
    try:
        with db.get_connection() as conn:
            entity = conn.execute(
                "SELECT * FROM entities WHERE id = ?", (entity_id,)
            ).fetchone()

            if not entity:
                return None

            observations = conn.execute(
                "SELECT content FROM observations WHERE entity_id = ?", (entity_id,)
            ).fetchall()

            result = dict(entity)
            if observations:
                result["observations"] = ",".join(obs[0] for obs in observations)
            return result
    except sqlite3.Error as e:
        raise DatabaseError(f"Read failed: {str(e)}")


def get_entity_relationships(
    db: DatabaseManager, entity_id: Optional[str] = None
) -> List[Dict]:
    """Get relationships between entities and their observations."""
    try:
        query = """
            SELECT e.id, e.name, e.type,
                   GROUP_CONCAT(DISTINCT o.content) as observations
            FROM entities e
            LEFT JOIN observations o ON e.id = o.entity_id
        """
        params = []

        if entity_id:
            query += " WHERE e.id = ?"
            params.append(entity_id)

        query += " GROUP BY e.id, e.name, e.type"

        with db.get_connection() as conn:
            results = conn.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in results]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get relationships: {str(e)}")


def get_entity_with_observation(db: DatabaseManager, entity_id: str) -> Optional[Dict]:
    """Get an entity with its latest observation."""
    try:
        with db.get_connection() as conn:
            result = conn.execute(
                """SELECT e.*, o.content as observation
                FROM entities e
                LEFT JOIN observations o ON e.id = o.entity_id
                WHERE e.id = ?""",
                (entity_id,),
            ).fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get entity with observation: {str(e)}")


async def execute_create_entity(
    db: DatabaseManager, arguments: Dict[str, Any]
) -> List[TextContent]:
    """Execute create entity operation.

    Args:
        db: Database manager instance
        arguments: Tool arguments
    """
    logger.info("Creating new entity", extra={"tool_arguments": arguments})

    with db.get_connection() as conn:
        conn.execute("PRAGMA busy_timeout = 5000")  # 5s timeout
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Create entity
            cursor = conn.execute(
                """INSERT INTO entities (name, type)
                VALUES (?, ?)""",
                (arguments["name"], arguments["type"]),
            )
            entity_id = cursor.lastrowid

            # Add observation if provided
            if "observation" in arguments:
                conn.execute(
                    "INSERT INTO observations (entity_id, content) VALUES (?, ?)",
                    (entity_id, arguments["observation"]),
                )

            conn.commit()
            return [
                TextContent(
                    type="text",
                    text=f"Created entity '{arguments['name']}' (ID: {entity_id})",
                )
            ]
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create entity: {str(e)}")
            raise DatabaseError(f"Failed to create entity: {str(e)}")


def execute_update_entity(
    db: DatabaseManager, arguments: Dict[str, Any]
) -> List[TextContent]:
    """Execute update entity operation."""
    logger.info("Updating entity", extra={"args": arguments})

    updates = {k: v for k, v in arguments.items() if k != "id"}
    success = update_entity(db, arguments["id"], updates)
    if not success:
        raise DatabaseError(f"Entity not found: {arguments['id']}")

    # Add observation if provided
    if "observation" in arguments:
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO observations (entity_id, content) VALUES (?, ?)",
                (arguments["id"], arguments["observation"]),
            )

    return [TextContent(type="text", text=f"Updated entity {arguments['id']}")]


def execute_delete_entity(
    db: DatabaseManager, arguments: Dict[str, Any]
) -> List[TextContent]:
    """Execute delete entity operation."""
    logger.info("Deleting entity", extra={"args": arguments})

    success = delete_entity(db, arguments["id"])
    if not success:
        raise DatabaseError(f"Entity not found: {arguments['id']}")

    return [TextContent(type="text", text=f"Deleted entity {arguments['id']}")]


def execute_view_relationships(
    db: DatabaseManager, arguments: Dict[str, Any]
) -> List[TextContent]:
    """Execute view relationships operation."""
    logger.info("Viewing relationships", extra={"relationship_args": arguments})

    entity_id = arguments["entity_id"]
    with db.get_connection() as conn:
        cursor = conn.execute(
            """SELECT
                e.id, e.name, e.type, e.created_at, e.updated_at,
                o.content as observation,
                r.relationship_type,
                e2.id as related_id,
                e2.name as related_name,
                e2.type as related_type,
                e2.created_at as related_created_at,
                e2.updated_at as related_updated_at
            FROM entities e
            LEFT JOIN observations o ON e.id = o.entity_id
            LEFT JOIN entity_relationships r ON e.id = r.source_id
            LEFT JOIN entities e2 ON r.target_id = e2.id
            WHERE e.id = ?""",
            (entity_id,),
        )
        entity = cursor.fetchone()
        if not entity:
            raise DatabaseError(f"Entity not found: {entity_id}")

        result = [
            f"Entity {entity_id}:",
            f"Name: {entity['name']}",
            f"Type: {entity['type']}",
            f"Created: {entity['created_at']}",
            f"Updated: {entity['updated_at']}",
        ]

        if entity["observation"]:
            result.extend(
                [
                    "",  # Empty line for readability
                    f"Observation: {entity['observation']}",
                ]
            )

        if entity["related_name"]:
            result.extend(
                [
                    "",  # Empty line for readability
                    "Related Entity:",
                    f"  ID: {entity['related_id']}",
                    f"  Name: {entity['related_name']}",
                    f"  Type: {entity['related_type']}",
                    f"  Created: {entity['related_created_at']}",
                    f"  Updated: {entity['related_updated_at']}",
                    f"  Relationship Type: {entity['relationship_type']}",
                ]
            )

        return [TextContent(type="text", text="\n".join(result))]

"""Entity tool handlers for the IaC Memory MCP Server.

This module contains handlers for entity-related tools including:
- Entity creation and management
- Relationship viewing
- Entity updates and deletions
"""

import logging
from typing import Any, Dict

import mcp.types as types
from mcp.shared.exceptions import McpError

from ..db.entities import (
    execute_create_entity,
    execute_delete_entity,
    execute_update_entity,
    execute_view_relationships,
)
from ..utils.errors import ValidationError

# Configure module logger
logger = logging.getLogger("iac_memory.tools.entity")


async def handle_create_entity(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle create_entity tool."""
    # Validate required arguments
    if not arguments.get("name") or not arguments.get("type"):
        raise ValidationError("Missing required arguments: name and type are required")

    logger.info(
        "Creating entity",
        extra={
            "entity_type": arguments.get("type"),
            "operation_id": operation_id,
        },
    )

    try:
        # Execute creation
        return await execute_create_entity(db, arguments)

    except Exception as e:
        error_msg = f"Failed to create entity: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "create_entity",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_update_entity(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle update_entity tool."""
    try:
        logger.info(
            "Updating entity",
            extra={
                "entity_id": arguments.get("entity_id"),
                "operation_id": operation_id,
            },
        )

        # Execute update
        return execute_update_entity(db, arguments)

    except Exception as e:
        error_msg = f"Failed to update entity: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "update_entity",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_delete_entity(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle delete_entity tool."""
    try:
        logger.info(
            "Deleting entity",
            extra={
                "entity_id": arguments.get("entity_id"),
                "operation_id": operation_id,
            },
        )

        # Execute deletion
        return execute_delete_entity(db, arguments)

    except Exception as e:
        error_msg = f"Failed to delete entity: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "delete_entity",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_view_relationships(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle view_relationships tool."""
    try:
        logger.info(
            "Viewing entity relationships",
            extra={
                "entity_id": arguments.get("entity_id"),
                "operation_id": operation_id,
            },
        )

        # Execute relationship view
        return execute_view_relationships(db, arguments)

    except Exception as e:
        error_msg = f"Failed to view relationships: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "view_relationships",
                    "operation_id": operation_id,
                },
            )
        )


# Map tool names to their handlers
entity_tool_handlers = {
    "create_entity": handle_create_entity,
    "update_entity": handle_update_entity,
    "delete_entity": handle_delete_entity,
    "view_relationships": handle_view_relationships,
}

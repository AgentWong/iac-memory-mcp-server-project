"""Base tool handling functionality for the IaC Memory MCP Server.

This module contains the core tool handling logic including:
- Common utilities and error handling
- Base tool handler implementation
- Tool listing functionality
"""

import logging
import time
import traceback
from typing import Any, Dict, List

import mcp.types as types
from mcp.server.lowlevel.server import RequestContext
from mcp.shared.exceptions import McpError
from mcp.types import TextContent

from ..db.connection import DatabaseManager
from ..utils.errors import DatabaseError, ValidationError

# Configure module logger to inherit from root
logger = logging.getLogger("iac_memory.tools.base")


async def base_call_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    ctx: RequestContext | None = None,
    tool_handlers: Dict[str, callable] = None,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Execute tool operations with proper context and validation."""
    operation_id = f"tool_{tool_name}_{int(time.time())}"

    logger.info(f"Executing tool: {tool_name}", extra={"operation_id": operation_id})

    # Get database instance with validation
    try:
        db = DatabaseManager.get_instance()
        if not db.is_initialized():
            error_msg = "Database not initialized"
            logger.error(error_msg, extra={"operation_id": operation_id})
            raise McpError(
                types.ErrorData(
                    code=types.INTERNAL_ERROR,
                    message=error_msg,
                    data={
                        "operation": tool_name,
                        "operation_id": operation_id,
                        "database_path": db.db_path,
                    },
                )
            )
    except Exception as e:
        error_msg = f"Failed to get database instance: {str(e)}"
        logger.error(
            error_msg,
            extra={
                "operation_id": operation_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
        )
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={"operation": tool_name, "operation_id": operation_id},
            )
        )

    if not tool_handlers or tool_name not in tool_handlers:
        error_msg = f"Unknown tool: {tool_name}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    try:
        # Call the specific tool handler
        result = await tool_handlers[tool_name](db, arguments, operation_id)
        
        # If the result is already a list of content types, return it directly
        if isinstance(result, list):
            return result
        # Otherwise wrap the result in a TextContent
        return [TextContent(type="text", text=str(result))]

    except ValidationError as e:
        error_msg = f"Missing required arguments for {tool_name}: {str(e)}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    except DatabaseError as e:
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=str(e),
                data={"tool": tool_name, "error": str(e)},
            )
        )

    except Exception as e:
        logger.error(
            f"Tool execution failed: {str(e)}",
            extra={"tool": tool_name, "arguments": arguments},
        )
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=f"Tool execution failed: {str(e)}",
                data={"tool": tool_name, "error": str(e)},
            )
        )


async def base_list_tools(
    tool_schemas: Dict[str, Dict], ctx: RequestContext = None
) -> list[types.Tool]:
    """List available tools with comprehensive error handling and logging."""
    operation_id = f"list_tools_{int(time.time())}"
    logger.info("Starting list_tools operation", extra={"operation_id": operation_id})

    try:
        # Convert tool schemas to Tool objects with validation
        tools = []
        validation_errors = []

        for name, schema in tool_schemas.items():
            try:
                # Validate schema structure
                if not isinstance(schema, dict):
                    raise ValueError(f"Invalid schema type for {name}: {type(schema)}")

                if "type" not in schema or schema["type"] != "object":
                    raise ValueError(f"Schema for {name} must be an object type")

                tool = types.Tool(
                    name=name,
                    description=schema.get("description", "No description available"),
                    inputSchema=schema,
                )
                tools.append(tool)
                logger.debug(
                    f"Added tool: {name}",
                    extra={
                        "operation_id": operation_id,
                        "tool_name": name,
                        "has_description": bool(schema.get("description")),
                    },
                )

            except Exception as e:
                error_details = {
                    "tool_name": name,
                    "error": str(e),
                    "operation_id": operation_id,
                }
                logger.warning(
                    f"Failed to process tool {name}: {str(e)}", extra=error_details
                )
                validation_errors.append({"name": name, "error": str(e)})
                continue

        # Log completion status
        status_msg = f"Found {len(tools)} valid tools"
        if validation_errors:
            status_msg += f" ({len(validation_errors)} tools skipped due to errors)"

        logger.info(
            status_msg,
            extra={
                "operation_id": operation_id,
                "tool_count": len(tools),
                "error_count": len(validation_errors),
                "validation_errors": (validation_errors if validation_errors else None),
            },
        )

        return tools

    except Exception as e:
        error_msg = f"Failed to list tools: {str(e)}"
        error_details = {
            "operation_id": operation_id,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

        logger.error(error_msg, extra=error_details, exc_info=True)

        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "operation": "list_tools",
                    "operation_id": operation_id,
                    "error_details": error_details,
                },
            )
        )

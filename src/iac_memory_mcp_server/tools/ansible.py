"""Ansible tool handlers for the IaC Memory MCP Server.

This module contains handlers for Ansible-specific tools including:
- Collection information retrieval
- Module management
- Version history checks
"""

import logging
import re
from typing import Any, Dict

import mcp.types as types
from mcp.shared.exceptions import McpError
from mcp.types import TextContent

from ..db.ansible import (
    add_ansible_collection,
    add_ansible_module,
    get_ansible_collection_info,
    get_collection_modules,
    get_collection_version_history,
    get_module_by_name,
    get_module_compatibility,
    list_ansible_collections,
)

# Configure module logger
logger = logging.getLogger("iac_memory.tools.ansible")


async def handle_get_ansible_collection_info(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle get_ansible_collection_info tool."""
    try:
        logger.info(
            "Getting Ansible collection info",
            extra={
                "collection_name": arguments["collection_name"],
                "operation_id": operation_id,
            },
        )

        # Get collection info
        collection = get_ansible_collection_info(db, arguments["collection_name"])

        # Format output
        output = [
            f"Collection: {collection['name']}",
            f"Version: {collection['version']}",
            f"Source: {collection['source_url']}",
            f"Documentation: {collection['doc_url']}",
            f"Total Modules: {collection['module_count']}",
            f"Last Updated: {collection['updated_at']}",
        ]

        if collection["recent_modules"]:
            output.extend(
                [
                    "\nRecent Modules:",
                    *[
                        f"- {m['name']} ({m['type']}) v{m['version']}"
                        for m in collection["recent_modules"]
                    ],
                ]
            )

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        error_msg = f"Failed to get collection info: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "get_ansible_collection_info",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_list_ansible_collections(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle list_ansible_collections tool."""
    try:
        logger.info("Listing Ansible collections", extra={"operation_id": operation_id})

        # Get all collections
        collections = list_ansible_collections(db)

        # Apply any filters from criteria
        filter_criteria = arguments.get("filter_criteria", {})
        if filter_criteria and "name_pattern" in filter_criteria:
            pattern = re.compile(filter_criteria["name_pattern"])
            collections = [c for c in collections if pattern.match(c["name"])]

        # Format output
        if not collections:
            return [TextContent(type="text", text="No collections found")]

        output = ["Available Ansible Collections:"]
        for c in collections:
            output.append(
                f"\n- {c['name']} v{c['version']}"
                f"\n  Modules: {c['module_count']}"
                f"\n  Updated: {c['updated_at']}"
                f"\n  Latest Module Update: {c.get('latest_module_update', 'N/A')}"
                f"\n  Docs: {c['doc_url']}"
            )

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        error_msg = f"Failed to list collections: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "list_ansible_collections",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_get_collection_version_history(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle get_collection_version_history tool."""
    try:
        logger.info(
            "Getting collection version history",
            extra={
                "collection_name": arguments["collection_name"],
                "operation_id": operation_id,
            },
        )

        # Get version history
        versions = get_collection_version_history(db, arguments["collection_name"])

        # Format output
        output = [f"Version History for {arguments['collection_name']}:"]
        for v in versions:
            output.append(
                f"\nVersion: {v['version']}"
                f"\n  Added: {v['created_at']}"
                f"\n  Last Updated: {v['updated_at']}"
                f"\n  Source: {v['source_url']}"
                f"\n  Docs: {v['doc_url']}"
            )

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        error_msg = f"Failed to get collection version history: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "get_collection_version_history",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_get_ansible_module_info(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle get_ansible_module_info tool."""
    try:
        logger.info(
            "Getting Ansible module info",
            extra={
                "collection_name": arguments["collection_name"],
                "module_name": arguments["module_name"],
                "operation_id": operation_id,
            },
        )

        # Get module info
        module = get_module_by_name(
            db, arguments["collection_name"], arguments["module_name"]
        )
        if not module:
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND,
                    message=f"Module '{arguments['module_name']}' not found in collection '{arguments['collection_name']}'",
                    data={
                        "tool": "get_ansible_module_info",
                        "collection": arguments["collection_name"],
                        "module": arguments["module_name"],
                        "operation_id": operation_id,
                    },
                )
            )

        # Format output
        output = [
            f"Module: {module['name']}",
            f"Collection: {module['collection_name']} v{module['collection_version']}",
            f"Type: {module['type']}",
            f"Version: {module['version']}",
            f"Documentation: {module['doc_url']}",
            "\nSchema:",
            module["schema"],
        ]

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        error_msg = f"Failed to get module info: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "get_ansible_module_info",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_list_collection_modules(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle list_collection_modules tool."""
    try:
        logger.info(
            "Listing collection modules",
            extra={
                "collection_name": arguments["collection_name"],
                "operation_id": operation_id,
            },
        )

        # Get modules
        modules = get_collection_modules(db, arguments["collection_name"])

        # Apply any filters
        filter_criteria = arguments.get("filter_criteria", {})
        if filter_criteria:
            if "type_pattern" in filter_criteria:
                pattern = re.compile(filter_criteria["type_pattern"])
                modules = [m for m in modules if pattern.match(m["type"])]

        # Format output
        if not modules:
            return [TextContent(
                type="text",
                text=f"No modules found for collection {arguments['collection_name']}"
            )]

        output = [f"Modules in collection {arguments['collection_name']}:"]
        for m in modules:
            output.append(
                f"\n- {m['name']} ({m['type']})"
                f"\n  Version: {m['version']}"
                f"\n  Description: {m.get('description', 'No description available')}"
                f"\n  Documentation: {m['doc_url']}"
            )

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        error_msg = f"Failed to list collection modules: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "list_collection_modules",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_get_module_version_compatibility(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle get_module_version_compatibility tool."""
    try:
        logger.info(
            "Getting module version compatibility",
            extra={
                "collection_name": arguments["collection_name"],
                "module_name": arguments["module_name"],
                "version": arguments["version"],
                "operation_id": operation_id,
            },
        )

        try:
            # Get compatibility info
            result = get_module_compatibility(
                db,
                arguments["collection_name"],
                arguments["module_name"],
                arguments["version"],
            )
        except Exception as db_error:
            error_msg = str(db_error)
            logger.error(error_msg, extra={"operation_id": operation_id})
            return [TextContent(type="text", text=error_msg)]

        # Format output
        output = [
            "Module Compatibility Check:",
            f"Module: {result['module_name']}",
            f"Collection: {result['collection_name']}",
            f"Target Version: {result['target_version']}",
            f"Current Version: {result['current_version']}",
            f"Is Compatible: {'Yes' if result['is_compatible'] else 'No'}",
            "\nCompatibility Issues:",
        ]

        if not result["compatibility_issues"]:
            output.append("- No issues found")
        else:
            for issue in result["compatibility_issues"]:
                output.append(f"- {issue}")

        if result["breaking_changes"]:
            output.extend(
                [
                    "\nBreaking Changes:",
                    *[f"- {change}" for change in result["breaking_changes"]],
                ]
            )

        output.extend(
            [
                "\nVersion History:",
                *[
                    f"- {v['collection_version']} (Module v{v['module_version']}) - {v['released']}"
                    for v in result["version_history"]
                ],
            ]
        )

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        error_msg = f"Failed to check module version compatibility: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "get_module_version_compatibility",
                    "operation_id": operation_id,
                },
            )
        )


async def handle_add_ansible_collection(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle add_ansible_collection tool."""
    # Validate required arguments
    required_args = ["name", "version", "source_url", "doc_url"]
    missing_args = [arg for arg in required_args if arg not in arguments]
    if missing_args:
        error_msg = f"Missing required arguments for add_ansible_collection: {', '.join(missing_args)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [TextContent(type="text", text=error_msg)]

    try:
        logger.info(
            "Adding Ansible collection",
            extra={
                "collection_name": arguments["name"],
                "version": arguments["version"],
                "operation_id": operation_id,
            },
        )

        # Add collection
        collection_id = add_ansible_collection(
            db,
            arguments["name"],
            arguments["version"],
            arguments["source_url"],
            arguments["doc_url"],
        )

        return [TextContent(
            type="text",
            text=f"Added collection {arguments['name']} with ID: {collection_id}"
        )]

    except Exception as e:
        error_msg = f"Failed to add collection: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "add_ansible_collection",
                    "operation_id": operation_id,
                },
            )
        )

# Valid module types
VALID_MODULE_TYPES = {"cloud", "network", "database", "storage", "security", "monitoring"}

async def handle_add_ansible_module(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle add_ansible_module tool."""
    try:
        # Validate module type
        if arguments["module_type"] not in VALID_MODULE_TYPES:
            error_msg = f"Invalid module type: {arguments['module_type']}. Valid types are: {', '.join(sorted(VALID_MODULE_TYPES))}"
            logger.error(error_msg, extra={"operation_id": operation_id})
            return [TextContent(type="text", text=error_msg)]

        logger.info(
            "Adding Ansible module",
            extra={
                "collection": arguments["collection"],
                "module_name": arguments["name"],
                "operation_id": operation_id,
            },
        )

        # Add module
        module_id = add_ansible_module(
            db,
            arguments["collection"],
            arguments["name"],
            arguments["module_type"],
            arguments["schema"],
            arguments["version"],
            arguments["doc_url"],
        )

        return [TextContent(
            type="text",
            text=f"Added module {arguments['name']} with ID: {module_id}"
        )]

    except Exception as e:
        error_msg = f"Failed to add module: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=error_msg,
                data={
                    "tool": "add_ansible_module",
                    "operation_id": operation_id,
                },
            )
        )

# Map tool names to their handlers
ansible_tool_handlers = {
    "get_ansible_collection_info": handle_get_ansible_collection_info,
    "list_ansible_collections": handle_list_ansible_collections,
    "get_collection_version_history": handle_get_collection_version_history,
    "get_ansible_module_info": handle_get_ansible_module_info,
    "list_collection_modules": handle_list_collection_modules,
    "get_module_version_compatibility": handle_get_module_version_compatibility,
    "add_ansible_collection": handle_add_ansible_collection,
    "add_ansible_module": handle_add_ansible_module,
}

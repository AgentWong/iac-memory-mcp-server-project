"""Terraform tool handlers for the IaC Memory MCP Server.

This module contains handlers for Terraform-specific tools including:
- Provider information retrieval
- Resource management
- Version compatibility checks
"""

import logging
import re
from typing import Any, Dict

import mcp.types as types
from mcp.shared.exceptions import McpError
from mcp.types import TextContent

from ..db.terraform import (
    add_terraform_provider,
    add_terraform_resource,
    get_provider_resources,
    get_resource_info,
    get_terraform_provider_info,
    update_provider_version,
)

# Configure module logger
logger = logging.getLogger("iac_memory.tools.terraform")


async def handle_get_terraform_provider_info(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle get_terraform_provider_info tool."""
    try:
        logger.info(
            "Getting Terraform provider info",
            extra={
                "provider_name": arguments["provider_name"],
                "operation_id": operation_id,
            },
        )

        # Get provider info
        provider = get_terraform_provider_info(db, arguments["provider_name"])

        # Format output string
        info_str = f"""Provider: {provider['name']}
                    Version: {provider['version']}
                    Source: {provider['source_url']}
                    Documentation: {provider['doc_url']}
                    Supported Resources:"""

        for resource in provider["resources"]:
            info_str += f"\n- {resource['name']} ({resource['type']})"
            info_str += f"\n  Version: {resource['version']}"

        return [types.TextContent(type="text", text=info_str)]

    except Exception as e:
        error_msg = f"Failed to get provider info: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]


async def handle_list_provider_resources(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle list_provider_resources tool."""
    try:
        logger.info(
            "Listing provider resources",
            extra={
                "provider_name": arguments["provider_name"],
                "operation_id": operation_id,
            },
        )

        # Get resources
        resources = get_provider_resources(db, arguments["provider_name"])

        # Apply any filters
        filter_criteria = arguments.get("filter_criteria", {})
        if filter_criteria:
            if "type_pattern" in filter_criteria:
                pattern = re.compile(filter_criteria["type_pattern"])
                resources = [r for r in resources if pattern.match(r["resource_type"])]

        # Format output
        if not resources:
            return [types.TextContent(
                type="text",
                text=f"No resources found for provider {arguments['provider_name']}"
            )]

        output = [f"Resources for provider {arguments['provider_name']}:"]
        for r in resources:
            output.append(
                f"\n- {r['name']} ({r['resource_type']})"
                f"\n  Version: {r['version']}"
                f"\n  Documentation: {r['doc_url']}"
            )

        return [types.TextContent(
            type="text",
            text="\n".join(output)
        )]

    except Exception as e:
        error_msg = f"Failed to list provider resources: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]


async def handle_get_terraform_resource_info(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle get_terraform_resource_info tool."""
    try:
        logger.info(
            "Getting resource info",
            extra={
                "provider_name": arguments["provider_name"],
                "resource_name": arguments["resource_name"],
                "operation_id": operation_id,
            },
        )

        # Get resource info
        resource = get_resource_info(
            db,
            arguments["resource_name"],
            provider_name=arguments["provider_name"]
        )
        if not resource:
            error_msg = f"Resource '{arguments['resource_name']}' not found for provider '{arguments['provider_name']}'"
            logger.error(error_msg, extra={"operation_id": operation_id})
            return [types.TextContent(
                type="text",
                text=error_msg
            )]

        # Format output
        output = [
            f"Resource: {resource['name']}",
            f"Provider: {resource['provider_name']}",
            f"Type: {resource['resource_type']}",
            f"Version: {resource['version']}",
            f"Documentation: {resource['doc_url']}",
            "\nSchema:",
            resource["schema"],
        ]

        return [types.TextContent(
            type="text",
            text="\n".join(output)
        )]

    except Exception as e:
        error_msg = f"Failed to get resource info: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]


async def handle_add_terraform_provider(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle add_terraform_provider tool."""
    # Validate required arguments
    required_args = ["name", "version", "source_url", "doc_url"]
    missing_args = [arg for arg in required_args if arg not in arguments]
    if missing_args:
        error_msg = f"Missing required arguments for add_terraform_provider: {', '.join(missing_args)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]

    # Validate version format (x.y.z)
    version_pattern = re.compile(r'^\d+\.\d+\.\d+$')
    if not version_pattern.match(arguments["version"]):
        error_msg = "Invalid version format. Version must be in x.y.z format (e.g. 1.0.0)"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(
            type="text",
            text=error_msg
        )]

    try:
        # Add provider
        logger.info(
            "Adding Terraform provider",
            extra={
                "provider_name": arguments["name"],
                "version": arguments["version"],
                "operation_id": operation_id,
            },
        )

        provider_id = add_terraform_provider(
            db,
            arguments["name"],
            arguments["version"],
            arguments["source_url"],
            arguments["doc_url"],
        )

        return [types.TextContent(
            type="text",
            text=f"Added provider {arguments['name']} with ID: {provider_id}"
        )]

    except Exception as e:
        error_msg = f"Failed to add provider: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]

async def handle_add_terraform_resource(db: Any, arguments: Dict[str, Any], operation_id: str) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle add_terraform_resource tool."""
    # Validate required arguments
    required_args = ["provider", "name", "resource_type", "schema", "version", "doc_url"]
    missing_args = [arg for arg in required_args if arg not in arguments]
    if missing_args:
        error_msg = f"Missing required arguments for add_terraform_resource: {', '.join(missing_args)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(
            type="text",
            text=error_msg
        )]

    try:
        # Validate schema is valid JSON
        try:
            import json
            json.loads(arguments["schema"])
        except json.JSONDecodeError:
            error_msg = "Invalid schema format. Schema must be valid JSON."
            logger.error(error_msg, extra={"operation_id": operation_id})
            return [types.TextContent(type="text", text=error_msg)]

        # Add resource
        logger.info(
            "Adding Terraform resource",
            extra={
                "provider": arguments["provider"],
                "resource_name": arguments["name"],
                "operation_id": operation_id,
            },
        )

        resource_id = add_terraform_resource(
            db,
            arguments["provider"],
            arguments["name"],
            arguments["resource_type"],
            arguments["schema"],
            arguments["version"],
            arguments["doc_url"],
        )

        return [types.TextContent(
            type="text",
            text=f"Added resource {arguments['name']} with ID: {resource_id}"
        )]

    except Exception as e:
        error_msg = f"Failed to add resource: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]
async def handle_update_provider_version(
    db: Any, arguments: Dict[str, Any], operation_id: str
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle update_provider_version tool."""
    try:
        logger.info(
            "Updating provider version",
            extra={
                "provider_name": arguments["provider_name"],
                "new_version": arguments["new_version"],
                "operation_id": operation_id,
            },
        )

        # Validate version format (x.y.z)
        version_pattern = re.compile(r'^\d+\.\d+\.\d+$')
        if not version_pattern.match(arguments["new_version"]):
            error_msg = "Invalid version format. Version must be in x.y.z format (e.g. 1.0.0)"
            logger.error(error_msg, extra={"operation_id": operation_id})
            return [types.TextContent(type="text", text=error_msg)]

        # Update provider version
        success = update_provider_version(
            db,
            arguments["provider_name"],
            arguments["new_version"],
            arguments.get("new_source_url"),
            arguments.get("new_doc_url"),
        )

        if success:
            return [types.TextContent(
                type="text",
                text=f"Successfully updated provider {arguments['provider_name']} to version {arguments['new_version']}"
            )]
        else:
            error_msg = f"Provider {arguments['provider_name']} not found"
            logger.error(error_msg, extra={"operation_id": operation_id})
            return [types.TextContent(type="text", text=error_msg)]

    except Exception as e:
        error_msg = f"Failed to update provider version: {str(e)}"
        logger.error(error_msg, extra={"operation_id": operation_id})
        return [types.TextContent(type="text", text=error_msg)]

# Map tool names to their handlers
terraform_tool_handlers = {
    "get_terraform_provider_info": handle_get_terraform_provider_info,
    "list_provider_resources": handle_list_provider_resources,
    "get_terraform_resource_info": handle_get_terraform_resource_info,
    "add_terraform_provider": handle_add_terraform_provider,
    "add_terraform_resource": handle_add_terraform_resource,
    "update_provider_version": handle_update_provider_version,
}

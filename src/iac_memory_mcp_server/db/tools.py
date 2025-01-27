"""Database operations for tools.

This module contains the pure database operations for tools, without any MCP-specific
functionality like progress reporting or session management.
"""

import logging
import sys
from typing import Any, Dict, List

import mcp.types as types
from mcp.shared.exceptions import McpError
from mcp.types import TextContent

from ..utils.errors import ValidationError
from .connection import DatabaseError, DatabaseManager
from .entities import delete_entity, update_entity

# Configure module logger
logger = logging.getLogger("iac_memory.db.tools")

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

# Define tool schemas
TOOL_SCHEMAS = {
    # Terraform Provider Operations
    "get_terraform_provider_info": {
        "type": "object",
        "description": "Retrieve comprehensive information about a Terraform provider",
        "required": ["provider_name"],
        "properties": {
            "provider_name": {
                "type": "string",
                "description": "Name of the Terraform provider",
            }
        },
    },
    "list_terraform_providers": {
        "type": "object",
        "description": "List all cached Terraform providers with basic metadata",
        "required": [],
        "properties": {
            "filter_criteria": {
                "type": "object",
                "description": "Optional filtering criteria",
                "properties": {
                    "name_pattern": {
                        "type": "string",
                        "description": "Regex pattern to filter provider names",
                    }
                },
            }
        },
    },
    "get_provider_version_history": {
        "type": "object",
        "description": "Retrieve version history for a specific Terraform provider",
        "required": ["provider_name"],
        "properties": {
            "provider_name": {
                "type": "string",
                "description": "Name of the Terraform provider",
            }
        },
    },
    "get_terraform_resource_info": {
        "type": "object",
        "description": "Retrieve comprehensive information about a Terraform resource including schema and documentation",
        "required": ["provider_name", "resource_name"],
        "properties": {
            "provider_name": {
                "type": "string",
                "description": "Name of the Terraform provider",
            },
            "resource_name": {"type": "string", "description": "Name of the resource"},
        },
    },
    "list_provider_resources": {
        "type": "object",
        "description": "List all resources associated with a specific Terraform provider",
        "required": ["provider_name"],
        "properties": {
            "provider_name": {
                "type": "string",
                "description": "Name of the Terraform provider",
            },
            "filter_criteria": {
                "type": "object",
                "description": "Optional filtering criteria",
                "properties": {
                    "type_pattern": {
                        "type": "string",
                        "description": "Regex pattern to filter resource types",
                    }
                },
            },
        },
    },
    "get_ansible_collection_info": {
        "type": "object",
        "description": "Retrieve comprehensive information about an Ansible collection",
        "required": ["collection_name"],
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name of the Ansible collection",
            }
        },
    },
    "list_ansible_collections": {
        "type": "object",
        "description": "List all cached Ansible collections with basic metadata",
        "required": [],
        "properties": {
            "filter_criteria": {
                "type": "object",
                "description": "Optional filtering criteria",
                "properties": {
                    "name_pattern": {
                        "type": "string",
                        "description": "Regex pattern to filter collection names",
                    }
                },
            }
        },
    },
    "get_collection_version_history": {
        "type": "object",
        "description": "Retrieve version history for a specific Ansible collection",
        "required": ["collection_name"],
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name of the Ansible collection",
            }
        },
    },
    "get_ansible_module_info": {
        "type": "object",
        "description": "Retrieve comprehensive information about an Ansible module including schema and documentation",
        "required": ["collection_name", "module_name"],
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name of the Ansible collection",
            },
            "module_name": {"type": "string", "description": "Name of the module"},
        },
    },
    "get_resource_version_compatibility": {
        "type": "object",
        "description": "Check resource compatibility across provider versions",
        "required": ["provider_name", "resource_name", "version"],
        "properties": {
            "provider_name": {
                "type": "string",
                "description": "Name of the Terraform provider",
            },
            "resource_name": {
                "type": "string",
                "description": "Name of the resource to check",
            },
            "version": {
                "type": "string",
                "description": "Target provider version to check compatibility against",
            },
        },
    },
    "add_terraform_provider": {
        "type": "object",
        "description": "Add a new Terraform provider to the memory store with version and documentation information",
        "required": ["name", "version", "source_url", "doc_url"],
        "properties": {
            "name": {"type": "string", "description": "Provider name"},
            "version": {"type": "string", "description": "Provider version"},
            "source_url": {"type": "string", "description": "Source repository URL"},
            "doc_url": {"type": "string", "description": "Documentation URL"},
        },
    },
    "update_provider_version": {
        "type": "object",
        "description": "Update an existing Terraform provider's version information and documentation links",
        "required": ["provider_name", "new_version"],
        "properties": {
            "provider_name": {"type": "string", "description": "Name of the provider"},
            "new_version": {"type": "string", "description": "New version"},
            "new_source_url": {"type": "string", "description": "New source URL"},
            "new_doc_url": {"type": "string", "description": "New documentation URL"},
        },
    },
    # Terraform Resource Operations
    "add_terraform_resource": {
        "type": "object",
        "description": "Add a new Terraform resource definition with its schema and version information",
        "required": [
            "provider",
            "name",
            "resource_type",
            "schema",
            "version",
            "doc_url",
        ],
        "properties": {
            "provider_id": {"type": "string", "description": "Provider ID"},
            "name": {"type": "string", "description": "Resource name"},
            "resource_type": {"type": "string", "description": "Resource type"},
            "schema": {"type": "string", "description": "Resource schema"},
            "version": {"type": "string", "description": "Resource version"},
            "doc_url": {"type": "string", "description": "Documentation URL"},
        },
    },
    "update_resource_schema": {
        "type": "object",
        "description": "Update an existing Terraform resource's schema and related information",
        "required": ["resource_id", "new_schema"],
        "properties": {
            "resource_id": {"type": "string", "description": "Resource ID"},
            "new_schema": {"type": "string", "description": "New schema"},
            "new_version": {"type": "string", "description": "New version"},
            "new_doc_url": {"type": "string", "description": "New documentation URL"},
        },
    },
    # Ansible Collection Operations
    "add_ansible_collection": {
        "type": "object",
        "description": "Add a new Ansible collection to the memory store with version and documentation information",
        "required": ["name", "version", "source_url", "doc_url"],
        "properties": {
            "name": {"type": "string", "description": "Collection name"},
            "version": {"type": "string", "description": "Collection version"},
            "source_url": {"type": "string", "description": "Source repository URL"},
            "doc_url": {"type": "string", "description": "Documentation URL"},
        },
    },
    "update_collection_version": {
        "type": "object",
        "description": "Update an existing Ansible collection's version information and documentation links",
        "required": ["collection_id", "new_version"],
        "properties": {
            "collection_id": {"type": "string", "description": "Collection ID"},
            "new_version": {"type": "string", "description": "New version"},
            "new_source_url": {"type": "string", "description": "New source URL"},
            "new_doc_url": {"type": "string", "description": "New documentation URL"},
        },
    },
    # Ansible Module Operations
    "add_ansible_module": {
        "type": "object",
        "description": "Add a new Ansible module definition with its schema and version information",
        "required": [
            "collection",
            "name",
            "module_type",
            "schema",
            "version",
            "doc_url",
        ],
        "properties": {
            "collection": {"type": "string", "description": "Collection ID or name"},
            "name": {"type": "string", "description": "Module name"},
            "module_type": {"type": "string", "description": "Module type"},
            "schema": {"type": "string", "description": "Module schema"},
            "version": {"type": "string", "description": "Module version"},
            "doc_url": {"type": "string", "description": "Documentation URL"},
        },
    },
    "update_module_version": {
        "type": "object",
        "description": "Update an existing Ansible module's schema and related information",
        "required": ["module_id", "new_schema"],
        "properties": {
            "module_id": {"type": "string", "description": "Module ID"},
            "new_schema": {"type": "string", "description": "New schema"},
            "new_version": {"type": "string", "description": "New version"},
            "new_doc_url": {"type": "string", "description": "New documentation URL"},
        },
    },
    "get_module_version_compatibility": {
        "type": "object",
        "description": "Check module compatibility across collection versions",
        "required": ["collection_name", "module_name", "version"],
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name of the Ansible collection",
            },
            "module_name": {
                "type": "string",
                "description": "Name of the module to check",
            },
            "version": {
                "type": "string",
                "description": "Target collection version to check compatibility against",
            },
        },
    },
    # Entity Operations
    "create_entity": {
        "type": "object",
        "description": "Create a new entity in the knowledge graph with optional initial observations",
        "required": ["name", "type"],
        "properties": {
            "name": {"type": "string", "description": "Entity name"},
            "type": {"type": "string", "description": "Entity type"},
            "observation": {"type": "string", "description": "Initial observation"},
        },
    },
    "update_entity": {
        "type": "object",
        "description": "Update an existing entity's properties and add new observations",
        "required": ["id"],
        "properties": {
            "id": {"type": "string", "description": "Entity ID"},
            "name": {"type": "string", "description": "New name"},
            "type": {"type": "string", "description": "New type"},
            "observation": {"type": "string", "description": "New observation"},
        },
    },
    "delete_entity": {
        "type": "object",
        "description": "Remove an entity and its relationships from the knowledge graph",
        "required": ["id"],
        "properties": {"id": {"type": "string", "description": "Entity ID"}},
    },
    "view_relationships": {
        "type": "object",
        "description": "Retrieve all relationships and observations for a specific entity",
        "required": ["entity_id"],
        "properties": {"entity_id": {"type": "string", "description": "Entity ID"}},
    },
}


def validate_tool_arguments(tool_name: str, arguments: Dict[str, Any]) -> None:
    """Validate tool arguments against schema.

    Args:
        tool_name: Name of tool to validate
        arguments: Tool arguments to validate

    Raises:
        ValidationError: If arguments are invalid
        McpError: If validation fails
    """
    try:
        from jsonschema import ValidationError as JsonSchemaValidationError
        from jsonschema import validate

        # Get schema for tool
        if tool_name not in TOOL_SCHEMAS:
            logger.error(f"Unknown tool requested: {tool_name}")
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND,
                    message=f"Unknown tool: {tool_name}",
                    data={"available_tools": list(TOOL_SCHEMAS.keys())},
                )
            )

        schema = TOOL_SCHEMAS[tool_name]

        # Validate against schema
        try:
            validate(instance=arguments, schema=schema)
            logger.debug(f"Schema validation passed for tool: {tool_name}")
        except JsonSchemaValidationError as e:
            logger.error(f"Schema validation failed for {tool_name}: {str(e)}")
            raise ValidationError(
                f"Missing required arguments for {tool_name}: {str(e)}"
            )

        # Additional validation for specific tools
        if tool_name.startswith("terraform_"):
            if "version" in arguments and not arguments["version"].strip():
                logger.error(f"Empty version provided for {tool_name}")
                raise McpError(
                    types.ErrorData(
                        code=types.INVALID_REQUEST,
                        message="Version cannot be empty",
                        data={"tool": tool_name, "field": "version"},
                    )
                )

        elif tool_name.startswith("ansible_"):
            if "name" in arguments and not arguments["name"].strip():
                logger.error(f"Empty name provided for {tool_name}")
                raise McpError(
                    types.ErrorData(
                        code=types.INVALID_REQUEST,
                        message="Name cannot be empty",
                        data={"tool": tool_name, "field": "name"},
                    )
                )

    except ImportError:
        logger.warning("jsonschema not available, falling back to basic validation")
        # Basic validation if jsonschema not available
        schema = TOOL_SCHEMAS[tool_name]
        required = schema.get("required", [])
        missing = [field for field in required if field not in arguments]
        if missing:
            logger.error(f"Missing required fields for {tool_name}: {missing}")
            raise McpError(
                types.ErrorData(
                    code=types.INVALID_REQUEST,
                    message=f"Missing required fields: {', '.join(missing)}",
                    data={"tool": tool_name, "missing_fields": missing},
                )
            )

        # Basic type validation
        properties = schema.get("properties", {})
        for field, value in arguments.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    logger.error(f"Invalid type for field {field} in {tool_name}")
                    raise McpError(
                        types.ErrorData(
                            code=types.INVALID_REQUEST,
                            message=f"Field {field} must be a string",
                            data={
                                "tool": tool_name,
                                "field": field,
                                "expected": "string",
                                "received": type(value).__name__,
                            },
                        )
                    )
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    logger.error(f"Invalid type for field {field} in {tool_name}")
                    raise McpError(
                        types.ErrorData(
                            code=types.INVALID_REQUEST,
                            message=f"Field {field} must be a number",
                            data={
                                "tool": tool_name,
                                "field": field,
                                "expected": "number",
                                "received": type(value).__name__,
                            },
                        )
                    )
                elif expected_type == "boolean" and not isinstance(value, bool):
                    logger.error(f"Invalid type for field {field} in {tool_name}")
                    raise McpError(
                        types.ErrorData(
                            code=types.INVALID_REQUEST,
                            message=f"Field {field} must be a boolean",
                            data={
                                "tool": tool_name,
                                "field": field,
                                "expected": "boolean",
                                "received": type(value).__name__,
                            },
                        )
                    )


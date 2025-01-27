"""Resource handlers for the IaC Memory MCP Server.

This module contains the MCP server handlers for resource operations.
Database operations are handled in db/resources.py.
"""

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import mcp.types as types
from mcp.server.lowlevel.server import RequestContext, Server
from mcp.shared.exceptions import McpError
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, Url
from pydantic_core.core_schema import ValidationInfo

from .context import BaseContext as TestContext
from .db.connection import DatabaseError
from .db.resources import (
    get_ansible_collections,
    get_ansible_modules,
    get_entities,
    get_entity_relationships,
    get_terraform_providers,
    get_terraform_resources,
)
from .db.terraform import get_provider_resources, get_resource_info
from .shared import get_db

# Configure module logger to inherit from root
logger = logging.getLogger("iac_memory.resources")


class ResourceUrl:
    """Custom URL type for resource URIs that supports template variables."""

    @classmethod
    def validate(cls, value: Any, handler: Optional[ValidationInfo] = None) -> str:
        """Validate and normalize resource URLs."""
        if isinstance(value, str):
            # Parse URL components
            try:
                parsed = urlparse(value)
            except Exception as e:
                raise ValueError(f"Invalid URL format: {str(e)}")

            # Validate scheme
            if parsed.scheme not in ["terraform", "ansible", "iac", "resources"]:
                raise ValueError(
                    f"Invalid scheme '{parsed.scheme}'. Must be one of: terraform, ansible, iac, resources"
                )

            # For template URIs, preserve the exact string without any parsing
            if "{" in value and "}" in value:
                # Just validate the scheme
                scheme = value.split("://", 1)[0]
                if scheme not in ["terraform", "ansible", "iac", "resources"]:
                    raise ValueError(
                        f"Invalid scheme '{scheme}'. Must be one of: terraform, ansible, iac, resources"
                    )
                return value

            # For concrete URIs, validate path components
            path = parsed.path.strip("/")
            if not path:
                raise ValueError("Path cannot be empty")

            parts = path.split("/")
            if len(parts) < 2:
                raise ValueError(
                    "Invalid resource path. Must have at least 2 components."
                )

            # For hierarchical URIs (resources://terraform/providers/aws),
            # we only validate basic path structure
            if parsed.scheme == "resources":
                if not parts:
                    raise ValueError("Path cannot be empty for hierarchical URIs")

                if len(parts) < 2:
                    raise ValueError("Path must include at least two components")

            return value
        elif isinstance(value, (Url, ResourceUrl)):
            return str(value)
        else:
            raise ValueError(f"Invalid URL type: {type(value)}")

    def __init__(self, url: str):
        """Initialize with a URL string."""
        self._url = url if "{" in url and "}" in url else self.validate(url, None)
        self._is_template = "{" in url and "}" in url

    def __str__(self) -> str:
        """Return the raw URL string."""
        return self._url

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"ResourceUrl({self._url!r})"

    def __eq__(self, other):
        """Compare URLs, preserving template variables."""
        if isinstance(other, str):
            return str(self) == other
        return str(self) == str(other)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> CoreSchema:
        """Get Pydantic core schema for URL validation."""
        return CoreSchema(type="str", validator=cls.validate)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Get JSON schema for URL validation."""
        return {
            "type": "string",
            "format": "uri",
            "pattern": "^(terraform|ansible|iac|resources)://.*$",
        }


# Define resource templates for common access patterns
RESOURCE_TEMPLATES = [
    {
        "uriTemplate": "resources://terraform/providers/{provider_name}",
        "name": "Terraform Provider",
        "description": "Access Terraform provider information and resources",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "resources://terraform/resources/{provider_name}/{resource_type}",
        "name": "Terraform Resource",
        "description": "Access specific Terraform resource type information",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "resources://ansible/collections/{collection_name}",
        "name": "Ansible Collection",
        "description": "Access Ansible collection information and modules",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "resources://ansible/modules/{collection_name}/{module_name}",
        "name": "Ansible Module",
        "description": "Access specific Ansible module information",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "resources://entities/{entity_id}",
        "name": "Entity",
        "description": "Access entity information including observations and relationships",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "resources://entities/{entity_id}/relationships",
        "name": "Entity Relationships",
        "description": "Access entity relationship information",
        "mimeType": "application/json",
    },
]


def extract_template_variables(uri: str, template: str) -> Optional[Dict[str, str]]:
    """Extract variables from a URI based on a template pattern.

    Args:
        uri: The actual URI to parse
        template: The template pattern containing {variable} placeholders

    Returns:
        Dictionary of variable names to values, or None if URI doesn't match template
    """
    # Convert template into regex pattern
    pattern_parts = template.split("/")
    uri_parts = uri.split("/")

    if len(pattern_parts) != len(uri_parts):
        return None

    variables = {}
    for template_part, uri_part in zip(pattern_parts, uri_parts):
        if template_part.startswith("{") and template_part.endswith("}"):
            var_name = template_part[1:-1]
            variables[var_name] = uri_part
        elif template_part != uri_part:
            return None

    return variables


async def handle_list_resources(
    ctx: RequestContext = None, page: int = 1, per_page: int = 50
) -> list[types.Resource]:
    """List available resources and resource templates.

    Lists both concrete resources from the database and available resource templates
    that can be used to construct valid resource URIs.

    Args:
        ctx: Request context
        page: Page number (1-based)
        per_page: Number of items per page
    """
    if ctx is None:
        try:
            from mcp.server.lowlevel.server import request_ctx

            ctx = request_ctx.get()
        except LookupError:
            ctx = TestContext(operation_name="list_resources")

    logger.info("Starting list_resources operation")

    # Get database instance
    db = get_db()
    logger.info("Listing available resources", extra={"database_path": db.db_path})

    # Validate database state
    if not db.is_initialized():
        msg = "Database not initialized"
        logger.error(msg)
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message=msg,
                data={"operation": "list_resources", "database_path": db.db_path},
            )
        )

    try:
        # Get all available resources
        result = []

        # Debug log database connection
        logger.debug(f"Using database at: {db.db_path}")

        # Get Terraform providers
        logger.debug("Fetching Terraform providers...")
        terraform_providers = [dict(p) for p in get_terraform_providers(db)]
        logger.debug(f"Found {len(terraform_providers)} Terraform providers")
        for p in terraform_providers:
            result.append(
                types.Resource(
                    uri=str(
                        ResourceUrl(f"resources://terraform/providers/{p['name']}")
                    ),
                    name=f"Provider: {p['name']}",
                    description=(
                        f"Terraform Provider v{p['version']} with {p['resource_count']} resources. "
                        f"Updated: {p['updated_at']}"
                    ),
                    mimeType="application/json",
                )
            )

        # Get Terraform resources
        logger.debug("Fetching Terraform resources...")
        terraform_resources = [dict(r) for r in get_terraform_resources(db)]
        logger.debug(
            f"Found {len(terraform_resources)} Terraform resources: {terraform_resources}"
        )
        for r in terraform_resources:
            result.append(
                types.Resource(
                    uri=str(
                        ResourceUrl(
                            f"resources://terraform/resources/{r['provider_name']}/{r['resource_type']}"
                        )
                    ),
                    name=r["name"],
                    description=(
                        f"Terraform Resource v{r['version']} from provider {r['provider_name']} "
                        f"v{r['provider_version']} ({r.get('relationship_type', 'MANAGED')})"
                    ),
                    mimeType="application/json",
                )
            )

        # Get Ansible collections
        logger.debug("Fetching Ansible collections...")
        ansible_collections = [dict(c) for c in get_ansible_collections(db)]
        logger.debug(f"Found {len(ansible_collections)} Ansible collections")
        for c in ansible_collections:
            result.append(
                types.Resource(
                    uri=str(
                        ResourceUrl(f"resources://ansible/collections/{c['name']}")
                    ),
                    name=f"Collection: {c['name']}",
                    description=(
                        f"Ansible Collection v{c['version']} with {c['module_count']} modules. "
                        f"Updated: {c['updated_at']}"
                    ),
                    mimeType="application/json",
                )
            )

        # Get Ansible modules
        logger.debug("Fetching Ansible resources...")
        ansible_modules = get_ansible_modules(db)
        logger.debug(f"Found {len(ansible_modules)} Ansible modules: {ansible_modules}")
        for m in ansible_modules:
            result.append(
                types.Resource(
                    uri=str(
                        ResourceUrl(
                            f"resources://ansible/modules/{m['collection_name']}/{m['module_name']}"
                        )
                    ),
                    name=m["module_name"],
                    description=f"Ansible Module v{m['module_version']} from collection {m['collection_name']} v{m['collection_version']}",
                    mimeType="application/json",
                )
            )

        # Get entities and relationships
        logger.debug("Fetching entities...")
        entities = [dict(e) for e in get_entities(db)]
        logger.debug(f"Found {len(entities)} entities")
        for e in entities:
            result.append(
                types.Resource(
                    uri=str(ResourceUrl(f"iac://entity/{e['id']}")),
                    name=f"Entity: {e['name']}",
                    description=(
                        f"Type: {e['type']}, Relationships: {e['relationship_count']}, "
                        f"Created: {e['created_at']}, Updated: {e['updated_at']}"
                    ),
                    mimeType="application/json",
                )
            )

        # Add concrete resources first
        concrete_resources = result.copy()
        result.clear()

        # Add template resources with raw (unencoded) URIs
        logger.debug("Adding resource templates...")
        for template in RESOURCE_TEMPLATES:
            # Create template URI without URL encoding the variables
            uri_str = template["uriTemplate"]
            try:
                # Create template resource using model_construct to bypass validation
                template_resource = types.Resource.model_construct(
                    uri=uri_str,  # Use raw string for template URIs
                    name=template["name"],
                    description=template["description"],
                    mimeType=template["mimeType"],
                )
                result.append(template_resource)
                logger.debug(f"Added template with URI: {uri_str}")
            except Exception as e:
                logger.error(f"Failed to add template {uri_str}: {str(e)}")
                # Log the full error for debugging
                logger.debug(f"Template error details: {str(e)}", exc_info=True)

        # Add concrete resources after templates
        result.extend(concrete_resources)
        logger.debug(
            f"Added {len(RESOURCE_TEMPLATES)} resource templates and {len(concrete_resources)} concrete resources"
        )

        # Log all URIs for debugging
        logger.debug("All URIs in response:")
        for r in result:
            logger.debug(f"  {str(r.uri)}")

        # Apply pagination
        total_resources = len(result)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        logger.info(f"Found {total_resources} total resources (including templates)")
        logger.info(f"Returning page {page} with {per_page} items per page")

        # Debug database state
        logger.debug("Database state:")
        logger.debug(f"Database path: {db.db_path}")
        logger.debug(f"Database initialized: {db.is_initialized()}")

        # Return paginated results
        return result[start_idx:end_idx]

    except DatabaseError as e:
        raise McpError(
            types.ErrorData(
                code=types.INTERNAL_ERROR,
                message="Failed to list resources",
                data={"error": str(e), "operation": "list_resources"},
            )
        )


async def handle_read_resource(
    uri: ResourceUrl, ctx: RequestContext = None
) -> str | bytes:
    """Read a specific resource's content by its URI."""
    if ctx is None:
        ctx = TestContext()

    # Get database instance early to ensure correct context
    db = ctx.db if hasattr(ctx, "db") else get_db()  # Use context's DB if available

    logger.info("Starting resource read operation")
    logger.info(f"Reading resource: {uri}")

    # Extract and validate resource URI
    uri_str = str(uri)
    scheme, path = uri_str.split("://", 1)

    # Support both legacy and hierarchical URI schemes
    if scheme not in ["terraform", "ansible", "iac", "resources"]:
        raise McpError(
            types.ErrorData(
                code=types.METHOD_NOT_FOUND,
                message=f"Resource not found: Unsupported URI scheme '{scheme}'",
                data={
                    "uri": uri_str,
                    "supported_schemes": ["terraform", "ansible", "iac", "resources"],
                    "example_hierarchical": "resources://terraform/providers/aws",
                },
            )
        )

    # Check if URI matches any templates first
    if scheme == "resources":
        for template in RESOURCE_TEMPLATES:
            variables = extract_template_variables(uri_str, template["uriTemplate"])
            if variables:
                logger.debug(
                    f"URI matches template {template['uriTemplate']} with variables {variables}"
                )
                if "terraform/providers" in template["uriTemplate"]:
                    provider_name = variables.get("provider_name")
                    resources = get_provider_resources(db, provider_name)
                    if resources:
                        provider = resources[0]
                        return (
                            f"Provider: {provider['provider_name']}\n"
                            f"Version: {provider['provider_version']}\n"
                            f"Resources: {len(resources)}\n"
                            f"Documentation: {provider['doc_url']}\n"
                            f"Relationships:\n"
                            + "\n".join(
                                f"- {r['resource_type']} ({r['relationship_type']})"
                                for r in resources
                            )
                        )
                elif "terraform/resources" in template["uriTemplate"]:
                    provider_name = variables.get("provider_name")
                    resource_type = variables.get("resource_type")
                    resources = [
                        r
                        for r in get_terraform_resources(db)
                        if r["provider_name"] == provider_name
                        and r["resource_type"] == resource_type
                    ]
                    if resources:
                        resource = resources[0]
                        return (
                            f"Resource: {resource['name']}\n"
                            f"Provider: {resource['provider_name']}\n"
                            f"Type: {resource['resource_type']}\n"
                            f"Version: {resource['version']}\n"
                            f"Documentation: {resource['doc_url']}\n"
                            f"Schema:\n{resource['schema']}"
                        )
                elif "/entities/" in template["uriTemplate"]:
                    entity_id = variables.get("entity_id")
                    if entity_id:
                        if "relationships" in template["uriTemplate"]:
                            relationships = get_entity_relationships(db, entity_id)
                            return (
                                "\n".join(
                                    f"{r['source_id']} -> {r['target_id']}: {r['relationship_type']}"
                                    for r in relationships
                                )
                                if relationships
                                else "No relationships found"
                            )
                        else:
                            from .db.entities import get_entity_with_observation

                            result = get_entity_with_observation(db, entity_id)
                            if result:
                                response = (
                                    f"Entity: {result['name']}\n"
                                    f"Type: {result['type']}\n"
                                    f"Created: {result['created_at']}\n"
                                    f"Updated: {result['updated_at']}"
                                )
                                if result.get("observation"):
                                    response += (
                                        f"\nObservation: {result['observation']}"
                                    )
                                return response

    # Handle hierarchical URIs (new format)
    if scheme == "resources":
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND,
                    message="Invalid resource path: Must have at least 2 components",
                    data={
                        "uri": uri_str,
                        "example": "resources://terraform/providers/aws",
                    },
                )
            )

        # Validate resource type
        resource_type = parts[0]  # terraform, ansible, or entities
        if resource_type not in ["terraform", "ansible", "entities"]:
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND,
                    message=f"Invalid resource path: Unsupported resource type '{resource_type}'",
                    data={
                        "uri": uri_str,
                        "supported_types": ["terraform", "ansible", "entities"],
                        "example": "resources://terraform/providers/aws",
                    },
                )
            )

        # Validate category
        category = parts[1]  # providers, resources, collections, modules
        valid_categories = {
            "terraform": ["providers", "resources"],
            "ansible": ["collections", "modules"],
            "entities": ["relationships"],
        }
        if category not in valid_categories.get(resource_type, []):
            raise ValueError("Invalid resource path")

        # Validate name component
        name = parts[2] if len(parts) > 2 else None
        if not name:
            raise ValueError("Invalid resource path")

        # Map hierarchical URI to legacy format
        if resource_type == "terraform" and category == "providers":
            scheme = "terraform"
            path = f"provider/{name}" if name else "provider"
        elif resource_type == "terraform" and category == "resources":
            scheme = "terraform"
            path = "/".join(parts[2:]) if len(parts) > 2 else ""
        elif resource_type == "ansible" and category == "collections":
            scheme = "ansible"
            path = f"collection/{name}" if name else "collection"
        elif resource_type == "ansible" and category == "modules":
            scheme = "ansible"
            path = "/".join(parts[2:]) if len(parts) > 2 else ""
        elif resource_type == "entities":
            scheme = "iac"
            path = f"entity/{name}" if name else "entity"

    try:
        logger.info("Parsing resource URI")

        # Parse path based on scheme
        parts = path.strip("/").split("/")

        if scheme == "terraform":
            if len(parts) != 2:
                raise ValueError(
                    "Invalid Terraform resource path. Expected format: provider/resource_type"
                )
            provider_name = parts[0]
            resource_type = parts[1]

            # Debug logging to inspect database state
            all_resources = get_terraform_resources(db)
            logger.debug(
                f"All terraform resources in DB: {[dict(r) for r in all_resources]}"
            )

            resources = get_provider_resources(db, provider_name)
            if not resources:
                raise McpError(
                    types.ErrorData(
                        code=types.METHOD_NOT_FOUND,
                        message=f"Resource not found: Provider '{provider_name}' does not exist",
                        data={"uri": uri_str},
                    )
                )

            matching_resources = [
                r for r in resources if r["resource_type"] == resource_type
            ]
            if not matching_resources:
                raise McpError(
                    types.ErrorData(
                        code=types.METHOD_NOT_FOUND,
                        message=f"Resource not found: Resource type '{resource_type}' not found for provider '{provider_name}'",
                        data={"uri": uri_str},
                    )
                )

            resource = matching_resources[0]
            return (
                f"Resource: {resource['name']}\n"
                f"Provider: {resource['provider_name']}\n"
                f"Type: {resource['resource_type']}\n"
                f"Version: {resource['version']}\n"
                f"Documentation: {resource['doc_url']}\n"
                f"Relationship: {resource.get('relationship_type', 'MANAGED')}\n"
                f"Schema:\n{resource['schema']}"
            )

        elif scheme == "ansible":
            if len(parts) != 2:
                raise ValueError(
                    "Invalid Ansible resource path. Expected format: collection_name/module_name"
                )
            collection_name, module_name = parts
            # Get module info using the collection and module names
            from .db.ansible import get_module_by_name

            module = get_module_by_name(db, collection_name, module_name)
            if not module:
                raise ValueError(
                    f"Module {module_name} not found in collection {collection_name}"
                )

            return (
                f"Module: {module['name']}\n"
                f"Collection: {module['collection_name']}\n"
                f"Type: {module['type']}\n"
                f"Version: {module['version']}\n"
                f"Documentation: {module['doc_url']}\n"
                f"Schema:\n{module['schema']}"
            )

        elif scheme == "iac":
            if len(parts) != 2 or parts[0] != "entity":
                raise ValueError("Invalid IaC resource path")
            name = parts[1]

        logger.info(f"Resolved resource name: {name}")
        if not name:
            raise McpError(
                types.ErrorData(
                    code=types.INVALID_REQUEST,
                    message="Resource name cannot be empty",
                    data={"uri": uri_str},
                )
            )
    except Exception as e:
        error_msg = f"Failed to parse resource URI: {str(e)}"
        logger.error(error_msg, extra={"uri": uri_str})
        # Determine if this is a "not found" error
        if "not found" in str(e).lower() or "no resources found" in str(e).lower():
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND,
                    message=error_msg,
                    data={
                        "uri": uri_str,
                        "error": str(e),
                        "expected_format": "[terraform|ansible|iac]://<path>",
                    },
                )
            )
        else:
            raise McpError(
                types.ErrorData(
                    code=types.INVALID_REQUEST,
                    message=error_msg,
                    data={
                        "uri": uri_str,
                        "error": str(e),
                        "expected_format": "[terraform|ansible|iac]://<path>",
                    },
                )
            )

    if not db.is_initialized():
        logger.info("Database not initialized, resetting")
        if os.environ.get("MCP_TEST_MODE"):
            logger.info("Test mode detected - resetting database to clean state")
            db.reset_database()

    try:
        # Handle Terraform resources
        if scheme == "terraform":
            if len(parts) < 2:
                raise ValueError("Invalid Terraform resource path")

            if parts[0] == "provider":
                resources = get_provider_resources(db, parts[1])
                if resources:
                    provider = resources[0]  # All resources have provider info
                    return (
                        f"Provider: {provider['provider_name']}\n"
                        f"Version: {provider['provider_version']}\n"
                        f"Resources: {len(resources)}\n"
                        f"Documentation: {provider['doc_url']}\n"
                        f"Relationships:\n"
                        + "\n".join(
                            f"- {r['resource_type']} ({r['relationship_type']})"
                            for r in resources
                        )
                    )
            elif parts[0] == "resource":
                resource = get_resource_info(db, parts[1])
                if resource:
                    return (
                        f"Resource: {resource['name']}\n"
                        f"Provider: {resource['provider_name']}\n"
                        f"Type: {resource['resource_type']}\n"
                        f"Version: {resource['version']}\n"
                        f"Documentation: {resource['doc_url']}\n"
                        f"Relationship: {resource['relationship_type']}\n"
                        f"Schema:\n{resource['schema']}"
                    )

        elif scheme == "ansible":
            from .db.ansible import get_collection_modules, get_module_info

            if parts[0] == "collection":
                modules = get_collection_modules(db, parts[1])
                if modules:
                    collection = modules[0]  # All modules have collection info
                    return (
                        f"Collection: {collection['collection_name']}\n"
                        f"Version: {collection['collection_version']}\n"
                        f"Modules: {len(modules)}\n"
                        f"Documentation: {collection['doc_url']}"
                    )
            else:  # module
                module = get_module_info(db, parts[1])
                if module:
                    return (
                        f"Module: {module['name']}\n"
                        f"Collection: {module['collection_name']}\n"
                        f"Type: {module['type']}\n"
                        f"Version: {module['version']}\n"
                        f"Documentation: {module['doc_url']}\n"
                        f"Schema:\n{module['schema']}"
                    )

        elif scheme == "iac":
            from .db.entities import get_entity_with_observation

            result = get_entity_with_observation(db, parts[1])
            if result:
                response = (
                    f"Entity: {result['name']}\n"
                    f"Type: {result['type']}\n"
                    f"Created: {result['created_at']}\n"
                    f"Updated: {result['updated_at']}"
                )
                if result.get("observation"):
                    response += f"\nObservation: {result['observation']}"
                return response

        # If we get here, resource wasn't found
        logger.info(f"Resource not found: {uri_str}")
        raise McpError(
            types.ErrorData(
                code=types.METHOD_NOT_FOUND,
                message=f"Resource not found: {uri_str}",
                data={"uri": uri_str},
            )
        )

    except McpError:
        raise
    except Exception as e:
        if "not found" in str(e).lower() or "no such" in str(e).lower():
            raise McpError(
                types.ErrorData(
                    code=types.METHOD_NOT_FOUND,
                    message=f"Resource not found: {name}",
                    data={
                        "uri": uri_str,
                        "resource_name": name,
                    },
                )
            )
        else:
            raise McpError(
                types.ErrorData(
                    code=types.INTERNAL_ERROR,
                    message="Failed to read resource",
                    data={
                        "uri": uri_str,
                        "error": str(e),
                        "operation": "read_resource",
                        "resource_name": name,
                    },
                )
            )


def register_resources(server: Server, db: Any) -> None:
    """Register all resource handlers with the server."""

    @server.list_resources()
    async def list_resources(ctx: RequestContext = None):
        return await handle_list_resources(ctx)

    @server.read_resource()
    async def read_resource(uri: ResourceUrl, ctx: RequestContext = None):
        return await handle_read_resource(uri, ctx)

    @server.list_resource_templates()
    async def list_resource_templates():
        """List available resource templates."""
        return [types.ResourceTemplate(**template) for template in RESOURCE_TEMPLATES]

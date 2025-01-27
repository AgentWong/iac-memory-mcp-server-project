"""Database package for IaC Memory MCP Server."""

from .ansible import (
    add_ansible_collection,
    add_ansible_module,
    get_collection_modules,
    get_module_info,
    update_collection_version,
    update_module_version,
)
from .connection import DatabaseError, DatabaseManager, UniqueConstraintError
from .core import execute_query, execute_write, get_db, reset_database
from .entities import (
    create_entity,
    delete_entity,
    get_entity,
    get_entity_with_observation,
    update_entity,
)
from .resources import (
    get_ansible_collections,
    get_ansible_modules,
    get_entities,
    get_entity_relationships,
    get_terraform_providers,
    get_terraform_resources,
)
from .terraform import (
    add_terraform_provider,
    add_terraform_resource,
    get_provider_resources,
    get_resource_info,
    update_provider_version,
    update_resource_schema,
)

__all__ = [
    "DatabaseManager",
    "DatabaseError",
    "UniqueConstraintError",
    "get_db",
    "execute_query",
    "execute_write",
    "reset_database",
    # Entity operations
    "create_entity",
    "update_entity",
    "delete_entity",
    "get_entity",
    "get_entity_relationships",
    "get_entity_with_observation",
    # Resource operations
    "get_terraform_resources",
    "get_terraform_providers",
    "get_ansible_modules",
    "get_ansible_collections",
    "get_entities",
    # Terraform operations
    "add_terraform_provider",
    "get_provider_resources",
    "update_provider_version",
    "add_terraform_resource",
    "get_resource_info",
    "update_resource_schema",
    # Ansible operations
    "add_ansible_collection",
    "get_collection_modules",
    "update_collection_version",
    "add_ansible_module",
    "get_module_info",
    "update_module_version",
]

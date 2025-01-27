# IaC Memory MCP Server

A Model Context Protocol (MCP) server that enhances Claude AI's capabilities by providing persistent memory storage for Infrastructure-as-Code (IaC) components, with a focus on version tracking and relationship mapping for Terraform and Ansible resources.

> [!NOTE]  
> This was a personal project to determine the state of AI's ability if the person using it (me)
> doesn't have subject matter expertise (lack of Python knowledge).  Since it has become rather cost
> prohibitive, I do not intend to develop or maintain this project further.

## Overview

The IaC Memory MCP Server addresses the challenge of maintaining accurate, version-aware context for IaC components by providing:

- Persistent storage and version tracking for IaC components
- Hierarchical resource organization with URI-based access
- Comprehensive relationship mapping between components
- Version-specific documentation management
- Schema validation and temporal metadata tracking
- Automated relationship analysis and insights

## Core Components

### Resource Management

The server implements a sophisticated resource management system with hierarchical URIs:

#### Resource URI Structure
```
resources://<platform>/<category>/<name>
```

Supported platforms:
- terraform
- ansible
- iac (for general infrastructure entities)

Example URIs:
```
resources://terraform/providers/aws
resources://terraform/resources/aws/s3_bucket
resources://ansible/collections/community.aws
resources://ansible/modules/community.aws/s3_bucket
```

#### Resource Templates
The server provides dynamic resource templates for standardized access patterns:
- Terraform provider information: `resources://terraform/providers/{provider_name}`
- Resource type details: `resources://terraform/resources/{provider_name}/{resource_type}`
- Ansible collection data: `resources://ansible/collections/{collection_name}`
- Module information: `resources://ansible/modules/{collection_name}/{module_name}`

### Prompts

The server implements four specialized prompts for IaC component discovery and analysis:

#### search_resources
- Purpose: Search for IaC resources
- Arguments:
  - `provider`: Provider name
  - `resource_type`: Resource type
- Returns: Information about specific resources for the given provider

#### analyze_entity
- Purpose: Analyze an entity and its relationships
- Arguments:
  - `entity_id`: Entity ID
  - `include_relationships`: Include relationships
- Returns: Detailed entity analysis including name, type, and observations

#### terraform_provider
- Purpose: Get information about a Terraform provider
- Arguments:
  - `provider_name`: Name of the Terraform provider (required)
  - `version`: Specific version to query (optional)
- Returns: Detailed provider information for the specified version

#### ansible_module
- Purpose: Get information about an Ansible module
- Arguments:
  - `collection_name`: Name of the Ansible collection (required)
  - `module_name`: Name of the module (required)
  - `version`: Specific version to query (optional)
- Returns: Detailed module information for the specified version

### Tools

The server implements comprehensive tooling for IaC component management:

#### Terraform Tools
- `get_terraform_provider_info`: Retrieve detailed provider information including version and resources
- `list_provider_resources`: List all resources available for a specific provider
- `get_terraform_resource_info`: Get detailed information about a specific resource type
- `add_terraform_provider`: Register new providers with versioning
- `add_terraform_resource`: Add resource definitions with schemas
- `update_provider_version`: Update provider versions with new documentation

#### Ansible Tools
- `get_ansible_collection_info`: Get detailed information about an Ansible collection
- `list_ansible_collections`: List all available Ansible collections
- `get_collection_version_history`: View version history of a collection
- `get_ansible_module_info`: Get detailed information about a specific module
- `list_collection_modules`: List all modules in a collection
- `get_module_version_compatibility`: Check version compatibility of modules
- `add_ansible_collection`: Register new Ansible collections
- `add_ansible_module`: Add new modules with validation and documentation

#### Entity Operations
- `create_entity`: Create new infrastructure entities
- `update_entity`: Modify existing entity configurations
- `delete_entity`: Remove entities with relationship cleanup
- `view_relationships`: Analyze entity dependencies and relationships

## Configuration

The server supports configuration through environment variables:

- `DATABASE_URL`: SQLite database location
- `MCP_DEBUG`: Enable debug logging when set
- `MCP_TEST_MODE`: Enable test mode for database resets

For development, create a `.env` file:
```bash
DATABASE_URL=sqlite:////path/to/db.sqlite
MCP_DEBUG=1
MCP_TEST_MODE=1
```

## Integration with Claude Desktop

### Development Setup
```json
"mcpServers": {
  "iac-memory": {
    "command": "uv",
    "args": [
      "--directory",
      "/path/to/iac-memory-mcp-server",
      "run",
      "iac-memory-mcp-server"
    ]
    "env": {
          "DATABASE_URL": "sqlite:////home/herman/iac.db"
      }
  }
}
```

### Production Setup
```json
"mcpServers": {
  "iac-memory": {
    "command": "uvx",
    "args": [
        "--from",
        "git+https://github.com/AgentWong/iac-memory-mcp-server.git",
        "python",
        "-m",
        "iac_memory_mcp_server"
    ],
    "env": {
          "DATABASE_URL": "sqlite:////home/herman/iac.db"
      }
  }
}
```

## Development

### Local Development
```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Development server with MCP Inspector
npx @modelcontextprotocol/inspector uv run iac-memory-mcp-server
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
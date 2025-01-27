"""Registration of prompts for the IaC Memory MCP Server."""

import logging
import sys

import mcp.types as types
from mcp.server.lowlevel.server import request_ctx
from mcp.shared.context import RequestContext
from mcp.shared.exceptions import McpError

from .db.connection import DatabaseManager

# Configure module logger
logger = logging.getLogger("iac_memory.prompts")

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


async def handle_list_prompts(ctx: RequestContext = None) -> list[types.Prompt]:
    """List available prompts."""
    if ctx is None:
        ctx = request_ctx.get()
    try:
        logger.info("Listing available prompts")

        # Main operation - get prompts
        prompts = [
            types.Prompt(
                name="search_resources",
                description="Search for IaC resources",
                arguments=[
                    types.PromptArgument(name="provider", description="Provider name"),
                    types.PromptArgument(
                        name="resource_type", description="Resource type"
                    ),
                ],
            ),
            types.Prompt(
                name="analyze_entity",
                description="Analyze an entity and its relationships",
                arguments=[
                    types.PromptArgument(name="entity_id", description="Entity ID"),
                    types.PromptArgument(
                        name="include_relationships",
                        description="Include relationships",
                    ),
                ],
            ),
            types.Prompt(
                name="terraform_provider",
                description="Get information about a Terraform provider",
                arguments=[
                    types.PromptArgument(
                        name="provider_name",
                        description="Name of the Terraform provider",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="version",
                        description="Specific version to query (optional)",
                        required=False,
                    ),
                ],
            ),
            types.Prompt(
                name="ansible_module",
                description="Get information about an Ansible module",
                arguments=[
                    types.PromptArgument(
                        name="collection_name",
                        description="Name of the Ansible collection",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="module_name",
                        description="Name of the module",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="version",
                        description="Specific version to query (optional)",
                        required=False,
                    ),
                ],
            ),
        ]
        # Verification step
        logger.info(f"Found {len(prompts)} prompts")
        return prompts
    except Exception as e:
        logger.error(f"Error listing prompts: {str(e)}")
        raise


async def handle_get_prompt(prompt_name: str, arguments: dict) -> types.GetPromptResult:
    """Get a prompt with the given arguments."""

    async def handle_prompt():
        try:
            logger.info(
                f"Getting prompt: {prompt_name}", extra={"arguments": arguments}
            )

            # Main operation - format prompt
            if prompt_name == "search_resources":
                provider = arguments.get("provider", "")
                resource_type = arguments.get("resource_type", "")
                message = f"Show me information about the {resource_type} resource in the {provider} provider"
            elif prompt_name == "analyze_entity":
                entity_id = arguments.get("entity_id", "")

                # Get entity details including observations and relationships
                with DatabaseManager.get_instance().get_connection() as conn:
                    cursor = conn.execute(
                        """SELECT e.*, o.content as observation 
                            FROM entities e
                            LEFT JOIN observations o ON e.id = o.entity_id
                            WHERE e.id = ?""",
                        (entity_id,),
                    )
                    entity = cursor.fetchone()
                    if not entity:
                        raise ValueError(f"Entity not found: {entity_id}")

                    message = f"Analyze entity {entity_id}:\n"
                    message += f"Name: {entity['name']}\n"
                    message += f"Type: {entity['type']}\n"
                    if entity["observation"]:
                        message += f"Observation: {entity['observation']}\n"
            else:
                raise McpError(
                    types.ErrorData(
                        code=types.METHOD_NOT_FOUND,
                        message=f"Unknown prompt: {prompt_name}",
                        data={
                            "available_prompts": ["search_resources", "analyze_entity"]
                        },
                    )
                )

            # Create prompt result
            result = types.GetPromptResult(
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=message),
                    )
                ]
            )

            logger.info(
                "Prompt generated successfully",
                extra={"prompt_name": prompt_name, "arguments": arguments},
            )

            return result

        except Exception as e:
            raise McpError(
                types.ErrorData(
                    code=types.INTERNAL_ERROR,
                    message=f"Failed to get prompt: {str(e)}",
                    data={"prompt_name": prompt_name, "arguments": arguments},
                )
            )

    return await handle_prompt()


def register_prompts(server, db):
    """Register all prompts with the server."""
    # Register handlers directly
    server.get_prompt()(handle_get_prompt)
    server.list_prompts()(handle_list_prompts)

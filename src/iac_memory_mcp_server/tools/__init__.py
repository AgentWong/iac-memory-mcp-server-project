"""Tool handling package for the IaC Memory MCP Server.

This package provides the tool handling functionality including:
- Tool registration and management
- Tool execution
- Tool listing and schema validation
"""

import logging
from typing import Any, Dict

from mcp.server.lowlevel.server import RequestContext, Server

from ..db.tools import TOOL_SCHEMAS
from .ansible import ansible_tool_handlers
from .base import base_call_tool, base_list_tools
from .entity import entity_tool_handlers
from .terraform import terraform_tool_handlers

# Configure package logger
logger = logging.getLogger("iac_memory.tools")

# Combine all tool handlers
tool_handlers = {
    **terraform_tool_handlers,
    **ansible_tool_handlers,
    **entity_tool_handlers,
}


async def handle_call_tool(
    tool_name: str, arguments: Dict[str, Any], ctx: RequestContext | None = None
) -> Any:
    """Main entry point for tool execution."""
    return await base_call_tool(tool_name, arguments, ctx, tool_handlers)


async def handle_list_tools(ctx: RequestContext = None) -> list:
    """Main entry point for tool listing."""
    return await base_list_tools(TOOL_SCHEMAS, ctx)


def register_tools(server: Server) -> None:
    """Register all tool handlers with the server."""

    @server.call_tool()
    async def call_tool(
        name: str, arguments: Dict[str, Any], ctx: RequestContext | None = None
    ):
        return await handle_call_tool(name, arguments, ctx)

    @server.list_tools()
    async def list_tools(ctx: RequestContext = None):
        return await handle_list_tools(ctx)

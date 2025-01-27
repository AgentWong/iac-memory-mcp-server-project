"""Database context tests.

This module tests the database context functionality including:
- Info message handling 
- Error handling

Uses direct database access through db_test_context.
"""

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import METHOD_NOT_FOUND
from pydantic import AnyUrl

from iac_memory_mcp_server.resources import handle_read_resource
from iac_memory_mcp_server.server import db
from iac_memory_mcp_server.tools import handle_call_tool

from .test_utils.base_utils import capture_taskgroup_errors
from .test_utils.db_utils import db_test_context


@pytest.mark.asyncio
async def test_info_messages():
    """Test info message handling through Context"""
    async with db_test_context(operation_name="test_info_messages") as ctx:
        async with capture_taskgroup_errors():
            # Initialize database and verify info messages
            db.reset_database()
        await ctx.info("Test message")
        assert len(ctx.info_messages) > 0
        assert "Test message" in ctx.info_messages[0]

        arguments = {"name": "test-entity", "type": "test-type"}
        await handle_call_tool("create_entity", arguments)


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling through Context"""
    async with db_test_context(operation_name="test_error_handling") as _:
        async with capture_taskgroup_errors():
            # Test invalid tool arguments
            result = await handle_call_tool("create_entity", {})
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 1, "Should have one error message"
            assert "Missing required arguments" in result[0].text

        # Test invalid resource URI
        with pytest.raises(McpError) as exc_info:
            await handle_read_resource(AnyUrl("invalid://uri"))
        assert exc_info.value.error.code == METHOD_NOT_FOUND
        assert (
            "Resource not found: Unsupported URI scheme" in exc_info.value.error.message
        )

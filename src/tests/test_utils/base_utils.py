"""Base test utilities shared between database and MCP client testing.

This module provides common functionality used by both database-direct
and MCP client testing approaches. It includes:

- BaseTestContext: Common context functionality
- Error capture utilities
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from iac_memory_mcp_server.context import BaseContext
from iac_memory_mcp_server.utils.errors import DatabaseError


class BaseTestContext(BaseContext):
    """Base class for test contexts with common functionality."""

    pass


@asynccontextmanager
async def capture_taskgroup_errors() -> AsyncGenerator[None, None]:
    """Context manager for error handling."""
    try:
        yield
    except Exception as e:
        # Let DatabaseError pass through unchanged
        if isinstance(e, DatabaseError):
            raise
        # Re-raise other exceptions
        raise

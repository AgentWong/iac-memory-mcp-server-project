"""Database testing utilities for direct database access.

This module provides utilities for testing database functionality
directly without MCP client overhead. It includes:

- DbTestContext: Database testing context with logging
- Context manager for database tests
- Progress and error tracking

Usage:
    async with db_test_context() as ctx:
        # Database test code here
        await ctx.info("Starting operation")
        with ctx.db.get_connection() as conn:
            # Direct database operations
            conn.execute("SELECT * FROM entities")
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from iac_memory_mcp_server.db.connection import DatabaseManager
from iac_memory_mcp_server.utils.errors import DatabaseError

from .base_utils import BaseTestContext
from .exceptions import DatabaseTestError, TimeoutError


class DbTestContext(BaseTestContext):
    """Test context for direct database testing."""

    def __init__(self, operation_name: str = "test"):
        super().__init__(operation_name)
        self.db = DatabaseManager.get_instance()
        self.info_messages = []
        self.logger = logging.getLogger(f"db_test.{operation_name}")
        self.logger.setLevel(logging.DEBUG)

        # Create a handler that captures messages
        class MessageCaptureHandler(logging.Handler):
            def __init__(self, message_list, operation_name):
                super().__init__()
                self.message_list = message_list
                self.operation_name = operation_name

            def emit(self, record):
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                msg = f"{timestamp} - {record.levelname} - [{self.operation_name}] {self.format(record)}"
                self.message_list.append(msg)

        # Add handler to capture database logs
        capture_handler = MessageCaptureHandler(self.info_messages, self.operation_name)
        capture_handler.setFormatter(logging.Formatter("%(message)s"))

        # Ensure root logger is properly configured for tests
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Enable all logging during tests

        # Add handler to all relevant loggers
        loggers = [
            logging.getLogger("iac_memory.db"),
            logging.getLogger("iac_memory.db.terraform"),
            logging.getLogger("iac_memory.db.tools"),
            logging.getLogger("iac_memory.resources"),
        ]

        for logger in loggers:
            logger.addHandler(capture_handler)
            logger.setLevel(logging.DEBUG)  # Ensure each logger allows debug messages

    async def info(self, message: str, **extra: Any) -> None:
        """Record info message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{timestamp} - INFO - [{self.operation_name}] {message}"
        self.info_messages.insert(0, msg)
        self.logger.info(msg, extra=extra)

    async def debug(self, message: str, **extra: Any) -> None:
        """Record debug message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{timestamp} - DEBUG - [{self.operation_name}] {message}"
        self.info_messages.append(msg)
        self.logger.debug(msg, extra=extra)

    async def warning(self, message: str, **extra: Any) -> None:
        """Record warning message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{timestamp} - WARNING - [{self.operation_name}] {message}"
        self.info_messages.append(msg)
        self.logger.warning(msg, extra=extra)

    async def error(self, message: str, **extra: Any) -> None:
        """Record error message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{timestamp} - ERROR - [{self.operation_name}] {message}"
        self.info_messages.append(msg)
        self.logger.error(msg, extra=extra)


@asynccontextmanager
async def db_test_context(
    operation_name: str = "test", timeout_seconds: float = 5.0
) -> AsyncGenerator[DbTestContext, None]:
    """Context manager for database testing.

    Args:
        operation_name: Name of the test operation
        timeout_seconds: Maximum time to wait for operations

    Raises:
        TimeoutError: If operations exceed timeout
        DatabaseError: For database errors
    """
    ctx = DbTestContext(operation_name)

    try:
        async with asyncio.timeout(timeout_seconds):
            yield ctx
    except asyncio.TimeoutError as e:
        raise TimeoutError(f"Database test timeout after {timeout_seconds}s") from e
    except Exception as e:
        if isinstance(e, DatabaseError):
            # Let DatabaseError propagate up unchanged
            raise
        # Wrap other errors
        raise DatabaseTestError(str(e)) from e

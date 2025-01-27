"""Base context functionality for IaC Memory MCP Server."""

import time
from typing import Any, List

from anyio import create_memory_object_stream
from mcp.server.lowlevel.server import Server, request_ctx
from mcp.shared.session import BaseSession
from mcp.types import (
    ClientNotification,
    ClientRequest,
    ClientResult,
    ServerNotification,
    ServerRequest,
)


class DbTestSession(
    BaseSession[
        ClientRequest,
        ClientNotification,
        ClientResult,
        ServerRequest,
        ServerNotification,
    ]
):
    """Test session for direct database testing."""

    def __init__(self, operation_name: str = "test"):
        read_stream_send, read_stream_recv = create_memory_object_stream(100)
        write_stream_send, write_stream_recv = create_memory_object_stream(100)

        super().__init__(
            read_stream=read_stream_recv,
            write_stream=write_stream_send,
            receive_request_type=ServerRequest,
            receive_notification_type=ServerNotification,
        )

        self.read_stream_send = read_stream_send
        self.write_stream_recv = write_stream_recv
        self.request_id = f"test-{int(time.time() * 1000)}"
        self.operation_name = operation_name
        self.start_time = time.time()
        self.info_messages: List[str] = []
        self.notifications: List[ServerNotification] = []

    async def info(self, message: str, **extra: Any) -> None:
        """Record info message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.info_messages.append(f"{timestamp} - {message}")

    async def send_log_message(
        self, level: str, data: Any, logger: str | None = None
    ) -> None:
        """Record log message."""
        message = f"[{level}]"
        if logger:
            message += f" [{logger}]"
        message += f" {data}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.info_messages.append(f"{timestamp} - {message}")


class BaseContext:
    """Base class for operation contexts with common functionality."""

    def __init__(self, operation_name: str = "test"):
        self.request_id = f"op-{int(time.time())}"
        self.operation_name = operation_name
        self.start_time = time.time()
        self.session = DbTestSession(operation_name=operation_name)
        self.server = Server("test")
        # Store the token when setting the context
        self._token = request_ctx.set(self)

    async def send_log_message(self, level: str, message: str) -> None:
        """Send a log message if session is available."""
        if self.session:
            await self.session.send_log_message(level, message)

    def __del__(self):
        """Clean up context when object is destroyed."""
        try:
            if hasattr(self, "_token"):
                request_ctx.reset(self._token)
        except (LookupError, ValueError):
            pass

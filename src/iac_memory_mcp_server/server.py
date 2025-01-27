import asyncio
import logging
import os
import sys
import traceback

import mcp.server.stdio
from mcp.server.lowlevel.server import (
    NotificationOptions,
    Server,
)
from mcp.server.models import InitializationOptions

from .prompts import register_prompts
from .resources import register_resources
from .shared import db
from .tools import register_tools

# Configure root logger with proper formatting and handlers
root_logger = logging.getLogger()  # Get root logger

# Only enable logging when MCP_DEBUG is set
if os.environ.get("MCP_DEBUG"):
    root_logger.setLevel(logging.DEBUG)

    # Create formatter
    console_formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")

    # Create stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(console_formatter)
    stderr_handler.setLevel(logging.DEBUG)

    # Add handler to root logger
    root_logger.addHandler(stderr_handler)
else:
    # Disable all logging when MCP_DEBUG is not set
    root_logger.setLevel(logging.CRITICAL + 1)  # Above CRITICAL to disable all logging

# Get server logger as child of root
logger = logging.getLogger("iac_memory.server")
# No need to set level or add handlers - will inherit from root

# Initialize server instance with proper name and version
server = Server("iac-memory-mcp-server", version="0.1.0")

# Configure server capabilities
server.notification_options = NotificationOptions(
    resources_changed=True, tools_changed=True, prompts_changed=True
)


def init_database():
    """Initialize and configure the database."""
    logger.info("Initializing database")
    try:
        # Only reset database if we're in a test environment
        if os.environ.get("MCP_TEST_MODE"):
            logger.info("Test mode detected - resetting database to clean state")
            db.reset_database()

        if not db.is_initialized():
            raise RuntimeError(f"Database failed to initialize. Path: {db.db_path}")

        with db.get_connection() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;
                PRAGMA case_sensitive_like = OFF;
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = NORMAL;
                PRAGMA busy_timeout = 5000;
                PRAGMA temp_store = MEMORY;
            """
            )
            conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise


def register_handlers():
    """Register all server request handlers."""
    logger.info("Registering request handlers")
    try:
        # Register core handlers in order of dependency
        register_tools(
            server
        )  # Register tools first since other handlers may need them
        register_resources(server, db)  # Register resources next
        register_prompts(
            server, db
        )  # Register prompts last since they may use both tools and resources

        # Log success after all registrations complete
        logger.info("All handlers registered successfully")
    except Exception as e:
        logger.error(f"Failed to register handlers: {e}", exc_info=True)
        raise


async def main():
    """Initialize and run the MCP server."""
    try:
        logger.info("Starting MCP server", extra={"component": "server"})

        # Initialize components
        logger.info("Initializing server components", extra={"component": "server"})
        init_database()
        register_handlers()

        # Create initialization options with all capabilities enabled
        init_options = InitializationOptions(
            server_name="iac-memory-mcp-server",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(
                    prompts_changed=True, resources_changed=True, tools_changed=True
                ),
                experimental_capabilities={},
            ),
        )

        logger.info(
            "Starting server with stdio transport"
        )  # Keep stderr logging here since it's before server.run()
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            try:
                # After this point, we'll use MCP native logging through the session
                await server.run(
                    read_stream, write_stream, init_options, raise_exceptions=False
                )
            except Exception as e:
                logger.error(f"Server runtime error: {e}", exc_info=True)
                raise RuntimeError(f"Server runtime error: {e}") from e

    except Exception as e:
        logger.error(
            f"Fatal server error:\n"
            f"Error: {str(e)}\n"
            f"Database state: {'Initialized' if db.is_initialized() else 'Not initialized'}\n"
            f"Database path: {db.db_path}\n"
            f"Stack trace: {traceback.format_exc()}"
        )
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Server failed with error: {e}", exc_info=True)
        sys.exit(1)

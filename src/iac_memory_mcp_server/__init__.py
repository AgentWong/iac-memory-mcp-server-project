"""IaC Memory MCP Server package.

This package implements a Model Context Protocol (MCP) server for infrastructure
as code memory management.
"""

import asyncio
import os
import sys

from . import server


def main():
    """Main entry point for the package."""
    # Add src directory to Python path if not already there
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    asyncio.run(server.main())


if __name__ == "__main__":
    main()

# Export main items at package level
__all__ = ["main", "server", "db"]

"""Main entry point for running the package as a module."""

import asyncio
import sys

from .server import main as server_main


def main():
    """Main entry point with proper Windows compatibility"""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(server_main())
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nShutdown complete", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

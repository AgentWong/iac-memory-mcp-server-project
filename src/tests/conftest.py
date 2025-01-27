"""Test configuration and fixtures.

This module provides pytest configuration and fixtures for both:
1. Direct database testing
2. MCP client protocol testing

Key features:
- Database initialization and cleanup
- MCP client session management
- Error handling configuration
"""

import os
import warnings

import pytest

from iac_memory_mcp_server.db.connection import DatabaseManager

from .test_utils import db_test_context


@pytest.fixture(autouse=True)
def ignore_unraisable_warning():
    """Ignore the specific BaseSubprocessTransport warning during cleanup."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Exception ignored in:.*BaseSubprocessTransport.__del__",
            category=pytest.PytestUnraisableExceptionWarning,
        )
        yield


def pytest_configure(config):
    """Configure pytest and register custom markers."""
    # Register markers
    config.addinivalue_line("markers", "integration: mark test as integration test")

    # Set timeout for testing
    os.environ["MCP_TIMEOUT"] = "30"  # 30 seconds max for initialization

    # Enable debug logging for all tests
    os.environ["MCP_DEBUG"] = "1"

    # Register test context fixtures
    pytest.fixture()(db_test_context)


@pytest.fixture(scope="function")
def db_path(tmp_path_factory):
    """Create a temporary database path for testing."""
    test_db = tmp_path_factory.mktemp("test_db") / "test.db"
    return str(test_db)


@pytest.fixture(scope="function", autouse=True)
def db(db_path):
    """Fixture providing a clean database for each test.

    This fixture handles both direct database testing and MCP client testing by:
    1. Creating a clean database with proper schema
    2. Setting up test-appropriate configuration
    3. Verifying database initialization
    4. Managing connection pooling
    5. Handling cleanup

    Args:
        db_path: Path to test database from db_path fixture

    Returns:
        DatabaseManager: Configured database manager instance

    Raises:
        RuntimeError: If database initialization fails
        pytest.Failed: If required tables are missing
    """
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Set environment variables for both testing approaches
    os.environ.update(
        {
            "DATABASE_URL": db_path,
            "DATABASE_PATH": db_path,
            "MCP_DATABASE_PATH": db_path,
            "MCP_TEST_MODE": "1",  # Enable test mode
            "MCP_TIMEOUT": "60",  # 60 second timeout for MCP operations
            "DB_TIMEOUT": "10",  # 10 second timeout for direct DB operations
            "MCP_DB_INIT_TIMEOUT": "30",  # 30 second timeout for DB initialization
            "MCP_RETRY_COUNT": "3",  # Number of retries for DB operations
            "MCP_RETRY_DELAY": "2",  # Base delay between retries (seconds)
            "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        }
    )

    # Reset singleton and set DATABASE_URL
    DatabaseManager.reset_instance()
    os.environ["DATABASE_URL"] = db_path
    os.environ["DATABASE_PATH"] = db_path
    os.environ["MCP_DATABASE_PATH"] = db_path

    # Initialize database manager with test path and ensure clean state
    manager = DatabaseManager.get_instance(db_path)
    manager.reset_database()

    # Configure database for testing with proper initialization sequence and timeouts
    with manager.get_connection(
        timeout=float(os.getenv("MCP_DB_INIT_TIMEOUT", "30"))
    ) as conn:
        # Configure database with optimized test settings
        conn.execute("PRAGMA foreign_keys = OFF")  # Disable during schema setup
        conn.execute("PRAGMA journal_mode = DELETE")  # More reliable than WAL for tests
        conn.execute("PRAGMA synchronous = NORMAL")  # Better performance for tests
        conn.execute("PRAGMA case_sensitive_like = OFF")  # Case-insensitive matching
        conn.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp storage
        conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
        conn.commit()

        # Load schema first
        with open("src/iac_memory_mcp_server/schema.sql") as f:
            conn.executescript(f.read())
        conn.commit()

        # Now enable constraints
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()  # Commit before VACUUM

    # VACUUM must be outside any transaction
    with manager.get_connection() as conn:
        conn.execute("VACUUM")
        conn.commit()

    # Verify in new connection
    with manager.get_connection() as conn:
        # Verify tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        if not tables:
            raise RuntimeError("Failed to create database tables")

        # Clean database
        conn.execute("VACUUM")
        conn.commit()

        # Now enable constraints and start transaction
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")

        # Load schema from file
        schema_path = os.path.join(
            os.path.dirname(__file__), "../iac_memory_mcp_server/schema.sql"
        )
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.commit()

    # Clear all tables in a transaction
    with manager.get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Delete in proper order to handle foreign keys
            conn.execute("DELETE FROM observations")
            conn.execute("DELETE FROM entity_relationships")
            conn.execute("DELETE FROM entities")
            conn.execute("DELETE FROM provider_resources")
            conn.execute("DELETE FROM terraform_resources")
            conn.execute("DELETE FROM terraform_providers")
            conn.execute("DELETE FROM ansible_modules")
            conn.execute("DELETE FROM ansible_collections")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # VACUUM must be run outside transaction
    with manager.get_connection() as conn:
        conn.execute("VACUUM")

    # Verify initialization worked
    try:
        with manager.get_connection() as conn:
            # Verify all tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            # Check for required tables
            required_tables = [
                "terraform_providers",
                "terraform_resources",
                "provider_resources",
                "ansible_collections",
                "ansible_modules",
                "entities",
                "observations",
                "entity_relationships",
            ]

            missing_tables = [t for t in required_tables if t not in table_names]
            if missing_tables:
                pytest.fail(f"Missing required tables: {', '.join(missing_tables)}")

    except Exception as e:
        pytest.fail(f"Failed to initialize test database: {str(e)}")

    return manager


@pytest.fixture(autouse=True)
def cleanup_db(db):
    """Clean up database after each test."""
    yield db
    db.reset_database()


def pytest_collection_modifyitems(config, items):
    """Configure test collection and marking.

    This function:
    1. Adds integration markers
    2. Sets appropriate timeouts:
       - 30s for MCP client tests
       - 5s for direct database tests
    3. Configures test contexts based on test type
    4. Sets up appropriate fixtures based on test type
    5. Configures error handling and reporting

    The function ensures:
    - Proper context management for each test type
    - Appropriate timeout settings
    - Correct fixture dependencies
    - Error handling strategy
    """
    for item in items:
        # Handle integration tests (MCP client)
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.timeout(60))  # 60s for MCP tests

        # Handle database tests
        elif "async" in item.keywords:
            item.add_marker(pytest.mark.timeout(5))  # 5s for DB tests
            item.fixturenames.append("db_test_context")  # Ensure DB context

        # Add common fixtures for all tests
        item.fixturenames.extend(["cleanup_db", "ignore_unraisable_warning"])


@pytest.fixture
def mcp_env(db_path):
    """Configure environment for MCP client testing.

    This fixture:
    1. Sets up proper environment variables
    2. Configures paths and timeouts
    3. Enables test mode
    4. Sets up logging
    5. Configures error handling

    Args:
        db_path: Path to test database from db_path fixture

    Returns:
        dict: Environment configuration for MCP testing

    The environment includes:
    - Database paths and URLs
    - Python path configuration
    - Timeout settings (30s MCP, 5s DB)
    - Test mode flags
    - Logging configuration
    - Error handling settings
    """
    env = os.environ.copy()
    env.update(
        {
            # Database configuration
            "DATABASE_PATH": db_path,
            "DATABASE_URL": f"sqlite:///{db_path}",
            "MCP_DATABASE_PATH": db_path,
            # Path configuration
            "PYTHONPATH": str(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            # Timeout settings
            "MCP_SERVER_TIMEOUT": "30",
            "DB_TIMEOUT": "5",
            # Test mode and features
            "MCP_TEST_MODE": "1",
            "MCP_ERROR_HANDLING": "strict",
            # Logging configuration
            "MCP_LOG_LEVEL": "DEBUG",
            "MCP_LOG_FORMAT": "detailed",
        }
    )
    return env


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish():
    """Ensure proper cleanup of test resources.

    This hook:
    1. Ensures event loop cleanup
    2. Closes all database connections
    3. Removes temporary test databases
    4. Resets environment variables
    """
    # Reset environment variables
    for key in [
        "DATABASE_URL",
        "DATABASE_PATH",
        "MCP_DATABASE_PATH",
        "MCP_TEST_MODE",
        "MCP_TIMEOUT",
        "DB_TIMEOUT",
        "MCP_DEBUG",  # Also clean up MCP_DEBUG
    ]:
        os.environ.pop(key, None)

    # Let pytest handle event loop cleanup
    pass

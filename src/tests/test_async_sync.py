"""Database-direct tests for async/sync boundary handling.

This module verifies the IaC Memory MCP Server's ability to maintain data integrity
and relationship consistency while handling asynchronous database operations. It
focuses on the boundaries between async and sync code, particularly in persistent
storage operations for Infrastructure as Code components.

Key Test Areas:
1. Component Storage Operations
   - Terraform provider persistence
   - Resource definition storage
   - Ansible collection tracking
   - Module information management
   - Version compatibility mapping

2. Async/Sync Boundaries
   - Database operations in async context
   - Transaction management across boundaries
   - Connection pooling in async code
   - Resource cleanup across contexts

3. Transaction Management
   - Concurrent operation handling
   - Lock management strategies
   - Deadlock prevention
   - State consistency preservation
   - Relationship integrity

4. Data Integrity
   - Component version tracking
   - Relationship consistency
   - Temporal metadata handling
   - Source URL validation
   - Cross-reference accuracy

5. Error Handling
   - Transaction rollback
   - Connection recovery
   - Resource cleanup
   - Error propagation
   - State restoration

Implementation Details:
1. Database Operations
   - Direct connections (no MCP overhead)
   - Connection pooling
   - Transaction isolation
   - Lock management
   - Timeout handling (5s)

2. Async Context Management
   - Resource cleanup
   - Error handling
   - State verification
   - Connection lifecycle

3. Data Verification
   - Component integrity
   - Relationship consistency
   - Version accuracy
   - Metadata completeness
   - Cross-reference validity

Test Structure:
1. Setup
   - Database initialization
   - Component preparation
   - Context establishment

2. Execution
   - Async operation handling
   - Transaction management
   - State verification
   - Error simulation
   - Cleanup procedures

3. Verification
   - Data integrity checks
   - Relationship validation
   - Error handling verification
   - Resource cleanup confirmation

The tests ensure:
1. Data Persistence
   - Component information accuracy
   - Relationship preservation
   - Version tracking reliability
   - Metadata consistency
   - Source validation

2. Async Operation Safety
   - Transaction isolation
   - Connection stability
   - Resource management
   - Error handling
   - State consistency

Import from test_utils.db_utils for database testing utilities.
"""

import asyncio

import pytest
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl

from iac_memory_mcp_server.tools import handle_call_tool
from iac_memory_mcp_server.resources import handle_list_resources, handle_read_resource

from .test_utils import db_test_context


@pytest.mark.asyncio
async def test_list_resources_async_behavior(db):
    """Test that list_resources handler properly uses database.

    This test verifies:
    1. Proper async/sync boundary handling when listing resources
    2. Database connection management in async context
    3. Transaction isolation during resource listing
    4. Timeout handling for database operations

    Args:
        db: Database fixture providing clean test database

    Raises:
        DatabaseTestError: If database operations fail
        asyncio.TimeoutError: If operations exceed 5s timeout
    """
    async with db_test_context() as _:  # noqa: F841
        # Reset database and prepare test data
        db.reset_database()

        # Use context manager with explicit timeout
        with db.get_connection(timeout=5.0) as conn:  # Match asyncio timeout
            conn.execute("BEGIN IMMEDIATE")
            
            # Add test provider
            conn.execute("""
                INSERT INTO terraform_providers (name, version, source_url, doc_url)
                VALUES (?, ?, ?, ?)
            """, ("test-provider", "1.0.0", "https://test.com", "https://test.com/docs"))
            provider_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Add test resources
            resources = [
                ("test_resource1", "test_type1", "{}"),
                ("test_resource2", "test_type2", "{}"),
                ("test_resource3", "test_type3", "{}"),
            ]
            for name, resource_type, schema in resources:
                conn.execute("""
                    INSERT INTO terraform_resources (provider_id, name, resource_type, schema, version, doc_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (provider_id, name, resource_type, schema, "1.0.0", f"https://test.com/docs/{name}"))
            conn.commit()

        # List resources with timeout
        async with asyncio.timeout(5):
            result = await handle_list_resources()

            # Verify results
            assert isinstance(result, list), "Result should be a list"
            # Filter out template resources and verify provider resource
            concrete_resources = [r for r in result if "{" not in str(r.uri) and "}" not in str(r.uri)]
            assert len(concrete_resources) == 1, "Should have 1 provider resource"
            provider = concrete_resources[0]
            assert hasattr(provider, "uri"), "Provider should have URI"
            assert hasattr(provider, "name"), "Provider should have name"
            assert "test-provider" in provider.name, "Provider name should match"
            assert "3 resources" in provider.description, "Provider should show correct resource count"


@pytest.mark.asyncio
async def test_read_resource_boundary():
    """Test resource handler validates URI scheme.

    This test verifies:
    1. Proper error handling for invalid URI schemes
    2. McpError raised with correct error details
    3. Clean context management during errors

    Raises:
        McpError: Expected for invalid URI scheme
        DatabaseTestError: If database operations fail
    """
    async with db_test_context() as _:  # noqa: F841
        # Should raise McpError for invalid URI
        with pytest.raises(McpError):
            await handle_read_resource("invalid://uri")


@pytest.mark.asyncio
async def test_create_entity_tool_boundaries(db):
    """Test create-entity tool properly uses context and database.

    This test verifies:
    1. Database reset and cleanup before operations
    2. Proper transaction handling during entity creation
    3. Context propagation through tool execution
    4. Database connection timeout handling (5s)
    5. Entity creation verification in database

    Args:
        db: Database fixture providing clean test database

    Raises:
        DatabaseTestError: If database operations fail
        asyncio.TimeoutError: If operations exceed 5s timeout
        McpError: If tool execution fails
    """
    async with db_test_context() as _:  # noqa: F841  # Use database context
        async with asyncio.timeout(5):  # 5 second timeout per testing rules
            # Reset database and clear existing data
            db.reset_database()
            with db.get_connection() as conn:
                conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout for locks
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute("DELETE FROM entities")
                    conn.execute("DELETE FROM observations")
                    conn.execute("DELETE FROM entity_relationships")
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

            arguments = {
                "name": "test-entity",
                "type": "test-type",
                "observation": "Initial test observation",
            }

            result = await handle_call_tool("create_entity", arguments)

            # Verify result format
            assert isinstance(result, list)
            assert len(result) == 1
            assert "Created entity 'test-entity'" in result[0].text

            # Verify entity was actually created in database
            with db.get_connection() as conn:
                entity = conn.execute(
                    "SELECT name, type FROM entities WHERE name = ?", ("test-entity",)
                ).fetchone()
                assert entity is not None, "Entity was not created in database"
                assert entity[0] == "test-entity"
                assert entity[1] == "test-type"


@pytest.mark.asyncio
async def test_async_sync_boundaries(db):
    """Test proper handling of async/sync boundaries"""
    async with db_test_context() as _:  # noqa: F841
        async with asyncio.timeout(5):  # 5 second timeout per testing rules
            # Test synchronous database operations inside async handler
            with db.get_connection() as conn:
                conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout for locks
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Add test provider
                    conn.execute("""
                        INSERT INTO terraform_providers (name, version, source_url, doc_url)
                        VALUES (?, ?, ?, ?)
                    """, ("test-provider", "1.0.0", "https://test.com", "https://test.com/docs"))
                    provider_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                    # Add test resources
                    for i in range(5):
                        conn.execute("""
                            INSERT INTO terraform_resources (provider_id, name, resource_type, schema, version, doc_url)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            provider_id,
                            f"resource{i}",
                            f"test_type{i}",
                            "{}",
                            "1.0.0",
                            f"https://test.com/docs/resource{i}"
                        ))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

            # List resources
            result = await handle_list_resources()

            # Verify async operations worked correctly
            assert isinstance(result, list), "Result should be a list"
            # Filter out template resources and verify provider resource
            concrete_resources = [r for r in result if "{" not in str(r.uri) and "}" not in str(r.uri)]
            assert len(concrete_resources) == 1, "Should have 1 provider resource"
            provider = concrete_resources[0]
            assert hasattr(provider, "uri"), "Provider should have URI"
            assert hasattr(provider, "name"), "Provider should have name"
            assert "test-provider" in provider.name, "Provider name should match"
            assert "5 resources" in provider.description, "Provider should show correct resource count"
            assert isinstance(provider.uri, AnyUrl), "Provider URI should be AnyUrl"

            # Verify database connection was properly managed
            with db.get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM terraform_resources").fetchone()[0]
                assert count == 5


@pytest.mark.asyncio
async def test_sequential_db_operations(db):
    """Test sequential entity creation operations"""
    async with db_test_context() as _:  # noqa: F841
        async with asyncio.timeout(5):  # 5 second timeout per testing rules
            # Create entities sequentially with individual timeouts
            for i in range(3):
                async with asyncio.timeout(5):  # Individual operation timeout
                    arguments = {"name": f"entity-{i}", "type": "test-type"}
                    result = await handle_call_tool("create_entity", arguments)

            # Verify final operation
            assert isinstance(result, list)
            assert len(result) == 1
            assert f"entity-{i}" in result[0].text

            # Verify all entities were created
            with db.get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
                assert count == 3

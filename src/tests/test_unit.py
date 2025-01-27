"""
Database-direct tests for unit functionality.
Uses direct database connections for testing without MCP client overhead.
"""

import asyncio
import sqlite3

import pytest
import pytest_asyncio
from mcp.shared.exceptions import McpError
from mcp.types import METHOD_NOT_FOUND
from pydantic import AnyUrl

from iac_memory_mcp_server.db.connection import DatabaseError, DatabaseManager
from iac_memory_mcp_server.resources import handle_list_resources, handle_read_resource
from iac_memory_mcp_server.shared import get_db
from iac_memory_mcp_server.tools import handle_call_tool

from .test_utils.base_utils import capture_taskgroup_errors
from .test_utils.db_utils import db_test_context
from .test_utils.exceptions import DatabaseTestError


# Test database setup
@pytest_asyncio.fixture
def test_db(tmp_path):
    """Create a test database"""
    test_db = tmp_path / "test.db"
    db = DatabaseManager.get_instance(str(test_db))
    db.reset_database()  # Ensure clean state with all tables
    yield db


@pytest.mark.asyncio
async def test_database_initialization(test_db):
    """Test database initialization and schema creation"""
    async with db_test_context(operation_name="db_init") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting database initialization test")

            try:
                # Configure and clean database
                with test_db.get_connection() as conn:
                    await ctx.info("Configuring database parameters")
                    # Set PRAGMAs before transaction
                    conn.execute("PRAGMA foreign_keys = ON")
                    conn.execute(
                        "PRAGMA journal_mode = DELETE"
                    )  # More reliable than WAL for tests
                    conn.execute("PRAGMA synchronous = FULL")  # Ensure data integrity

                    # VACUUM must be outside transaction and after PRAGMA changes
                    conn.execute("VACUUM")  # Clean up the database file
                    conn.commit()  # Ensure VACUUM completes
                    conn.execute("BEGIN IMMEDIATE")
                    try:

                        await ctx.info("Clearing database tables")
                        tables_to_clear = [
                            "entities",
                            "observations",
                            "entity_relationships",
                            "terraform_providers",
                            "terraform_resources",
                            "provider_resources",
                            "ansible_collections",
                            "ansible_modules",
                        ]
                        for table in tables_to_clear:
                            conn.execute(f"DELETE FROM {table}")

                        conn.commit()
                        await ctx.info("Database configuration completed")
                    except Exception as e:
                        conn.rollback()
                        await ctx.info(f"Database configuration failed: {str(e)}")
                        raise DatabaseTestError("Failed to configure database") from e

                # Verify database structure and connection pooling
                with (
                    test_db.get_connection() as conn1,
                    test_db.get_connection() as conn2,
                ):
                    await ctx.info(
                        "Verifying database structure and connection handling"
                    )

                    # Verify connections are different objects but share same pool
                    assert (
                        conn1 is not conn2
                    ), "Connection pooling not working - same connection returned"
                    assert (
                        conn1.row_factory == conn2.row_factory
                    ), "Connections have different row factories"

                    # Check tables exist
                    tables = conn1.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                    table_names = [t[0] for t in tables]

                    expected_tables = [
                        "terraform_providers",
                        "terraform_resources",
                        "provider_resources",
                        "ansible_collections",
                        "ansible_modules",
                        "entities",
                        "observations",
                        "entity_relationships",
                    ]

                    # Verify all expected tables exist and have correct structure
                    missing_tables = []
                    invalid_schemas = []
                    for table in expected_tables:
                        if table not in table_names:
                            missing_tables.append(table)
                            await ctx.info(f"Missing table: {table}")
                        else:
                            # Get table schema
                            schema = conn1.execute(
                                f"PRAGMA table_info({table})"
                            ).fetchall()
                            if not schema:
                                invalid_schemas.append(f"{table} (empty schema)")
                            # Verify primary key exists
                            if not any(
                                col[5] == 1 for col in schema
                            ):  # col[5] is pk flag
                                invalid_schemas.append(f"{table} (no primary key)")

                    assert (
                        not missing_tables
                    ), f"Missing tables: {', '.join(missing_tables)}"
                    assert (
                        not invalid_schemas
                    ), f"Invalid schemas: {', '.join(invalid_schemas)}"
                    await ctx.info("All expected tables present with valid schemas")

                # Verify table schemas
                with test_db.get_connection() as conn:
                    await ctx.info("Verifying table schemas")
                    test_queries = {
                        "terraform_providers": "SELECT id, name, version FROM terraform_providers LIMIT 1",
                        "terraform_resources": "SELECT id, provider_id, name FROM terraform_resources LIMIT 1",
                        "ansible_collections": "SELECT id, name, version FROM ansible_collections LIMIT 1",
                        "ansible_modules": "SELECT id, collection_id, name FROM ansible_modules LIMIT 1",
                    }

                    for table, query in test_queries.items():
                        try:
                            conn.execute(query)
                            await ctx.info(f"Verified schema for {table}")
                        except Exception as e:
                            await ctx.info(
                                f"Schema verification failed for {table}: {str(e)}"
                            )
                            raise DatabaseTestError(
                                f"Invalid schema for {table}"
                            ) from e

                await ctx.info("Database initialization test completed successfully")

            except Exception as e:
                await ctx.info(f"Database initialization test failed: {str(e)}")
                raise DatabaseTestError("Database initialization test failed") from e


@pytest.mark.asyncio
async def test_database_connection_context():
    """Test database connection context manager"""
    async with db_test_context(operation_name="db_connection") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting connection context test")

            try:
                await ctx.info("Initializing database instance")
                db = DatabaseManager.get_instance("test.db")
                db.reset_database()
                await ctx.info("Testing connection context and transaction handling")
                with db.get_connection() as conn1, db.get_connection() as conn2:
                    # Verify connection properties
                    for conn in [conn1, conn2]:
                        assert isinstance(
                            conn, sqlite3.Connection
                        ), "Connection not of correct type"
                        assert conn is not None, "Connection is None"
                        assert (
                            conn.isolation_level is not None
                        ), "Missing isolation level"

                    # Test transaction isolation
                    conn1.execute(
                        "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)"
                    )
                    conn1.execute("INSERT INTO test_table DEFAULT VALUES")

                    # Verify data not visible in concurrent connection
                    count = conn2.execute("SELECT COUNT(*) FROM test_table").fetchone()[
                        0
                    ]
                    assert (
                        count == 0
                    ), "Transaction isolation failed - data visible before commit"

                    # Test transaction rollback
                    conn1.rollback()
                    count = conn2.execute("SELECT COUNT(*) FROM test_table").fetchone()[
                        0
                    ]
                    assert count == 0, "Transaction rollback failed"

                    # Test successful commit
                    conn1.execute("INSERT INTO test_table DEFAULT VALUES")
                    conn1.commit()
                    count = conn2.execute("SELECT COUNT(*) FROM test_table").fetchone()[
                        0
                    ]
                    assert (
                        count == 1
                    ), "Transaction commit failed - data not visible after commit"
                await ctx.info("Verifying connection closure")
                with pytest.raises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")

                await ctx.info("Connection context test completed successfully")
            except Exception as e:
                await ctx.info(f"Connection test failed: {str(e)}")
                raise DatabaseTestError("Database connection test failed") from e


@pytest.mark.asyncio
async def test_database_error_handling(tmp_path):
    """Test database error handling"""
    async with db_test_context(operation_name="error_handling") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting database error handling test")

            try:
                await ctx.info("Setting up test database")
                test_db = tmp_path / "error_test.db"
                db = DatabaseManager.get_instance(str(test_db))
                db.reset_database()
                await ctx.info("Testing query error handling")
                with pytest.raises(DatabaseError) as exc_info:
                    db.execute_query("SELECT * FROM nonexistent_table")
                assert "no such table" in str(exc_info.value).lower()
                await ctx.info("Testing write error handling")
                with pytest.raises(DatabaseError) as exc_info:
                    db.execute_write(
                        "INSERT INTO nonexistent_table VALUES (?)", ("test",)
                    )
                assert "no such table" in str(exc_info.value).lower()

                await ctx.info("Error handling test completed successfully")
            except Exception as e:
                await ctx.info(f"Error handling test failed: {str(e)}")
                raise DatabaseTestError("Database error handling test failed") from e


@pytest_asyncio.fixture(autouse=True)
async def event_loop_fixture():
    """Ensure proper event loop cleanup for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    # Clean up the loop
    if not loop.is_closed():
        # Cancel all tasks
        tasks = asyncio.all_tasks(loop)
        if tasks:
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        # Close the loop
        loop.close()
    asyncio.set_event_loop(None)


@pytest.mark.asyncio
async def test_list_resources_handler(event_loop_fixture):
    """Test list_resources handler returns proper IaC resources"""
    async with db_test_context(operation_name="list_resources") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting list resources test")

            # Add test provider and resource
            db = DatabaseManager.get_instance()
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )
            db.add_terraform_resource(
                provider_id,
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )

            # Add test collection and module
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )
            db.add_ansible_module(
                collection_id,
                "ec2_instance",
                "cloud",
                '{"type": "object"}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html",
            )

            # Test default pagination
            resources = await handle_list_resources(ctx)

            # Verify result format
            assert isinstance(resources, list), "Result should be a list"
            # Filter out template resources
            concrete_resources = [r for r in resources if "{" not in str(r.uri) and "}" not in str(r.uri)]
            assert len(concrete_resources) > 0, "Should have concrete resources"

            # Test custom pagination
            paginated = await handle_list_resources(ctx, page=1, per_page=2)
            # Filter out template resources from paginated results
            concrete_paginated = [r for r in paginated if "{" not in str(r.uri) and "}" not in str(r.uri)]
            assert len(concrete_paginated) <= 2, "Should respect per_page limit"

            # Verify resource format
            for resource in resources:
                assert hasattr(resource, "uri")
                assert hasattr(resource, "name")
                uri = str(resource.uri)
                # Skip template URIs that contain variable placeholders
                if "{" in uri or "}" in uri:
                    continue
                # Check that concrete resource URIs use proper scheme
                assert uri.startswith(
                    (
                        "resources://terraform/",
                        "resources://ansible/",
                        "resources://entities/",
                    )
                ), f"Invalid URI scheme: {uri}"

            # Verify specific resources
            terraform_resources = [
                r
                for r in resources
                if str(r.uri).startswith("resources://terraform/") and "{" not in str(r.uri)
            ]
            ansible_resources = [
                r
                for r in resources
                if str(r.uri).startswith("resources://ansible/") and "{" not in str(r.uri)
            ]

            assert len(terraform_resources) > 0, "No Terraform resources found"
            assert len(ansible_resources) > 0, "No Ansible resources found"

            # Verify resource content
            aws_instance = next(
                (r for r in terraform_resources if "aws_instance" in str(r.uri)), None
            )
            assert aws_instance is not None, "AWS instance resource not found"
            assert aws_instance.name == "instance"

            ec2_module = next(
                (r for r in ansible_resources if "ec2_instance" in str(r.uri)), None
            )
            assert ec2_module is not None, "EC2 module resource not found"
            assert ec2_module.name == "ec2_instance"

            await ctx.info("List resources test completed")


@pytest.mark.asyncio
async def test_read_resource_handler(db):
    """Test read_resource handler for IaC resources"""
    async with db_test_context(operation_name="read_resource") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting read resource test")

            # Add test provider and resource
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )
            db.add_terraform_resource(
                provider_id,
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )

            # Add test collection and module
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )
            db.add_ansible_module(
                collection_id,
                "ec2_instance",
                "cloud",
                '{"type": "object"}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html",
            )

            # Test reading Terraform resource with legacy URI
            await ctx.info("Testing Terraform resource reading with legacy URI")
            terraform_uri = AnyUrl("terraform://aws/aws_instance")
            terraform_content = await handle_read_resource(terraform_uri)
            assert "aws_instance" in terraform_content
            assert "4.0.0" in terraform_content

            # Test reading Terraform resource with hierarchical URI
            await ctx.info("Testing Terraform resource reading with hierarchical URI")
            terraform_hier_uri = AnyUrl(
                "resources://terraform/resources/aws/aws_instance"
            )
            terraform_hier_content = await handle_read_resource(terraform_hier_uri)
            assert "aws_instance" in terraform_hier_content
            assert "4.0.0" in terraform_hier_content

            # Test reading Ansible module with legacy URI
            await ctx.info("Testing Ansible module reading with legacy URI")
            ansible_uri = AnyUrl("ansible://community.aws/ec2_instance")
            ansible_content = await handle_read_resource(ansible_uri)
            assert "ec2_instance" in ansible_content
            assert "3.0.0" in ansible_content

            # Test reading Ansible module with hierarchical URI
            await ctx.info("Testing Ansible module reading with hierarchical URI")
            ansible_hier_uri = AnyUrl(
                "resources://ansible/modules/community.aws/ec2_instance"
            )
            ansible_hier_content = await handle_read_resource(ansible_hier_uri)
            assert "ec2_instance" in ansible_hier_content
            assert "3.0.0" in ansible_hier_content

            # Test invalid legacy resource
            await ctx.info("Testing nonexistent legacy resource handling")
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource("terraform://nonexistent/resource")
            assert exc_info.value.error.code == METHOD_NOT_FOUND
            assert "Resource not found" in exc_info.value.error.message

            # Test invalid hierarchical format
            await ctx.info("Testing invalid hierarchical format")
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource("resources://invalid")
            assert exc_info.value.error.code == METHOD_NOT_FOUND
            assert "Invalid resource path" in exc_info.value.error.message

            # Test invalid resource type in hierarchical URI
            await ctx.info("Testing invalid resource type in hierarchical URI")
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource("resources://unknown/category/name")
            assert exc_info.value.error.code == METHOD_NOT_FOUND
            assert "Unsupported resource type" in exc_info.value.error.message

            # Test invalid resource
            await ctx.info("Testing nonexistent resource handling")
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource("resource://internal/nonexistent")
            assert exc_info.value.error.code == METHOD_NOT_FOUND, "Wrong error code"
            assert (
                "Resource not found" in exc_info.value.error.message
            ), "Wrong error message"

            await ctx.info("Read resource test completed")


@pytest.mark.asyncio
async def test_create_entity_tool():
    """Test create-entity tool handler"""
    async with db_test_context(operation_name="create_entity") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting create entity test")

            # Reset database first
            db = get_db()
            db.reset_database()
            with db.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute("DELETE FROM entities")
                    conn.execute("DELETE FROM observations")
                    conn.execute("DELETE FROM sqlite_sequence")
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

        try:
            # Test entity creation
            arguments = {
                "name": "test-entity",
                "type": "test-type",
                "observation": "Initial test observation",
            }

            await ctx.info("Creating test entity")
            result = await handle_call_tool("create_entity", arguments)
            # Verify result format
            await ctx.info("Verifying result format")
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 1, "Expected single result item"
            assert "Created entity 'test-entity'" in result[0].text, "Incorrect result message"

            # Verify database state, constraints and referential integrity
            await ctx.info("Verifying database state and constraints")
            with db.get_connection() as conn:
                # Enable foreign key checks
                conn.execute("PRAGMA foreign_keys = ON")

                # Verify entity and timestamps
                entity = conn.execute(
                    """SELECT id, name, type, created_at, updated_at 
                    FROM entities WHERE name = ?""",
                    ("test-entity",),
                ).fetchone()

                # Verify created_at and updated_at are within last 5 seconds
                from datetime import datetime, timedelta

                now = datetime.now()
                created_at = datetime.fromisoformat(entity[3])
                updated_at = datetime.fromisoformat(entity[4])
                assert now - created_at < timedelta(
                    seconds=5
                ), "Created timestamp too old"
                assert now - updated_at < timedelta(
                    seconds=5
                ), "Updated timestamp too old"

                assert entity is not None, "Entity not found in database"
                assert entity[1] == "test-entity", "Incorrect entity name"
                assert entity[2] == "test-type", "Incorrect entity type"
                assert entity[3] is not None, "Missing created_at timestamp"
                assert entity[4] is not None, "Missing updated_at timestamp"

                entity_id = entity[0]

                # Verify observation
                observation = conn.execute(
                    """SELECT content, created_at 
                    FROM observations 
                    WHERE entity_id = ?""",
                    (entity_id,),
                ).fetchone()

                assert observation is not None, "Observation not found"
                assert (
                    observation[0] == "Initial test observation"
                ), "Incorrect observation content"
                assert observation[1] is not None, "Missing observation timestamp"

            await ctx.info("Entity creation test completed successfully")

        except AssertionError as e:
            await ctx.info(f"Verification failed: {str(e)}")
            raise DatabaseTestError(f"Entity verification failed: {str(e)}") from e
        except Exception as e:
            await ctx.info(f"Unexpected error in entity creation test: {str(e)}")
            raise DatabaseTestError("Entity creation test failed") from e


@pytest.mark.asyncio
async def test_ansible_module_tools():
    """Test Ansible module-related tools."""
    async with db_test_context(operation_name="ansible_module_tools") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting Ansible module tools test")

            try:
                # Setup test data
                db = get_db()
                db.reset_database()

                # Add test collection
                collection_result = await handle_call_tool(
                    "add_ansible_collection",
                    {
                        "name": "test.collection",
                        "version": "1.0.0",
                        "source_url": "https://github.com/test/collection",
                        "doc_url": "https://docs.test/collection",
                    },
                )
                collection_id = collection_result[0].text.split("ID: ")[1]

                # Add test modules
                await handle_call_tool(
                    "add_ansible_module",
                    {
                        "collection": collection_id,
                        "name": "test_module1",
                        "module_type": "cloud",
                        "schema": '{"type": "object", "required": ["param1"], "properties": {"param1": {"type": "string"}}}',
                        "version": "1.0.0",
                        "doc_url": "https://docs.test/collection/module1",
                    },
                )
                await handle_call_tool(
                    "add_ansible_module",
                    {
                        "collection": collection_id,
                        "name": "test_module2",
                        "module_type": "network",
                        "schema": '{"type": "object", "properties": {"param2": {"type": "string"}}}',
                        "version": "1.0.0",
                        "doc_url": "https://docs.test/collection/module2",
                    },
                )

                # Test list_collection_modules
                await ctx.info("Testing list_collection_modules")
                list_result = await handle_call_tool(
                    "list_collection_modules",
                    {"collection_name": "test.collection"}
                )
                assert isinstance(list_result, list), "Result should be a list"
                assert len(list_result) == 1, "Should have one result message"
                assert "test_module1" in list_result[0].text
                assert "test_module2" in list_result[0].text

                # Test filtering by module type
                filter_result = await handle_call_tool(
                    "list_collection_modules",
                    {
                        "collection_name": "test.collection",
                        "filter_criteria": {"type_pattern": "^cloud$"}
                    }
                )
                assert isinstance(filter_result, list), "Result should be a list"
                assert len(filter_result) == 1, "Should have one result message"
                assert "test_module1" in filter_result[0].text
                assert "test_module2" not in filter_result[0].text

                # Add newer version of module with breaking changes
                await handle_call_tool(
                    "add_ansible_module",
                    {
                        "collection": collection_id,
                        "name": "test_module1",
                        "module_type": "cloud",
                        "schema": '{"type": "object", "required": ["param1", "param2"], "properties": {"param1": {"type": "string"}, "param2": {"type": "string"}}}',
                        "version": "2.0.0",
                        "doc_url": "https://docs.test/collection/module1",
                    },
                )

                # Test get_module_version_compatibility
                await ctx.info("Testing get_module_version_compatibility")
                compat_result = await handle_call_tool(
                    "get_module_version_compatibility",
                    {
                        "collection_name": "test.collection",
                        "module_name": "test_module1",
                        "version": "1.0.0"
                    }
                )
                assert isinstance(compat_result, list), "Result should be a list"
                assert len(compat_result) == 1, "Should have one result message"
                assert "Breaking Changes:" in compat_result[0].text
                assert "Required fields" in compat_result[0].text
                assert "param2" in compat_result[0].text

                # Test with nonexistent module
                invalid_result = await handle_call_tool(
                    "get_module_version_compatibility",
                    {
                        "collection_name": "test.collection",
                        "module_name": "nonexistent",
                        "version": "1.0.0"
                    }
                )
                assert isinstance(invalid_result, list), "Result should be a list"
                assert len(invalid_result) == 1, "Should have one error message"
                assert "not found" in invalid_result[0].text.lower()

                await ctx.info("Ansible module tools test completed successfully")

            except Exception as e:
                await ctx.info(f"Ansible module tools test failed: {str(e)}")
                raise DatabaseTestError("Ansible module tools test failed") from e


@pytest.mark.asyncio
async def test_tool_error_handling():
    """Test error handling in tool handlers"""
    async with db_test_context(operation_name="error_handling") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting error handling test")

            try:
                # Test missing arguments for Terraform provider
                await ctx.info("Testing missing provider arguments")
                result = await handle_call_tool("add_terraform_provider", {})
                assert isinstance(result, list), "Result should be a list"
                assert len(result) == 1, "Should have one error message"
                assert "Missing required arguments" in result[0].text

                # Test missing arguments for Ansible collection
                await ctx.info("Testing missing collection arguments")
                result = await handle_call_tool("add_ansible_collection", {})
                assert isinstance(result, list), "Result should be a list"
                assert len(result) == 1, "Should have one error message"
                assert "Missing required arguments" in result[0].text

                # Test invalid provider version format
                await ctx.info("Testing invalid provider version")
                result = await handle_call_tool(
                    "add_terraform_provider",
                    {
                        "name": "test",
                        "version": "invalid",
                        "source_url": "https://test.com",
                        "doc_url": "https://test.com/docs",
                    },
                )
                assert isinstance(result, list), "Result should be a list"
                assert len(result) == 1, "Should have one error message"
                assert "Invalid version format" in result[0].text

                # Test invalid resource schema
                await ctx.info("Testing invalid resource schema")
                # First create a provider
                provider_result = await handle_call_tool(
                    "add_terraform_provider",
                    {
                        "name": "test",
                        "version": "1.0.0",
                        "source_url": "https://test.com",
                        "doc_url": "https://test.com/docs",
                    },
                )
                provider_id = provider_result[0].text.split("ID: ")[1]

                result = await handle_call_tool(
                    "add_terraform_resource",
                    {
                        "provider": provider_id,
                        "name": "test_resource",
                        "resource_type": "test_type",
                        "schema": "invalid_json",
                        "version": "1.0.0",
                        "doc_url": "https://test.com/docs",
                    },
                )
                assert isinstance(result, list), "Result should be a list"
                assert len(result) == 1, "Should have one error message"
                assert "Invalid schema format" in result[0].text

                # First create a collection
                await ctx.info("Creating test collection")
                collection_result = await handle_call_tool(
                    "add_ansible_collection",
                    {
                        "name": "test_collection",
                        "version": "1.0.0",
                        "source_url": "https://test.com",
                        "doc_url": "https://test.com/docs",
                    },
                )
                collection_id = collection_result[0].text.split("ID: ")[1]

                # Test invalid module type
                await ctx.info("Testing invalid module type")
                result = await handle_call_tool(
                    "add_ansible_module",
                    {
                        "collection": collection_id,
                        "name": "test_module",
                        "module_type": "invalid_type",
                        "schema": "{}",
                        "version": "1.0.0",
                        "doc_url": "https://test.com/docs",
                    },
                )
                assert isinstance(result, list), "Result should be a list"
                assert len(result) == 1, "Should have one error message"
                assert "Invalid module type" in result[0].text

                await ctx.info("Error handling test completed successfully")

            except Exception as e:
                await ctx.info(f"Error handling test failed: {str(e)}")
                raise DatabaseTestError("Tool error handling test failed") from e

            # Verify database cleanup after errors
            db = get_db()
            with db.get_connection() as conn:
                # Check all tables are empty
                tables = ["entities", "observations", "entity_relationships"]
                for table in tables:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    assert count == 0, f"Table {table} not empty after error test"
                await ctx.info("Database cleanup verified")

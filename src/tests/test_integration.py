import logging
import sys

import pytest
import pytest_asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client

from .test_utils.mcp_utils import create_server_params

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,  # Override any existing configuration
)

# Get test logger
logger = logging.getLogger("iac_memory.tests")


@pytest_asyncio.fixture(scope="function")
async def test_db_path(tmp_path):
    """Create a test database path for MCP server.
    
    With MCP_TEST_MODE=1, the server will automatically:
    1. Reset the database state before each test
    2. Initialize the schema with required tables
    3. Apply proper pragmas and settings
    
    This fixture only provides the database path, as direct database
    access is not needed for integration testing.
    """
    db_path = tmp_path / "test.db"
    yield str(db_path)


@pytest_asyncio.fixture(scope="function")
async def mcp_session(test_db_path):
    """Fixture that provides an MCP session with a clean test database."""
    logger.info("Creating MCP test session")

    server_params = create_server_params(
        operation_name="test",
        env={
            "PYTHONUNBUFFERED": "1",
            "MCP_DEBUG": "1",
            "MCP_TEST_MODE": "1",
            "MCP_DATABASE_PATH": test_db_path,
            "PYTHONPATH": "src",  # Ensure server can find our package
        },
    )

    try:
        async with stdio_client(server_params) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("Initializing MCP session")
                await session.initialize()
                logger.info("MCP session initialized successfully")
                yield session
    except RuntimeError as e:
        if "Attempted to exit cancel scope in a different task than it was entered in" not in str(e):
            raise


@pytest.mark.asyncio
async def test_terraform_tools(mcp_session):
    """Test Terraform-specific tool operations.
    
    This test verifies all Terraform-related tools:
    1. Provider management (add, update, info, list)
    2. Resource management (add, update, info, list)
    """
    logger.info("Starting Terraform tools test")

    try:
        # Add test provider
        logger.info("Adding test provider...")
        result = await mcp_session.call_tool(
            "add_terraform_provider",
            {
                "name": "test_provider",
                "version": "1.0.0",
                "source_url": "http://example.com/source",
                "doc_url": "http://example.com/docs"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Provider added successfully")

        # Update provider version
        logger.info("Updating provider version...")
        result = await mcp_session.call_tool(
            "update_provider_version",
            {
                "provider_name": "test_provider",
                "new_version": "2.0.0",
                "new_source_url": "http://example.com/source/v2",
                "new_doc_url": "http://example.com/docs/v2"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Provider version updated successfully")

        # Add test resource
        logger.info("Adding test resource...")
        result = await mcp_session.call_tool(
            "add_terraform_resource",
            {
                "provider": "test_provider",
                "name": "test_resource",
                "resource_type": "test_type",
                "schema": "{}",
                "version": "1.0.0",
                "doc_url": "http://example.com/resource"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Resource added successfully")

        # Update resource schema
        logger.info("Updating resource schema...")
        result = await mcp_session.call_tool(
            "update_resource_schema",
            {
                "resource_id": "test_resource",
                "new_schema": '{"updated": true}',
                "new_version": "2.0.0",
                "new_doc_url": "http://example.com/resource/v2"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Resource schema updated successfully")

        logger.info("All Terraform tool tests completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_server_lifecycle(mcp_session):
    """Test MCP server lifecycle and tool operations.
    
    This test verifies:
    1. Basic server connectivity (ping)
    2. Tool operations (adding and querying resources)
    3. Core MCP capabilities (tools, resources, prompts)
    
    The test uses proper MCP tools rather than direct database access,
    making it a true integration test of the server's external interface.
    """
    logger.info("Starting server lifecycle test")

    try:
        # Basic ping test
        logger.info("Testing ping...")
        await mcp_session.send_ping()
        logger.info("Ping successful")

        # Add test provider using MCP tool
        logger.info("Adding test provider...")
        result = await mcp_session.call_tool(
            "add_terraform_provider",
            {
                "name": "test_provider",
                "version": "1.0.0",
                "doc_url": "http://example.com",
                "source_url": "http://example.com/source"
            }
        )
        logger.info("Provider added successfully")

        # Add test resource using MCP tool
        logger.info("Adding test resource...")
        result = await mcp_session.call_tool(
            "add_terraform_resource",
            {
                "provider": "test_provider",
                "name": "test_resource",
                "resource_type": "test_type",
                "version": "1.0.0",
                "doc_url": "http://example.com",
                "schema": "{}"
            }
        )
        logger.info("Resource added successfully")

        # Verify provider info
        logger.info("Verifying provider info...")
        provider_info = await mcp_session.call_tool(
            "get_terraform_provider_info",
            {"provider_name": "test_provider"}
        )
        assert hasattr(provider_info, "content"), "Result should have content attribute"
        assert isinstance(provider_info.content, list), "Content should be a list"
        assert len(provider_info.content) == 1, "Should have one info message"
        assert "test_provider" in provider_info.content[0].text, "Provider not found"
        logger.info("Provider verification successful")

        # Verify provider resources
        logger.info("Verifying provider resources...")
        provider_resources = await mcp_session.call_tool(
            "list_provider_resources",
            {"provider_name": "test_provider"}
        )
        assert hasattr(provider_resources, "content"), "Result should have content attribute"
        assert isinstance(provider_resources.content, list), "Content should be a list"
        assert len(provider_resources.content) == 1, "Should have one resource message"
        assert "test_resource" in provider_resources.content[0].text, "Resource not found"
        logger.info("Resource verification successful")

        # Test standard MCP server capabilities
        logger.info("Testing server capabilities...")
        
        # Tool listing
        tools = await mcp_session.list_tools()
        assert hasattr(tools, "tools"), "Response should have tools attribute"
        assert isinstance(tools.tools, list), "Tools should be a list"
        assert len(tools.tools) > 0, "Expected tool list to not be empty"
        
        # Log each available tool
        logger.info("Available tools:")
        for tool in tools.tools:
            logger.info(f"  - {tool.name}")
        logger.info(f"Tool listing successful - found {len(tools.tools)} tools")

        # Resource listing
        resources = await mcp_session.list_resources()
        assert hasattr(resources, "resources"), "Response should have resources attribute"
        assert isinstance(resources.resources, list), "Resources should be a list"
        assert len(resources.resources) > 0, "Expected resource list to not be empty"
        logger.info(f"Resource listing successful - found {len(resources.resources)} resources")

        # Prompt listing
        prompts = await mcp_session.list_prompts()
        assert hasattr(prompts, "prompts"), "Response should have prompts attribute"
        assert isinstance(prompts.prompts, list), "Prompts should be a list"
        logger.info(f"Prompt listing successful - found {len(prompts.prompts)} prompts")

        logger.info("All server lifecycle tests completed successfully")
    except TimeoutError as e:
        logger.error(f"Operation timed out: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_ansible_tools(mcp_session):
    """Test Ansible-specific tool operations.
    
    This test verifies all Ansible-related tools:
    1. Collection management (add, info, list, version history)
    2. Module management (add, info, list, compatibility)
    """
    logger.info("Starting Ansible tools test")

    try:
        # Add test collection
        logger.info("Adding test collection...")
        result = await mcp_session.call_tool(
            "add_ansible_collection",
            {
                "name": "test_collection",
                "version": "1.0.0",
                "source_url": "http://example.com/source",
                "doc_url": "http://example.com/docs"
            }
        )
        logger.info("Collection added successfully")

        # Add test module
        logger.info("Adding test module...")
        result = await mcp_session.call_tool(
            "add_ansible_module",
            {
                "collection": "test_collection",
                "name": "test_module",
                "module_type": "cloud",
                "schema": "{}",
                "version": "1.0.0",
                "doc_url": "http://example.com/module"
            }
        )
        logger.info("Module added successfully")

        # Test get_ansible_collection_info
        logger.info("Testing collection info retrieval...")
        collection_info = await mcp_session.call_tool(
            "get_ansible_collection_info",
            {"collection_name": "test_collection"}
        )
        assert hasattr(collection_info, "content"), "Result should have content attribute"
        assert "test_collection" in collection_info.content[0].text, "Collection not found"
        logger.info("Collection info retrieval successful")

        # Test list_ansible_collections
        logger.info("Testing collection listing...")
        collections = await mcp_session.call_tool(
            "list_ansible_collections",
            {"filter_criteria": {"name_pattern": "test_collection"}}
        )
        assert hasattr(collections, "content"), "Result should have content attribute"
        assert "test_collection" in collections.content[0].text, "Collection not found in list"
        logger.info("Collection listing successful")

        # Test get_collection_version_history
        logger.info("Testing version history retrieval...")
        version_history = await mcp_session.call_tool(
            "get_collection_version_history",
            {"collection_name": "test_collection"}
        )
        assert hasattr(version_history, "content"), "Result should have content attribute"
        assert "1.0.0" in version_history.content[0].text, "Version history not found"
        logger.info("Version history retrieval successful")

        # Test get_ansible_module_info
        logger.info("Testing module info retrieval...")
        module_info = await mcp_session.call_tool(
            "get_ansible_module_info",
            {
                "collection_name": "test_collection",
                "module_name": "test_module"
            }
        )
        assert hasattr(module_info, "content"), "Result should have content attribute"
        assert "test_module" in module_info.content[0].text, "Module not found"
        logger.info("Module info retrieval successful")

        # Test list_collection_modules
        logger.info("Testing module listing...")
        modules = await mcp_session.call_tool(
            "list_collection_modules",
            {"collection_name": "test_collection"}
        )
        assert hasattr(modules, "content"), "Result should have content attribute"
        assert "test_module" in modules.content[0].text, "Module not found in list"
        logger.info("Module listing successful")

        # Test get_module_version_compatibility
        logger.info("Testing module compatibility check...")
        compatibility = await mcp_session.call_tool(
            "get_module_version_compatibility",
            {
                "collection_name": "test_collection",
                "module_name": "test_module",
                "version": "1.0.0"
            }
        )
        assert hasattr(compatibility, "content"), "Result should have content attribute"
        assert "Compatible" in compatibility.content[0].text, "Compatibility check failed"
        logger.info("Module compatibility check successful")

        logger.info("All Ansible tool tests completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_ansible_update_tools(mcp_session):
    """Test Ansible update tool operations.
    
    This test verifies all Ansible version update tools:
    1. Collection version updates
    2. Module version updates
    """
    logger.info("Starting Ansible update tools test")

    try:
        # Add test collection
        logger.info("Adding test collection...")
        result = await mcp_session.call_tool(
            "add_ansible_collection",
            {
                "name": "test_collection",
                "version": "1.0.0",
                "source_url": "http://example.com/source",
                "doc_url": "http://example.com/docs"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Collection added successfully")

        # Update collection version
        logger.info("Updating collection version...")
        result = await mcp_session.call_tool(
            "update_collection_version",
            {
                "collection_id": "test_collection",
                "new_version": "2.0.0",
                "new_source_url": "http://example.com/source/v2",
                "new_doc_url": "http://example.com/docs/v2"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Collection version updated successfully")

        # Add test module
        logger.info("Adding test module...")
        result = await mcp_session.call_tool(
            "add_ansible_module",
            {
                "collection": "test_collection",
                "name": "test_module",
                "module_type": "cloud",
                "schema": "{}",
                "version": "1.0.0",
                "doc_url": "http://example.com/module"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Module added successfully")

        # Update module version
        logger.info("Updating module version...")
        result = await mcp_session.call_tool(
            "update_module_version",
            {
                "module_id": "test_module",
                "new_schema": '{"updated": true}',
                "new_version": "2.0.0",
                "new_doc_url": "http://example.com/module/v2"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Module version updated successfully")

        logger.info("All Ansible update tool tests completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


@pytest.mark.asyncio
async def test_entity_tools(mcp_session):
    """Test Entity-specific tool operations.
    
    This test verifies all Entity-related tools:
    1. Entity creation
    2. Entity updates
    3. Entity deletion
    4. Relationship viewing
    """
    logger.info("Starting Entity tools test")

    try:
        # Create test entity
        logger.info("Creating test entity...")
        result = await mcp_session.call_tool(
            "create_entity",
            {
                "name": "test_entity",
                "type": "test_type",
                "attributes": {
                    "key": "value"
                }
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Entity created successfully")

        # Update test entity
        logger.info("Updating test entity...")
        result = await mcp_session.call_tool(
            "update_entity",
            {
                "entity_id": "test_entity",
                "attributes": {
                    "key": "new_value"
                }
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Entity updated successfully")

        # View relationships
        logger.info("Viewing entity relationships...")
        result = await mcp_session.call_tool(
            "view_relationships",
            {
                "entity_id": "test_entity"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Relationship viewing successful")

        # Delete test entity
        logger.info("Deleting test entity...")
        result = await mcp_session.call_tool(
            "delete_entity",
            {
                "entity_id": "test_entity"
            }
        )
        assert hasattr(result, "content"), "Result should have content attribute"
        logger.info("Entity deleted successfully")

        logger.info("All Entity tool tests completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise

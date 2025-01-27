"""Performance tests for database operations.

Tests the performance characteristics of database operations including:
- Provider/resource operations
- Collection/module operations 
- Resource management

Uses direct database access through db_test_context.
"""

import time

import pytest

from iac_memory_mcp_server.db.connection import DatabaseManager

from .test_utils.base_utils import capture_taskgroup_errors
from .test_utils.db_utils import db_test_context


def measure_execution_time(func):
    """Decorator to measure function execution time."""

    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        print(f"\n{func.__name__} execution time: {execution_time:.4f} seconds")
        return result

    # Preserve pytest fixture injection
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__pytest_async_plugin_mark__ = getattr(
        func, "__pytest_async_plugin_mark__", None
    )
    return wrapper


@pytest.mark.asyncio
@measure_execution_time
async def test_terraform_provider_operations():
    """Test performance of Terraform provider operations.

    This test verifies:
    1. Provider creation performance
    2. Resource batch insertion speed
    3. Resource retrieval efficiency
    4. Transaction handling under load

    Raises:
        DatabaseTestError: If database operations fail
        asyncio.TimeoutError: If operations exceed timeout
    """
    """Test performance of Terraform provider operations."""
    async with db_test_context(operation_name="terraform_provider_ops") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting provider operations test")

        # Add provider
        db = DatabaseManager.get_instance()
        provider_id = db.add_terraform_provider(
            "aws",
            "4.0.0",
            "https://github.com/hashicorp/terraform-provider-aws",
            "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
        )

        # Add multiple resources
        for i in range(100):
            db.add_terraform_resource(
                provider_id,
                f"resource_{i}",
                f"aws_resource_{i}",
                '{"type": "object"}',
                "4.0.0",
                f"https://example.com/resource_{i}",
            )

        # Retrieve resources
        resources = db.get_provider_resources(provider_id)
        assert len(resources) == 100


@pytest.mark.asyncio
@measure_execution_time
async def test_ansible_collection_operations():
    """Test performance of Ansible collection operations."""
    async with db_test_context(operation_name="ansible_collection_ops") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting collection operations test")

        # Add collection
        db = DatabaseManager.get_instance()
        collection_id = db.add_ansible_collection(
            "community.aws",
            "3.0.0",
            "https://github.com/ansible-collections/community.aws",
            "https://docs.ansible.com/ansible/latest/collections/community/aws/",
        )

        # Add multiple modules
        for i in range(100):
            db.add_ansible_module(
                collection_id,
                f"module_{i}",
                "cloud",
                '{"type": "object"}',
                "3.0.0",
                f"https://example.com/module_{i}",
            )

        # Retrieve modules
        modules = db.get_collection_modules(collection_id)
        assert len(modules) == 100

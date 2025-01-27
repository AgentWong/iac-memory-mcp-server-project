"""Database method tests using direct database access.

Tests the core database operations including:
- Provider management
- Resource tracking
- Collection handling
- Module operations

Uses db_test_context for direct database testing without MCP overhead.
"""

import pytest

from .test_utils import capture_taskgroup_errors, db_test_context


# Terraform Provider Tests
@pytest.mark.asyncio
async def test_add_terraform_provider(db):
    """Test adding a new Terraform provider."""
    async with db_test_context(operation_name="add_provider") as _:
        async with capture_taskgroup_errors():
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )
            assert provider_id is not None

            # Verify provider was added
            with db.get_connection() as conn:
                provider = conn.execute(
                    "SELECT * FROM terraform_providers WHERE id = ?", (provider_id,)
                ).fetchone()
                assert provider["name"] == "aws"
                assert provider["version"] == "4.0.0"


@pytest.mark.asyncio
async def test_get_provider_resources(db):
    """Test retrieving resources for a provider."""
    async with db_test_context(operation_name="get_provider_resources") as _:
        async with capture_taskgroup_errors():
            # Add provider
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )

    # Add some resources
    db.add_terraform_resource(
        provider_id,
        "instance",
        "aws_instance",
        '{"type": "object"}',
        "4.0.0",
        "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
    )

    resources = db.get_provider_resources(provider_id)
    assert len(resources) == 1
    assert resources[0]["name"] == "instance"
    assert resources[0]["provider_name"] == "aws"


@pytest.mark.asyncio
async def test_update_provider_version(db):
    """Test updating a provider's version."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )

            # Update version
            success = db.update_provider_version(
                provider_id,
                "4.1.0",
                new_doc_url="https://registry.terraform.io/providers/hashicorp/aws/4.1.0/docs",
            )
            assert success is True

            with db.get_connection() as conn:
                provider = conn.execute(
                    "SELECT * FROM terraform_providers WHERE id = ?", (provider_id,)
                ).fetchone()
                assert provider["version"] == "4.1.0"


# Terraform Resource Tests
@pytest.mark.asyncio
async def test_add_terraform_resource(db):
    """Test adding a new Terraform resource."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )

            resource_id = db.add_terraform_resource(
                provider_id,
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )
            assert resource_id is not None

            # Verify resource was added
            with db.get_connection() as conn:
                resource = conn.execute(
                    "SELECT * FROM terraform_resources WHERE id = ?", (resource_id,)
                ).fetchone()
                assert resource["name"] == "instance"
                assert resource["resource_type"] == "aws_instance"  # Use column name


@pytest.mark.asyncio
async def test_get_resource_info(db):
    """Test retrieving resource information."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )

            resource_id = db.add_terraform_resource(
                provider_id,
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )

            info = db.get_resource_info(resource_id)
            assert info is not None
            assert info["name"] == "instance"
            assert info["provider_name"] == "aws"
            assert info["provider_version"] == "4.0.0"


@pytest.mark.asyncio
async def test_update_resource_schema(db):
    """Test updating a resource's schema."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )

            resource_id = db.add_terraform_resource(
                provider_id,
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )

            # Update schema
            new_schema = '{"type": "object", "properties": {"instance_type": {"type": "string"}}}'
            success = db.update_resource_schema(
                resource_id, new_schema, new_version="4.1.0"
            )
            assert success is True

            info = db.get_resource_info(resource_id)
            assert info["schema"] == new_schema
            assert info["version"] == "4.1.0"


# Ansible Collection Tests
@pytest.mark.asyncio
async def test_add_ansible_collection(db):
    """Test adding a new Ansible collection."""
    async with db_test_context(operation_name="add_collection") as _:  # noqa: F841
        async with capture_taskgroup_errors():
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )
            assert collection_id is not None

            # Verify collection was added
            with db.get_connection() as conn:
                collection = conn.execute(
                    "SELECT * FROM ansible_collections WHERE id = ?", (collection_id,)
                ).fetchone()
                assert collection["name"] == "community.aws"
                assert collection["version"] == "3.0.0"


@pytest.mark.asyncio
async def test_get_collection_modules(db):
    """Test retrieving modules for a collection."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )

            # Add a module
            db.add_ansible_module(
                collection_id,
                "ec2_instance",
                "cloud",  # Type should be a category like "cloud", not a description
                '{"instance_type": {"type": "string"}}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html",
            )

            modules = db.get_collection_modules(collection_id)
            assert len(modules) == 1
            assert modules[0]["name"] == "ec2_instance"
            assert modules[0]["collection_name"] == "community.aws"


@pytest.mark.asyncio
async def test_update_collection_version(db):
    """Test updating a collection's version."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )

            # Update version
            success = db.update_collection_version(
                collection_id,
                "3.1.0",
                new_doc_url="https://docs.ansible.com/ansible/3.1.0/collections/community/aws/",
            )
            assert success is True

            with db.get_connection() as conn:
                collection = conn.execute(
                    "SELECT * FROM ansible_collections WHERE id = ?", (collection_id,)
                ).fetchone()
                assert collection["version"] == "3.1.0"


# Ansible Module Tests
@pytest.mark.asyncio
async def test_add_ansible_module(db):
    """Test adding a new Ansible module."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )

            module_id = db.add_ansible_module(
                collection_id,
                "ec2_instance",
                "Manages EC2 instances",
                '{"instance_type": {"type": "string"}}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html",
            )
            assert module_id is not None

            # Verify module was added
            with db.get_connection() as conn:
                module = conn.execute(
                    "SELECT * FROM ansible_modules WHERE id = ?", (module_id,)
                ).fetchone()
                assert module["name"] == "ec2_instance"
                assert module["description"] == "Manages EC2 instances"


@pytest.mark.asyncio
async def test_get_module_info(db):
    """Test retrieving module information."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            collection_id = db.add_ansible_collection(
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )

            module_id = db.add_ansible_module(
                collection_id,
                "ec2_instance",
                "Manages EC2 instances",
                '{"type": "object"}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html",
            )

            info = db.get_module_info(module_id)
            assert info is not None
            assert info["name"] == "ec2_instance"
            assert info["collection_name"] == "community.aws"
            assert info["collection_version"] == "3.0.0"


@pytest.mark.asyncio
async def test_add_ansible_module_by_name(db):
    """Test adding Ansible modules using collection name."""
    async with db_test_context() as _:
        async with capture_taskgroup_errors():
            # First add a collection
            collection_id = db.add_ansible_collection(  # noqa: F841
                "community.aws",
                "3.0.0",
                "https://github.com/ansible-collections/community.aws",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/",
            )

            # Add module using collection name
            module_id = db.add_ansible_module(
                "community.aws",  # Using name instead of ID
                "s3_bucket",
                "cloud",
                '{"bucket": {"type": "string"}}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/s3_bucket_module.html",
            )
            assert module_id is not None

            # Verify module was added correctly
            with db.get_connection() as conn:
                # Check module properties
                module = conn.execute(
                    """SELECT m.*, c.name as collection_name
                    FROM ansible_modules m
                    JOIN ansible_collections c ON m.collection_id = c.id
                    WHERE m.id = ?""",
                    (module_id,),
                ).fetchone()
                assert module["name"] == "s3_bucket"
                assert module["type"] == "cloud"
                assert module["collection_name"] == "community.aws"

            # Add another module using the same collection name
            module_id2 = db.add_ansible_module(
                "community.aws",
                "ec2_instance",
                "cloud",
                '{"instance_type": {"type": "string"}}',
                "3.0.0",
                "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html",
            )
            assert module_id2 is not None

            # Verify module count for collection
            with db.get_connection() as conn:
                count = conn.execute(
                    """SELECT COUNT(*) FROM ansible_modules m
                    JOIN ansible_collections c ON m.collection_id = c.id
                    WHERE c.name = ?""",
                    ("community.aws",),
                ).fetchone()[0]
                assert count == 2, "Expected two modules for collection"

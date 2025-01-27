-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Entity and relationship tracking
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Terraform-specific tables
CREATE TABLE IF NOT EXISTS terraform_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    version TEXT NOT NULL,
    source_url TEXT NOT NULL,
    doc_url TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS terraform_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    schema TEXT NOT NULL,
    description TEXT,
    version TEXT NOT NULL,
    doc_url TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES terraform_providers(id) ON DELETE CASCADE,
    UNIQUE(provider_id, name COLLATE NOCASE, version)
);

CREATE TABLE IF NOT EXISTS provider_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    provider_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    doc_url TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES terraform_providers(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES terraform_resources(id) ON DELETE CASCADE,
    UNIQUE(provider_id, resource_id)
);

-- Ansible-specific tables
CREATE TABLE IF NOT EXISTS ansible_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE,
    version TEXT NOT NULL,
    source_url TEXT NOT NULL,
    doc_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS ansible_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    schema TEXT NOT NULL,
    version TEXT NOT NULL,
    doc_url TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES ansible_collections(id) ON DELETE CASCADE,
    UNIQUE(collection_id, name, version)
);

-- Relationship tracking
CREATE TABLE IF NOT EXISTS entity_relationships (
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id, target_id, relationship_type),
    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_tf_providers_name ON terraform_providers(name);
CREATE INDEX IF NOT EXISTS idx_tf_resources_name ON terraform_resources(name);
CREATE INDEX IF NOT EXISTS idx_ansible_collections_name ON ansible_collections(name);
CREATE INDEX IF NOT EXISTS idx_ansible_modules_name ON ansible_modules(name);
CREATE INDEX IF NOT EXISTS idx_provider_resources ON provider_resources(provider_id, resource_id);
CREATE INDEX IF NOT EXISTS idx_entity_relationships ON entity_relationships(source_id, target_id);
CREATE INDEX IF NOT EXISTS idx_observations ON observations(entity_id);
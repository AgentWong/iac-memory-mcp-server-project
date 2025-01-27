# IaC Memory MCP Server Project - Design Goals

## Project Vision

The IaC Memory MCP Server Project aims to enhance Claude AI's capabilities by providing persistent memory storage for Infrastructure as Code (IaC) related information, specifically focused on Terraform and Ansible components. This server acts as a specialized cache that maintains up-to-date information about frequently used IaC components, ensuring accurate version tracking and relationship mapping.

## Core Problem Statement

Claude AI operates with:
- Limited context retention across interactions
- Training data fixed at a certain point in time
- No built-in mechanism for tracking IaC component versions

This limitation impacts work with:
- Terraform providers and their resources
- Ansible collections and their modules
- Version-specific naming conventions and compatibility
- Relationship tracking between components

## Design Principles

### 1. MCP Native Integration
- Leverage MCP Python SDK's native capabilities
- Utilize core MCP concepts:
  - Server management
  - Tool implementation
  - Resource exposure
  - Context handling
  - Prompt templating
- Avoid reinventing functionality already provided by the SDK

### 2. Data Persistence
- Use SQLite as the primary database
- Maintain a separate, human-readable schema.sql file
- Track temporal metadata for all components:
  - Source URL where information was obtained
  - Timestamp of when data was fetched
  - Enable Claude to assess information freshness
- Focus on relationship mapping between:
  - Terraform providers and their resources
  - Ansible collections and their modules
  - Other relevant component relationships
- Store version-specific information and naming conventions

### 3. Architectural Simplicity
- Single-user system design
- Local-only deployment (server and client on same machine)
- No network traffic considerations
- Minimal security overhead (no SQL injection prevention needed)
- Focus on functionality over security hardening

### 4. Core Capabilities

The server must effectively manage:

1. Terraform Components:
   - Provider information
   - Resource definitions
   - Version tracking
   - Naming conventions across versions

2. Ansible Components:
   - Collection information
   - Module definitions
   - Version tracking
   - Naming conventions across versions

3. Relationship Management:
   - Parent-child relationships between components
   - Version compatibility mapping
   - Cross-reference capabilities

## Implementation Guidelines

### 1. MCP Protocol Alignment
- Implement server using MCP Python SDK
- Follow SDK patterns and conventions
- Avoid unnecessary abstractions or custom protocols
- No REST API or FastAPI implementations

### 2. Database Design
- Use schema.sql for clear structure definition
- Implement proper relationship mapping
- Focus on query efficiency
- Maintain data integrity through proper constraints

### 3. Feature Scope
- Focus on core IaC component tracking
- Implement only necessary functionality
- Avoid feature creep
- Maintain simplicity in design and implementation

### 4. Code Organization
- Clear separation of concerns
- Well-documented functions and classes
- Logical file structure
- Maintainable and readable code

## Success Criteria

The project will be considered successful when it:

1. Provides reliable persistence of IaC component information
2. Maintains accurate relationship mapping between components
3. Offers quick and efficient data retrieval
4. Integrates seamlessly with Claude AI through MCP
5. Effectively tracks version-specific information
6. Maintains data integrity and consistency
7. Operates efficiently in a local environment
8. Requires minimal maintenance and oversight

## Out of Scope

The following are explicitly not goals of this project:

1. Network deployment capabilities
2. Multi-user support
3. Advanced security features
4. REST API implementation
5. Complex authentication systems
6. Distributed database support
7. External API integrations
8. Web interface development

## Development Practices

1. Code Quality:
   - Clear documentation
   - Consistent coding style
   - Proper error handling
   - Efficient database operations

2. Testing:
   - Basic functionality testing
   - Data integrity verification
   - Performance validation
   - Integration testing with Claude AI

3. Documentation:
   - Clear setup instructions
   - Usage guidelines
   - Database schema documentation
   - API documentation

This document serves as the primary reference for project development, ensuring all work aligns with the original intent and maintains focus on the core objectives.
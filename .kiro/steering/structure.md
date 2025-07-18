# Project Structure

## Root Directory Layout

```
aiaml/
├── aiaml_server.py          # Main entry point (compatibility wrapper)
├── pyproject.toml           # Package configuration
├── requirements.txt         # Dependencies
├── run_server.sh           # Execution script using uv
├── README.md               # Documentation
├── spec.md                 # Detailed product specification
└── memory/                 # Memory storage directory
    └── files/              # Individual memory markdown files
```

## Package Structure

```
aiaml/                      # Main package directory
├── __init__.py            # Package initialization, exports main()
├── server.py              # MCP server implementation and startup
├── config.py              # Configuration management
├── auth.py                # Authentication and connection handling
├── memory.py              # Memory storage and retrieval operations
└── errors.py              # Error handling framework
```

## Memory File Organization

### File Naming Convention
- Format: `YYYYMMDD_HHMMSS_[8-char-id].md`
- Example: `20240115_103000_abc12345.md`

### File Structure
```markdown
---
id: abc12345
timestamp: 2024-01-15T10:30:00.123456
agent: claude
user: marco
topics: ["programming", "python", "preferences"]
---

Memory content as markdown text...
```

## Configuration Files

- **Environment Variables**: Primary configuration method
  - `AIAML_API_KEY`: Authentication for remote connections
  - `AIAML_ENABLE_SYNC`: Enable/disable Git synchronization
  - `AIAML_GITHUB_REMOTE`: Git remote URL for sync
  - `AIAML_MEMORY_DIR`: Custom memory storage directory
  - `AIAML_LOG_LEVEL`: Logging verbosity

## Code Organization Principles

### Separation of Concerns
- **server.py**: MCP server setup, tool registration, startup logic
- **memory.py**: All memory operations (store, search, recall)
- **auth.py**: Authentication logic and connection handling
- **config.py**: Configuration loading and validation
- **errors.py**: Centralized error handling and response formatting

### Module Responsibilities
- **Main Entry Point**: `aiaml_server.py` imports and calls `main()` from package
- **Tool Implementation**: Each MCP tool has validation, processing, and error handling
- **Background Operations**: Git sync runs in separate threads
- **Atomic Operations**: File writes use temporary files with atomic rename

### Error Handling Strategy
- **Graceful Degradation**: Continue operation despite individual failures
- **Structured Responses**: Consistent error format across all tools
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Input Validation**: Validate all parameters before processing

### Testing and Development
- **MCP Inspector**: Use `mcp dev` for interactive testing
- **Local Development**: Run directly with Python or uv
- **Package Installation**: Support both development and production installs
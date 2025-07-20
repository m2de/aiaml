# Testing Standards and Guidelines

## Overview

This document provides testing standards and guidelines for AIAML development. All development work should follow these testing practices to ensure code quality and maintainability.

## Testing Philosophy

- **Layered Testing**: Test individual modules before integration
- **Dependency Isolation**: Tests should work without external dependencies when possible
- **Comprehensive Coverage**: Test functionality, performance, and edge cases
- **Consistent Patterns**: Use standardized test structures and naming

## Test Suite Structure

### Current Test Files

| Test File | Purpose | Dependencies | When to Run |
|-----------|---------|--------------|-------------|
| `test_module_structure.py` | Architecture validation | None | After refactoring |
| `test_cross_platform.py` | Core functionality | None | Every session |
| `test_optimized_search.py` | Search functionality | MCP | After search changes |
| `test_search_performance_detailed.py` | Performance benchmarking | MCP | Performance work |
| `test_mcp_integration.py` | MCP integration | MCP | After MCP changes |
| `test_task_requirements.py` | Requirements verification | MCP | Task completion |

### Running Tests

```bash
# Quick validation (no dependencies)
python3 test_module_structure.py
python3 test_cross_platform.py

# Full test suite (requires MCP)
python3 run_tests.py

# Individual MCP tests
uv run --with "mcp[cli]" python3 test_optimized_search.py
```

## Development Standards

### File Size Limits
- **Maximum 500 lines per Python file**
- Enforced by `test_module_structure.py`
- Split large files into focused modules

### Test Function Structure
```python
def test_feature_name():
    """Test description."""
    print("Testing Feature Name")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        
        # Test implementation
        result = function_under_test(config)
        
        if expected_condition:
            print("  ✓ Test passed")
            return True
        else:
            print("  ✗ Test failed")
            return False
```

### Test Data Patterns
```python
# Use consistent test data
test_memories = [
    ("claude", "user1", ["python", "programming"], "Python programming"),
    ("gpt", "user1", ["javascript", "web"], "JavaScript development"),
    ("claude", "user2", ["data", "science"], "Data science with Python")
]

# Always use temporary directories
with tempfile.TemporaryDirectory() as temp_dir:
    config = Config(
        memory_dir=Path(temp_dir) / "memory" / "files",
        enable_git_sync=False
    )
```

### Performance Standards
- **Search Time**: < 2 seconds per search for 10,000+ memories
- **Cache Hit Rate**: > 30% for repeated searches
- **Memory Usage**: Reasonable consumption for large datasets

## Required Testing for Changes

### Code Changes
- Run `test_module_structure.py` to verify file sizes
- Run `test_cross_platform.py` to verify core functionality
- Run relevant specific tests for changed modules

### New Features
1. Write unit tests for individual functions
2. Add integration tests for feature interactions
3. Update `run_tests.py` if adding new test files
4. Ensure tests work with and without MCP dependencies

### Refactoring
1. Run structure tests to ensure architecture remains sound
2. Run cross-platform tests to verify functionality preserved
3. Run full test suite to ensure no regressions
4. Update test documentation if patterns change

## Error Handling in Tests

### Expected Failures
```python
error = validate_memory_input("", "user1", ["topic"], "content")
if error and error.error_code.startswith("VALIDATION"):
    print("  ✓ Validation correctly rejected invalid input")
else:
    print("  ✗ Validation should have rejected invalid input")
    return False
```

### Exception Handling
```python
try:
    result = potentially_failing_function()
    # Validate result
except ExpectedException:
    print("  ✓ Expected exception caught")
except Exception as e:
    print(f"  ✗ Unexpected exception: {e}")
    return False
```

## Documentation References

For detailed testing guidance, see:
- `TESTING_GUIDE.md` - Comprehensive testing methodology
- `TESTING_PATTERNS.md` - Ready-to-use code patterns and templates
- `TESTING_SUMMARY.md` - Documentation overview and navigation

## Quality Gates

Before committing code:
- [ ] All relevant tests pass
- [ ] New tests added for new functionality
- [ ] File size limits maintained (< 500 lines)
- [ ] Test patterns followed consistently
- [ ] Performance targets met

## Troubleshooting

### Common Issues
- **Import Errors**: Install MCP dependencies or run cross-platform tests only
- **File Permissions**: Ensure tests use `tempfile.TemporaryDirectory()`
- **Test Isolation**: Reset state between tests, use separate temp directories

### Getting Help
1. Check `TESTING_GUIDE.md` troubleshooting section
2. Review existing test patterns in `TESTING_PATTERNS.md`
3. Run individual tests to isolate issues
4. Verify MCP dependencies if needed

This testing framework ensures consistent, reliable development across all sessions.
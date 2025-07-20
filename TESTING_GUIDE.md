# AIAML Testing Guide

## Overview

This document provides comprehensive guidelines for testing the AIAML (AI Agnostic Memory Layer) codebase. It establishes consistent testing patterns and processes to ensure reliability and maintainability across development sessions.

## Testing Philosophy

### Core Principles
1. **Layered Testing**: Test individual modules before integration
2. **Dependency Isolation**: Tests should work without external dependencies when possible
3. **Comprehensive Coverage**: Test functionality, performance, and edge cases
4. **Consistent Patterns**: Use standardized test structures and naming
5. **Clear Documentation**: Each test should be self-documenting

### Test Categories
- **Unit Tests**: Individual module functionality
- **Integration Tests**: Module interactions
- **Performance Tests**: Speed and efficiency validation
- **Structure Tests**: Code organization and architecture
- **Cross-Platform Tests**: Functionality without external dependencies

## Test Suite Structure

### Primary Test Files

#### 1. `test_module_structure.py` - Architecture Validation
**Purpose**: Validates the overall code structure and organization
**Dependencies**: None (pure Python)
**Run Frequency**: Every refactoring or structural change

```python
# Tests included:
- Syntax validation for all Python files
- Import structure verification
- File size limit enforcement (500 lines max)
- Module export validation
```

#### 2. `test_cross_platform.py` - Core Functionality
**Purpose**: Tests core functionality without MCP dependencies
**Dependencies**: None (uses conditional imports)
**Run Frequency**: Every development session

```python
# Tests included:
- Config module functionality
- Error handling system
- Memory validation
- Performance monitoring
- Cache functionality
- Git sync utilities
- Memory parsing and storage
- Search relevance scoring
```

#### 3. `test_optimized_search.py` - Search Functionality
**Purpose**: Tests the optimized search system
**Dependencies**: MCP (via uv run)
**Run Frequency**: After search-related changes

```python
# Tests included:
- Memory creation and storage
- Search performance with various scenarios
- Cache behavior validation
- Performance statistics tracking
```

#### 4. `test_search_performance_detailed.py` - Performance Benchmarking
**Purpose**: Detailed performance analysis and benchmarking
**Dependencies**: MCP (via uv run)
**Run Frequency**: Performance optimization sessions

```python
# Tests included:
- Large dataset creation (100+ memories)
- Complex search scenarios
- Performance target validation
- Cache efficiency analysis
```

#### 5. `test_mcp_integration.py` - MCP Integration
**Purpose**: Tests MCP server integration
**Dependencies**: MCP (via uv run)
**Run Frequency**: After MCP-related changes

```python
# Tests included:
- MCP tool functionality
- Server integration
- Performance stats tool simulation
```

#### 6. `test_task_requirements.py` - Requirements Verification
**Purpose**: Validates specific task requirements
**Dependencies**: MCP (via uv run)
**Run Frequency**: Task completion verification

```python
# Tests included:
- Specific requirement validation
- Feature completeness checks
- Performance target verification
```

## Running Tests

### Quick Test (No Dependencies)
```bash
# Run structure and cross-platform tests
python3 test_module_structure.py
python3 test_cross_platform.py
```

### Full Test Suite (Requires MCP)
```bash
# Run all tests using the test runner
python3 run_tests.py

# Or run individual tests with uv
uv run --with "mcp[cli]" python3 test_optimized_search.py
```

### Test Runner Usage
The `run_tests.py` script provides a unified interface:

```bash
python3 run_tests.py
```

**Test Execution Order**:
1. Module Structure Validation
2. Cross-Platform Functionality  
3. Basic Optimized Search
4. Detailed Performance Benchmarking
5. MCP Server Integration
6. Task Requirements Verification

## Test Development Standards

### Test File Structure
```python
#!/usr/bin/env python3
"""Brief description of what this test validates."""

import sys
import tempfile
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, '.')

# Import only what's needed for this test
from aiaml.config import Config
from aiaml.memory import store_memory_atomic

def test_specific_functionality():
    """Test a specific piece of functionality."""
    print("Testing Specific Functionality")
    print("-" * 40)
    
    # Use temporary directories for file operations
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test setup
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(
            memory_dir=memory_dir,
            enable_git_sync=False  # Disable for testing
        )
        
        # Test execution
        result = some_function(config)
        
        # Validation with clear success/failure messages
        if expected_condition:
            print("  ✓ Test passed")
            return True
        else:
            print("  ✗ Test failed")
            return False

def main():
    """Run all tests in this file."""
    print("Test Suite Name")
    print("=" * 50)
    
    tests = [
        ("Test Name", test_specific_functionality),
        # Add more tests here
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary reporting
    print(f"\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    return passed == len(results)

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test suite failed: {e}")
        sys.exit(1)
```

### Test Naming Conventions

#### File Names
- `test_<module>_<aspect>.py` - For specific module testing
- `test_<functionality>.py` - For feature testing
- `test_<integration_type>.py` - For integration testing

#### Function Names
- `test_<specific_feature>()` - Individual test functions
- `test_<module>_<functionality>()` - Module-specific tests
- `main()` - Test runner function

#### Test Categories
- **Unit Tests**: `test_unit_<module>_<function>()`
- **Integration Tests**: `test_integration_<modules>()`
- **Performance Tests**: `test_performance_<aspect>()`
- **Validation Tests**: `test_validation_<input_type>()`

### Test Data Management

#### Temporary Directories
Always use `tempfile.TemporaryDirectory()` for file operations:

```python
with tempfile.TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    memory_dir = temp_path / "memory" / "files"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    config = Config(memory_dir=memory_dir, enable_git_sync=False)
    # Test operations here
```

#### Test Memory Data
Use consistent test data patterns:

```python
test_memories = [
    ("claude", "user1", ["python", "programming"], "Python programming fundamentals"),
    ("gpt", "user1", ["javascript", "web"], "JavaScript web development"),
    ("claude", "user2", ["python", "data"], "Python data science"),
    ("gemini", "user1", ["machine", "learning"], "Machine learning algorithms")
]
```

### Error Handling in Tests

#### Expected Failures
```python
# Test that validation correctly rejects invalid input
error = validate_memory_input("", "user1", ["topic"], "content")
if error and error.error_code.startswith("VALIDATION"):
    print("  ✓ Validation correctly rejected empty agent")
else:
    print("  ✗ Validation should have rejected empty agent")
    return False
```

#### Exception Handling
```python
try:
    result = potentially_failing_function()
    if expected_condition:
        print("  ✓ Function succeeded as expected")
    else:
        print("  ✗ Function succeeded but result was unexpected")
        return False
except ExpectedException as e:
    print("  ✓ Function correctly raised expected exception")
except Exception as e:
    print(f"  ✗ Function raised unexpected exception: {e}")
    return False
```

## Performance Testing Guidelines

### Performance Targets
- **Search Time**: < 2 seconds per search for 10,000+ memories
- **Cache Hit Rate**: > 30% for repeated searches
- **Memory Usage**: Reasonable memory consumption for large datasets
- **File Operations**: Atomic operations with proper locking

### Performance Test Structure
```python
def test_performance_targets():
    """Test that performance targets are met."""
    # Create substantial test dataset
    for i in range(100):  # Scale based on test requirements
        create_test_memory(i)
    
    # Measure performance
    start_time = time.time()
    results = search_memories_optimized(keywords, config)
    search_time = time.time() - start_time
    
    # Validate against targets
    if search_time < target_time:
        print(f"  ✓ Search time: {search_time:.4f}s (target: <{target_time}s)")
        return True
    else:
        print(f"  ✗ Search time: {search_time:.4f}s exceeds target")
        return False
```

## Dependency Management

### MCP Dependencies
Some tests require MCP dependencies. Handle this gracefully:

```python
# In test files that need MCP
try:
    from aiaml.memory import search_memories_optimized
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

def test_mcp_functionality():
    if not MCP_AVAILABLE:
        print("  ⚠️  Skipping MCP test - dependencies not available")
        return True
    
    # Run MCP-dependent tests
```

### Conditional Imports
The main package uses conditional imports to handle missing dependencies:

```python
# In aiaml/__init__.py
try:
    from .server import main
    _server_available = True
except ImportError:
    _server_available = False
    def main():
        raise ImportError("MCP dependencies not available...")
```

## Test Environment Setup

### Local Development
```bash
# Install dependencies
pip install -e .
pip install 'mcp[cli]>=1.0.0'

# Run tests
python3 run_tests.py
```

### CI/CD Environment
```bash
# Install with uv (recommended)
uv install --with "mcp[cli]"

# Run tests with uv
uv run python3 run_tests.py
```

### Docker Environment
```dockerfile
# Install Python and dependencies
RUN pip install -e .
RUN pip install 'mcp[cli]>=1.0.0'

# Run tests
CMD ["python3", "run_tests.py"]
```

## Troubleshooting Common Issues

### Import Errors
- **Problem**: `ModuleNotFoundError: No module named 'mcp'`
- **Solution**: Install MCP dependencies or run cross-platform tests only

### File Permission Errors
- **Problem**: Permission denied when creating test files
- **Solution**: Ensure tests use `tempfile.TemporaryDirectory()`

### Test Isolation Issues
- **Problem**: Tests interfere with each other
- **Solution**: Reset state between tests, use separate temp directories

### Performance Test Variability
- **Problem**: Performance tests give inconsistent results
- **Solution**: Run multiple iterations, use relative performance comparisons

## Best Practices Summary

### Do's ✅
- Use temporary directories for all file operations
- Reset performance stats and cache between tests
- Provide clear success/failure messages
- Handle missing dependencies gracefully
- Test both success and failure cases
- Use consistent test data patterns
- Document test purpose and requirements

### Don'ts ❌
- Don't write to the actual memory directory during tests
- Don't rely on external services or files
- Don't skip cleanup in test teardown
- Don't use hardcoded file paths
- Don't ignore test failures
- Don't create tests that depend on specific timing
- Don't mix different types of tests in the same file

## Future Test Development

When adding new tests:

1. **Choose the Right Category**: Determine if it's unit, integration, or performance
2. **Follow Naming Conventions**: Use consistent file and function names
3. **Handle Dependencies**: Make tests work with and without MCP
4. **Use Standard Structure**: Follow the established test file template
5. **Add to Test Runner**: Update `run_tests.py` if needed
6. **Document Purpose**: Clearly explain what the test validates
7. **Test Edge Cases**: Include both success and failure scenarios

This testing guide ensures consistent, reliable, and maintainable tests across all development sessions.
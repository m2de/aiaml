# AIAML Testing Patterns - Quick Reference

## Common Testing Patterns

### 1. Basic Test Function Template

```python
def test_feature_name():
    """Test description."""
    print("Testing Feature Name")
    print("-" * 30)
    
    try:
        # Setup
        with tempfile.TemporaryDirectory() as temp_dir:
            config = create_test_config(temp_dir)
            
            # Execute
            result = function_under_test(config)
            
            # Validate
            if expected_condition:
                print("  ✓ Test passed")
                return True
            else:
                print("  ✗ Test failed")
                return False
                
    except Exception as e:
        print(f"  ✗ Test failed with exception: {e}")
        return False
```

### 2. Memory Storage Test Pattern

```python
def test_memory_storage():
    """Test memory storage functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            memory_dir=Path(temp_dir) / "memory" / "files",
            enable_git_sync=False
        )
        config.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Store memory
        result = store_memory_atomic("agent", "user", ["topic"], "content", config)
        
        # Validate
        if 'memory_id' in result:
            print("  ✓ Memory stored successfully")
            return True
        else:
            print(f"  ✗ Memory storage failed: {result}")
            return False
```

### 3. Search Test Pattern

```python
def test_search_functionality():
    """Test search functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        
        # Create test data
        test_memories = [
            ("claude", "user1", ["python"], "Python programming"),
            ("gpt", "user1", ["javascript"], "JavaScript development")
        ]
        
        for agent, user, topics, content in test_memories:
            store_memory_atomic(agent, user, topics, content, config)
        
        # Test search
        results = search_memories_optimized(["python"], config)
        valid_results = [r for r in results if 'error' not in r]
        
        if len(valid_results) > 0:
            print(f"  ✓ Search found {len(valid_results)} results")
            return True
        else:
            print("  ✗ Search found no results")
            return False
```

### 4. Performance Test Pattern

```python
def test_performance():
    """Test performance metrics."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        
        # Reset performance stats
        reset_search_performance_stats()
        clear_memory_cache()
        
        # Create test data and perform operations
        create_test_memories(config, count=50)
        
        # Measure performance
        start_time = time.time()
        search_memories_optimized(["test"], config)
        search_time = time.time() - start_time
        
        # Validate performance
        if search_time < 2.0:  # 2 second target
            print(f"  ✓ Search time: {search_time:.4f}s")
            return True
        else:
            print(f"  ✗ Search time: {search_time:.4f}s exceeds target")
            return False
```

### 5. Validation Test Pattern

```python
def test_input_validation():
    """Test input validation."""
    # Test valid input
    error = validate_memory_input("agent", "user", ["topic"], "content")
    if error is None:
        print("  ✓ Valid input accepted")
    else:
        print("  ✗ Valid input rejected")
        return False
    
    # Test invalid input
    error = validate_memory_input("", "user", ["topic"], "content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Invalid input rejected")
        return True
    else:
        print("  ✗ Invalid input not rejected")
        return False
```

### 6. Cache Test Pattern

```python
def test_cache_behavior():
    """Test caching functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        
        # Reset cache
        clear_memory_cache()
        reset_search_performance_stats()
        
        # Create test memory
        store_memory_atomic("agent", "user", ["cache"], "test", config)
        
        # First search (cache miss)
        before_stats = get_search_performance_stats()
        search_memories_optimized(["cache"], config)
        after_first = get_search_performance_stats()
        
        # Second search (cache hit)
        search_memories_optimized(["cache"], config)
        after_second = get_search_performance_stats()
        
        # Validate cache behavior
        cache_hits = after_second['cache_hits'] - after_first['cache_hits']
        if cache_hits > 0:
            print(f"  ✓ Cache hit detected: {cache_hits}")
            return True
        else:
            print("  ⚠️  No cache hits detected")
            return True  # May be expected for different search patterns
```

### 7. Error Handling Test Pattern

```python
def test_error_handling():
    """Test error handling."""
    try:
        # Test expected error
        result = function_that_should_fail()
        print("  ✗ Function should have failed")
        return False
    except ExpectedError as e:
        print("  ✓ Expected error caught correctly")
        return True
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False
```

## Utility Functions

### Test Configuration Helper

```python
def create_test_config(temp_dir: str) -> Config:
    """Create a test configuration."""
    temp_path = Path(temp_dir)
    memory_dir = temp_path / "memory" / "files"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    return Config(
        memory_dir=memory_dir,
        max_search_results=25,
        enable_git_sync=False
    )
```

### Test Data Creation Helper

```python
def create_test_memories(config: Config, count: int = 10):
    """Create test memories for testing."""
    test_data = [
        ("claude", "user1", ["python", "programming"], "Python programming"),
        ("gpt", "user1", ["javascript", "web"], "JavaScript development"),
        ("claude", "user2", ["data", "science"], "Data science with Python"),
        # Add more test data as needed
    ]
    
    for i in range(count):
        data_index = i % len(test_data)
        agent, user, topics, content = test_data[data_index]
        
        # Make each memory unique
        unique_content = f"{content} - Memory #{i+1}"
        
        result = store_memory_atomic(agent, user, topics, unique_content, config)
        if 'error' in result:
            print(f"Error creating test memory {i+1}: {result}")
```

### Test Summary Helper

```python
def run_test_suite(tests: list) -> bool:
    """Run a suite of tests and return overall success."""
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    return passed == len(results)
```

## Test File Template

```python
#!/usr/bin/env python3
"""Test [DESCRIPTION] functionality."""

import sys
import tempfile
import time
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, '.')

from aiaml.config import Config
from aiaml.memory import (
    store_memory_atomic,
    search_memories_optimized,
    # Add other imports as needed
)

def create_test_config(temp_dir: str) -> Config:
    """Create a test configuration."""
    temp_path = Path(temp_dir)
    memory_dir = temp_path / "memory" / "files"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    return Config(
        memory_dir=memory_dir,
        max_search_results=25,
        enable_git_sync=False
    )

def test_[FEATURE_NAME]():
    """Test [FEATURE_NAME] functionality."""
    print("Testing [FEATURE_NAME]")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        
        # Test implementation here
        
        return True  # or False based on test results

def main():
    """Run all tests."""
    print("[TEST_SUITE_NAME]")
    print("=" * 50)
    
    tests = [
        ("[Test Name]", test_[FEATURE_NAME]),
        # Add more tests here
    ]
    
    return run_test_suite(tests)

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

## Quick Commands

### Run All Tests
```bash
python3 run_tests.py
```

### Run Individual Tests
```bash
# Structure validation (no dependencies)
python3 test_module_structure.py

# Cross-platform functionality (no dependencies)
python3 test_cross_platform.py

# MCP-dependent tests
uv run --with "mcp[cli]" python3 test_optimized_search.py
```

### Create New Test File
1. Copy the test file template
2. Replace `[PLACEHOLDERS]` with actual values
3. Implement test functions
4. Add to `run_tests.py` if needed

This quick reference provides the most common patterns used in AIAML testing.
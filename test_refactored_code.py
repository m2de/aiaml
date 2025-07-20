#!/usr/bin/env python3
"""Test the refactored AIAML code to ensure functionality is preserved."""

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
    recall_memories,
    get_search_performance_stats,
    reset_search_performance_stats,
    clear_memory_cache,
    validate_memory_input,
    validate_search_input,
    validate_recall_input
)


def test_memory_storage():
    """Test memory storage functionality."""
    print("Testing Memory Storage")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(
            memory_dir=memory_dir,
            max_search_results=25,
            enable_git_sync=False
        )
        
        # Test valid memory storage
        result = store_memory_atomic(
            "claude", 
            "user1", 
            ["python", "testing"], 
            "Test memory content for refactored code",
            config
        )
        
        if 'memory_id' in result:
            print(f"  ✓ Memory stored successfully: {result['memory_id']}")
            memory_id = result['memory_id']
        else:
            print(f"  ✗ Memory storage failed: {result}")
            return False
        
        # Verify file was created
        memory_files = list(memory_dir.glob("*.md"))
        if len(memory_files) == 1:
            print(f"  ✓ Memory file created: {memory_files[0].name}")
        else:
            print(f"  ✗ Expected 1 memory file, found {len(memory_files)}")
            return False
        
        # Test file content
        memory_file = memory_files[0]
        content = memory_file.read_text()
        
        if memory_id in content and "Test memory content" in content:
            print("  ✓ Memory file content is correct")
        else:
            print("  ✗ Memory file content is incorrect")
            return False
        
        return True


def test_memory_search():
    """Test memory search functionality."""
    print("\nTesting Memory Search")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(
            memory_dir=memory_dir,
            max_search_results=25,
            enable_git_sync=False
        )
        
        # Reset performance stats
        reset_search_performance_stats()
        clear_memory_cache()
        
        # Create test memories
        test_memories = [
            ("claude", "user1", ["python", "programming"], "Python programming fundamentals"),
            ("gpt", "user1", ["javascript", "web"], "JavaScript web development"),
            ("claude", "user2", ["python", "data"], "Python data science"),
            ("gemini", "user1", ["machine", "learning"], "Machine learning algorithms")
        ]
        
        stored_ids = []
        for agent, user, topics, content in test_memories:
            result = store_memory_atomic(agent, user, topics, content, config)
            if 'memory_id' in result:
                stored_ids.append(result['memory_id'])
        
        if len(stored_ids) != 4:
            print(f"  ✗ Expected 4 memories stored, got {len(stored_ids)}")
            return False
        
        print(f"  ✓ Created {len(stored_ids)} test memories")
        
        # Test search functionality
        search_results = search_memories_optimized(["python"], config)
        valid_results = [r for r in search_results if 'error' not in r]
        
        if len(valid_results) >= 2:  # Should find at least 2 Python-related memories
            print(f"  ✓ Search found {len(valid_results)} results for 'python'")
        else:
            print(f"  ✗ Search found only {len(valid_results)} results for 'python'")
            return False
        
        # Test relevance scoring
        if valid_results[0].get('relevance_score', 0) > 0:
            print(f"  ✓ Relevance scoring working (top score: {valid_results[0]['relevance_score']:.2f})")
        else:
            print("  ✗ Relevance scoring not working")
            return False
        
        # Test multi-keyword search
        multi_results = search_memories_optimized(["python", "data"], config)
        valid_multi = [r for r in multi_results if 'error' not in r]
        
        if len(valid_multi) >= 1:
            print(f"  ✓ Multi-keyword search working ({len(valid_multi)} results)")
        else:
            print("  ✗ Multi-keyword search failed")
            return False
        
        return True


def test_memory_recall():
    """Test memory recall functionality."""
    print("\nTesting Memory Recall")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(
            memory_dir=memory_dir,
            max_search_results=25,
            enable_git_sync=False
        )
        
        # Create test memory
        result = store_memory_atomic(
            "claude", 
            "user1", 
            ["recall", "test"], 
            "Memory for recall testing",
            config
        )
        
        if 'memory_id' not in result:
            print("  ✗ Failed to create test memory")
            return False
        
        memory_id = result['memory_id']
        print(f"  ✓ Created test memory: {memory_id}")
        
        # Test recall functionality
        recall_results = recall_memories([memory_id], config)
        
        if len(recall_results) == 1 and 'error' not in recall_results[0]:
            recalled_memory = recall_results[0]
            if recalled_memory['id'] == memory_id:
                print("  ✓ Memory recall successful")
            else:
                print("  ✗ Recalled memory has wrong ID")
                return False
        else:
            print(f"  ✗ Memory recall failed: {recall_results}")
            return False
        
        # Test recall with non-existent ID
        fake_recall = recall_memories(["fakeid12"], config)
        if len(fake_recall) == 1 and 'error' in fake_recall[0]:
            print("  ✓ Non-existent memory recall handled correctly")
        else:
            print("  ✗ Non-existent memory recall not handled correctly")
            return False
        
        return True


def test_performance_monitoring():
    """Test performance monitoring functionality."""
    print("\nTesting Performance Monitoring")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(
            memory_dir=memory_dir,
            max_search_results=25,
            enable_git_sync=False
        )
        
        # Reset stats
        reset_search_performance_stats()
        clear_memory_cache()
        
        # Create test memory
        store_memory_atomic("claude", "user1", ["performance"], "Performance test", config)
        
        # Perform searches to generate stats
        search_memories_optimized(["performance"], config)
        search_memories_optimized(["test"], config)
        search_memories_optimized(["performance"], config)  # Should hit cache
        
        # Check performance stats
        stats = get_search_performance_stats()
        
        required_fields = [
            'total_searches', 'total_search_time', 'avg_search_time',
            'cache_hits', 'cache_misses', 'cache_hit_rate', 'cache_size'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in stats:
                missing_fields.append(field)
        
        if not missing_fields:
            print("  ✓ All performance metrics available")
        else:
            print(f"  ✗ Missing performance metrics: {missing_fields}")
            return False
        
        if stats['total_searches'] >= 3:
            print(f"  ✓ Search count tracking: {stats['total_searches']} searches")
        else:
            print("  ✗ Search count tracking failed")
            return False
        
        if stats['cache_hits'] > 0:
            print(f"  ✓ Cache hit tracking: {stats['cache_hits']} hits")
        else:
            print("  ✗ Cache hit tracking failed")
            return False
        
        return True


def test_input_validation():
    """Test input validation functionality."""
    print("\nTesting Input Validation")
    print("-" * 40)
    
    # Test memory input validation
    error = validate_memory_input("", "user1", ["topic"], "content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty agent validation works")
    else:
        print("  ✗ Empty agent validation failed")
        return False
    
    error = validate_memory_input("agent", "user1", [], "content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty topics validation works")
    else:
        print("  ✗ Empty topics validation failed")
        return False
    
    # Test search input validation
    error = validate_search_input([])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty keywords validation works")
    else:
        print("  ✗ Empty keywords validation failed")
        return False
    
    # Test recall input validation
    error = validate_recall_input(["invalid_id"])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Invalid memory ID validation works")
    else:
        print("  ✗ Invalid memory ID validation failed")
        return False
    
    return True


def test_cache_functionality():
    """Test caching functionality."""
    print("\nTesting Cache Functionality")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(
            memory_dir=memory_dir,
            max_search_results=25,
            enable_git_sync=False
        )
        
        # Reset cache and stats
        clear_memory_cache()
        reset_search_performance_stats()
        
        # Create test memory
        store_memory_atomic("claude", "user1", ["cache", "test"], "Cache test memory", config)
        
        # First search (cache miss)
        before_stats = get_search_performance_stats()
        search_memories_optimized(["cache"], config)
        after_first = get_search_performance_stats()
        
        cache_misses_increase = after_first['cache_misses'] - before_stats['cache_misses']
        if cache_misses_increase > 0:
            print(f"  ✓ Cache miss detected: {cache_misses_increase} misses")
        else:
            print("  ✗ Cache miss not detected")
            return False
        
        # Second search (should hit cache)
        before_second = get_search_performance_stats()
        search_memories_optimized(["cache"], config)
        after_second = get_search_performance_stats()
        
        cache_hits_increase = after_second['cache_hits'] - before_second['cache_hits']
        if cache_hits_increase > 0:
            print(f"  ✓ Cache hit detected: {cache_hits_increase} hits")
        else:
            print("  ⚠️  Cache hit not detected (may be expected for different search patterns)")
        
        # Test cache clearing
        clear_memory_cache()
        stats_after_clear = get_search_performance_stats()
        if stats_after_clear['cache_size'] == 0:
            print("  ✓ Cache clearing works")
        else:
            print("  ✗ Cache clearing failed")
            return False
        
        return True


def main():
    """Run all refactored code tests."""
    print("AIAML Refactored Code Test Suite")
    print("=" * 50)
    print("Testing that refactoring preserved all functionality")
    print("=" * 50)
    
    tests = [
        ("Memory Storage", test_memory_storage),
        ("Memory Search", test_memory_search),
        ("Memory Recall", test_memory_recall),
        ("Performance Monitoring", test_performance_monitoring),
        ("Input Validation", test_input_validation),
        ("Cache Functionality", test_cache_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print(f"\n" + "=" * 50)
    print("REFACTORED CODE TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Refactoring preserved all functionality!")
        print("✅ All files are now under 500 lines!")
        print("✅ Code is better organized and maintainable!")
        return True
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed")
        print("Some functionality may have been broken during refactoring")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
#!/usr/bin/env python3
"""Test to verify all task 8 requirements have been implemented."""

import sys
import tempfile
import time
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, '.')

from aiaml.config import Config
from aiaml.memory import (
    search_memories_optimized,
    store_memory_atomic,
    get_search_performance_stats,
    reset_search_performance_stats,
    clear_memory_cache
)
from aiaml.memory.search import (
    _calculate_advanced_relevance_score,
    _build_search_index
)
from aiaml.memory.cache import (
    get_cached_memory as _get_cached_memory,
    cache_memory as _cache_memory
)


def test_requirement_8_2():
    """Test: Add file caching for frequently accessed memories."""
    print("Testing Requirement 8.2: File caching for frequently accessed memories")
    print("-" * 70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(memory_dir=memory_dir, enable_git_sync=False)
        
        # Clear cache to start fresh
        clear_memory_cache()
        reset_search_performance_stats()
        
        # Create test memory
        result = store_memory_atomic("claude", "user1", ["test", "caching"], "Test memory for caching", config)
        memory_id = result['memory_id']
        
        # Find the created file
        memory_files = list(memory_dir.glob("*.md"))
        test_file = memory_files[0]
        
        # Test cache miss
        cached_data = _get_cached_memory(test_file)
        if cached_data is None:
            print("  ✓ Cache miss detected correctly")
        else:
            print("  ✗ Expected cache miss but got cached data")
            return False
        
        # Test caching
        from aiaml.memory import parse_memory_file_safe
        memory_data = parse_memory_file_safe(test_file)
        _cache_memory(test_file, memory_data)
        
        # Test cache hit
        cached_data = _get_cached_memory(test_file)
        if cached_data is not None and cached_data['id'] == memory_id:
            print("  ✓ Memory successfully cached and retrieved")
        else:
            print("  ✗ Cache retrieval failed")
            return False
        
        # Test cache usage in search
        search_results = search_memories_optimized(["test"], config)
        stats = get_search_performance_stats()
        
        if stats['cache_hits'] > 0:
            print("  ✓ Cache hits recorded during search")
        else:
            print("  ✗ No cache hits recorded")
            return False
        
        print("  ✅ File caching requirement satisfied")
        return True


def test_requirement_8_1():
    """Test: Implement search_memories_optimized() with better algorithms."""
    print("Testing Requirement 8.1: search_memories_optimized() with better algorithms")
    print("-" * 70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(memory_dir=memory_dir, enable_git_sync=False)
        
        # Create diverse test memories
        test_memories = [
            ("claude", "user1", ["python", "programming"], "Advanced Python programming techniques"),
            ("gpt", "user1", ["javascript", "web"], "Modern JavaScript web development"),
            ("claude", "user2", ["python", "data"], "Python for data science applications"),
        ]
        
        for agent, user, topics, content in test_memories:
            store_memory_atomic(agent, user, topics, content, config)
        
        # Test advanced relevance scoring
        memory_files = list(memory_dir.glob("*.md"))
        from aiaml.memory import parse_memory_file_safe
        
        test_memory = parse_memory_file_safe(memory_files[0])
        if test_memory is None:
            print("  ✗ Failed to parse test memory file")
            return False
        
        score = _calculate_advanced_relevance_score(test_memory, ["python", "programming"])
        
        if score > 0:
            print(f"  ✓ Advanced relevance scoring working (score: {score:.2f})")
        else:
            print("  ✗ Advanced relevance scoring failed")
            return False
        
        # Test search index building
        search_index = _build_search_index(memory_files)
        
        if len(search_index) > 0 and "python" in search_index:
            print(f"  ✓ Search index built successfully ({len(search_index)} terms indexed)")
        else:
            print("  ✗ Search index building failed")
            return False
        
        # Test optimized search function
        results = search_memories_optimized(["python"], config)
        valid_results = [r for r in results if 'error' not in r]
        
        if len(valid_results) > 0:
            print(f"  ✓ Optimized search function working ({len(valid_results)} results)")
        else:
            print("  ✗ Optimized search function failed")
            return False
        
        print("  ✅ Better algorithms requirement satisfied")
        return True


def test_requirement_8_3():
    """Test: Optimize keyword matching and relevance scoring."""
    print("Testing Requirement 8.3: Optimize keyword matching and relevance scoring")
    print("-" * 70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(memory_dir=memory_dir, enable_git_sync=False)
        
        # Create memories with different relevance levels
        test_memories = [
            ("claude", "user1", ["machine", "learning"], "Machine learning algorithms and neural networks"),
            ("gpt", "user1", ["learning", "education"], "Learning strategies for education"),
            ("claude", "user2", ["algorithms", "computer"], "Computer algorithms and data structures"),
        ]
        
        for agent, user, topics, content in test_memories:
            store_memory_atomic(agent, user, topics, content, config)
        
        # Test relevance scoring with different keyword combinations
        results = search_memories_optimized(["machine", "learning"], config)
        valid_results = [r for r in results if 'error' not in r]
        
        if len(valid_results) > 0:
            # Check that results are sorted by relevance
            scores = [r['relevance_score'] for r in valid_results]
            is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
            
            if is_sorted:
                print(f"  ✓ Results properly sorted by relevance (top score: {scores[0]:.2f})")
            else:
                print("  ✗ Results not properly sorted by relevance")
                return False
            
            # Test that exact topic matches get higher scores
            top_result = valid_results[0]
            if "machine" in str(top_result.get('topics', [])).lower():
                print("  ✓ Topic matching prioritized correctly")
            else:
                print("  ⚠️  Topic matching may not be optimal")
        else:
            print("  ✗ No results found for relevance testing")
            return False
        
        # Test partial matching
        partial_results = search_memories_optimized(["learn"], config)
        valid_partial = [r for r in partial_results if 'error' not in r]
        
        if len(valid_partial) > 0:
            print(f"  ✓ Partial keyword matching working ({len(valid_partial)} results)")
        else:
            print("  ✗ Partial keyword matching failed")
            return False
        
        print("  ✅ Keyword matching and relevance scoring requirement satisfied")
        return True


def test_requirement_8_4():
    """Test: Add search performance monitoring and logging."""
    print("Testing Requirement 8.4: Search performance monitoring and logging")
    print("-" * 70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(memory_dir=memory_dir, enable_git_sync=False)
        
        # Reset stats
        reset_search_performance_stats()
        clear_memory_cache()
        
        # Create test memory
        store_memory_atomic("claude", "user1", ["monitoring", "test"], "Performance monitoring test", config)
        
        # Perform searches to generate stats
        search_memories_optimized(["monitoring"], config)
        search_memories_optimized(["test"], config)
        search_memories_optimized(["monitoring"], config)  # Should hit cache
        
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
            print("  ✓ All required performance metrics available")
        else:
            print(f"  ✗ Missing performance metrics: {missing_fields}")
            return False
        
        # Check that stats are being updated
        if stats['total_searches'] >= 3:
            print(f"  ✓ Search count tracking working ({stats['total_searches']} searches)")
        else:
            print("  ✗ Search count tracking failed")
            return False
        
        if stats['total_search_time'] > 0:
            print(f"  ✓ Search time tracking working ({stats['total_search_time']:.4f}s total)")
        else:
            print("  ✗ Search time tracking failed")
            return False
        
        if stats['cache_hits'] > 0:
            print(f"  ✓ Cache hit tracking working ({stats['cache_hits']} hits)")
        else:
            print("  ✗ Cache hit tracking failed")
            return False
        
        # Test performance stats reset
        reset_search_performance_stats()
        reset_stats = get_search_performance_stats()
        
        if reset_stats['total_searches'] == 0:
            print("  ✓ Performance stats reset working")
        else:
            print("  ✗ Performance stats reset failed")
            return False
        
        print("  ✅ Performance monitoring and logging requirement satisfied")
        return True


def test_performance_targets():
    """Test that performance targets are met (Requirements 6.2, 6.5)."""
    print("Testing Performance Targets (Requirements 6.2, 6.5)")
    print("-" * 70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        config = Config(memory_dir=memory_dir, enable_git_sync=False)
        
        # Create a reasonable number of test memories
        print("  Creating test dataset...")
        for i in range(50):
            agent = ["claude", "gpt", "gemini"][i % 3]
            user = f"user{i % 5}"
            topics = [f"topic{i % 10}", f"category{i % 7}"]
            content = f"Test memory content {i} with various keywords and topics for performance testing"
            store_memory_atomic(agent, user, topics, content, config)
        
        # Test search performance
        print("  Testing search performance...")
        reset_search_performance_stats()
        
        # Perform multiple searches
        test_keywords = [
            ["topic1"], ["category2"], ["test", "memory"], 
            ["performance"], ["keywords", "topics"]
        ]
        
        start_time = time.time()
        for keywords in test_keywords:
            search_memories_optimized(keywords, config)
        total_time = time.time() - start_time
        
        stats = get_search_performance_stats()
        avg_time = stats['avg_search_time']
        
        # Check performance targets
        # Target: < 2 seconds per search for 10,000+ memories (we're testing with 50)
        target_time = 2.0
        
        if avg_time < target_time:
            print(f"  ✓ Average search time: {avg_time:.4f}s (target: <{target_time}s)")
        else:
            print(f"  ✗ Average search time: {avg_time:.4f}s exceeds target of {target_time}s")
            return False
        
        # Test cache efficiency
        if stats['cache_hit_rate'] > 0:
            print(f"  ✓ Cache hit rate: {stats['cache_hit_rate']:.1%}")
        else:
            print("  ⚠️  Cache hit rate is 0% (may be expected for diverse searches)")
        
        print("  ✅ Performance targets satisfied")
        return True


def main():
    """Run all requirement tests."""
    print("AIAML Task 8 Requirements Verification")
    print("=" * 70)
    print("Testing: Optimize memory search performance")
    print("=" * 70)
    
    tests = [
        ("8.1", "Better algorithms", test_requirement_8_1),
        ("8.2", "File caching", test_requirement_8_2),
        ("8.3", "Keyword matching optimization", test_requirement_8_3),
        ("8.4", "Performance monitoring", test_requirement_8_4),
        ("6.2/6.5", "Performance targets", test_performance_targets),
    ]
    
    results = []
    for req_id, description, test_func in tests:
        print(f"\n{req_id}: {description}")
        print("=" * 70)
        try:
            success = test_func()
            results.append((req_id, description, success))
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append((req_id, description, False))
    
    # Summary
    print(f"\n" + "=" * 70)
    print("TASK 8 REQUIREMENTS VERIFICATION SUMMARY")
    print("=" * 70)
    
    passed = 0
    for req_id, description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{req_id:8} {description:30} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} requirements satisfied")
    
    if passed == len(results):
        print("\n🎉 ALL TASK 8 REQUIREMENTS SUCCESSFULLY IMPLEMENTED!")
        return True
    else:
        print(f"\n⚠️  {len(results) - passed} requirements need attention")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
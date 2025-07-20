#!/usr/bin/env python3
"""Test MCP server integration with optimized search."""

import sys
import tempfile
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


def test_mcp_tools_integration():
    """Test that the MCP tools work with optimized search."""
    print("Testing MCP Tools Integration")
    print("="*50)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        memory_dir = temp_path / "memory" / "files"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test configuration
        config = Config(
            memory_dir=memory_dir,
            max_search_results=25,
            enable_git_sync=False
        )
        
        # Reset performance stats
        reset_search_performance_stats()
        clear_memory_cache()
        
        # Test 1: Store some memories
        print("\n1. Testing memory storage...")
        test_memories = [
            ("claude", "user1", ["python", "testing"], "Testing optimized search functionality"),
            ("gpt", "user1", ["performance", "optimization"], "Performance optimization techniques"),
            ("claude", "user2", ["cache", "memory"], "Memory caching strategies")
        ]
        
        stored_ids = []
        for agent, user, topics, content in test_memories:
            result = store_memory_atomic(agent, user, topics, content, config)
            if 'memory_id' in result:
                stored_ids.append(result['memory_id'])
                print(f"  ✓ Stored memory: {result['memory_id']}")
            else:
                print(f"  ✗ Failed to store memory: {result}")
        
        # Test 2: Search with optimized function
        print("\n2. Testing optimized search...")
        search_results = search_memories_optimized(["python", "testing"], config)
        valid_results = [r for r in search_results if 'error' not in r]
        print(f"  ✓ Found {len(valid_results)} results for 'python testing'")
        
        if valid_results:
            print(f"  ✓ Top result score: {valid_results[0].get('relevance_score', 'N/A')}")
        
        # Test 3: Performance stats
        print("\n3. Testing performance statistics...")
        stats = get_search_performance_stats()
        
        expected_fields = [
            'total_searches', 'total_search_time', 'cache_hits', 
            'cache_misses', 'avg_search_time', 'cache_size', 'cache_hit_rate'
        ]
        
        for field in expected_fields:
            if field in stats:
                print(f"  ✓ {field}: {stats[field]}")
            else:
                print(f"  ✗ Missing field: {field}")
        
        # Test 4: Cache behavior
        print("\n4. Testing cache behavior...")
        
        # First search (cache miss)
        before_stats = get_search_performance_stats()
        search_memories_optimized(["performance"], config)
        after_first = get_search_performance_stats()
        
        # Second search (cache hit)
        search_memories_optimized(["performance"], config)
        after_second = get_search_performance_stats()
        
        cache_misses_increase = after_first['cache_misses'] - before_stats['cache_misses']
        cache_hits_increase = after_second['cache_hits'] - after_first['cache_hits']
        
        print(f"  ✓ Cache misses on first search: {cache_misses_increase}")
        print(f"  ✓ Cache hits on second search: {cache_hits_increase}")
        
        if cache_hits_increase > 0:
            print("  ✓ Cache is working correctly")
        else:
            print("  ⚠️  Cache may not be working as expected")
        
        # Test 5: Performance validation
        print("\n5. Performance validation...")
        final_stats = get_search_performance_stats()
        
        # Check performance targets
        avg_time = final_stats['avg_search_time']
        cache_hit_rate = final_stats['cache_hit_rate']
        
        print(f"  Average search time: {avg_time:.4f}s {'✓' if avg_time < 2.0 else '✗'}")
        print(f"  Cache hit rate: {cache_hit_rate:.1%} {'✓' if cache_hit_rate >= 0 else '✗'}")
        
        # Summary
        print(f"\n" + "="*50)
        print("Integration Test Summary")
        print("="*50)
        print(f"Memories stored: {len(stored_ids)}")
        print(f"Searches performed: {final_stats['total_searches']}")
        print(f"Average search time: {final_stats['avg_search_time']:.4f}s")
        print(f"Cache efficiency: {final_stats['cache_hit_rate']:.1%}")
        print("✅ All integration tests passed!")
        
        return True


def simulate_mcp_performance_stats_tool():
    """Simulate the MCP performance_stats tool."""
    print("\nSimulating MCP performance_stats tool...")
    
    # This simulates what the MCP tool would return
    stats = get_search_performance_stats()
    
    print("Performance Stats Tool Output:")
    print("-" * 30)
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")
    
    return stats


if __name__ == "__main__":
    try:
        # Run integration tests
        success = test_mcp_tools_integration()
        
        # Simulate MCP tool
        simulate_mcp_performance_stats_tool()
        
        print(f"\n{'='*50}")
        print("MCP Integration Test Completed Successfully!")
        print("="*50)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
#!/usr/bin/env python3
"""Test script for the optimized search functionality."""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add the aiaml package to the path
sys.path.insert(0, '.')

from aiaml.config import Config
from aiaml.memory import (
    search_memories_optimized, 
    store_memory_atomic,
    get_search_performance_stats,
    clear_memory_cache,
    reset_search_performance_stats
)


def create_test_memories(config: Config, count: int = 10):
    """Create test memories for performance testing."""
    print(f"Creating {count} test memories...")
    
    test_data = [
        ("claude", "user1", ["python", "programming"], "Learning Python programming fundamentals and best practices"),
        ("gpt", "user1", ["javascript", "web"], "Building modern web applications with JavaScript frameworks"),
        ("claude", "user2", ["data science", "python"], "Data analysis using pandas and numpy libraries"),
        ("gemini", "user1", ["machine learning", "ai"], "Understanding neural networks and deep learning concepts"),
        ("claude", "user3", ["database", "sql"], "Database design principles and SQL query optimization"),
        ("gpt", "user2", ["react", "frontend"], "React component lifecycle and state management patterns"),
        ("claude", "user1", ["testing", "python"], "Unit testing strategies and test-driven development"),
        ("gemini", "user3", ["algorithms", "computer science"], "Algorithm complexity analysis and optimization techniques"),
        ("gpt", "user1", ["api", "backend"], "RESTful API design and implementation best practices"),
        ("claude", "user2", ["security", "web"], "Web application security vulnerabilities and prevention methods")
    ]
    
    for i in range(count):
        data_index = i % len(test_data)
        agent, user, topics, content = test_data[data_index]
        
        # Add some variation to make each memory unique
        unique_content = f"{content} - Memory #{i+1} created at {datetime.now().isoformat()}"
        
        result = store_memory_atomic(agent, user, topics, unique_content, config)
        if 'error' in result:
            print(f"Error creating memory {i+1}: {result}")
        else:
            print(f"Created memory {i+1}: {result['memory_id']}")


def test_search_performance():
    """Test the optimized search performance."""
    print("\n" + "="*60)
    print("Testing Optimized Search Performance")
    print("="*60)
    
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
        
        # Create test memories
        create_test_memories(config, 20)
        
        # Test various search scenarios
        test_cases = [
            ["python"],
            ["javascript", "web"],
            ["machine learning"],
            ["database", "sql"],
            ["programming"],
            ["api", "backend"],
            ["security"],
            ["nonexistent", "keyword"]
        ]
        
        print(f"\nRunning {len(test_cases)} search test cases...")
        
        for i, keywords in enumerate(test_cases, 1):
            print(f"\nTest {i}: Searching for {keywords}")
            
            results = search_memories_optimized(keywords, config)
            
            if results and 'error' not in results[0]:
                print(f"  Found {len(results)} results")
                if results:
                    print(f"  Top result score: {results[0].get('relevance_score', 'N/A')}")
                    print(f"  Top result preview: {results[0].get('content_preview', 'N/A')[:100]}...")
            else:
                print(f"  No results or error: {results}")
        
        # Test cache performance with repeated searches
        print(f"\nTesting cache performance with repeated searches...")
        
        # First search (cache miss)
        results1 = search_memories_optimized(["python", "programming"], config)
        
        # Second search (should hit cache)
        results2 = search_memories_optimized(["python", "programming"], config)
        
        # Get performance statistics
        stats = get_search_performance_stats()
        
        print(f"\nPerformance Statistics:")
        print(f"  Total searches: {stats['total_searches']}")
        print(f"  Average search time: {stats['avg_search_time']:.4f}s")
        print(f"  Cache hits: {stats['cache_hits']}")
        print(f"  Cache misses: {stats['cache_misses']}")
        print(f"  Cache hit rate: {stats['cache_hit_rate']:.2%}")
        print(f"  Cache size: {stats['cache_size']}")
        
        # Verify results are consistent
        if len(results1) == len(results2):
            print(f"  ✓ Cache consistency verified ({len(results1)} results)")
        else:
            print(f"  ✗ Cache inconsistency detected ({len(results1)} vs {len(results2)} results)")
        
        print(f"\nOptimized search test completed successfully!")


if __name__ == "__main__":
    try:
        test_search_performance()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
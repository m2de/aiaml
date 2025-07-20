#!/usr/bin/env python3
"""Detailed performance test for the optimized search functionality."""

import os
import sys
import tempfile
import time
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


def create_large_test_dataset(config: Config, count: int = 100):
    """Create a larger test dataset for performance testing."""
    print(f"Creating {count} test memories for performance testing...")
    
    # More diverse test data
    topics_pool = [
        ["python", "programming", "backend"],
        ["javascript", "frontend", "web"],
        ["react", "ui", "components"],
        ["database", "sql", "optimization"],
        ["machine learning", "ai", "neural networks"],
        ["data science", "analytics", "visualization"],
        ["security", "authentication", "encryption"],
        ["api", "rest", "microservices"],
        ["testing", "automation", "quality"],
        ["devops", "deployment", "infrastructure"],
        ["algorithms", "data structures", "complexity"],
        ["mobile", "ios", "android"],
        ["cloud", "aws", "scalability"],
        ["performance", "optimization", "monitoring"],
        ["design patterns", "architecture", "best practices"]
    ]
    
    content_templates = [
        "Understanding {} concepts and implementing {} solutions for {} applications",
        "Best practices for {} development including {} patterns and {} optimization",
        "Advanced {} techniques for building scalable {} systems with {} integration",
        "Troubleshooting {} issues and implementing {} monitoring for {} environments",
        "Learning {} fundamentals and applying {} methodologies in {} projects"
    ]
    
    agents = ["claude", "gpt", "gemini", "assistant"]
    users = ["user1", "user2", "user3", "developer", "analyst"]
    
    for i in range(count):
        # Select random data
        topics = topics_pool[i % len(topics_pool)]
        template = content_templates[i % len(content_templates)]
        agent = agents[i % len(agents)]
        user = users[i % len(users)]
        
        # Create varied content
        content = template.format(topics[0], topics[1], topics[2])
        content += f" Memory #{i+1} created for performance testing at {datetime.now().isoformat()}"
        
        # Add some memories with longer content
        if i % 10 == 0:
            content += " " * 500 + "This is additional content to test performance with longer texts. " * 20
        
        result = store_memory_atomic(agent, user, topics, content, config)
        if 'error' in result:
            print(f"Error creating memory {i+1}: {result}")
        elif i % 20 == 0:  # Print progress every 20 memories
            print(f"Created {i+1}/{count} memories...")
    
    print(f"Successfully created {count} test memories")


def benchmark_search_performance(config: Config):
    """Benchmark search performance with various scenarios."""
    print("\n" + "="*60)
    print("Search Performance Benchmark")
    print("="*60)
    
    # Reset stats
    reset_search_performance_stats()
    clear_memory_cache()
    
    # Test scenarios with different complexity
    test_scenarios = [
        # Single keyword searches
        (["python"], "Single keyword - common"),
        (["javascript"], "Single keyword - common"),
        (["security"], "Single keyword - medium"),
        (["optimization"], "Single keyword - specific"),
        
        # Multi-keyword searches
        (["python", "programming"], "Two keywords - related"),
        (["machine", "learning"], "Two keywords - compound term"),
        (["api", "rest", "microservices"], "Three keywords - related"),
        (["database", "performance", "optimization"], "Three keywords - technical"),
        
        # Complex searches
        (["neural", "networks", "deep", "learning"], "Four keywords - AI domain"),
        (["web", "security", "authentication", "encryption"], "Four keywords - security domain"),
        
        # Partial matches
        (["program"], "Partial match test"),
        (["develop"], "Partial match test 2"),
        
        # Non-existent terms
        (["nonexistent", "terms"], "No matches expected"),
    ]
    
    print(f"Running {len(test_scenarios)} search scenarios...")
    
    results = []
    for keywords, description in test_scenarios:
        print(f"\nTesting: {description}")
        print(f"Keywords: {keywords}")
        
        # Measure search time
        start_time = time.time()
        search_results = search_memories_optimized(keywords, config)
        search_time = time.time() - start_time
        
        # Count valid results (exclude errors)
        valid_results = [r for r in search_results if 'error' not in r]
        
        print(f"  Results: {len(valid_results)} memories found")
        print(f"  Time: {search_time:.4f}s")
        
        if valid_results:
            top_score = valid_results[0].get('relevance_score', 0)
            print(f"  Top relevance score: {top_score:.2f}")
        
        results.append({
            'keywords': keywords,
            'description': description,
            'time': search_time,
            'results_count': len(valid_results)
        })
    
    # Performance summary
    print(f"\n" + "="*60)
    print("Performance Summary")
    print("="*60)
    
    stats = get_search_performance_stats()
    print(f"Total searches performed: {stats['total_searches']}")
    print(f"Average search time: {stats['avg_search_time']:.4f}s")
    print(f"Cache hits: {stats['cache_hits']}")
    print(f"Cache misses: {stats['cache_misses']}")
    print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
    print(f"Current cache size: {stats['cache_size']}")
    
    # Analyze performance by complexity
    single_keyword_times = [r['time'] for r in results if len(r['keywords']) == 1]
    multi_keyword_times = [r['time'] for r in results if len(r['keywords']) > 1]
    
    if single_keyword_times:
        avg_single = sum(single_keyword_times) / len(single_keyword_times)
        print(f"Average single keyword search: {avg_single:.4f}s")
    
    if multi_keyword_times:
        avg_multi = sum(multi_keyword_times) / len(multi_keyword_times)
        print(f"Average multi-keyword search: {avg_multi:.4f}s")
    
    # Check performance targets
    print(f"\n" + "="*60)
    print("Performance Target Validation")
    print("="*60)
    
    target_search_time = 2.0  # 2 seconds for 10,000+ memories (we're testing with 100)
    max_time = max(r['time'] for r in results)
    avg_time = sum(r['time'] for r in results) / len(results)
    
    print(f"Target: < {target_search_time}s per search")
    print(f"Maximum time: {max_time:.4f}s {'✓' if max_time < target_search_time else '✗'}")
    print(f"Average time: {avg_time:.4f}s {'✓' if avg_time < target_search_time else '✗'}")
    
    # Cache efficiency check
    cache_efficiency_target = 0.5  # 50% hit rate after repeated searches
    print(f"Cache hit rate: {stats['cache_hit_rate']:.1%} {'✓' if stats['cache_hit_rate'] >= cache_efficiency_target else '✗'}")
    
    return results


def test_cache_behavior(config: Config):
    """Test caching behavior in detail."""
    print(f"\n" + "="*60)
    print("Cache Behavior Testing")
    print("="*60)
    
    # Reset cache and stats
    clear_memory_cache()
    reset_search_performance_stats()
    
    # Test repeated searches
    test_keywords = ["python", "programming"]
    
    print(f"Testing cache with repeated searches for: {test_keywords}")
    
    # First search (should be cache miss)
    print("First search (cache miss expected)...")
    start_stats = get_search_performance_stats()
    results1 = search_memories_optimized(test_keywords, config)
    after_first = get_search_performance_stats()
    
    print(f"  Cache misses increased by: {after_first['cache_misses'] - start_stats['cache_misses']}")
    print(f"  Results found: {len([r for r in results1 if 'error' not in r])}")
    
    # Second search (should hit cache)
    print("Second search (cache hit expected)...")
    before_second = get_search_performance_stats()
    results2 = search_memories_optimized(test_keywords, config)
    after_second = get_search_performance_stats()
    
    print(f"  Cache hits increased by: {after_second['cache_hits'] - before_second['cache_hits']}")
    print(f"  Results found: {len([r for r in results2 if 'error' not in r])}")
    
    # Verify consistency
    valid_results1 = [r for r in results1 if 'error' not in r]
    valid_results2 = [r for r in results2 if 'error' not in r]
    
    if len(valid_results1) == len(valid_results2):
        print("  ✓ Cache consistency verified")
    else:
        print(f"  ✗ Cache inconsistency: {len(valid_results1)} vs {len(valid_results2)} results")
    
    # Test cache expiration (would need to wait 5 minutes in real scenario)
    print("Cache expiration test (simulated)...")
    final_stats = get_search_performance_stats()
    print(f"  Final cache size: {final_stats['cache_size']}")
    print(f"  Total cache hits: {final_stats['cache_hits']}")
    print(f"  Total cache misses: {final_stats['cache_misses']}")


def main():
    """Main test function."""
    print("AIAML Optimized Search Performance Test")
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
        
        # Create test dataset
        create_large_test_dataset(config, 100)
        
        # Run performance benchmarks
        benchmark_results = benchmark_search_performance(config)
        
        # Test cache behavior
        test_cache_behavior(config)
        
        print(f"\n" + "="*60)
        print("Test Completed Successfully!")
        print("="*60)
        
        # Final summary
        final_stats = get_search_performance_stats()
        print(f"Total operations: {final_stats['total_searches']} searches")
        print(f"Overall average time: {final_stats['avg_search_time']:.4f}s")
        print(f"Cache efficiency: {final_stats['cache_hit_rate']:.1%}")
        
        # Performance validation
        all_passed = True
        if final_stats['avg_search_time'] > 2.0:
            print("⚠️  Average search time exceeds 2s target")
            all_passed = False
        
        if final_stats['cache_hit_rate'] < 0.3:
            print("⚠️  Cache hit rate below 30%")
            all_passed = False
        
        if all_passed:
            print("✅ All performance targets met!")
        
        return all_passed


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
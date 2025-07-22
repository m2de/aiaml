"""Memory caching functionality for improved performance."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# Global cache for frequently accessed memories
_memory_cache = {}
_cache_timestamps = {}
_cache_max_age = timedelta(minutes=5)  # Cache expires after 5 minutes
_cache_max_size = 100  # Maximum number of cached memories

# Performance monitoring data
_search_performance_stats = {
    'total_searches': 0,
    'total_search_time': 0.0,
    'cache_hits': 0,
    'cache_misses': 0,
    'avg_search_time': 0.0,
    'last_reset': datetime.now()
}


def _clean_expired_cache() -> None:
    """Remove expired entries from the memory cache."""
    current_time = datetime.now()
    expired_keys = []
    
    for key, timestamp in _cache_timestamps.items():
        if current_time - timestamp > _cache_max_age:
            expired_keys.append(key)
    
    for key in expired_keys:
        _memory_cache.pop(key, None)
        _cache_timestamps.pop(key, None)


def _manage_cache_size() -> None:
    """Ensure cache doesn't exceed maximum size by removing oldest entries."""
    if len(_memory_cache) <= _cache_max_size:
        return
    
    # Sort by timestamp and remove oldest entries
    sorted_items = sorted(_cache_timestamps.items(), key=lambda x: x[1])
    items_to_remove = len(_memory_cache) - _cache_max_size
    
    for i in range(items_to_remove):
        key = sorted_items[i][0]
        _memory_cache.pop(key, None)
        _cache_timestamps.pop(key, None)


def get_cached_memory(file_path: Path) -> Optional[Dict[str, Any]]:
    """Get memory from cache if available and not expired."""
    cache_key = str(file_path)
    
    if cache_key not in _memory_cache:
        return None
    
    # Check if cache entry is still valid
    if cache_key in _cache_timestamps:
        if datetime.now() - _cache_timestamps[cache_key] <= _cache_max_age:
            _search_performance_stats['cache_hits'] += 1
            return _memory_cache[cache_key]
        else:
            # Remove expired entry
            _memory_cache.pop(cache_key, None)
            _cache_timestamps.pop(cache_key, None)
    
    return None


def cache_memory(file_path: Path, memory_data: Dict[str, Any]) -> None:
    """Cache a memory for faster future access."""
    cache_key = str(file_path)
    
    # Clean expired entries and manage size
    _clean_expired_cache()
    _manage_cache_size()
    
    # Add to cache
    _memory_cache[cache_key] = memory_data
    _cache_timestamps[cache_key] = datetime.now()
    _search_performance_stats['cache_misses'] += 1


def clear_memory_cache() -> None:
    """Clear the memory cache."""
    global _memory_cache, _cache_timestamps
    _memory_cache.clear()
    _cache_timestamps.clear()


def get_search_performance_stats() -> Dict[str, Any]:
    """Get current search performance statistics."""
    stats = _search_performance_stats.copy()
    stats['cache_size'] = len(_memory_cache)
    stats['cache_hit_rate'] = (
        stats['cache_hits'] / max(1, stats['cache_hits'] + stats['cache_misses'])
    )
    return stats


def reset_search_performance_stats() -> None:
    """Reset search performance statistics."""
    global _search_performance_stats
    _search_performance_stats = {
        'total_searches': 0,
        'total_search_time': 0.0,
        'cache_hits': 0,
        'cache_misses': 0,
        'avg_search_time': 0.0,
        'last_reset': datetime.now()
    }


def update_search_stats(search_time: float) -> None:
    """Update search performance statistics."""
    _search_performance_stats['total_searches'] += 1
    _search_performance_stats['total_search_time'] += search_time
    _search_performance_stats['avg_search_time'] = (
        _search_performance_stats['total_search_time'] / 
        _search_performance_stats['total_searches']
    )
"""Memory storage and retrieval operations for AIAML."""

import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
import tempfile
import fcntl
import errno
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict

from .config import Config
from .errors import ErrorResponse, error_handler, ErrorCategory


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


def _get_cached_memory(file_path: Path) -> Optional[Dict[str, Any]]:
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


def _cache_memory(file_path: Path, memory_data: Dict[str, Any]) -> None:
    """Cache a memory for faster future access."""
    cache_key = str(file_path)
    
    # Clean expired entries and manage size
    _clean_expired_cache()
    _manage_cache_size()
    
    # Add to cache
    _memory_cache[cache_key] = memory_data
    _cache_timestamps[cache_key] = datetime.now()
    _search_performance_stats['cache_misses'] += 1


def _calculate_advanced_relevance_score(memory_data: Dict[str, Any], keywords: List[str]) -> float:
    """
    Calculate advanced relevance score using multiple factors:
    - Keyword frequency and position
    - Topic matching with fuzzy matching
    - Content length normalization
    - Recency boost
    """
    score = 0.0
    content = memory_data.get('content', '').lower()
    topics = [topic.lower() for topic in memory_data.get('topics', [])]
    
    # Normalize keywords
    normalized_keywords = [kw.lower().strip() for kw in keywords]
    
    for keyword in normalized_keywords:
        if not keyword:
            continue
            
        # 1. Exact content matches with position weighting
        content_matches = []
        start = 0
        while True:
            pos = content.find(keyword, start)
            if pos == -1:
                break
            content_matches.append(pos)
            start = pos + 1
        
        # Weight matches by position (earlier matches get higher scores)
        content_length = len(content) if content else 1
        for pos in content_matches:
            position_weight = 1.0 - (pos / content_length) * 0.3  # Up to 30% reduction for later positions
            score += 2.0 * position_weight
        
        # 2. Topic matching with fuzzy matching
        for topic in topics:
            if keyword in topic:
                # Exact substring match
                score += 5.0
            elif len(keyword) >= 3:
                # Fuzzy matching for longer keywords
                # Simple fuzzy matching: check if most characters are present
                keyword_chars = set(keyword)
                topic_chars = set(topic)
                overlap = len(keyword_chars.intersection(topic_chars))
                if overlap >= len(keyword_chars) * 0.7:  # 70% character overlap
                    score += 3.0
        
        # 3. Word boundary matches (higher weight for complete words)
        word_pattern = r'\b' + re.escape(keyword) + r'\b'
        word_matches = len(re.findall(word_pattern, content))
        score += word_matches * 1.5
        
        # 4. Partial word matches
        partial_matches = len(re.findall(re.escape(keyword), content)) - word_matches
        score += partial_matches * 0.5
    
    # 5. Content length normalization (prevent bias toward very long content)
    if content:
        length_factor = min(1.0, 1000 / len(content))  # Normalize around 1000 characters
        score *= (0.7 + 0.3 * length_factor)
    
    # 6. Recency boost (newer memories get slight preference)
    try:
        timestamp_str = memory_data.get('timestamp', '')
        if timestamp_str:
            # Parse ISO timestamp
            memory_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            age_days = (datetime.now() - memory_time.replace(tzinfo=None)).days
            recency_boost = max(0.0, 1.0 - (age_days / 365))  # Boost decreases over a year
            score *= (1.0 + recency_boost * 0.1)  # Up to 10% boost for recent memories
    except (ValueError, TypeError):
        pass  # Skip recency boost if timestamp parsing fails
    
    return score


def _build_search_index(memory_files: List[Path]) -> Dict[str, List[Tuple[Path, Dict[str, Any]]]]:
    """
    Build an inverted index for faster keyword searching.
    Returns a dictionary mapping keywords to lists of (file_path, memory_data) tuples.
    """
    index = defaultdict(list)
    
    for file_path in memory_files:
        # Try to get from cache first
        memory_data = _get_cached_memory(file_path)
        
        if memory_data is None:
            # Parse file and cache it
            memory_data = parse_memory_file_safe(file_path)
            if memory_data:
                _cache_memory(file_path, memory_data)
        
        if not memory_data:
            continue
        
        # Extract all words from content and topics for indexing
        content = memory_data.get('content', '').lower()
        topics = memory_data.get('topics', [])
        
        # Index content words
        content_words = re.findall(r'\b\w+\b', content)
        for word in content_words:
            if len(word) >= 2:  # Only index words with 2+ characters
                index[word].append((file_path, memory_data))
        
        # Index topic words
        for topic in topics:
            topic_words = re.findall(r'\b\w+\b', topic.lower())
            for word in topic_words:
                if len(word) >= 2:
                    index[word].append((file_path, memory_data))
    
    return index


def search_memories_optimized(keywords: List[str], config: Config) -> List[Dict[str, Any]]:
    """
    Optimized memory search with caching, better algorithms, and performance monitoring.
    
    Features:
    - File caching for frequently accessed memories
    - Advanced relevance scoring with multiple factors
    - Inverted index for faster keyword matching
    - Performance monitoring and logging
    - Optimized for large datasets (10,000+ memories)
    
    Args:
        keywords: List of keywords to search for
        config: Server configuration
        
    Returns:
        List of matching memories with relevance scores
    """
    logger = logging.getLogger('aiaml.memory_search')
    start_time = time.time()
    
    try:
        # Update performance stats
        _search_performance_stats['total_searches'] += 1
        
        # Validate input
        if not keywords or not isinstance(keywords, list):
            return []
        
        # Clean and normalize keywords
        normalized_keywords = [kw.lower().strip() for kw in keywords if kw and isinstance(kw, str)]
        if not normalized_keywords:
            return []
        
        logger.debug(f"Starting optimized search for keywords: {normalized_keywords}")
        
        # Get all memory files
        memory_files = list(config.memory_dir.glob("*.md"))
        if not memory_files:
            logger.debug("No memory files found")
            return []
        
        logger.debug(f"Found {len(memory_files)} memory files to search")
        
        # Build search index for faster lookups
        search_index = _build_search_index(memory_files)
        
        # Find candidate memories using the index
        candidate_memories = {}  # Use dict to avoid duplicates by file path
        for keyword in normalized_keywords:
            # Direct keyword matches
            if keyword in search_index:
                for file_path, memory_data in search_index[keyword]:
                    candidate_memories[str(file_path)] = memory_data
            
            # Partial matches for longer keywords
            if len(keyword) >= 3:
                for indexed_word in search_index:
                    if keyword in indexed_word or indexed_word in keyword:
                        for file_path, memory_data in search_index[indexed_word]:
                            candidate_memories[str(file_path)] = memory_data
        
        logger.debug(f"Found {len(candidate_memories)} candidate memories")
        
        # Calculate relevance scores for candidates
        scored_results = []
        for file_path_str, memory_data in candidate_memories.items():
            score = _calculate_advanced_relevance_score(memory_data, keywords)
            
            if score > 0:
                scored_results.append({
                    'memory_id': memory_data['id'],
                    'agent': memory_data.get('agent'),
                    'user': memory_data.get('user'),
                    'topics': memory_data.get('topics', []),
                    'content_preview': memory_data.get('content', '')[:200] + "..." if len(memory_data.get('content', '')) > 200 else memory_data.get('content', ''),
                    'timestamp': memory_data.get('timestamp'),
                    'relevance_score': score
                })
        
        # Sort by relevance score (descending) and limit results
        scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        final_results = scored_results[:config.max_search_results]
        
        # Log performance metrics
        search_time = time.time() - start_time
        _search_performance_stats['total_search_time'] += search_time
        _search_performance_stats['avg_search_time'] = (
            _search_performance_stats['total_search_time'] / 
            _search_performance_stats['total_searches']
        )
        
        logger.info(
            f"Search completed in {search_time:.3f}s, found {len(final_results)} results",
            extra={
                'operation': 'search_memories_optimized',
                'keywords': keywords,
                'search_time': search_time,
                'results_count': len(final_results),
                'candidates_count': len(candidate_memories),
                'cache_hits': _search_performance_stats['cache_hits'],
                'cache_misses': _search_performance_stats['cache_misses']
            }
        )
        
        return final_results
        
    except Exception as e:
        search_time = time.time() - start_time
        logger.error(f"Error in optimized search after {search_time:.3f}s: {e}", exc_info=True)
        
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'search_memories_optimized',
            'keywords': keywords,
            'search_time': search_time
        })
        return [error_response.to_dict()]


def get_search_performance_stats() -> Dict[str, Any]:
    """
    Get current search performance statistics.
    
    Returns:
        Dictionary containing performance metrics
    """
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


def clear_memory_cache() -> None:
    """Clear the memory cache."""
    global _memory_cache, _cache_timestamps
    _memory_cache.clear()
    _cache_timestamps.clear()


def generate_memory_id() -> str:
    """Generate a unique 8-character memory ID."""
    return str(uuid.uuid4()).replace("-", "")[:8]


def create_timestamp() -> str:
    """Create a timestamp string for file naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_memory_filename(memory_id: str) -> str:
    """Create a memory filename with timestamp and ID."""
    timestamp = create_timestamp()
    return f"{timestamp}_{memory_id}.md"


def parse_memory_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a memory file and extract metadata and content."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Split frontmatter and content
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                memory_content = parts[2].strip()
                
                # Parse frontmatter as YAML-like format
                frontmatter = {}
                for line in frontmatter_text.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Handle list values (topics)
                        if value.startswith('[') and value.endswith(']'):
                            # Parse as JSON array
                            try:
                                frontmatter[key] = json.loads(value)
                            except json.JSONDecodeError:
                                # Fallback: split by comma and clean up
                                items = value[1:-1].split(',')
                                frontmatter[key] = [item.strip().strip('"\'') for item in items if item.strip()]
                        else:
                            frontmatter[key] = value
                
                return {
                    'id': frontmatter.get('id'),
                    'timestamp': frontmatter.get('timestamp'),
                    'agent': frontmatter.get('agent'),
                    'user': frontmatter.get('user'),
                    'topics': frontmatter.get('topics', []),
                    'content': memory_content,
                    'file_path': str(file_path)
                }
        
        return None
        
    except Exception as e:
        logging.getLogger('aiaml.memory').error(f"Error parsing memory file {file_path}: {e}")
        return None


def parse_memory_file_safe(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a memory file with comprehensive error handling and graceful recovery."""
    try:
        return parse_memory_file(file_path)
    except Exception as e:
        # Handle corrupted memory files gracefully
        error_response = error_handler.handle_memory_error(e, {
            'file_path': str(file_path),
            'operation': 'parse_memory_file_safe'
        })
        
        # Log the error but continue processing other files
        logger = logging.getLogger('aiaml.memory_recovery')
        logger.warning(
            f"Skipping corrupted memory file {file_path.name}: {error_response.message}",
            extra={
                'operation': 'memory_file_recovery',
                'file_path': str(file_path),
                'error_code': error_response.error_code
            }
        )
        
        return None




def recall_memories(memory_ids: List[str], config: Config) -> List[Dict[str, Any]]:
    """Retrieve full memory details by IDs."""
    try:
        results = []
        memory_files = list(config.memory_dir.glob("*.md"))
        
        for memory_id in memory_ids:
            try:
                found = False
                for file_path in memory_files:
                    try:
                        memory_data = parse_memory_file_safe(file_path)
                        if memory_data and memory_data.get('id') == memory_id:
                            results.append(memory_data)
                            found = True
                            break
                    except Exception as e:
                        # Log file processing errors but continue searching
                        logging.getLogger('aiaml.memory').warning(
                            f"Error processing memory file {file_path.name} during recall: {e}"
                        )
                        continue
                
                if not found:
                    # Create a specific error response for not found memory
                    not_found_error = error_handler.handle_memory_error(
                        FileNotFoundError(f"Memory with ID {memory_id} not found"),
                        {
                            'memory_id': memory_id,
                            'operation': 'recall'
                        }
                    )
                    results.append(not_found_error.to_dict())
                    
            except Exception as e:
                # Handle individual memory retrieval errors
                memory_error = error_handler.handle_memory_error(e, {
                    'memory_id': memory_id,
                    'operation': 'recall_individual'
                })
                results.append(memory_error.to_dict())
        
        return results
                
    except Exception as e:
        # Handle unexpected errors with proper error response
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'recall',
            'memory_ids': memory_ids if isinstance(memory_ids, list) else str(memory_ids),
            'memory_ids_count': len(memory_ids) if isinstance(memory_ids, list) else 0
        })
        
        return [error_response.to_dict()]


def sync_to_github(memory_id: str, filename: str) -> None:
    """
    Sync a new memory file to GitHub repository in the background.
    
    This function runs in a separate thread and handles Git operations
    with retry logic and comprehensive error handling.
    """
    logger = logging.getLogger('aiaml.git_sync')
    
    try:
        # Get the memory directory parent (should contain .git)
        memory_dir = Path("memory")
        git_dir = memory_dir / ".git"
        
        if not git_dir.exists():
            logger.warning("Git repository not initialized, skipping sync")
            return
        
        # Add the new file to Git
        try:
            subprocess.run(
                ["git", "add", f"files/{filename}"],
                check=True,
                capture_output=True,
                cwd=memory_dir,
                timeout=30
            )
            
            # Commit the new memory
            commit_message = f"Add memory {memory_id}"
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True,
                capture_output=True,
                cwd=memory_dir,
                timeout=30
            )
            
            # Push to remote if configured
            remote_url = os.getenv("AIAML_GITHUB_REMOTE")
            if remote_url:
                try:
                    subprocess.run(
                        ["git", "push", "origin", "main"],
                        check=True,
                        capture_output=True,
                        cwd=memory_dir,
                        timeout=60
                    )
                    logger.info(f"Memory {memory_id} synced to GitHub successfully")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to push memory {memory_id} to GitHub: {e}")
            else:
                logger.debug(f"Memory {memory_id} committed locally (no remote configured)")
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git operation failed for memory {memory_id}: {e}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Git operation timed out for memory {memory_id}")
            
    except Exception as e:
        logger.error(f"Unexpected error during Git sync for memory {memory_id}: {e}")


def validate_memory_input(agent: str, user: str, topics: List[str], content: str) -> Optional[ErrorResponse]:
    """Validate memory input parameters."""
    try:
        # Validate agent
        if not agent or not isinstance(agent, str) or len(agent.strip()) == 0:
            raise ValueError("Agent name is required and must be a non-empty string")
        
        # Validate user
        if not user or not isinstance(user, str) or len(user.strip()) == 0:
            raise ValueError("User identifier is required and must be a non-empty string")
        
        # Validate topics
        if not isinstance(topics, list):
            raise ValueError("Topics must be a list")
        
        for topic in topics:
            if not isinstance(topic, str) or len(topic.strip()) == 0:
                raise ValueError("Each topic must be a non-empty string")
        
        # Validate content
        if not content or not isinstance(content, str) or len(content.strip()) == 0:
            raise ValueError("Content is required and must be a non-empty string")
        
        # Additional validation rules
        if len(agent.strip()) > 50:
            raise ValueError("Agent name must be 50 characters or less")
        
        if len(user.strip()) > 50:
            raise ValueError("User identifier must be 50 characters or less")
        
        if len(topics) > 20:
            raise ValueError("Maximum 20 topics allowed")
        
        for topic in topics:
            if len(topic.strip()) > 30:
                raise ValueError("Each topic must be 30 characters or less")
        
        if len(content.strip()) > 100000:  # 100KB limit
            raise ValueError("Content must be 100,000 characters or less")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'agent': agent,
            'user': user,
            'topics_count': len(topics) if isinstance(topics, list) else 0,
            'content_length': len(content) if isinstance(content, str) else 0
        })


def validate_search_input(keywords: List[str]) -> Optional[ErrorResponse]:
    """Validate search input parameters."""
    try:
        # Validate keywords
        if not isinstance(keywords, list):
            raise ValueError("Keywords must be a list")
        
        if len(keywords) == 0:
            raise ValueError("At least one keyword is required")
        
        if len(keywords) > 10:
            raise ValueError("Maximum 10 keywords allowed")
        
        for keyword in keywords:
            if not isinstance(keyword, str) or len(keyword.strip()) == 0:
                raise ValueError("Each keyword must be a non-empty string")
            
            if len(keyword.strip()) > 50:
                raise ValueError("Each keyword must be 50 characters or less")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'keywords_count': len(keywords) if isinstance(keywords, list) else 0,
            'keywords': keywords if isinstance(keywords, list) else None
        })


def validate_recall_input(memory_ids: List[str]) -> Optional[ErrorResponse]:
    """Validate recall input parameters."""
    try:
        # Validate memory_ids
        if not isinstance(memory_ids, list):
            raise ValueError("Memory IDs must be a list")
        
        if len(memory_ids) == 0:
            raise ValueError("At least one memory ID is required")
        
        if len(memory_ids) > 50:
            raise ValueError("Maximum 50 memory IDs allowed")
        
        for memory_id in memory_ids:
            if not isinstance(memory_id, str) or len(memory_id.strip()) == 0:
                raise ValueError("Each memory ID must be a non-empty string")
            
            # Validate memory ID format (8 character alphanumeric)
            if not re.match(r'^[a-f0-9]{8}$', memory_id.strip()):
                raise ValueError(f"Invalid memory ID format: {memory_id}")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'memory_ids_count': len(memory_ids) if isinstance(memory_ids, list) else 0,
            'memory_ids': memory_ids if isinstance(memory_ids, list) else None
        })
def acquire_file_lock(lock_file_path: Path, timeout: int = 10) -> Optional[int]:
    """
    Acquire an exclusive lock on a file with timeout.
    
    Args:
        lock_file_path: Path to the lock file
        timeout: Maximum time to wait for lock in seconds
        
    Returns:
        File descriptor if lock acquired, None if failed
    """
    try:
        # Create lock file if it doesn't exist
        if not lock_file_path.exists():
            lock_file_path.touch()
            
        # Open the lock file
        lock_fd = os.open(str(lock_file_path), os.O_RDWR)
        
        # Try to acquire the lock with timeout
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                # Try non-blocking lock
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_fd  # Lock acquired
            except (IOError, OSError) as e:
                # Check if it's a "would block" error
                if e.errno != errno.EWOULDBLOCK:
                    os.close(lock_fd)
                    raise
                # Wait a bit before retrying
                time.sleep(0.1)
        
        # Timeout reached
        os.close(lock_fd)
        return None
        
    except Exception as e:
        logger = logging.getLogger('aiaml.memory')
        logger.error(f"Failed to acquire file lock: {e}")
        if 'lock_fd' in locals():
            try:
                os.close(lock_fd)
            except:
                pass
        return None


def release_file_lock(lock_fd: int) -> bool:
    """
    Release a previously acquired file lock.
    
    Args:
        lock_fd: File descriptor returned by acquire_file_lock
        
    Returns:
        True if lock released successfully, False otherwise
    """
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        return True
    except Exception as e:
        logger = logging.getLogger('aiaml.memory')
        logger.error(f"Failed to release file lock: {e}")
        return False


def store_memory_atomic(agent: str, user: str, topics: List[str], content: str, config: Config) -> Dict[str, Any]:
    """
    Store a new memory with atomic file operations and file locking to prevent concurrent write conflicts.
    
    This function implements:
    1. File locking to prevent concurrent write conflicts
    2. Temporary file creation in a secure manner
    3. Atomic rename to ensure file consistency
    4. Comprehensive error handling for all storage operations
    
    Args:
        agent: Name of the agent creating the memory
        user: User identifier
        topics: List of topics for the memory
        content: Memory content text
        config: Server configuration
        
    Returns:
        Dictionary with operation result
    """
    logger = logging.getLogger('aiaml.memory')
    lock_fd = None
    temp_file = None
    
    try:
        # Validate input parameters
        validation_error = validate_memory_input(agent, user, topics, content)
        if validation_error:
            return validation_error.to_dict()
        
        # Generate unique memory ID and filename
        memory_id = generate_memory_id()
        filename = create_memory_filename(memory_id)
        file_path = config.memory_dir / filename
        
        # Ensure memory directory exists
        config.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Create lock file path
        lock_file_path = config.memory_dir / ".memory_lock"
        
        # Acquire lock with timeout
        logger.debug(f"Attempting to acquire lock for memory storage: {memory_id}")
        lock_fd = acquire_file_lock(lock_file_path)
        if lock_fd is None:
            error_msg = "Failed to acquire lock for memory storage (timeout)"
            logger.error(error_msg)
            error_response = ErrorResponse(
                error="Memory storage failed",
                error_code="MEMORY_LOCK_TIMEOUT",
                message=error_msg,
                timestamp=datetime.now().isoformat(),
                category=ErrorCategory.MEMORY_OPERATION.value,
                context={
                    'memory_id': memory_id,
                    'operation': 'store_memory_atomic'
                }
            )
            return error_response.to_dict()
        
        logger.debug(f"Lock acquired for memory storage: {memory_id}")
        
        # Create memory metadata
        timestamp = datetime.now().isoformat()
        
        # Create memory file content with frontmatter
        memory_content = f"""---
id: {memory_id}
timestamp: {timestamp}
agent: {agent}
user: {user}
topics: {json.dumps(topics)}
---

{content}"""
        
        # Create a secure temporary file in the same directory
        try:
            # Use tempfile for secure temporary file creation
            fd, temp_path = tempfile.mkstemp(dir=str(config.memory_dir), suffix='.tmp')
            temp_file = Path(temp_path)
            
            # Write content to temporary file
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(memory_content)
                # Ensure data is written to disk
                f.flush()
                os.fsync(fd)
            
            # Perform atomic rename
            temp_file.rename(file_path)
            logger.debug(f"Memory file created successfully: {file_path}")
            
            # Sync to Git in background if enabled
            if config.enable_git_sync:
                threading.Thread(
                    target=sync_to_github,
                    args=(memory_id, filename),
                    daemon=True
                ).start()
            
            return {
                "memory_id": memory_id,
                "message": f"Memory stored successfully with ID: {memory_id}",
                "timestamp": timestamp,
                "filename": filename
            }
            
        except Exception as e:
            # Handle specific file operation errors
            if isinstance(e, PermissionError):
                error_code = "MEMORY_PERMISSION_DENIED"
                message = f"Permission denied when writing memory file: {e}"
            elif isinstance(e, OSError) and e.errno == errno.ENOSPC:
                error_code = "MEMORY_NO_SPACE"
                message = "No space left on device for memory storage"
            elif isinstance(e, OSError):
                error_code = "MEMORY_IO_ERROR"
                message = f"File system error during memory storage: {e}"
            else:
                error_code = "MEMORY_STORAGE_ERROR"
                message = f"Failed to store memory: {e}"
            
            logger.error(message, exc_info=True)
            error_response = ErrorResponse(
                error="Memory storage failed",
                error_code=error_code,
                message=message,
                timestamp=datetime.now().isoformat(),
                category=ErrorCategory.MEMORY_OPERATION.value,
                context={
                    'memory_id': memory_id,
                    'operation': 'store_memory_atomic',
                    'file_path': str(file_path)
                }
            )
            return error_response.to_dict()
            
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in store_memory_atomic: {e}", exc_info=True)
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'store_memory_atomic',
            'agent': agent,
            'user': user,
            'topics': topics
        })
        return error_response.to_dict()
        
    finally:
        # Always release lock and clean up temporary file if needed
        if lock_fd is not None:
            release_file_lock(lock_fd)
            logger.debug("Released memory storage lock")
            
        # Clean up temporary file if it still exists
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
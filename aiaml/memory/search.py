"""Memory search functionality with optimization and caching."""

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import defaultdict

from ..config import Config
from ..errors import error_handler
from .cache import get_cached_memory, cache_memory, update_search_stats
from .core import parse_memory_file_safe
# Performance monitoring removed for simplicity


def _get_matching_topics(memory_topics: List[str], keywords: List[str]) -> List[str]:
    """
    Filter topics to return only those that match the search keywords.
    
    Args:
        memory_topics: List of topics from a memory
        keywords: List of search keywords
        
    Returns:
        List of topics that match any of the search keywords
    """
    if not memory_topics or not keywords:
        return []
    
    matching_topics = []
    normalized_keywords = [kw.lower().strip() for kw in keywords]
    
    for topic in memory_topics:
        topic_lower = topic.lower()
        for keyword in normalized_keywords:
            if not keyword:
                continue
            
            # Check if keyword matches topic (substring match)
            if keyword in topic_lower:
                matching_topics.append(topic)
                break  # Avoid adding the same topic multiple times
    
    return matching_topics


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
        memory_data = get_cached_memory(file_path)
        
        if memory_data is None:
            # Parse file and cache it
            memory_data = parse_memory_file_safe(file_path)
            if memory_data:
                cache_memory(file_path, memory_data)
        
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
                    'matching_topics': _get_matching_topics(memory_data.get('topics', []), keywords),
                    'memory_topics': memory_data.get('topics', []),
                    'content_preview': memory_data.get('content', '')[:200] + "..." if len(memory_data.get('content', '')) > 200 else memory_data.get('content', ''),
                    'content_preview_is_truncated': len(memory_data.get('content', '')) > 200,
                    'timestamp': memory_data.get('timestamp'),
                    'relevance_score': score
                })
        
        # Sort by relevance score (descending) and limit results
        scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        final_results = scored_results[:config.max_search_results]
        
        # Update performance metrics
        search_time = time.time() - start_time
        update_search_stats(search_time)
        
        logger.info(f"Search completed in {search_time:.3f}s, found {len(final_results)} results")
        
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
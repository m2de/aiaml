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
    - Topic matching with precise fuzzy matching
    - Content length normalization
    - Recency boost (only for relevant memories)
    - Minimum relevance threshold to filter out irrelevant memories
    """
    score = 0.0
    content = memory_data.get('content', '').lower()
    topics = [topic.lower() for topic in memory_data.get('topics', [])]
    
    # Normalize keywords
    normalized_keywords = [kw.lower().strip() for kw in keywords if kw and kw.strip()]
    if not normalized_keywords:
        return 0.0
    
    # Track if any keyword has a meaningful match
    has_relevant_match = False
    keyword_matches = {}  # Track matches per keyword for better scoring
    
    for keyword in normalized_keywords:
        keyword_score = 0.0
        keyword_has_match = False
        
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
        if content_matches:
            content_length = len(content) if content else 1
            for pos in content_matches:
                position_weight = 1.0 - (pos / content_length) * 0.2  # Reduced penalty for later positions
                keyword_score += 2.0 * position_weight
                keyword_has_match = True
        
        # 2. Topic matching with improved fuzzy matching
        for topic in topics:
            if keyword in topic:
                # Exact substring match in topic (high value)
                keyword_score += 6.0
                keyword_has_match = True
            elif len(keyword) >= 4:  # More restrictive fuzzy matching
                # Use Levenshtein-like distance for better fuzzy matching
                # Check if keyword and topic share enough consecutive characters
                max_consecutive = 0
                for i in range(len(topic) - len(keyword) + 1):
                    consecutive = 0
                    for j in range(len(keyword)):
                        if i + j < len(topic) and topic[i + j] == keyword[j]:
                            consecutive += 1
                        else:
                            break
                    max_consecutive = max(max_consecutive, consecutive)
                
                # Only consider it a fuzzy match if significant portion matches consecutively
                if max_consecutive >= len(keyword) * 0.8:  # 80% consecutive match
                    keyword_score += 2.5
                    keyword_has_match = True
        
        # 3. Word boundary matches (higher weight for complete words)
        word_pattern = r'\b' + re.escape(keyword) + r'\b'
        word_matches = len(re.findall(word_pattern, content))
        if word_matches > 0:
            keyword_score += word_matches * 2.5  # Increased weight for complete words
            keyword_has_match = True
        
        # 4. Partial word matches (only if we haven't found complete words)
        if word_matches == 0:
            partial_matches = len(re.findall(re.escape(keyword), content))
            if partial_matches > 0:
                keyword_score += partial_matches * 0.3  # Reduced weight for partial matches
                keyword_has_match = True
        
        # Track keyword match status
        keyword_matches[keyword] = keyword_score
        if keyword_has_match:
            has_relevant_match = True
        
        score += keyword_score
    
    # Early return if no relevant matches found
    if not has_relevant_match:
        return 0.0
    
    # Apply minimum relevance threshold
    MIN_RELEVANCE_THRESHOLD = 0.5
    if score < MIN_RELEVANCE_THRESHOLD:
        return 0.0
    
    # 5. Keyword coverage bonus (rewards memories that match multiple keywords)
    matched_keywords = sum(1 for s in keyword_matches.values() if s > 0)
    if len(normalized_keywords) > 1:
        coverage_ratio = matched_keywords / len(normalized_keywords)
        score *= (1.0 + coverage_ratio * 0.3)  # Up to 30% bonus for matching multiple keywords
    
    # 6. Content length normalization (prevent bias toward very long content)
    if content:
        # More nuanced length normalization
        content_length = len(content)
        if content_length <= 500:
            length_factor = 1.0  # No penalty for short content
        elif content_length <= 2000:
            length_factor = 0.95  # Small penalty for medium content
        else:
            length_factor = max(0.8, 2000 / content_length)  # Larger penalty for very long content
        score *= length_factor
    
    # 7. Recency boost (only for memories that are already relevant)
    if score > 0:  # Only apply recency boost to relevant memories
        try:
            timestamp_str = memory_data.get('timestamp', '')
            if timestamp_str:
                # Parse ISO timestamp
                memory_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                age_days = (datetime.now() - memory_time.replace(tzinfo=None)).days
                recency_boost = max(0.0, 1.0 - (age_days / 180))  # Boost over 6 months instead of a year
                score *= (1.0 + recency_boost * 0.05)  # Reduced to 5% max boost
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
        
        # Find candidate memories using the index with improved precision
        candidate_memories = {}  # Use dict to avoid duplicates by file path
        for keyword in normalized_keywords:
            # Direct keyword matches (exact word matches)
            if keyword in search_index:
                for file_path, memory_data in search_index[keyword]:
                    candidate_memories[str(file_path)] = memory_data
            
            # More precise partial matches for longer keywords
            if len(keyword) >= 4:  # Increased minimum length for partial matching
                for indexed_word in search_index:
                    # More restrictive partial matching conditions
                    if len(indexed_word) >= 3:  # Only match against reasonably long words
                        # Check for meaningful overlap
                        if (keyword in indexed_word and len(keyword) >= len(indexed_word) * 0.7) or \
                           (indexed_word in keyword and len(indexed_word) >= len(keyword) * 0.7):
                            for file_path, memory_data in search_index[indexed_word]:
                                candidate_memories[str(file_path)] = memory_data
                        # Also check for common prefixes/suffixes for related terms
                        elif len(keyword) >= 5 and len(indexed_word) >= 5:
                            # Check for common prefix or suffix of at least 4 characters
                            if (keyword[:4] == indexed_word[:4] and abs(len(keyword) - len(indexed_word)) <= 3) or \
                               (keyword[-4:] == indexed_word[-4:] and abs(len(keyword) - len(indexed_word)) <= 3):
                                for file_path, memory_data in search_index[indexed_word]:
                                    candidate_memories[str(file_path)] = memory_data
        
        logger.debug(f"Found {len(candidate_memories)} candidate memories")
        
        # Calculate relevance scores for candidates
        scored_results = []
        for file_path_str, memory_data in candidate_memories.items():
            score = _calculate_advanced_relevance_score(memory_data, keywords)
            
            # Only include results that pass the relevance threshold
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
        
        # Sort by relevance score (descending) and apply tiered result limiting
        scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Implement tiered results: ensure high-quality results while still including lower ones
        if scored_results:
            max_results = config.max_search_results
            
            # Get the top scoring result's score for comparison
            top_score = scored_results[0]['relevance_score']
            
            # Tier 1: High relevance results (within 70% of top score)
            tier1_threshold = top_score * 0.7
            tier1_results = [r for r in scored_results if r['relevance_score'] >= tier1_threshold]
            
            # Tier 2: Medium relevance results (within 40% of top score)  
            tier2_threshold = top_score * 0.4
            tier2_results = [r for r in scored_results if tier2_threshold <= r['relevance_score'] < tier1_threshold]
            
            # Tier 3: Lower relevance results (everything else)
            tier3_results = [r for r in scored_results if r['relevance_score'] < tier2_threshold]
            
            # Combine tiers with appropriate limits
            final_results = []
            
            # Always include tier 1 results (up to max_results)
            final_results.extend(tier1_results[:max_results])
            
            # Add tier 2 results if we have room (up to 50% of remaining space)
            remaining_slots = max_results - len(final_results)
            if remaining_slots > 0:
                tier2_limit = max(1, remaining_slots // 2)
                final_results.extend(tier2_results[:tier2_limit])
            
            # Add tier 3 results if we still have room
            remaining_slots = max_results - len(final_results)
            if remaining_slots > 0:
                final_results.extend(tier3_results[:remaining_slots])
        else:
            final_results = []
        
        # Update performance metrics
        search_time = time.time() - start_time
        update_search_stats(search_time)
        
        # Enhanced logging with tier information
        if final_results:
            tier_info = ""
            if scored_results:
                top_score = scored_results[0]['relevance_score']
                tier1_count = len([r for r in final_results if r['relevance_score'] >= top_score * 0.7])
                tier2_count = len([r for r in final_results if top_score * 0.4 <= r['relevance_score'] < top_score * 0.7])
                tier3_count = len(final_results) - tier1_count - tier2_count
                tier_info = f" (T1:{tier1_count}, T2:{tier2_count}, T3:{tier3_count})"
                
                logger.debug(f"Score distribution - Top: {top_score:.2f}, Min: {final_results[-1]['relevance_score']:.2f}")
            
            logger.info(f"Search completed in {search_time:.3f}s, found {len(final_results)} results{tier_info}")
        else:
            logger.info(f"Search completed in {search_time:.3f}s, no relevant results found")
        
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
"""Memory storage and retrieval operations for AIAML."""

import json
import re
import uuid
import threading
import subprocess
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .config import Config
from .errors import error_handler, ErrorResponse


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


def store_memory(agent: str, user: str, topics: List[str], content: str, config: Config) -> Dict[str, Any]:
    """Store a new memory with atomic file operations."""
    try:
        # Generate unique memory ID and filename
        memory_id = generate_memory_id()
        filename = create_memory_filename(memory_id)
        file_path = config.memory_dir / filename
        
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
        
        # Write file atomically
        temp_path = file_path.with_suffix('.tmp')
        temp_path.write_text(memory_content, encoding='utf-8')
        temp_path.rename(file_path)
        
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
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'store_memory',
            'agent': agent,
            'user': user,
            'topics': topics
        })
        return error_response.to_dict()


def search_memories(keywords: List[str], config: Config) -> List[Dict[str, Any]]:
    """Search for memories by keywords with relevance scoring."""
    try:
        results = []
        memory_files = list(config.memory_dir.glob("*.md"))
        
        for file_path in memory_files:
            memory_data = parse_memory_file_safe(file_path)
            if not memory_data:
                continue
            
            # Calculate relevance score
            score = 0
            content_lower = memory_data.get('content', '').lower()
            topics_lower = [topic.lower() for topic in memory_data.get('topics', [])]
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                
                # Score for content matches
                content_matches = len(re.findall(re.escape(keyword_lower), content_lower))
                score += content_matches * 2
                
                # Score for topic matches (higher weight)
                for topic in topics_lower:
                    if keyword_lower in topic:
                        score += 5
            
            if score > 0:
                results.append({
                    'memory_id': memory_data['id'],
                    'agent': memory_data.get('agent'),
                    'user': memory_data.get('user'),
                    'topics': memory_data.get('topics', []),
                    'content_preview': memory_data.get('content', '')[:200] + "..." if len(memory_data.get('content', '')) > 200 else memory_data.get('content', ''),
                    'timestamp': memory_data.get('timestamp'),
                    'relevance_score': score
                })
        
        # Sort by relevance score (descending) and limit results
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:config.max_search_results]
        
    except Exception as e:
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'search_memories',
            'keywords': keywords
        })
        return [error_response.to_dict()]


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
#!/usr/bin/env python3
"""
AI Agnostic Memory Layer (AIAML) MCP Server

A simple local memory system for AI agents that provides persistent storage
and retrieval of memories using markdown files.
"""

import json
import re
import uuid
import threading
import subprocess
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("AI Agnostic Memory Layer")

# Memory storage directory
MEMORY_DIR = Path(__file__).parent / "memory" / "files"
MEMORY_DIR.mkdir(exist_ok=True, parents=True)

# Memory backup configuration
MEMORY_BACKUP_DIR = Path(__file__).parent / "memory"
ENABLE_GITHUB_SYNC = os.getenv("AIAML_ENABLE_SYNC", "true").lower() == "true"
GITHUB_REMOTE_URL = os.getenv("AIAML_GITHUB_REMOTE", "")


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


def sync_to_github(memory_id: str, filename: str) -> None:
    """
    Sync a new memory file to GitHub repository in the background.
    
    Args:
        memory_id: The memory ID that was created
        filename: The filename of the memory file
    """
    if not ENABLE_GITHUB_SYNC:
        return
    
    def _sync():
        try:
            # Add the new file
            subprocess.run(["git", "add", f"files/{filename}"], check=True, capture_output=True, cwd=MEMORY_BACKUP_DIR)
            
            # Create commit message
            commit_message = f"Add memory {memory_id} ({filename})"
            subprocess.run(["git", "commit", "-m", commit_message], check=True, capture_output=True, cwd=MEMORY_BACKUP_DIR)
            
            # Push to remote (always push, since we have remote configured)
            subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True, cwd=MEMORY_BACKUP_DIR)
                
        except subprocess.CalledProcessError as e:
            # Log error but don't fail the main operation
            print(f"GitHub sync failed for {memory_id}: {e}")
        except Exception as e:
            # Log any other errors
            print(f"Unexpected error during GitHub sync for {memory_id}: {e}")
    
    # Run sync in background thread
    thread = threading.Thread(target=_sync, daemon=True)
    thread.start()


def parse_memory_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a memory file and return its contents."""
    try:
        content = file_path.read_text(encoding="utf-8")
        
        # Split frontmatter and content
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                memory_content = parts[2].strip()
                
                # Parse frontmatter
                metadata = {}
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Handle topics as a list
                        if key == "topics":
                            # Remove brackets and split by comma
                            topics_str = value.strip("[]")
                            metadata[key] = [t.strip() for t in topics_str.split(",") if t.strip()]
                        else:
                            metadata[key] = value
                
                return {
                    "id": metadata.get("id", ""),
                    "timestamp": metadata.get("timestamp", ""),
                    "agent": metadata.get("agent", ""),
                    "user": metadata.get("user", ""),
                    "topics": metadata.get("topics", []),
                    "content": memory_content
                }
    except Exception:
        return None
    
    return None


def calculate_relevance_score(memory_data: Dict[str, Any], keywords: List[str]) -> Dict[str, Any]:
    """Calculate relevance score for a memory based on keyword matches."""
    if not keywords:
        return {"score": 0, "matching_keywords": []}
    
    keywords_lower = [k.lower() for k in keywords]
    topics_text = " ".join(memory_data.get("topics", [])).lower()
    content_text = memory_data.get("content", "").lower()
    user_text = memory_data.get("user", "").lower()
    agent_text = memory_data.get("agent", "").lower()
    
    matching_keywords = []
    topic_matches = 0
    content_matches = 0
    user_matches = 0
    agent_matches = 0
    exact_matches = 0
    
    for keyword in keywords_lower:
        # Count matches in topics (weighted 2x)
        topic_count = topics_text.count(keyword)
        if topic_count > 0:
            topic_matches += topic_count
            matching_keywords.append(keyword)
        
        # Count matches in content
        content_count = content_text.count(keyword)
        if content_count > 0:
            content_matches += content_count
            if keyword not in matching_keywords:
                matching_keywords.append(keyword)
        
        # Count matches in user field
        user_count = user_text.count(keyword)
        if user_count > 0:
            user_matches += user_count
            if keyword not in matching_keywords:
                matching_keywords.append(keyword)
        
        # Count matches in agent field
        agent_count = agent_text.count(keyword)
        if agent_count > 0:
            agent_matches += agent_count
            if keyword not in matching_keywords:
                matching_keywords.append(keyword)
        
        # Count exact word matches (bonus points)
        combined_text = f"{topics_text} {content_text} {user_text} {agent_text}"
        exact_word_matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', combined_text))
        if exact_word_matches > 0:
            exact_matches += exact_word_matches
    
    # Calculate relevance score: (topic_matches * 2) + content_matches + user_matches + agent_matches + exact_matches
    relevance_score = (topic_matches * 2) + content_matches + user_matches + agent_matches + exact_matches
    
    return {
        "score": relevance_score,
        "matching_keywords": list(set(matching_keywords))  # Remove duplicates
    }


def search_memories(keywords: List[str]) -> List[Dict[str, Any]]:
    """Search for memories containing the specified keywords, sorted by relevance."""
    results = []
    
    if not keywords:
        return results
    
    # Convert keywords to lowercase for case-insensitive search
    keywords_lower = [k.lower() for k in keywords]
    
    for memory_file in MEMORY_DIR.glob("*.md"):
        memory_data = parse_memory_file(memory_file)
        if not memory_data:
            continue
        
        # Calculate relevance score
        relevance_info = calculate_relevance_score(memory_data, keywords)
        
        # Only include memories that have at least one matching keyword
        if relevance_info["score"] > 0:
            results.append({
                "id": memory_data["id"],
                "timestamp": memory_data["timestamp"],
                "relevance_score": relevance_info["score"],
                "matching_keywords": relevance_info["matching_keywords"]
            })
    
    # Sort by relevance score (descending), then by timestamp (most recent first) as tiebreaker
    results.sort(key=lambda x: (x["relevance_score"], x["timestamp"]), reverse=True)
    
    # Limit to maximum 25 results
    return results[:25]


@mcp.tool()
def remember(agent: str, user: str, topics: List[str], content: str) -> Dict[str, str]:
    """
    Store a new memory entry.
    
    Args:
        agent: The AI agent name (e.g., "claude", "gemini", "chatgpt")
        user: The user identifier (e.g., "marco", "unknown")
        topics: List of keywords/domains for categorizing the memory (each keyword should be a single word, e.g. ["todo", "list"], not ["todo list"] or ["to_do_list"])
        content: The full content to remember
    
    Returns:
        Dictionary containing the memory ID and success message
    """
    try:
        # Generate unique memory ID
        memory_id = generate_memory_id()
        
        # Create timestamp
        timestamp = datetime.now().isoformat()
        
        # Create memory file content
        frontmatter = f"""---
id: {memory_id}
timestamp: {timestamp}
agent: {agent}
user: {user}
topics: [{', '.join(topics)}]
---

{content}"""
        
        # Create filename and save
        filename = create_memory_filename(memory_id)
        file_path = MEMORY_DIR / filename
        
        file_path.write_text(frontmatter, encoding="utf-8")
        
        # Trigger background sync to GitHub
        sync_to_github(memory_id, filename)
        
        return {
            "memory_id": memory_id,
            "message": f"Memory stored successfully with ID: {memory_id}"
        }
        
    except Exception as e:
        return {
            "memory_id": "",
            "message": f"Error storing memory: {str(e)}"
        }


@mcp.tool()
def think(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Search for relevant memories by keywords, sorted by relevance.
    
    Args:
        keywords: List of keywords to search for in memory topics and content
    
    Returns:
        List of up to 25 matching memories, sorted by relevance score (descending).
        Each memory contains:
        - id: Memory ID
        - timestamp: When the memory was created
        - relevance_score: Number indicating how well the memory matches the keywords
        - matching_keywords: List of keywords that matched in this memory (each keyword should be a single word, e.g. ["todo", "list"], not ["todo list"] or ["to_do_list"])
        
        Memories that match more keywords or have keywords in topics (vs content) 
        will have higher relevance scores and appear first.
    """
    try:
        return search_memories(keywords)
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]


@mcp.tool()
def recall(memory_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve full memory details by ID. Should use `think` first to get IDs.
    
    Args:
        memory_ids: List of memory IDs to retrieve
    
    Returns:
        List of complete memory objects with agent, user, topics, and content
    """
    results = []
    
    try:
        for memory_id in memory_ids:
            # Find the memory file by ID
            found = False
            for memory_file in MEMORY_DIR.glob(f"*_{memory_id}.md"):
                memory_data = parse_memory_file(memory_file)
                if memory_data and memory_data["id"] == memory_id:
                    results.append({
                        "id": memory_data["id"],
                        "timestamp": memory_data["timestamp"],
                        "agent": memory_data["agent"],
                        "user": memory_data["user"],
                        "topics": memory_data["topics"],
                        "content": memory_data["content"]
                    })
                    found = True
                    break
            
            if not found:
                results.append({
                    "id": memory_id,
                    "error": f"Memory with ID {memory_id} not found"
                })
                
    except Exception as e:
        results.append({"error": f"Recall failed: {str(e)}"})
    
    return results


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
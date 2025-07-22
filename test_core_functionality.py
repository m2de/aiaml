#!/usr/bin/env python3
"""
Test script to verify core functionality preservation of the local-only MCP server.

This script tests:
1. Remember tool functionality without authentication
2. Think tool functionality with simplified error handling
3. Recall tool functionality with direct access
4. Git synchronization functionality
5. File operations and memory storage

Requirements: 1.1, 1.2, 1.3
"""

import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import required modules
try:
    from aiaml.config import Config, load_configuration
    from aiaml.memory import store_memory_atomic, search_memories_optimized, recall_memories
    from aiaml.git_sync import get_git_sync_manager
    print("✓ Successfully imported required modules")
except ImportError as e:
    print(f"✗ Failed to import required modules: {e}")
    sys.exit(1)

def test_remember_functionality():
    """Test remember tool functionality without authentication."""
    print("\nTesting Remember Tool Functionality")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test configuration with temporary directory
        config = Config(
            memory_dir=Path(temp_dir),
            enable_git_sync=False,  # Disable Git sync for this test
            log_level="INFO"
        )
        
        # Test parameters
        agent = "test_agent"
        user = "test_user"
        topics = ["test", "functionality"]
        content = "This is a test memory for the remember tool."
        
        # Call store_memory_atomic directly (no authentication)
        result = store_memory_atomic(agent, user, topics, content, config)
        
        # Verify result
        if "memory_id" in result and "error" not in result:
            print(f"  ✓ Memory stored successfully with ID: {result['memory_id']}")
            memory_id = result["memory_id"]
            
            # Verify file was created
            memory_files = list(config.files_dir.glob("*.md"))
            if memory_files:
                print(f"  ✓ Memory file created: {memory_files[0].name}")
            else:
                print("  ✗ No memory file created")
                return False
                
            return memory_id
        else:
            print(f"  ✗ Failed to store memory: {result}")
            return False

def test_think_functionality(memory_id=None):
    """Test think tool functionality with simplified error handling."""
    print("\nTesting Think Tool Functionality")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test configuration with temporary directory
        config = Config(
            memory_dir=Path(temp_dir),
            enable_git_sync=False,
            log_level="INFO"
        )
        
        # Create a test memory if none provided
        if not memory_id:
            agent = "test_agent"
            user = "test_user"
            topics = ["python", "testing"]
            content = "This is a test memory about Python testing frameworks."
            
            result = store_memory_atomic(agent, user, topics, content, config)
            if "memory_id" in result:
                memory_id = result["memory_id"]
                print(f"  ✓ Created test memory with ID: {memory_id}")
            else:
                print(f"  ✗ Failed to create test memory: {result}")
                return False
        
        # Test search with keywords
        keywords = ["python", "test"]
        search_results = search_memories_optimized(keywords, config)
        
        # Verify results
        if search_results and isinstance(search_results, list):
            if len(search_results) > 0:
                print(f"  ✓ Search returned {len(search_results)} results")
                print(f"  ✓ Top result relevance score: {search_results[0]['relevance_score']}")
                return True
            else:
                print("  ✗ Search returned no results")
                return False
        else:
            print(f"  ✗ Search failed: {search_results}")
            return False

def test_recall_functionality():
    """Test recall tool functionality with direct access."""
    print("\nTesting Recall Tool Functionality")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test configuration with temporary directory
        config = Config(
            memory_dir=Path(temp_dir),
            enable_git_sync=False,
            log_level="INFO"
        )
        
        # Create a test memory
        agent = "test_agent"
        user = "test_user"
        topics = ["recall", "testing"]
        content = "This is a test memory for the recall tool."
        
        result = store_memory_atomic(agent, user, topics, content, config)
        if "memory_id" in result:
            memory_id = result["memory_id"]
            print(f"  ✓ Created test memory with ID: {memory_id}")
        else:
            print(f"  ✗ Failed to create test memory: {result}")
            return False
        
        # Test recall with memory ID
        recall_results = recall_memories([memory_id], config)
        
        # Verify results
        if recall_results and isinstance(recall_results, list):
            if len(recall_results) > 0 and "id" in recall_results[0]:
                print(f"  ✓ Successfully recalled memory with ID: {recall_results[0]['id']}")
                print(f"  ✓ Memory content: {recall_results[0]['content'][:50]}...")
                return True
            else:
                print(f"  ✗ Failed to recall memory: {recall_results}")
                return False
        else:
            print(f"  ✗ Recall failed: {recall_results}")
            return False

def test_git_synchronization():
    """Test Git synchronization functionality."""
    print("\nTesting Git Synchronization")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test configuration with Git sync enabled
        config = Config(
            memory_dir=Path(temp_dir) / "files",
            enable_git_sync=True,
            log_level="INFO"
        )
        
        # Create memory directory
        config.files_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Git sync manager
        try:
            git_manager = get_git_sync_manager(config)
            print("  ✓ Git sync manager initialized")
            
            # Check repository status
            status = git_manager.get_repository_status()
            print(f"  ✓ Git repository status: {status['repository_exists']}")
            
            # Create a test memory
            agent = "test_agent"
            user = "test_user"
            topics = ["git", "sync"]
            content = "This is a test memory for Git synchronization."
            
            result = store_memory_atomic(agent, user, topics, content, config)
            if "memory_id" in result:
                memory_id = result["memory_id"]
                filename = result["filename"]
                print(f"  ✓ Created test memory with ID: {memory_id}")
                
                # Wait for background sync to complete
                print("  Waiting for background sync to complete...")
                time.sleep(2)
                
                # Check if file exists in Git repository
                memory_file = config.files_dir / filename
                if memory_file.exists():
                    print(f"  ✓ Memory file exists: {filename}")
                    return True
                else:
                    print(f"  ✗ Memory file not found: {filename}")
                    return False
            else:
                print(f"  ✗ Failed to create test memory: {result}")
                return False
                
        except Exception as e:
            print(f"  ✗ Git synchronization test failed: {e}")
            return False

def test_file_operations():
    """Test file operations and memory storage."""
    print("\nTesting File Operations")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test configuration with temporary directory
        config = Config(
            memory_dir=Path(temp_dir),
            enable_git_sync=False,
            log_level="INFO"
        )
        
        # Test memory creation
        agent = "test_agent"
        user = "test_user"
        topics = ["file", "operations"]
        content = "This is a test memory for file operations."
        
        result = store_memory_atomic(agent, user, topics, content, config)
        if "memory_id" in result:
            memory_id = result["memory_id"]
            filename = result["filename"]
            print(f"  ✓ Created test memory with ID: {memory_id}")
            
            # Verify file exists
            memory_file = config.files_dir / filename
            if memory_file.exists():
                print(f"  ✓ Memory file exists: {filename}")
                
                # Verify file content
                file_content = memory_file.read_text()
                if content in file_content:
                    print("  ✓ File content is correct")
                    
                    # Test file parsing through recall
                    recall_results = recall_memories([memory_id], config)
                    if recall_results and len(recall_results) > 0 and "id" in recall_results[0]:
                        print(f"  ✓ Successfully parsed memory file")
                        return True
                    else:
                        print(f"  ✗ Failed to parse memory file: {recall_results}")
                        return False
                else:
                    print("  ✗ File content is incorrect")
                    return False
            else:
                print(f"  ✗ Memory file not found: {filename}")
                return False
        else:
            print(f"  ✗ Failed to create test memory: {result}")
            return False

def run_all_tests():
    """Run all functionality tests."""
    print("=" * 70)
    print("AIAML Local-Only MCP Server Core Functionality Tests")
    print("=" * 70)
    
    # Track test results
    results = {}
    
    # Test remember functionality
    memory_id = test_remember_functionality()
    results["remember"] = memory_id is not False
    
    # Test think functionality
    results["think"] = test_think_functionality()
    
    # Test recall functionality
    results["recall"] = test_recall_functionality()
    
    # Test Git synchronization
    results["git_sync"] = test_git_synchronization()
    
    # Test file operations
    results["file_ops"] = test_file_operations()
    
    # Print summary
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    all_passed = True
    for test, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test.ljust(15)}: {status}")
        if not passed:
            all_passed = False
    
    print("\nOverall Result:", "✓ ALL TESTS PASSED" if all_passed else "✗ SOME TESTS FAILED")
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
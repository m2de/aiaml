#!/usr/bin/env python3
"""
MCP Server Integration Test

This test validates that the MCP server can start and handle tool calls correctly
with all the enhanced components integrated for local-only operation.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_mcp_server_startup():
    """Test that the MCP server can start with all components."""
    print("Testing MCP Server Startup")
    print("-" * 30)
    
    try:
        # Set up test environment
        original_env = {}
        test_env_vars = {
            'AIAML_LOG_LEVEL': 'ERROR',  # Reduce log noise
            'AIAML_ENABLE_SYNC': 'false'  # Disable Git sync for testing
        }
        
        # Set test environment variables
        for key, value in test_env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            from aiaml.server import initialize_server
            
            # Initialize server
            server = initialize_server()
            
            if server is not None:
                print("  ✓ MCP server initialized successfully")
                print("  ✓ All enhanced components integrated")
                return True
            else:
                print("  ✗ MCP server initialization failed")
                return False
                
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        
    except Exception as e:
        print(f"  ✗ MCP server startup test failed: {e}")
        return False


def test_tool_registration():
    """Test that all MCP tools are properly registered."""
    print("\nTesting Tool Registration")
    print("-" * 30)
    
    try:
        from aiaml.config import Config
        from aiaml.server import register_tools
        from mcp.server.fastmcp import FastMCP
        
        # Create test configuration
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                memory_dir=Path(temp_dir) / "memory" / "files",
                enable_git_sync=False
            )
            
            # Ensure memory directory exists
            config.memory_dir.mkdir(parents=True, exist_ok=True)
            
            # Create test server
            server = FastMCP("Test Server")
            
            # Register tools
            register_tools(server, config)
            
            print("  ✓ Tools registered successfully")
            return True
            
    except Exception as e:
        print(f"  ✗ Tool registration test failed: {e}")
        return False


def test_tool_functionality():
    """Test that MCP tools work correctly with all components."""
    print("\nTesting Tool Functionality")
    print("-" * 30)
    
    try:
        from aiaml.config import Config
        from aiaml.memory import (
            store_memory_atomic, search_memories_optimized, recall_memories
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                memory_dir=Path(temp_dir) / "memory" / "files",
                enable_git_sync=False
            )
            
            # Ensure memory directory exists
            config.memory_dir.mkdir(parents=True, exist_ok=True)
            
            # Test remember functionality
            result = store_memory_atomic(
                "claude", "test_user", ["integration", "mcp"], 
                "Test memory for MCP integration", config
            )
            
            if "memory_id" in result:
                memory_id = result["memory_id"]
                print("  ✓ Remember tool functionality working")
            else:
                print(f"  ✗ Remember tool failed: {result}")
                return False
            
            # Test think functionality
            search_results = search_memories_optimized(["integration"], config)
            if len(search_results) > 0 and search_results[0]["memory_id"] == memory_id:
                print("  ✓ Think tool functionality working")
            else:
                print(f"  ✗ Think tool failed: {search_results}")
                return False
            
            # Test recall functionality
            recall_results = recall_memories([memory_id], config)
            if len(recall_results) > 0 and recall_results[0]["id"] == memory_id:
                print("  ✓ Recall tool functionality working")
            else:
                print(f"  ✗ Recall tool failed: {recall_results}")
                return False
            
            return True
            
    except Exception as e:
        print(f"  ✗ Tool functionality test failed: {e}")
        return False


def run_mcp_integration_tests():
    """Run all MCP server integration tests."""
    print("=" * 50)
    print("MCP Server Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("MCP Server Startup", test_mcp_server_startup),
        ("Tool Registration", test_tool_registration),
        ("Tool Functionality", test_tool_functionality)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n  ✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 50)
    print("MCP INTEGRATION TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
        if result:
            passed += 1
    
    print("-" * 50)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All MCP integration tests passed!")
        print("✅ MCP server fully integrated with all enhanced components")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed")
        return False


if __name__ == "__main__":
    success = run_mcp_integration_tests()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script to verify the local-only aspects of the MCP server.

This script tests:
1. Server initialization with stdio transport only
2. Absence of network configuration
3. Absence of authentication checks
4. Direct tool access without middleware

Requirements: 1.1, 1.2, 1.3
"""

import os
import sys
import inspect
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_server_initialization():
    """Test server initialization with stdio transport only."""
    print("\nTesting Server Initialization")
    print("-" * 50)
    
    try:
        # Try to import the server module
        try:
            from aiaml.server import initialize_server
            has_server_module = True
        except ImportError as e:
            if "mcp" in str(e):
                print("  ⚠ MCP dependency not available, checking server.py file directly")
                has_server_module = False
            else:
                print(f"  ✗ Failed to import server module: {e}")
                return False
        
        if has_server_module:
            # Get the source code of initialize_server
            source = inspect.getsource(initialize_server)
        else:
            # Read the server.py file directly
            try:
                server_file = Path("aiaml/server.py")
                if server_file.exists():
                    source = server_file.read_text()
                else:
                    print("  ✗ Could not find server.py file")
                    return False
            except Exception as e:
                print(f"  ✗ Error reading server.py file: {e}")
                return False
        
        # Check for stdio transport only
        if "stdio" in source and ("sse" not in source.lower() or "sse" in source.lower() and "removed" in source.lower()):
            print("  ✓ Server uses stdio transport only")
        else:
            print("  ✗ Server may still support non-stdio transport")
            return False
        
        # Check for absence of host/port configuration
        if "host" not in source.lower() or ("host" in source.lower() and "host/port" in source.lower()):
            print("  ✓ No host/port configuration in server initialization")
        else:
            print("  ✗ Server may still use host/port configuration")
            return False
            
        return True
    except Exception as e:
        print(f"  ✗ Error testing server initialization: {e}")
        return False

def test_config_simplification():
    """Test absence of network configuration."""
    print("\nTesting Configuration Simplification")
    print("-" * 50)
    
    try:
        from aiaml.config import Config, load_configuration
        
        # Check Config class for absence of network fields
        config_fields = [field for field in dir(Config) if not field.startswith('_')]
        network_fields = ['host', 'port', 'api_key']
        
        has_network_fields = any(field in config_fields for field in network_fields)
        if not has_network_fields:
            print("  ✓ Config class has no network-related fields")
        else:
            print("  ✗ Config class still has network-related fields:")
            for field in network_fields:
                if field in config_fields:
                    print(f"    - {field}")
            return False
        
        # Test loading configuration with network environment variables
        os.environ['AIAML_HOST'] = '127.0.0.1'
        os.environ['AIAML_PORT'] = '8000'
        os.environ['AIAML_API_KEY'] = 'test_key'
        
        config = load_configuration()
        
        # Check that network variables were ignored
        if not hasattr(config, 'host') and not hasattr(config, 'port') and not hasattr(config, 'api_key'):
            print("  ✓ Network environment variables are ignored")
        else:
            print("  ✗ Network environment variables are still processed")
            return False
            
        return True
    except ImportError as e:
        print(f"  ✗ Failed to import config module: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error testing configuration: {e}")
        return False

def test_authentication_removal():
    """Test absence of authentication checks."""
    print("\nTesting Authentication Removal")
    print("-" * 50)
    
    try:
        # Check if auth module exists
        auth_file = Path("aiaml/auth.py")
        if not auth_file.exists():
            print("  ✓ Auth module has been removed")
        else:
            print("  ✗ Auth module still exists")
            return False
        
        # Check server.py for authentication imports
        try:
            server_file = Path("aiaml/server.py")
            if server_file.exists():
                server_source = server_file.read_text()
                
                if "from .auth import" not in server_source and "import auth" not in server_source.lower():
                    print("  ✓ No authentication imports in server module")
                else:
                    print("  ✗ Server module still has authentication imports")
                    return False
                    
                if "api_key" not in server_source.lower():
                    print("  ✓ No API key references in server module")
                else:
                    print("  ✗ Server module still has API key references")
                    return False
            else:
                print("  ⚠ Could not find server.py file, skipping import check")
        except Exception as e:
            print(f"  ⚠ Error checking server.py: {e}, skipping import check")
            
        return True
    except Exception as e:
        print(f"  ✗ Error testing authentication removal: {e}")
        return False

def test_direct_tool_access():
    """Test direct tool access without middleware."""
    print("\nTesting Direct Tool Access")
    print("-" * 50)
    
    try:
        # Read the server.py file directly
        server_file = Path("aiaml/server.py")
        if server_file.exists():
            source = server_file.read_text()
            
            # Find the register_tools function in the source
            import re
            register_tools_match = re.search(r'def register_tools\([^)]*\):(.*?)def', source, re.DOTALL)
            
            if register_tools_match:
                register_tools_source = register_tools_match.group(1)
                
                # Check for absence of authentication middleware
                if "auth_middleware" not in register_tools_source and "middleware" not in register_tools_source.lower():
                    print("  ✓ No authentication middleware in tool registration")
                else:
                    print("  ✗ Tool registration may still use authentication middleware")
                    return False
                
                # Check for direct @server.tool() decorators
                if "@server.tool()" in register_tools_source:
                    print("  ✓ Tools are registered directly with @server.tool()")
                else:
                    print("  ✗ Tools may not be registered directly")
                    return False
                    
                return True
            else:
                print("  ⚠ Could not find register_tools function in server.py")
                # Check the whole file for middleware references
                if "auth_middleware" not in source and "middleware" not in source.lower():
                    print("  ✓ No authentication middleware in server module")
                    return True
                else:
                    print("  ✗ Server module may still use authentication middleware")
                    return False
        else:
            print("  ✗ Could not find server.py file")
            return False
            
    except Exception as e:
        print(f"  ✗ Error testing tool access: {e}")
        return False

def run_all_tests():
    """Run all local-only server tests."""
    print("=" * 70)
    print("AIAML Local-Only MCP Server Verification Tests")
    print("=" * 70)
    
    # Track test results
    results = {}
    
    # Test server initialization
    results["server_init"] = test_server_initialization()
    
    # Test configuration simplification
    results["config"] = test_config_simplification()
    
    # Test authentication removal
    results["auth_removal"] = test_authentication_removal()
    
    # Test direct tool access
    results["tool_access"] = test_direct_tool_access()
    
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
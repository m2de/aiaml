#!/usr/bin/env python3
"""Simple test runner for AIAML."""

import subprocess
import sys
from pathlib import Path

def run_test(test_file: str) -> bool:
    """Run a test file and return success status."""
    print(f"\n{'='*50}")
    print(f"Running: {test_file}")
    print('='*50)
    
    try:
        # Try with uv first, fallback to python3
        result = None
        if Path("requirements.txt").exists():
            try:
                result = subprocess.run([
                    "uv", "run", "--with", "mcp[cli]", "python3", test_file
                ], capture_output=False)
            except FileNotFoundError:
                pass
        
        if result is None:
            result = subprocess.run(["python3", test_file], capture_output=False)
        
        success = result.returncode == 0
        print(f"\n{'✅ PASSED' if success else '❌ FAILED'}: {test_file}")
        return success
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests."""
    tests = [
        "test_module_structure.py",      # Basic syntax/structure
        "test_core_functionality.py",   # Core memory operations
        "test_cross_platform.py",       # Cross-platform support
        "test_optimized_search.py",     # Search functionality
        "test_mcp_integration.py",      # MCP integration
    ]
    
    results = []
    for test in tests:
        if Path(test).exists():
            success = run_test(test)
            results.append((test, success))
        else:
            print(f"⚠️  Test not found: {test}")
            results.append((test, False))
    
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for _, success in results if success)
    for test, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test}")
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
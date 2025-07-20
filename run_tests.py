#!/usr/bin/env python3
"""Test runner for AIAML optimized search functionality."""

import sys
import subprocess
from pathlib import Path


def run_test(test_file: str, description: str) -> bool:
    """Run a single test file and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"File: {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([
            "uv", "run", "--with", "mcp[cli]", "python3", test_file
        ], capture_output=False, text=True)
        
        success = result.returncode == 0
        print(f"\n{'✅ PASSED' if success else '❌ FAILED'}: {description}")
        return success
        
    except Exception as e:
        print(f"❌ ERROR running {test_file}: {e}")
        return False


def main():
    """Run all tests for the optimized search functionality."""
    print("AIAML Optimized Search Test Suite")
    print("="*60)
    
    tests = [
        ("test_module_structure.py", "Module Structure Validation"),
        ("test_cross_platform.py", "Cross-Platform Functionality"),
        ("test_optimized_search.py", "Basic Optimized Search Functionality"),
        ("test_search_performance_detailed.py", "Detailed Performance Benchmarking"),
        ("test_mcp_integration.py", "MCP Server Integration"),
        ("test_task_requirements.py", "Task Requirements Verification"),
    ]
    
    results = []
    for test_file, description in tests:
        if Path(test_file).exists():
            success = run_test(test_file, description)
            results.append((test_file, description, success))
        else:
            print(f"⚠️  Test file not found: {test_file}")
            results.append((test_file, description, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print("="*60)
    
    passed = 0
    for test_file, description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {description}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest suite failed: {e}")
        sys.exit(1)
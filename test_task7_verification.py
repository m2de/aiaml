#!/usr/bin/env python3
"""
Comprehensive test script for Task 7: Verify core functionality preservation.

This script combines both core functionality tests and local-only verification tests
to ensure that the server works correctly after removing remote connection capabilities.

Requirements: 1.1, 1.2, 1.3
"""

import os
import sys
import importlib.util

# Import the test modules
spec1 = importlib.util.spec_from_file_location("test_core_functionality", "test_core_functionality.py")
test_core = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(test_core)

spec2 = importlib.util.spec_from_file_location("test_local_only_server", "test_local_only_server.py")
test_local = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(test_local)

def run_all_tests():
    """Run all tests for Task 7 verification."""
    print("=" * 70)
    print("TASK 7: VERIFY CORE FUNCTIONALITY PRESERVATION")
    print("=" * 70)
    print("\nPart 1: Core Functionality Tests")
    print("-" * 50)
    
    core_results = test_core.run_all_tests()
    
    print("\nPart 2: Local-Only Server Verification")
    print("-" * 50)
    
    local_results = test_local.run_all_tests()
    
    # Print final summary
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION RESULTS")
    print("=" * 70)
    
    print(f"Core Functionality: {'✓ PASSED' if core_results else '✗ FAILED'}")
    print(f"Local-Only Server: {'✓ PASSED' if local_results else '✗ FAILED'}")
    print(f"\nOverall Result: {'✓ ALL TESTS PASSED' if core_results and local_results else '✗ SOME TESTS FAILED'}")
    
    return core_results and local_results

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
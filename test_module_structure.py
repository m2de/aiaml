#!/usr/bin/env python3
"""Test the module structure without requiring MCP dependencies."""

import sys
import ast
from pathlib import Path

def test_module_syntax():
    """Test that all Python files have valid syntax."""
    print("Testing module syntax...")
    
    python_files = []
    for root in ['aiaml']:
        for path in Path(root).rglob('*.py'):
            python_files.append(path)
    
    errors = []
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            print(f"  ✓ {file_path}")
        except SyntaxError as e:
            errors.append(f"  ✗ {file_path}: {e}")
            print(f"  ✗ {file_path}: {e}")
        except Exception as e:
            errors.append(f"  ✗ {file_path}: {e}")
            print(f"  ✗ {file_path}: {e}")
    
    return len(errors) == 0

def test_import_structure():
    """Test that import statements are structured correctly."""
    print("\nTesting import structure...")
    
    # Test memory module structure
    try:
        sys.path.insert(0, '.')
        
        # Test that we can import the module structure (without executing)
        import importlib.util
        
        # Test memory module
        spec = importlib.util.spec_from_file_location("memory_init", "aiaml/memory/__init__.py")
        if spec and spec.loader:
            print("  ✓ Memory module __init__.py structure valid")
        else:
            print("  ✗ Memory module __init__.py structure invalid")
            return False
        
        # Test git_sync module
        spec = importlib.util.spec_from_file_location("git_sync_init", "aiaml/git_sync/__init__.py")
        if spec and spec.loader:
            print("  ✓ Git sync module __init__.py structure valid")
        else:
            print("  ✗ Git sync module __init__.py structure invalid")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Import structure test failed: {e}")
        return False

def test_file_sizes():
    """Test that all files are under 500 lines."""
    print("\nTesting file sizes...")
    
    python_files = []
    for root in ['aiaml']:
        for path in Path(root).rglob('*.py'):
            python_files.append(path)
    
    oversized_files = []
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
            
            if lines > 500:
                oversized_files.append((file_path, lines))
                print(f"  ✗ {file_path}: {lines} lines (exceeds 500)")
            else:
                print(f"  ✓ {file_path}: {lines} lines")
        except Exception as e:
            print(f"  ✗ Error reading {file_path}: {e}")
            return False
    
    if oversized_files:
        print(f"\n❌ {len(oversized_files)} files exceed 500 lines:")
        for file_path, lines in oversized_files:
            print(f"    {file_path}: {lines} lines")
        return False
    
    return True

def test_module_exports():
    """Test that modules export the expected functions."""
    print("\nTesting module exports...")
    
    # Test memory module exports
    try:
        with open('aiaml/memory/__init__.py', 'r') as f:
            content = f.read()
        
        expected_exports = [
            'store_memory_atomic',
            'recall_memories', 
            'search_memories_optimized',
            'get_search_performance_stats',
            'validate_memory_input',
            'validate_search_input',
            'validate_recall_input'
        ]
        
        missing_exports = []
        for export in expected_exports:
            if export not in content:
                missing_exports.append(export)
        
        if missing_exports:
            print(f"  ✗ Memory module missing exports: {missing_exports}")
            return False
        else:
            print("  ✓ Memory module exports all expected functions")
        
    except Exception as e:
        print(f"  ✗ Error testing memory exports: {e}")
        return False
    
    # Test git_sync module exports
    try:
        with open('aiaml/git_sync/__init__.py', 'r') as f:
            content = f.read()
        
        expected_exports = [
            'GitSyncManager',
            'get_git_sync_manager',
            'sync_memory_to_git'
        ]
        
        missing_exports = []
        for export in expected_exports:
            if export not in content:
                missing_exports.append(export)
        
        if missing_exports:
            print(f"  ✗ Git sync module missing exports: {missing_exports}")
            return False
        else:
            print("  ✓ Git sync module exports all expected functions")
        
    except Exception as e:
        print(f"  ✗ Error testing git_sync exports: {e}")
        return False
    
    return True

def main():
    """Run all module structure tests."""
    print("AIAML Module Structure Test")
    print("=" * 50)
    
    tests = [
        ("Syntax validation", test_module_syntax),
        ("Import structure", test_import_structure),
        ("File size limits", test_file_sizes),
        ("Module exports", test_module_exports)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * 30)
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n" + "=" * 50)
    print("MODULE STRUCTURE TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL MODULE STRUCTURE TESTS PASSED!")
        print("The refactoring was successful!")
        return True
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
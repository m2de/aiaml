#!/usr/bin/env python3
"""Test cross-platform file operations and memory storage."""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, '.')

from aiaml.config import Config
from aiaml.memory.core import store_memory_atomic
from aiaml.file_lock import FileLock
from aiaml.platform import get_platform_info, create_secure_temp_file


def test_cross_platform_memory_storage():
    """Test cross-platform memory storage with file locking."""
    print("Testing Cross-Platform Memory Storage")
    print("-" * 40)
    
    try:
        platform_info = get_platform_info()
        print(f"  Platform: {platform_info.get_platform_name()}")
        print(f"  Windows: {platform_info.is_windows}")
        print(f"  Unix: {platform_info.is_unix}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            memory_dir = temp_path / "memory" / "files"
            memory_dir.mkdir(parents=True, exist_ok=True)
            
            # Create test configuration
            config = Config(
                memory_dir=memory_dir,
                enable_git_sync=False,  # Disable Git sync for this test
                max_search_results=25
            )
            
            # Test memory storage with cross-platform file locking
            result = store_memory_atomic(
                agent="test_agent",
                user="test_user",
                topics=["cross-platform", "testing"],
                content="This is a test memory for cross-platform compatibility testing.",
                config=config
            )
            
            if 'memory_id' in result:
                print(f"  ✓ Memory stored successfully: {result['memory_id']}")
                
                # Verify the file was created
                memory_files = list(memory_dir.glob("*.md"))
                if len(memory_files) == 1:
                    print("  ✓ Memory file created successfully")
                    
                    # Verify file content
                    memory_file = memory_files[0]
                    content = memory_file.read_text(encoding='utf-8')
                    
                    if "cross-platform" in content and "testing" in content:
                        print("  ✓ Memory file content is correct")
                    else:
                        print("  ✗ Memory file content is incorrect")
                        return False
                else:
                    print(f"  ✗ Expected 1 memory file, found {len(memory_files)}")
                    return False
            else:
                print(f"  ✗ Memory storage failed: {result}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Cross-platform memory storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_concurrent_file_locking():
    """Test concurrent file locking across platforms."""
    print("\nTesting Concurrent File Locking")
    print("-" * 40)
    
    try:
        import threading
        import time
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            lock_file = temp_path / "concurrent_test.lock"
            
            results = []
            
            def worker(worker_id, delay):
                """Worker function to test concurrent locking."""
                try:
                    time.sleep(delay)  # Stagger the workers
                    
                    file_lock = FileLock(lock_file, timeout=2)
                    if file_lock.acquire():
                        # Hold the lock for a short time
                        time.sleep(0.5)
                        file_lock.release()
                        results.append(f"Worker {worker_id}: SUCCESS")
                    else:
                        results.append(f"Worker {worker_id}: TIMEOUT")
                except Exception as e:
                    results.append(f"Worker {worker_id}: ERROR - {e}")
            
            # Start multiple workers
            threads = []
            for i in range(3):
                thread = threading.Thread(target=worker, args=(i, i * 0.1))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=10)
            
            # Check results
            success_count = sum(1 for result in results if "SUCCESS" in result)
            
            if success_count >= 1:  # At least one should succeed
                print(f"  ✓ Concurrent file locking works ({success_count}/3 succeeded)")
                for result in results:
                    print(f"    {result}")
            else:
                print("  ✗ Concurrent file locking failed")
                for result in results:
                    print(f"    {result}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Concurrent file locking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_platform_specific_paths():
    """Test platform-specific path handling."""
    print("\nTesting Platform-Specific Path Handling")
    print("-" * 40)
    
    try:
        from aiaml.platform import normalize_path
        
        platform_info = get_platform_info()
        
        # Test various path formats
        test_paths = [
            "memory/files",
            "./memory/files",
            "../test/memory",
            Path("memory") / "files"
        ]
        
        for test_path in test_paths:
            try:
                normalized = normalize_path(test_path)
                if isinstance(normalized, Path) and normalized.is_absolute():
                    print(f"  ✓ Path normalization works: {test_path} -> {normalized.name}")
                else:
                    print(f"  ✗ Path normalization failed for: {test_path}")
                    return False
            except Exception as e:
                print(f"  ✗ Path normalization error for {test_path}: {e}")
                return False
        
        # Test secure temp file creation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            fd, temp_file = create_secure_temp_file(temp_path, suffix='.test')
            
            try:
                # Write some test data
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write("Cross-platform test data")
                    f.flush()
                    os.fsync(fd)
                
                # Verify the file exists and has correct content
                if temp_file.exists():
                    content = temp_file.read_text(encoding='utf-8')
                    if content == "Cross-platform test data":
                        print("  ✓ Secure temp file creation and writing works")
                    else:
                        print("  ✗ Secure temp file content is incorrect")
                        return False
                else:
                    print("  ✗ Secure temp file was not created")
                    return False
                
                # Clean up
                temp_file.unlink()
                
            except Exception as e:
                print(f"  ✗ Secure temp file operation failed: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Platform-specific path handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_git_cross_platform_config():
    """Test Git cross-platform configuration."""
    print("\nTesting Git Cross-Platform Configuration")
    print("-" * 40)
    
    try:
        from aiaml.platform import (
            get_git_executable, 
            validate_git_availability, 
            get_platform_specific_git_config
        )
        
        platform_info = get_platform_info()
        
        # Test Git executable detection
        git_exe = get_git_executable()
        expected_exe = "git.exe" if platform_info.is_windows else "git"
        
        if git_exe == expected_exe:
            print(f"  ✓ Git executable detection correct: {git_exe}")
        else:
            print(f"  ⚠️  Git executable detection: expected {expected_exe}, got {git_exe}")
        
        # Test Git availability
        git_available, git_error = validate_git_availability()
        if git_available:
            print("  ✓ Git availability check passed")
        else:
            print(f"  ⚠️  Git not available: {git_error}")
        
        # Test platform-specific Git configuration
        git_config = get_platform_specific_git_config()
        
        if isinstance(git_config, dict) and 'core.autocrlf' in git_config:
            print("  ✓ Platform-specific Git config generated")
            
            # Check platform-specific values
            if platform_info.is_windows:
                if git_config['core.autocrlf'] == 'true':
                    print("  ✓ Windows-specific Git config correct")
                else:
                    print("  ✗ Windows-specific Git config incorrect")
                    return False
            elif platform_info.is_unix:
                if git_config['core.autocrlf'] == 'input':
                    print("  ✓ Unix-specific Git config correct")
                else:
                    print("  ✗ Unix-specific Git config incorrect")
                    return False
        else:
            print("  ✗ Platform-specific Git config generation failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Git cross-platform configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all cross-platform file operation tests."""
    print("AIAML Cross-Platform File Operations Test")
    print("=" * 50)
    
    platform_info = get_platform_info()
    system_info = platform_info.get_system_info()
    
    print(f"System Information:")
    print(f"  Platform: {system_info['platform']}")
    print(f"  System: {system_info['system']} {system_info['release']}")
    print(f"  Python: {system_info['python_version']} ({system_info['python_implementation']})")
    print(f"  Machine: {system_info['machine']}")
    print("=" * 50)
    
    tests = [
        ("Cross-Platform Memory Storage", test_cross_platform_memory_storage),
        ("Concurrent File Locking", test_concurrent_file_locking),
        ("Platform-Specific Path Handling", test_platform_specific_paths),
        ("Git Cross-Platform Configuration", test_git_cross_platform_config)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print(f"\n" + "=" * 50)
    print("CROSS-PLATFORM FILE OPERATIONS TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL CROSS-PLATFORM FILE OPERATIONS TESTS PASSED!")
        print("✅ Cross-platform compatibility implemented successfully!")
        print("✅ File locking works across platforms!")
        print("✅ Git operations are platform-aware!")
        print("✅ Path handling is cross-platform compatible!")
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
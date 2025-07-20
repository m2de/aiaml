#!/usr/bin/env python3
"""
Test automated directory and file management functionality for AIAML.

This test verifies that task 12 requirements are properly implemented:
- Automatic memory directory creation
- Git repository initialization on first run
- Backup and recovery mechanisms
- File permission handling
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_automated_file_management():
    """Test the automated directory and file management functionality."""
    print("Testing Automated Directory and File Management")
    print("=" * 50)
    
    success_count = 0
    total_tests = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test 1: Directory Structure Initialization
        total_tests += 1
        print("\n1. Testing directory structure initialization...")
        
        try:
            from aiaml.config import Config
            from aiaml.file_manager import initialize_aiaml_directories, get_file_manager
            
            # Create test configuration
            test_config = Config(
                memory_dir=temp_path / "memory" / "files",
                enable_git_sync=False,  # Disable Git for basic directory test
                log_level="ERROR"  # Reduce log noise
            )
            
            # Initialize directories
            result = initialize_aiaml_directories(test_config)
            
            if result:
                # Check that all required directories were created
                expected_dirs = [
                    test_config.memory_dir,
                    test_config.memory_dir.parent / "backups",
                    test_config.memory_dir.parent / "temp",
                    test_config.memory_dir.parent / "locks"
                ]
                
                all_exist = all(d.exists() and d.is_dir() for d in expected_dirs)
                
                if all_exist:
                    print("  ✓ All required directories created successfully")
                    success_count += 1
                else:
                    print("  ✗ Some required directories were not created")
                    for d in expected_dirs:
                        status = "✓" if d.exists() else "✗"
                        print(f"    {status} {d}")
            else:
                print("  ✗ Directory initialization failed")
                
        except Exception as e:
            print(f"  ✗ Directory initialization test failed: {e}")
        
        # Test 2: File Manager Status
        total_tests += 1
        print("\n2. Testing file manager status reporting...")
        
        try:
            file_manager = get_file_manager(test_config)
            status = file_manager.get_directory_status()
            
            if status.get('initialized', False):
                print("  ✓ File manager reports directories as initialized")
                success_count += 1
            else:
                print("  ✗ File manager reports directories as not initialized")
                print(f"    Status: {status}")
                
        except Exception as e:
            print(f"  ✗ File manager status test failed: {e}")
        
        # Test 3: Backup Functionality
        total_tests += 1
        print("\n3. Testing backup functionality...")
        
        try:
            # Create a test memory file
            test_file = test_config.memory_dir / "test_memory.md"
            test_content = """---
id: test123
timestamp: 2024-01-01T00:00:00
agent: test
user: test
topics: ["test"]
---

Test memory content"""
            
            test_file.write_text(test_content)
            
            # Create backup
            file_manager = get_file_manager(test_config)
            backup_path = file_manager.create_backup(test_file)
            
            if backup_path and backup_path.exists():
                # Verify backup content matches original
                backup_content = backup_path.read_text()
                if backup_content == test_content:
                    print("  ✓ Backup created successfully with correct content")
                    success_count += 1
                else:
                    print("  ✗ Backup content doesn't match original")
            else:
                print("  ✗ Backup creation failed")
                
        except Exception as e:
            print(f"  ✗ Backup functionality test failed: {e}")
        
        # Test 4: File Locking
        total_tests += 1
        print("\n4. Testing file locking functionality...")
        
        try:
            from aiaml.file_lock import memory_file_lock
            
            test_file = test_config.memory_dir / "lock_test.md"
            
            # Test lock acquisition and release
            with memory_file_lock(test_config, test_file, timeout=5.0) as lock:
                if lock.is_locked():
                    print("  ✓ File lock acquired successfully")
                    success_count += 1
                else:
                    print("  ✗ File lock not properly acquired")
                    
        except Exception as e:
            print(f"  ✗ File locking test failed: {e}")
        
        # Test 5: Git Repository Initialization (if Git is available)
        total_tests += 1
        print("\n5. Testing Git repository initialization...")
        
        try:
            from aiaml.platform import validate_git_availability
            from aiaml.git_sync import get_git_sync_manager
            
            git_available, git_error = validate_git_availability()
            
            if git_available:
                # Test Git sync manager directly
                git_config = Config(
                    memory_dir=temp_path / "git_test" / "memory" / "files",
                    enable_git_sync=True,
                    log_level="ERROR"  # Reduce log noise
                )
                
                # Ensure the directory structure exists
                git_config.memory_dir.mkdir(parents=True, exist_ok=True)
                
                # Create Git sync manager directly
                git_manager = get_git_sync_manager(git_config)
                
                git_repo_dir = git_config.memory_dir.parent  # This is "memory"
                git_dir = git_repo_dir / ".git"
                
                if git_dir.exists():
                    print("  ✓ Git repository initialized successfully")
                    success_count += 1
                else:
                    print("  ✗ Git repository not created by Git sync manager")
            else:
                print(f"  ~ Git not available, skipping test: {git_error}")
                success_count += 1  # Don't penalize for missing Git
                
        except Exception as e:
            print(f"  ✗ Git repository initialization test failed: {e}")
        
        # Test 6: File Permission Handling
        total_tests += 1
        print("\n6. Testing file permission handling...")
        
        try:
            file_manager = get_file_manager(test_config)
            
            # Test directory permissions
            test_dir = temp_path / "permission_test"
            success = file_manager._create_directory_with_permissions(test_dir, "Test directory")
            
            if success and test_dir.exists():
                # Test write access
                test_file = test_dir / "write_test.txt"
                test_file.write_text("test")
                
                if test_file.exists():
                    print("  ✓ File permissions handled correctly")
                    success_count += 1
                else:
                    print("  ✗ Write permission test failed")
            else:
                print("  ✗ Directory permission setup failed")
                
        except Exception as e:
            print(f"  ✗ File permission test failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("✓ All automated file management tests passed!")
        return True
    else:
        print(f"✗ {total_tests - success_count} tests failed")
        return False


def test_integration_with_memory_operations():
    """Test integration of file management with memory operations."""
    print("\nTesting Integration with Memory Operations")
    print("=" * 50)
    
    success_count = 0
    total_tests = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test 1: Memory Storage with Enhanced File Management
        total_tests += 1
        print("\n1. Testing memory storage with enhanced file management...")
        
        try:
            from aiaml.config import Config
            from aiaml.memory import store_memory_atomic
            from aiaml.file_manager import initialize_aiaml_directories
            
            # Create test configuration
            test_config = Config(
                memory_dir=temp_path / "memory" / "files",
                enable_git_sync=False,
                log_level="ERROR"
            )
            
            # Initialize directories
            initialize_aiaml_directories(test_config)
            
            # Store a memory
            result = store_memory_atomic(
                agent="test_agent",
                user="test_user", 
                topics=["test", "integration"],
                content="This is a test memory for integration testing.",
                config=test_config
            )
            
            if "memory_id" in result and "error" not in result:
                print("  ✓ Memory stored successfully with enhanced file management")
                success_count += 1
            else:
                print(f"  ✗ Memory storage failed: {result}")
                
        except Exception as e:
            print(f"  ✗ Memory storage integration test failed: {e}")
        
        # Test 2: Corrupted File Recovery
        total_tests += 1
        print("\n2. Testing corrupted file recovery...")
        
        try:
            from aiaml.memory import parse_memory_file_safe
            
            # Create a corrupted memory file
            corrupted_file = test_config.memory_dir / "20240101_120000_corrupt1.md"
            corrupted_file.write_text("This is corrupted content without proper frontmatter")
            
            # Try to parse it (should trigger recovery)
            result = parse_memory_file_safe(corrupted_file)
            
            # The function should return None for corrupted files but not crash
            if result is None:
                print("  ✓ Corrupted file handled gracefully")
                success_count += 1
            else:
                print("  ✗ Corrupted file not handled properly")
                
        except Exception as e:
            print(f"  ✗ Corrupted file recovery test failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Integration Test Results: {success_count}/{total_tests} tests passed")
    
    return success_count == total_tests


if __name__ == "__main__":
    print("AIAML Automated File Management Test Suite")
    print("=" * 60)
    
    # Run basic functionality tests
    basic_success = test_automated_file_management()
    
    # Run integration tests
    integration_success = test_integration_with_memory_operations()
    
    # Overall result
    print("\n" + "=" * 60)
    if basic_success and integration_success:
        print("🎉 ALL TESTS PASSED! Task 12 implementation is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
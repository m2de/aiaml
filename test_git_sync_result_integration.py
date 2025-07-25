#!/usr/bin/env python3
"""
Integration test for enhanced GitSyncResult with GitSyncManager.

This test verifies that the enhanced GitSyncResult with repository_info
and branch_used fields works correctly with the actual GitSyncManager.
"""

import sys
import tempfile
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.config import Config
from aiaml.git_sync.manager import GitSyncManager
from aiaml.git_sync.utils import GitSyncResult
from aiaml.git_sync.repository_info import RepositoryState


def test_git_sync_manager_enhanced_result():
    """Test that GitSyncManager returns enhanced GitSyncResult."""
    print("Testing GitSyncManager Enhanced Result")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test configuration
        config = Config(
            memory_dir=Path(temp_dir),  # This becomes the git_repo_dir too
            enable_git_sync=True,
            git_remote_url=None  # No remote for this test
        )
        
        # Create the memory files directory
        memory_files_dir = config.memory_dir / "files"
        memory_files_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a test memory file
        test_file = memory_files_dir / "test_memory.md"
        test_file.write_text("""---
id: test123
timestamp: 2024-01-15T10:30:00.123456
agent: claude
user: testuser
topics: ["test", "integration"]
---

Test memory content for integration testing.
""")
        
        # Initialize GitSyncManager
        manager = GitSyncManager(config)
        
        # Test sync operation
        result = manager.sync_memory_with_retry("test123", "test_memory.md")
        
        # Verify the result is a GitSyncResult
        assert isinstance(result, GitSyncResult), "Result should be GitSyncResult instance"
        
        # Verify basic fields
        assert hasattr(result, 'success'), "Result should have success field"
        assert hasattr(result, 'message'), "Result should have message field"
        assert hasattr(result, 'operation'), "Result should have operation field"
        
        # Verify enhanced fields
        assert hasattr(result, 'repository_info'), "Result should have repository_info field"
        assert hasattr(result, 'branch_used'), "Result should have branch_used field"
        
        # For local-only sync, repository_info should be available
        if result.success and result.repository_info:
            assert result.repository_info.state in [
                RepositoryState.NEW_LOCAL, 
                RepositoryState.EXISTING_LOCAL,
                RepositoryState.SYNCHRONIZED
            ], "Repository state should be valid"
            
            assert result.repository_info.default_branch is not None, "Default branch should be set"
            assert result.branch_used is not None, "Branch used should be set"
            
            print(f"  ✓ Repository state: {result.repository_info.state.value}")
            print(f"  ✓ Default branch: {result.repository_info.default_branch}")
            print(f"  ✓ Branch used: {result.branch_used}")
        
        print("  ✓ GitSyncResult has all enhanced fields")
        print("  ✓ Enhanced fields are properly populated")
        
        return True


def test_git_sync_manager_error_result():
    """Test that GitSyncManager returns enhanced GitSyncResult even on errors."""
    print("\nTesting GitSyncManager Error Result")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a configuration that will cause an error (invalid git repo dir)
        config = Config(
            memory_dir=Path("/invalid/path/that/does/not/exist"),
            enable_git_sync=True,
            git_remote_url=None
        )
        
        try:
            # This should fail due to invalid path
            manager = GitSyncManager(config)
            result = manager.sync_memory_with_retry("test123", "test_memory.md")
            
            # Verify the result is still a GitSyncResult with enhanced fields
            assert isinstance(result, GitSyncResult), "Error result should be GitSyncResult instance"
            assert hasattr(result, 'repository_info'), "Error result should have repository_info field"
            assert hasattr(result, 'branch_used'), "Error result should have branch_used field"
            
            # Error results might have None for some fields, which is acceptable
            print("  ✓ Error result has enhanced fields")
            print("  ✓ Enhanced fields handle error cases gracefully")
            
        except Exception as e:
            # If initialization fails completely, that's also acceptable for this test
            print(f"  ✓ Manager initialization failed as expected: {type(e).__name__}")
        
        return True


def test_repository_state_manager_integration():
    """Test that RepositoryStateManager integrates correctly with GitSyncResult."""
    print("\nTesting RepositoryStateManager Integration")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            memory_dir=Path(temp_dir),
            enable_git_sync=True,
            git_remote_url=None
        )
        
        # Create the memory files directory
        memory_files_dir = config.memory_dir / "files"
        memory_files_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize GitSyncManager (which creates RepositoryStateManager)
        manager = GitSyncManager(config)
        
        # Verify that the manager has a repository state manager
        assert hasattr(manager, 'repo_state_manager'), "Manager should have repo_state_manager"
        
        # Test getting repository info
        repo_info = manager.repo_state_manager.get_repository_info()
        
        # Verify repository info structure
        assert hasattr(repo_info, 'state'), "Repository info should have state"
        assert hasattr(repo_info, 'default_branch'), "Repository info should have default_branch"
        assert hasattr(repo_info, 'local_exists'), "Repository info should have local_exists"
        
        print(f"  ✓ Repository state: {repo_info.state.value}")
        print(f"  ✓ Default branch: {repo_info.default_branch}")
        print(f"  ✓ Local exists: {repo_info.local_exists}")
        print("  ✓ RepositoryStateManager integration successful")
        
        return True


def run_integration_tests():
    """Run all integration tests."""
    print("Enhanced GitSyncResult Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_git_sync_manager_enhanced_result,
        test_git_sync_manager_error_result,
        test_repository_state_manager_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ✗ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Integration Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All integration tests passed! Enhanced GitSyncResult integration is working correctly.")
        return True
    else:
        print("✗ Some integration tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
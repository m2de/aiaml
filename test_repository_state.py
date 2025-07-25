#!/usr/bin/env python3
"""
Unit tests for repository state management infrastructure.

This test suite validates the RepositoryState enum, RepositoryInfo dataclass,
and basic repository state detection logic with various repository configurations.
"""

import os
import tempfile
import subprocess
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the modules we're testing
from aiaml.config import Config
from aiaml.git_sync.state import (
    RepositoryState, 
    RepositoryInfo, 
    RepositoryStateManager
)
from aiaml.platform import get_git_executable, get_platform_info


def create_test_config(temp_dir: Path, git_remote_url: str = None, enable_git_sync: bool = True) -> Config:
    """Create a test configuration with the specified parameters."""
    return Config(
        memory_dir=temp_dir,
        enable_git_sync=enable_git_sync,
        git_remote_url=git_remote_url,
        git_retry_attempts=2,
        git_retry_delay=0.1
    )


def setup_git_repo(repo_dir: Path, with_remote: bool = False, remote_url: str = None) -> bool:
    """Set up a Git repository for testing."""
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Initialize repository
        subprocess.run(
            [git_executable, "init"],
            check=True,
            capture_output=True,
            cwd=repo_dir,
            shell=platform_info.is_windows
        )
        
        # Configure user for commits
        subprocess.run(
            [git_executable, "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
            cwd=repo_dir,
            shell=platform_info.is_windows
        )
        
        subprocess.run(
            [git_executable, "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
            cwd=repo_dir,
            shell=platform_info.is_windows
        )
        
        # Add remote if requested
        if with_remote and remote_url:
            subprocess.run(
                [git_executable, "remote", "add", "origin", remote_url],
                check=True,
                capture_output=True,
                cwd=repo_dir,
                shell=platform_info.is_windows
            )
        
        return True
        
    except Exception as e:
        print(f"Failed to set up Git repository: {e}")
        return False


def test_repository_state_enum():
    """Test RepositoryState enum values."""
    print("Testing RepositoryState Enum")
    print("-" * 30)
    
    # Test enum values
    expected_states = {
        "NEW_LOCAL": "new_local",
        "EXISTING_LOCAL": "existing_local", 
        "EXISTING_REMOTE": "existing_remote",
        "SYNCHRONIZED": "synchronized"
    }
    
    for state_name, expected_value in expected_states.items():
        state = getattr(RepositoryState, state_name)
        if state.value == expected_value:
            print(f"  ✓ {state_name} = {expected_value}")
        else:
            print(f"  ✗ {state_name} expected {expected_value}, got {state.value}")
            return False
    
    return True


def test_repository_info_dataclass():
    """Test RepositoryInfo dataclass structure."""
    print("Testing RepositoryInfo Dataclass")
    print("-" * 30)
    
    try:
        # Create a test instance
        repo_info = RepositoryInfo(
            state=RepositoryState.NEW_LOCAL,
            local_exists=False,
            remote_exists=False,
            remote_url=None,
            default_branch="main",
            local_branch=None,
            tracking_configured=False,
            needs_sync=False
        )
        
        # Test field access
        if repo_info.state == RepositoryState.NEW_LOCAL:
            print("  ✓ state field accessible")
        else:
            print("  ✗ state field not accessible")
            return False
        
        if repo_info.default_branch == "main":
            print("  ✓ default_branch field accessible")
        else:
            print("  ✗ default_branch field not accessible")
            return False
        
        if repo_info.local_exists is False:
            print("  ✓ local_exists field accessible")
        else:
            print("  ✗ local_exists field not accessible")
            return False
        
        print("  ✓ All RepositoryInfo fields accessible")
        return True
        
    except Exception as e:
        print(f"  ✗ Error testing RepositoryInfo: {e}")
        return False


def test_new_local_repository_detection():
    """Test detection of new local repository state."""
    print("Testing New Local Repository Detection")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path, git_remote_url=None)
        
        # Create state manager for directory with no .git and no remote
        state_manager = RepositoryStateManager(config, temp_path)
        
        # Test state detection
        detected_state = state_manager.detect_repository_state()
        if detected_state == RepositoryState.NEW_LOCAL:
            print("  ✓ Correctly detected NEW_LOCAL state")
        else:
            print(f"  ✗ Expected NEW_LOCAL, got {detected_state}")
            return False
        
        # Test repository info
        repo_info = state_manager.get_repository_info()
        if (repo_info.state == RepositoryState.NEW_LOCAL and 
            not repo_info.local_exists and 
            not repo_info.remote_exists and
            repo_info.remote_url is None):
            print("  ✓ Repository info correctly populated for NEW_LOCAL")
        else:
            print(f"  ✗ Repository info incorrect: {repo_info}")
            return False
        
        return True


def test_existing_local_repository_detection():
    """Test detection of existing local repository state."""
    print("Testing Existing Local Repository Detection")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Set up a local Git repository
        if not setup_git_repo(temp_path):
            print("  ✗ Failed to set up test Git repository")
            return False
        
        config = create_test_config(temp_path, git_remote_url=None)
        state_manager = RepositoryStateManager(config, temp_path)
        
        # Test state detection
        detected_state = state_manager.detect_repository_state()
        if detected_state == RepositoryState.EXISTING_LOCAL:
            print("  ✓ Correctly detected EXISTING_LOCAL state")
        else:
            print(f"  ✗ Expected EXISTING_LOCAL, got {detected_state}")
            return False
        
        # Test repository info
        repo_info = state_manager.get_repository_info()
        if (repo_info.state == RepositoryState.EXISTING_LOCAL and 
            repo_info.local_exists and 
            not repo_info.remote_exists):
            print("  ✓ Repository info correctly populated for EXISTING_LOCAL")
        else:
            print(f"  ✗ Repository info incorrect: {repo_info}")
            return False
        
        return True


def test_existing_local_with_remote_detection():
    """Test detection of existing local repository with remote configured."""
    print("Testing Existing Local Repository with Remote")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_remote_url = "https://github.com/test/repo.git"
        
        # Set up a local Git repository with remote
        if not setup_git_repo(temp_path, with_remote=True, remote_url=test_remote_url):
            print("  ✗ Failed to set up test Git repository with remote")
            return False
        
        config = create_test_config(temp_path, git_remote_url=test_remote_url)
        state_manager = RepositoryStateManager(config, temp_path)
        
        # Test state detection
        detected_state = state_manager.detect_repository_state()
        if detected_state == RepositoryState.EXISTING_LOCAL:
            print("  ✓ Correctly detected EXISTING_LOCAL state with remote")
        else:
            print(f"  ✗ Expected EXISTING_LOCAL, got {detected_state}")
            return False
        
        # Test repository info
        repo_info = state_manager.get_repository_info()
        if (repo_info.state == RepositoryState.EXISTING_LOCAL and 
            repo_info.local_exists and 
            repo_info.remote_url == test_remote_url):
            print("  ✓ Repository info correctly populated for EXISTING_LOCAL with remote")
        else:
            print(f"  ✗ Repository info incorrect: {repo_info}")
            return False
        
        return True


def test_default_branch_detection():
    """Test default branch detection logic."""
    print("Testing Default Branch Detection")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test with no repository (should default to "main")
        config = create_test_config(temp_path, git_remote_url=None)
        state_manager = RepositoryStateManager(config, temp_path)
        
        default_branch = state_manager.get_default_branch()
        if default_branch == "main":
            print("  ✓ Correctly defaulted to 'main' branch")
        else:
            print(f"  ✗ Expected 'main', got '{default_branch}'")
            return False
        
        # Test with local repository
        if not setup_git_repo(temp_path):
            print("  ✗ Failed to set up test Git repository")
            return False
        
        # Clear cache to force re-detection
        state_manager.clear_cache()
        
        # Create and switch to a test branch
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Create initial commit so we can create branches
            test_file = temp_path / "test.txt"
            test_file.write_text("test content")
            
            subprocess.run(
                [git_executable, "add", "test.txt"],
                check=True,
                capture_output=True,
                cwd=temp_path,
                shell=platform_info.is_windows
            )
            
            subprocess.run(
                [git_executable, "commit", "-m", "Initial commit"],
                check=True,
                capture_output=True,
                cwd=temp_path,
                shell=platform_info.is_windows
            )
            
            # Check current branch detection
            default_branch = state_manager.get_default_branch()
            if default_branch in ["main", "master"]:  # Git may use either as default
                print(f"  ✓ Detected local branch: {default_branch}")
            else:
                print(f"  ✗ Unexpected branch detected: {default_branch}")
                return False
            
        except Exception as e:
            print(f"  ✗ Error testing local branch detection: {e}")
            return False
        
        return True


def test_repository_state_manager_initialization():
    """Test RepositoryStateManager initialization."""
    print("Testing RepositoryStateManager Initialization")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path)
        
        try:
            # Test initialization
            state_manager = RepositoryStateManager(config, temp_path)
            
            if state_manager.config == config:
                print("  ✓ Config properly stored")
            else:
                print("  ✗ Config not properly stored")
                return False
            
            if state_manager.git_repo_dir == temp_path:
                print("  ✓ Git repo directory properly stored")
            else:
                print("  ✗ Git repo directory not properly stored")
                return False
            
            if state_manager.git_dir == temp_path / ".git":
                print("  ✓ Git directory path properly constructed")
            else:
                print("  ✗ Git directory path not properly constructed")
                return False
            
            # Test cache clearing
            state_manager.clear_cache()
            print("  ✓ Cache clearing works without error")
            
            return True
            
        except Exception as e:
            print(f"  ✗ Error during initialization: {e}")
            return False


def test_error_handling():
    """Test error handling in repository state detection."""
    print("Testing Error Handling")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test with invalid remote URL
        config = create_test_config(temp_path, git_remote_url="invalid://url")
        state_manager = RepositoryStateManager(config, temp_path)
        
        try:
            # Should not crash even with invalid remote
            detected_state = state_manager.detect_repository_state()
            print(f"  ✓ Handled invalid remote URL gracefully: {detected_state}")
            
            # Should return valid repository info
            repo_info = state_manager.get_repository_info()
            if isinstance(repo_info, RepositoryInfo):
                print("  ✓ Returned valid RepositoryInfo despite errors")
            else:
                print("  ✗ Did not return valid RepositoryInfo")
                return False
            
            # Should return valid default branch
            default_branch = state_manager.get_default_branch()
            if isinstance(default_branch, str) and default_branch:
                print(f"  ✓ Returned valid default branch: {default_branch}")
            else:
                print("  ✗ Did not return valid default branch")
                return False
            
            return True
            
        except Exception as e:
            print(f"  ✗ Error handling failed: {e}")
            return False


def run_all_tests():
    """Run all repository state management tests."""
    print("Repository State Management Tests")
    print("=" * 50)
    
    tests = [
        test_repository_state_enum,
        test_repository_info_dataclass,
        test_repository_state_manager_initialization,
        test_new_local_repository_detection,
        test_existing_local_repository_detection,
        test_existing_local_with_remote_detection,
        test_default_branch_detection,
        test_error_handling
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
                print("✓ PASSED\n")
            else:
                print("✗ FAILED\n")
        except Exception as e:
            print(f"✗ FAILED with exception: {e}\n")
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All repository state management tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
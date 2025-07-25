#!/usr/bin/env python3
"""
Test repository synchronization functionality for enhanced Git sync.

This test suite validates the synchronize_with_remote() method and related
functionality in the RepositoryStateManager class.
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to the path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.config import Config
from aiaml.git_sync.state import RepositoryStateManager
from aiaml.git_sync.repository_info import RepositoryState
from aiaml.git_sync.utils import GitSyncResult


def create_test_config(temp_dir: Path, remote_url: str = None) -> Config:
    """Create a test configuration."""
    return Config(
        memory_dir=temp_dir / "memory",
        enable_git_sync=True,
        git_remote_url=remote_url,
        log_level="DEBUG"
    )


def create_test_memory_file(files_dir: Path, memory_id: str, content: str = "Test memory content") -> Path:
    """Create a test memory file."""
    files_dir.mkdir(parents=True, exist_ok=True)
    
    memory_content = f"""---
id: {memory_id}
timestamp: 2024-01-15T10:30:00.123456
agent: claude
user: testuser
topics: ["test", "memory"]
---

{content}"""
    
    filename = f"20240115_103000_{memory_id}.md"
    file_path = files_dir / filename
    file_path.write_text(memory_content, encoding='utf-8')
    return file_path


def setup_git_repository(repo_dir: Path, remote_url: str = None) -> bool:
    """Set up a basic Git repository for testing."""
    try:
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Git repository
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True, check=True)
        
        # Create initial commit
        files_dir = repo_dir / "files"
        files_dir.mkdir(exist_ok=True)
        
        readme_file = repo_dir / "README.md"
        readme_file.write_text("# Test Repository\n\nThis is a test repository for AIAML sync testing.")
        
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True, check=True)
        
        # Add remote if provided
        if remote_url:
            subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=repo_dir, capture_output=True, check=True)
        
        return True
        
    except Exception as e:
        print(f"Error setting up Git repository: {e}")
        return False


def test_synchronize_with_remote_no_local_repo():
    """Test synchronization when local repository doesn't exist."""
    print("Testing synchronize_with_remote - No Local Repository")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path, "https://github.com/test/repo.git")
        
        # Don't create the repository - test with missing local repo
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        result = repo_state_manager.synchronize_with_remote()
        
        if not result.success and result.error_code == "NO_LOCAL_REPO":
            print("  ✓ Correctly detected missing local repository")
            return True
        else:
            print(f"  ✗ Expected NO_LOCAL_REPO error, got: {result.error_code}")
            return False


def test_synchronize_with_remote_no_remote_url():
    """Test synchronization when no remote URL is configured."""
    print("Testing synchronize_with_remote - No Remote URL")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path)  # No remote URL
        
        # Set up local repository
        if not setup_git_repository(config.git_repo_dir):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        result = repo_state_manager.synchronize_with_remote()
        
        if not result.success and result.error_code == "NO_REMOTE_URL":
            print("  ✓ Correctly detected missing remote URL")
            return True
        else:
            print(f"  ✗ Expected NO_REMOTE_URL error, got: {result.error_code}")
            return False


def test_synchronize_with_remote_no_local_remote():
    """Test synchronization when remote is not configured in local repository."""
    print("Testing synchronize_with_remote - No Local Remote")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path, "https://github.com/test/repo.git")
        
        # Set up local repository without remote
        if not setup_git_repository(config.git_repo_dir):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        result = repo_state_manager.synchronize_with_remote()
        
        if not result.success and result.error_code == "NO_LOCAL_REMOTE":
            print("  ✓ Correctly detected missing local remote configuration")
            return True
        else:
            print(f"  ✗ Expected NO_LOCAL_REMOTE error, got: {result.error_code}")
            return False


def test_synchronize_with_remote_not_accessible():
    """Test synchronization when remote repository is not accessible."""
    print("Testing synchronize_with_remote - Remote Not Accessible")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        # Use a non-existent remote URL
        config = create_test_config(temp_path, "https://github.com/nonexistent/repo.git")
        
        # Set up local repository with remote
        if not setup_git_repository(config.git_repo_dir, config.git_remote_url):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        result = repo_state_manager.synchronize_with_remote()
        
        if not result.success and result.error_code == "REMOTE_NOT_ACCESSIBLE":
            print("  ✓ Correctly detected inaccessible remote repository")
            return True
        else:
            print(f"  ✗ Expected REMOTE_NOT_ACCESSIBLE error, got: {result.error_code}")
            return False


def test_validate_existing_memory_files():
    """Test validation of existing memory files."""
    print("Testing validate_existing_memory_files")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path)
        
        # Set up local repository
        if not setup_git_repository(config.git_repo_dir):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        # Test with no memory files
        result = repo_state_manager._sync_ops.validate_existing_memory_files()
        if result.success:
            print("  ✓ Correctly handled empty memory files directory")
        else:
            print(f"  ✗ Failed to handle empty directory: {result.message}")
            return False
        
        # Create valid memory files
        files_dir = config.git_repo_dir / "files"
        create_test_memory_file(files_dir, "abc12345", "Valid memory content")
        create_test_memory_file(files_dir, "def67890", "Another valid memory")
        
        result = repo_state_manager._sync_ops.validate_existing_memory_files()
        if result.success:
            print("  ✓ Successfully validated valid memory files")
        else:
            print(f"  ✗ Failed to validate valid memory files: {result.message}")
            return False
        
        # Create invalid memory file
        invalid_file = files_dir / "20240115_103000_invalid1.md"
        invalid_file.write_text("Invalid memory file without frontmatter")
        
        result = repo_state_manager._sync_ops.validate_existing_memory_files()
        if not result.success and result.error_code == "MEMORY_VALIDATION_WARNINGS":
            print("  ✓ Correctly detected invalid memory files")
        else:
            print(f"  ✗ Failed to detect invalid memory files: {result.message}")
            return False
        
        return True


def test_resolve_merge_conflicts():
    """Test merge conflict resolution."""
    print("Testing resolve_merge_conflicts")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path, "https://github.com/test/repo.git")
        
        # Set up local repository
        if not setup_git_repository(config.git_repo_dir, config.git_remote_url):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        # Test with no conflicts (should succeed)
        result = repo_state_manager._sync_ops.resolve_merge_conflicts("main")
        if result.success:
            print("  ✓ Correctly handled no conflicts scenario")
        else:
            print(f"  ✗ Failed to handle no conflicts: {result.message}")
            return False
        
        return True


def test_sync_backup_operations():
    """Test backup creation, restoration, and cleanup operations."""
    print("Testing sync backup operations")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path)
        
        # Set up local repository
        if not setup_git_repository(config.git_repo_dir):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        # Create some test content
        test_file = config.git_repo_dir / "test_file.txt"
        test_file.write_text("Original content")
        
        # Test backup creation
        repo_state_manager._sync_ops.create_sync_backup()
        if repo_state_manager._sync_ops._temp_backup_dir is not None and repo_state_manager._sync_ops._temp_backup_dir.exists():
            print("  ✓ Successfully created sync backup")
        else:
            print("  ✗ Failed to create sync backup")
            return False
        
        # Modify the original file
        test_file.write_text("Modified content")
        
        # Test backup restoration
        repo_state_manager._sync_ops.restore_from_sync_backup()
        if test_file.read_text() == "Original content":
            print("  ✓ Successfully restored from sync backup")
        else:
            print("  ✗ Failed to restore from sync backup")
            return False
        
        # Test backup cleanup
        backup_dir = repo_state_manager._sync_ops._temp_backup_dir
        repo_state_manager._sync_ops.cleanup_sync_backup()
        if not backup_dir.exists():
            print("  ✓ Successfully cleaned up sync backup")
        else:
            print("  ✗ Failed to clean up sync backup")
            return False
        
        return True


def test_synchronize_with_mocked_remote():
    """Test synchronization with mocked remote operations."""
    print("Testing synchronize_with_remote - Mocked Remote Operations")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = create_test_config(temp_path, "https://github.com/test/repo.git")
        
        # Set up local repository with remote
        if not setup_git_repository(config.git_repo_dir, config.git_remote_url):
            print("  ✗ Failed to set up test repository")
            return False
        
        repo_state_manager = RepositoryStateManager(config, config.git_repo_dir)
        
        # Mock the remote accessibility check to return True
        with patch('aiaml.git_sync.remote_utils.check_remote_accessibility', return_value=True):
            # Mock the subprocess calls for Git operations
            with patch('subprocess.run') as mock_run:
                # Configure mock to simulate successful operations
                mock_run.return_value = MagicMock(returncode=0, stdout="0\n", stderr="")
                
                result = repo_state_manager.synchronize_with_remote()
                
                if result.success:
                    print("  ✓ Successfully synchronized with mocked remote")
                    return True
                else:
                    print(f"  ✗ Failed to synchronize with mocked remote: {result.message}")
                    return False


def run_all_tests():
    """Run all synchronization tests."""
    print("Repository Synchronization Test Suite")
    print("=" * 60)
    
    tests = [
        test_synchronize_with_remote_no_local_repo,
        test_synchronize_with_remote_no_remote_url,
        test_synchronize_with_remote_no_local_remote,
        test_synchronize_with_remote_not_accessible,
        test_validate_existing_memory_files,
        test_resolve_merge_conflicts,
        test_sync_backup_operations,
        test_synchronize_with_mocked_remote,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print("  PASSED\n")
            else:
                failed += 1
                print("  FAILED\n")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {e}\n")
    
    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests passed! ✓")
        return True
    else:
        print(f"{failed} test(s) failed! ✗")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
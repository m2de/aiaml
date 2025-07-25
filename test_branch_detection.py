#!/usr/bin/env python3
"""
Unit tests for dynamic branch detection system.

Tests the detect_remote_default_branch() function with various scenarios
including different Git hosting services and branch naming conventions.

Requirements: 2.1, 2.2, 2.3
"""

import tempfile
import subprocess
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.config import Config
from aiaml.git_sync.operations import detect_remote_default_branch


def create_test_config(temp_dir: str) -> Config:
    """Create a test configuration."""
    return Config(
        memory_dir=Path(temp_dir) / "memory" / "files",
        enable_git_sync=True,
        git_remote_url="https://github.com/test/repo.git",
        git_retry_attempts=3,
        git_retry_delay=0.1
    )


def test_symbolic_reference_detection():
    """Test branch detection using symbolic references."""
    print("Testing Symbolic Reference Detection")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        # Mock successful symbolic reference detection
        mock_output = "ref: refs/heads/develop\tHEAD\n1234567890abcdef\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "develop":
                print("  ✓ Successfully detected 'develop' branch via symbolic reference")
                return True
            else:
                print(f"  ✗ Expected 'develop', got '{branch}'")
                return False


def test_main_branch_detection():
    """Test detection of 'main' branch via symbolic reference."""
    print("Testing Main Branch Detection")
    print("-" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        # Mock symbolic reference pointing to main
        mock_output = "ref: refs/heads/main\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "main":
                print("  ✓ Successfully detected 'main' branch")
                return True
            else:
                print(f"  ✗ Expected 'main', got '{branch}'")
                return False


def test_master_branch_detection():
    """Test detection of 'master' branch via symbolic reference."""
    print("Testing Master Branch Detection")
    print("-" * 32)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        # Mock symbolic reference pointing to master
        mock_output = "ref: refs/heads/master\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "master":
                print("  ✓ Successfully detected 'master' branch")
                return True
            else:
                print(f"  ✗ Expected 'master', got '{branch}'")
                return False


def test_fallback_to_common_branches():
    """Test fallback logic when symbolic reference fails."""
    print("Testing Fallback to Common Branches")
    print("-" * 37)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        call_count = 0
        
        def mock_run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # First call: symbolic reference fails
            if call_count == 1:
                raise subprocess.CalledProcessError(1, args[0], stderr="fatal: not found")
            
            # Second call: checking 'main' branch fails
            elif call_count == 2:
                mock_result = MagicMock()
                mock_result.stdout = ""  # Empty output means branch doesn't exist
                mock_result.returncode = 0
                return mock_result
            
            # Third call: checking 'master' branch succeeds
            elif call_count == 3:
                mock_result = MagicMock()
                mock_result.stdout = "1234567890abcdef\trefs/heads/master\n"
                mock_result.returncode = 0
                return mock_result
            
            # Should not reach here
            raise Exception("Unexpected call")
        
        with patch('subprocess.run', side_effect=mock_run_side_effect):
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "master":
                print("  ✓ Successfully fell back to 'master' branch")
                return True
            else:
                print(f"  ✗ Expected 'master', got '{branch}'")
                return False


def test_fallback_to_default():
    """Test final fallback to 'main' when all detection methods fail."""
    print("Testing Fallback to Default")
    print("-" * 27)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        # Mock all commands to fail
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git", stderr="fatal: error")
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "main":
                print("  ✓ Successfully fell back to default 'main' branch")
                return True
            else:
                print(f"  ✗ Expected 'main', got '{branch}'")
                return False


def test_timeout_handling():
    """Test handling of command timeouts."""
    print("Testing Timeout Handling")
    print("-" * 24)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        # Mock timeout exception
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 30)
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "main":
                print("  ✓ Successfully handled timeout and fell back to 'main'")
                return True
            else:
                print(f"  ✗ Expected 'main', got '{branch}'")
                return False


def test_github_hosting_service():
    """Test branch detection with GitHub-style output."""
    print("Testing GitHub Hosting Service")
    print("-" * 31)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/user/repo.git"
        
        # Mock GitHub-style symbolic reference output
        mock_output = "ref: refs/heads/main\tHEAD\nab1234567890cdef\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "main":
                print("  ✓ Successfully detected GitHub default branch")
                return True
            else:
                print(f"  ✗ Expected 'main', got '{branch}'")
                return False


def test_gitlab_hosting_service():
    """Test branch detection with GitLab-style repository."""
    print("Testing GitLab Hosting Service")
    print("-" * 31)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://gitlab.com/user/repo.git"
        
        # Mock GitLab-style symbolic reference output (often uses 'main')
        mock_output = "ref: refs/heads/main\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "main":
                print("  ✓ Successfully detected GitLab default branch")
                return True
            else:
                print(f"  ✗ Expected 'main', got '{branch}'")
                return False


def test_bitbucket_hosting_service():
    """Test branch detection with Bitbucket-style repository."""
    print("Testing Bitbucket Hosting Service")
    print("-" * 33)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://bitbucket.org/user/repo.git"
        
        # Mock Bitbucket-style symbolic reference output (often uses 'master')
        mock_output = "ref: refs/heads/master\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "master":
                print("  ✓ Successfully detected Bitbucket default branch")
                return True
            else:
                print(f"  ✗ Expected 'master', got '{branch}'")
                return False


def test_custom_branch_name():
    """Test detection of custom branch names."""
    print("Testing Custom Branch Name")
    print("-" * 26)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = create_test_config(temp_dir)
        git_repo_dir = Path(temp_dir)
        remote_url = "https://github.com/test/repo.git"
        
        # Mock custom branch name
        mock_output = "ref: refs/heads/production\tHEAD\n"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            if branch == "production":
                print("  ✓ Successfully detected custom 'production' branch")
                return True
            else:
                print(f"  ✗ Expected 'production', got '{branch}'")
                return False


def run_all_tests():
    """Run all branch detection tests."""
    print("Dynamic Branch Detection System Tests")
    print("=" * 50)
    print()
    
    tests = [
        test_symbolic_reference_detection,
        test_main_branch_detection,
        test_master_branch_detection,
        test_fallback_to_common_branches,
        test_fallback_to_default,
        test_timeout_handling,
        test_github_hosting_service,
        test_gitlab_hosting_service,
        test_bitbucket_hosting_service,
        test_custom_branch_name
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All branch detection tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
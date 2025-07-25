#!/usr/bin/env python3
"""
Integration test for branch detection with real Git commands.

This test verifies that the detect_remote_default_branch function
works correctly with actual Git repositories.
"""

import tempfile
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.config import Config
from aiaml.git_sync.operations import detect_remote_default_branch


def test_with_public_repository():
    """Test branch detection with a real public repository."""
    print("Testing with Public Repository")
    print("-" * 35)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            memory_dir=Path(temp_dir) / "memory" / "files",
            enable_git_sync=True,
            git_retry_attempts=2,
            git_retry_delay=0.5
        )
        
        git_repo_dir = Path(temp_dir)
        
        # Test with a well-known public repository that uses 'main'
        remote_url = "https://github.com/octocat/Hello-World.git"
        
        try:
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            print(f"  ✓ Detected branch: {branch}")
            
            # The function should return a valid branch name
            if branch and isinstance(branch, str) and len(branch) > 0:
                print("  ✓ Function returned a valid branch name")
                return True
            else:
                print(f"  ✗ Invalid branch name returned: {branch}")
                return False
                
        except Exception as e:
            print(f"  ✗ Exception occurred: {e}")
            return False


def test_with_nonexistent_repository():
    """Test branch detection with a non-existent repository."""
    print("Testing with Non-existent Repository")
    print("-" * 38)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = Config(
            memory_dir=Path(temp_dir) / "memory" / "files",
            enable_git_sync=True,
            git_retry_attempts=1,
            git_retry_delay=0.1
        )
        
        git_repo_dir = Path(temp_dir)
        
        # Test with a non-existent repository
        remote_url = "https://github.com/nonexistent/nonexistent-repo.git"
        
        try:
            branch = detect_remote_default_branch(remote_url, config, git_repo_dir)
            
            # Should fall back to 'main' when repository doesn't exist
            if branch == "main":
                print("  ✓ Correctly fell back to 'main' for non-existent repository")
                return True
            else:
                print(f"  ✗ Expected 'main', got '{branch}'")
                return False
                
        except Exception as e:
            print(f"  ✗ Exception occurred: {e}")
            return False


def run_integration_tests():
    """Run integration tests for branch detection."""
    print("Branch Detection Integration Tests")
    print("=" * 45)
    print()
    
    tests = [
        test_with_public_repository,
        test_with_nonexistent_repository
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
    
    print("=" * 45)
    print(f"Integration tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All integration tests passed!")
        return True
    else:
        print("✗ Some integration tests failed")
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Unit tests for upstream tracking configuration system.

This test suite validates the setup_upstream_tracking() method and related
functionality in the RepositoryStateManager class.

Requirements tested: 4.1, 4.2, 4.3
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add the project root to the path so we can import aiaml modules
import sys
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.config import Config
from aiaml.git_sync.state import RepositoryStateManager, RepositoryState
from aiaml.git_sync.utils import GitSyncResult


class TestUpstreamTracking(unittest.TestCase):
    """Test cases for upstream tracking configuration."""
    
    def setUp(self):
        """Set up test environment before each test."""
        print(f"\nSetting up test: {self._testMethodName}")
        
        # Create temporary directory for test repository
        self.temp_dir = Path(tempfile.mkdtemp())
        self.git_repo_dir = self.temp_dir / "test_repo"
        self.git_repo_dir.mkdir(parents=True)
        
        # Create test configuration
        self.config = Config(
            memory_dir=self.temp_dir / "memory" / "files",
            git_remote_url="https://github.com/test/test-repo.git",
            enable_git_sync=True,
            git_retry_attempts=2,
            git_retry_delay=0.1
        )
        
        # Create RepositoryStateManager instance
        self.repo_manager = RepositoryStateManager(self.config, self.git_repo_dir)
        
        print(f"  Test directory: {self.temp_dir}")
        print(f"  Git repo directory: {self.git_repo_dir}")
    
    def tearDown(self):
        """Clean up test environment after each test."""
        print(f"Cleaning up test: {self._testMethodName}")
        
        # Remove temporary directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        
        print("  Cleanup completed")
    
    def _create_mock_git_repo(self):
        """Create a mock Git repository structure."""
        git_dir = self.git_repo_dir / ".git"
        git_dir.mkdir(parents=True)
        
        # Create basic Git structure
        (git_dir / "config").write_text("[core]\n    repositoryformatversion = 0\n")
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        
        refs_heads = git_dir / "refs" / "heads"
        refs_heads.mkdir(parents=True)
        (refs_heads / "main").write_text("abc123\n")
        
        refs_remotes = git_dir / "refs" / "remotes" / "origin"
        refs_remotes.mkdir(parents=True)
        (refs_remotes / "main").write_text("abc123\n")
        (refs_remotes / "develop").write_text("def456\n")
    
    def test_setup_upstream_tracking_no_local_repo(self):
        """Test setup_upstream_tracking fails when no local repository exists."""
        print("Testing upstream tracking setup with no local repository")
        
        # Ensure no .git directory exists
        git_dir = self.git_repo_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)
        
        result = self.repo_manager.setup_upstream_tracking("main")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "NO_LOCAL_REPO")
        self.assertIn("local Git repository does not exist", result.message)
        print("  ✓ Correctly failed when no local repository exists")
    
    def test_setup_upstream_tracking_no_remote_url(self):
        """Test setup_upstream_tracking fails when no remote URL is configured."""
        print("Testing upstream tracking setup with no remote URL")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Create config without remote URL
        config_no_remote = Config(
            memory_dir=self.temp_dir / "memory" / "files",
            git_remote_url=None,
            enable_git_sync=True
        )
        
        repo_manager = RepositoryStateManager(config_no_remote, self.git_repo_dir)
        result = repo_manager.setup_upstream_tracking("main")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "NO_REMOTE_URL")
        self.assertIn("no remote URL configured", result.message)
        print("  ✓ Correctly failed when no remote URL configured")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_no_local_remote(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking fails when remote is not configured locally."""
        print("Testing upstream tracking setup with no local remote configured")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        # Mock subprocess calls
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            if "remote" in command and "get-url" in command:
                # Simulate remote not configured
                result = Mock()
                result.returncode = 1
                result.stdout = ""
                result.stderr = "fatal: No such remote 'origin'"
                return result
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("main")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "NO_LOCAL_REMOTE")
        self.assertIn("remote 'origin' not configured", result.message)
        print("  ✓ Correctly failed when remote not configured locally")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_remote_branch_not_found(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking fails when remote branch doesn't exist."""
        print("Testing upstream tracking setup with non-existent remote branch")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        # Mock subprocess calls
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            if "remote" in command and "get-url" in command:
                # Simulate remote configured
                result = Mock()
                result.returncode = 0
                result.stdout = "https://github.com/test/test-repo.git"
                return result
            elif "ls-remote" in command and "--heads" in command:
                # Simulate remote branch not found
                result = Mock()
                result.returncode = 0
                result.stdout = ""  # Empty output means branch not found
                return result
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("nonexistent")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "REMOTE_BRANCH_NOT_FOUND")
        self.assertIn("remote branch 'origin/nonexistent' does not exist", result.message)
        print("  ✓ Correctly failed when remote branch doesn't exist")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_create_new_branch(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking creates new local branch from remote."""
        print("Testing upstream tracking setup by creating new local branch")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        # Track subprocess calls
        subprocess_calls = []
        
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            subprocess_calls.append(command)
            
            if "remote" in command and "get-url" in command:
                # Simulate remote configured
                result = Mock()
                result.returncode = 0
                result.stdout = "https://github.com/test/test-repo.git"
                return result
            elif "ls-remote" in command and "--heads" in command:
                # Simulate remote branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "abc123\trefs/heads/develop"
                return result
            elif "branch" in command and "--list" in command:
                # Simulate local branch doesn't exist
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            elif "checkout" in command and "-b" in command:
                # Simulate successful branch creation
                result = Mock()
                result.returncode = 0
                result.stdout = "Switched to a new branch 'develop'"
                return result
            elif "config" in command and "branch.develop.remote" in command:
                # Simulate upstream tracking configured
                result = Mock()
                result.returncode = 0
                result.stdout = "origin"
                return result
            elif "config" in command and "branch.develop.merge" in command:
                # Simulate merge configuration
                result = Mock()
                result.returncode = 0
                result.stdout = "refs/heads/develop"
                return result
            elif "status" in command and "-b" in command:
                # Simulate status with tracking info
                result = Mock()
                result.returncode = 0
                result.stdout = "## develop...origin/develop"
                return result
            elif "fetch" in command:
                # Simulate successful fetch
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("develop")
        
        self.assertTrue(result.success)
        self.assertIn("Successfully created branch 'develop' with upstream tracking", result.message)
        
        # Verify that checkout -b was called
        checkout_calls = [call for call in subprocess_calls if "checkout" in call and "-b" in call]
        self.assertEqual(len(checkout_calls), 1)
        self.assertIn("develop", checkout_calls[0])
        self.assertIn("origin/develop", checkout_calls[0])
        
        print("  ✓ Successfully created new branch with upstream tracking")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_existing_branch_no_tracking(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking configures tracking for existing branch."""
        print("Testing upstream tracking setup for existing branch without tracking")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        # Track subprocess calls
        subprocess_calls = []
        
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            subprocess_calls.append(command)
            
            if "remote" in command and "get-url" in command:
                # Simulate remote configured
                result = Mock()
                result.returncode = 0
                result.stdout = "https://github.com/test/test-repo.git"
                return result
            elif "ls-remote" in command and "--heads" in command:
                # Simulate remote branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "abc123\trefs/heads/main"
                return result
            elif "branch" in command and "--list" in command:
                # Simulate local branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "  main"
                return result
            elif "config" in command and "branch.main.remote" in command and "--set-upstream-to" not in command:
                # First call: simulate no tracking configured
                if len([call for call in subprocess_calls if "branch.main.remote" in call]) == 1:
                    result = Mock()
                    result.returncode = 1
                    result.stdout = ""
                    return result
                # After setup: simulate tracking configured
                else:
                    result = Mock()
                    result.returncode = 0
                    result.stdout = "origin"
                    return result
            elif "branch" in command and "--show-current" in command:
                # Simulate current branch
                result = Mock()
                result.returncode = 0
                result.stdout = "main"
                return result
            elif "branch" in command and "--set-upstream-to" in command:
                # Simulate successful upstream setup
                result = Mock()
                result.returncode = 0
                result.stdout = "Branch 'main' set up to track remote branch 'main' from 'origin'."
                return result
            elif "config" in command and "branch.main.merge" in command:
                # Simulate merge configuration
                result = Mock()
                result.returncode = 0
                result.stdout = "refs/heads/main"
                return result
            elif "status" in command and "-b" in command:
                # Simulate status with tracking info
                result = Mock()
                result.returncode = 0
                result.stdout = "## main...origin/main"
                return result
            elif "fetch" in command:
                # Simulate successful fetch
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("main")
        
        self.assertTrue(result.success)
        self.assertIn("Successfully set up upstream tracking for branch 'main'", result.message)
        
        # Verify that --set-upstream-to was called
        upstream_calls = [call for call in subprocess_calls if "--set-upstream-to" in call]
        self.assertEqual(len(upstream_calls), 1)
        self.assertIn("origin/main", upstream_calls[0])
        
        print("  ✓ Successfully configured upstream tracking for existing branch")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_already_configured(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking when tracking is already configured."""
        print("Testing upstream tracking setup when already configured")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            
            if "remote" in command and "get-url" in command:
                # Simulate remote configured
                result = Mock()
                result.returncode = 0
                result.stdout = "https://github.com/test/test-repo.git"
                return result
            elif "ls-remote" in command and "--heads" in command:
                # Simulate remote branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "abc123\trefs/heads/main"
                return result
            elif "branch" in command and "--list" in command:
                # Simulate local branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "  main"
                return result
            elif "config" in command and "branch.main.remote" in command:
                # Simulate tracking already configured
                result = Mock()
                result.returncode = 0
                result.stdout = "origin"
                return result
            elif "fetch" in command:
                # Simulate successful fetch
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("main")
        
        self.assertTrue(result.success)
        self.assertIn("Upstream tracking already configured for branch 'main'", result.message)
        print("  ✓ Correctly detected already configured upstream tracking")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_branch_creation_failed(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking handles branch creation failure."""
        print("Testing upstream tracking setup with branch creation failure")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            
            if "remote" in command and "get-url" in command:
                # Simulate remote configured
                result = Mock()
                result.returncode = 0
                result.stdout = "https://github.com/test/test-repo.git"
                return result
            elif "ls-remote" in command and "--heads" in command:
                # Simulate remote branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "abc123\trefs/heads/develop"
                return result
            elif "branch" in command and "--list" in command:
                # Simulate local branch doesn't exist
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            elif "checkout" in command and "-b" in command:
                # Simulate branch creation failure
                result = Mock()
                result.returncode = 1
                result.stderr = "fatal: A branch named 'develop' already exists."
                return result
            elif "fetch" in command:
                # Simulate successful fetch
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("develop")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "BRANCH_CREATION_FAILED")
        self.assertIn("Failed to create local branch 'develop'", result.message)
        print("  ✓ Correctly handled branch creation failure")
    
    @patch('aiaml.git_sync.state.subprocess.run')
    @patch('aiaml.git_sync.state.get_git_executable')
    @patch('aiaml.git_sync.state.get_platform_info')
    def test_setup_upstream_tracking_validation_failure(self, mock_platform, mock_git_exe, mock_subprocess):
        """Test setup_upstream_tracking handles validation failure."""
        print("Testing upstream tracking setup with validation failure")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        # Mock platform and git executable
        mock_platform.return_value = Mock(is_windows=False)
        mock_git_exe.return_value = "git"
        
        # Track which validation call we're on
        validation_calls = []
        
        def mock_run_side_effect(*args, **kwargs):
            command = args[0]
            
            if "remote" in command and "get-url" in command:
                # Simulate remote configured
                result = Mock()
                result.returncode = 0
                result.stdout = "https://github.com/test/test-repo.git"
                return result
            elif "ls-remote" in command and "--heads" in command:
                # Simulate remote branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "abc123\trefs/heads/main"
                return result
            elif "branch" in command and "--list" in command:
                # Simulate local branch exists
                result = Mock()
                result.returncode = 0
                result.stdout = "  main"
                return result
            elif "config" in command and "branch.main.remote" in command and "--set-upstream-to" not in command:
                validation_calls.append("remote_check")
                # First check during initial tracking check: no tracking
                if len(validation_calls) == 1:
                    result = Mock()
                    result.returncode = 1
                    result.stdout = ""
                    return result
                # During validation after setup: simulate remote configured
                else:
                    result = Mock()
                    result.returncode = 0
                    result.stdout = "origin"
                    return result
            elif "branch" in command and "--show-current" in command:
                # Simulate current branch
                result = Mock()
                result.returncode = 0
                result.stdout = "main"
                return result
            elif "branch" in command and "--set-upstream-to" in command:
                # Simulate successful upstream setup
                result = Mock()
                result.returncode = 0
                result.stdout = "Branch 'main' set up to track remote branch 'main' from 'origin'."
                return result
            elif "config" in command and "branch.main.merge" in command:
                # Simulate validation failure - no merge config
                result = Mock()
                result.returncode = 1
                result.stdout = ""
                return result
            elif "fetch" in command:
                # Simulate successful fetch
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                return result
            
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_subprocess.side_effect = mock_run_side_effect
        
        result = self.repo_manager.setup_upstream_tracking("main")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "NO_MERGE_CONFIG")
        self.assertIn("no merge configuration for branch 'main'", result.message)
        print("  ✓ Correctly handled validation failure")
    
    def test_check_remote_branch_exists_helper(self):
        """Test check_remote_branch_exists helper function."""
        print("Testing check_remote_branch_exists helper function")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        with patch('aiaml.git_sync.branch_utils.subprocess.run') as mock_subprocess, \
             patch('aiaml.git_sync.branch_utils.get_git_executable') as mock_git_exe, \
             patch('aiaml.git_sync.branch_utils.get_platform_info') as mock_platform:
            
            mock_platform.return_value = Mock(is_windows=False)
            mock_git_exe.return_value = "git"
            
            def mock_run_side_effect(*args, **kwargs):
                command = args[0]
                
                if "fetch" in command:
                    # Simulate successful fetch
                    return Mock(returncode=0, stdout="", stderr="")
                elif "ls-remote" in command and "--heads" in command:
                    if "main" in command:
                        # Simulate main branch exists
                        return Mock(returncode=0, stdout="abc123\trefs/heads/main")
                    else:
                        # Simulate other branches don't exist
                        return Mock(returncode=0, stdout="")
                
                return Mock(returncode=0, stdout="", stderr="")
            
            mock_subprocess.side_effect = mock_run_side_effect
            
            # Import the function
            from aiaml.git_sync.branch_utils import check_remote_branch_exists
            
            # Test existing branch
            exists = check_remote_branch_exists(self.git_repo_dir, "main")
            self.assertTrue(exists)
            
            # Test non-existing branch
            exists = check_remote_branch_exists(self.git_repo_dir, "nonexistent")
            self.assertFalse(exists)
            
            print("  ✓ Helper function correctly detects remote branch existence")
    
    def test_check_local_branch_exists_helper(self):
        """Test check_local_branch_exists helper function."""
        print("Testing check_local_branch_exists helper function")
        
        # Create mock Git repository
        self._create_mock_git_repo()
        
        with patch('aiaml.git_sync.branch_utils.subprocess.run') as mock_subprocess, \
             patch('aiaml.git_sync.branch_utils.get_git_executable') as mock_git_exe, \
             patch('aiaml.git_sync.branch_utils.get_platform_info') as mock_platform:
            
            mock_platform.return_value = Mock(is_windows=False)
            mock_git_exe.return_value = "git"
            
            def mock_run_side_effect(*args, **kwargs):
                command = args[0]
                
                if "branch" in command and "--list" in command:
                    if "main" in command:
                        # Simulate main branch exists
                        return Mock(returncode=0, stdout="  main")
                    else:
                        # Simulate other branches don't exist
                        return Mock(returncode=0, stdout="")
                
                return Mock(returncode=0, stdout="", stderr="")
            
            mock_subprocess.side_effect = mock_run_side_effect
            
            # Import the function
            from aiaml.git_sync.branch_utils import check_local_branch_exists
            
            # Test existing branch
            exists = check_local_branch_exists(self.git_repo_dir, "main")
            self.assertTrue(exists)
            
            # Test non-existing branch
            exists = check_local_branch_exists(self.git_repo_dir, "nonexistent")
            self.assertFalse(exists)
            
            print("  ✓ Helper function correctly detects local branch existence")


def run_tests():
    """Run all upstream tracking tests."""
    print("Running Upstream Tracking Configuration Tests")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestUpstreamTracking)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOverall result: {'PASS' if success else 'FAIL'}")
    
    return success


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
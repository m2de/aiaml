#!/usr/bin/env python3
"""
Unit tests for enhanced GitSyncResult with repository information.

This test file validates the enhanced GitSyncResult dataclass and the
create_git_sync_result helper function to ensure they properly handle
the new repository_info and branch_used fields.

Requirements tested: 5.1, 5.2
"""

import sys
import tempfile
from pathlib import Path

# Add the aiaml package to the path
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.git_sync.utils import GitSyncResult, create_git_sync_result
from aiaml.git_sync.repository_info import RepositoryState, RepositoryInfo


def test_enhanced_git_sync_result_structure():
    """Test that GitSyncResult has all required fields including new ones."""
    print("Testing Enhanced GitSyncResult Structure")
    print("-" * 40)
    
    # Test basic GitSyncResult creation with all fields
    repo_info = RepositoryInfo(
        state=RepositoryState.SYNCHRONIZED,
        local_exists=True,
        remote_exists=True,
        remote_url="https://github.com/test/repo.git",
        default_branch="main",
        local_branch="main",
        tracking_configured=True,
        needs_sync=False
    )
    
    result = GitSyncResult(
        success=True,
        message="Test operation completed",
        operation="test_operation",
        attempts=2,
        error_code=None,
        repository_info=repo_info,
        branch_used="main"
    )
    
    # Verify all fields are present and accessible
    assert result.success is True, "success field should be accessible"
    assert result.message == "Test operation completed", "message field should be accessible"
    assert result.operation == "test_operation", "operation field should be accessible"
    assert result.attempts == 2, "attempts field should be accessible"
    assert result.error_code is None, "error_code field should be accessible"
    assert result.repository_info is not None, "repository_info field should be accessible"
    assert result.branch_used == "main", "branch_used field should be accessible"
    
    # Verify repository_info content
    assert result.repository_info.state == RepositoryState.SYNCHRONIZED, "repository state should be correct"
    assert result.repository_info.default_branch == "main", "default branch should be correct"
    assert result.repository_info.remote_url == "https://github.com/test/repo.git", "remote URL should be correct"
    
    print("  ✓ GitSyncResult has all required fields")
    print("  ✓ New repository_info field is accessible")
    print("  ✓ New branch_used field is accessible")
    print("  ✓ Repository info contains expected data")
    
    return True


def test_git_sync_result_with_optional_fields():
    """Test GitSyncResult with optional fields set to None."""
    print("\nTesting GitSyncResult with Optional Fields")
    print("-" * 40)
    
    # Test with minimal required fields
    result = GitSyncResult(
        success=False,
        message="Operation failed",
        operation="test_operation"
    )
    
    # Verify default values
    assert result.success is False, "success should be False"
    assert result.message == "Operation failed", "message should be set"
    assert result.operation == "test_operation", "operation should be set"
    assert result.attempts == 1, "attempts should default to 1"
    assert result.error_code is None, "error_code should default to None"
    assert result.repository_info is None, "repository_info should default to None"
    assert result.branch_used is None, "branch_used should default to None"
    
    print("  ✓ Default values are correct")
    print("  ✓ Optional fields default to None")
    print("  ✓ Required fields are properly set")
    
    return True


def test_create_git_sync_result_helper():
    """Test the create_git_sync_result helper function."""
    print("\nTesting create_git_sync_result Helper Function")
    print("-" * 40)
    
    # Test with all parameters
    repo_info = RepositoryInfo(
        state=RepositoryState.EXISTING_LOCAL,
        local_exists=True,
        remote_exists=False,
        remote_url=None,
        default_branch="develop",
        local_branch="develop",
        tracking_configured=False,
        needs_sync=False
    )
    
    result = create_git_sync_result(
        success=True,
        message="Helper function test",
        operation="helper_test",
        attempts=3,
        error_code="TEST_ERROR",
        repository_info=repo_info,
        branch_used="develop"
    )
    
    # Verify all fields are set correctly
    assert result.success is True, "success should be True"
    assert result.message == "Helper function test", "message should be correct"
    assert result.operation == "helper_test", "operation should be correct"
    assert result.attempts == 3, "attempts should be 3"
    assert result.error_code == "TEST_ERROR", "error_code should be correct"
    assert result.repository_info is not None, "repository_info should be set"
    assert result.branch_used == "develop", "branch_used should be correct"
    
    # Verify repository info
    assert result.repository_info.state == RepositoryState.EXISTING_LOCAL, "repository state should be correct"
    assert result.repository_info.default_branch == "develop", "default branch should be develop"
    
    print("  ✓ Helper function creates correct GitSyncResult")
    print("  ✓ All parameters are properly passed through")
    print("  ✓ Repository info is correctly attached")
    
    return True


def test_create_git_sync_result_with_defaults():
    """Test create_git_sync_result with minimal parameters."""
    print("\nTesting create_git_sync_result with Defaults")
    print("-" * 40)
    
    # Test with minimal parameters
    result = create_git_sync_result(
        success=False,
        message="Minimal test",
        operation="minimal_operation"
    )
    
    # Verify required fields
    assert result.success is False, "success should be False"
    assert result.message == "Minimal test", "message should be correct"
    assert result.operation == "minimal_operation", "operation should be correct"
    
    # Verify defaults
    assert result.attempts == 1, "attempts should default to 1"
    assert result.error_code is None, "error_code should default to None"
    assert result.repository_info is None, "repository_info should default to None"
    assert result.branch_used is None, "branch_used should default to None"
    
    print("  ✓ Helper function works with minimal parameters")
    print("  ✓ Default values are applied correctly")
    
    return True


def test_repository_info_integration():
    """Test integration between GitSyncResult and RepositoryInfo."""
    print("\nTesting RepositoryInfo Integration")
    print("-" * 40)
    
    # Test with different repository states
    test_cases = [
        (RepositoryState.NEW_LOCAL, "main", None),
        (RepositoryState.EXISTING_LOCAL, "master", "https://github.com/test/repo.git"),
        (RepositoryState.EXISTING_REMOTE, "develop", "https://github.com/test/repo.git"),
        (RepositoryState.SYNCHRONIZED, "main", "https://github.com/test/repo.git")
    ]
    
    for state, branch, remote_url in test_cases:
        repo_info = RepositoryInfo(
            state=state,
            local_exists=(state != RepositoryState.NEW_LOCAL),
            remote_exists=(remote_url is not None),
            remote_url=remote_url,
            default_branch=branch,
            local_branch=branch if state != RepositoryState.EXISTING_REMOTE else None,
            tracking_configured=(state == RepositoryState.SYNCHRONIZED),
            needs_sync=(state in [RepositoryState.EXISTING_LOCAL, RepositoryState.EXISTING_REMOTE])
        )
        
        result = create_git_sync_result(
            success=True,
            message=f"Test for {state.value}",
            operation="integration_test",
            repository_info=repo_info,
            branch_used=branch
        )
        
        # Verify integration
        assert result.repository_info.state == state, f"State should be {state}"
        assert result.repository_info.default_branch == branch, f"Branch should be {branch}"
        assert result.repository_info.remote_url == remote_url, f"Remote URL should be {remote_url}"
        assert result.branch_used == branch, f"Branch used should be {branch}"
        
        print(f"  ✓ Integration test passed for {state.value}")
    
    return True


def test_error_scenarios():
    """Test GitSyncResult with error scenarios."""
    print("\nTesting Error Scenarios")
    print("-" * 40)
    
    # Test error with repository info
    repo_info = RepositoryInfo(
        state=RepositoryState.EXISTING_LOCAL,
        local_exists=True,
        remote_exists=True,
        remote_url="https://github.com/test/repo.git",
        default_branch="main",
        local_branch="main",
        tracking_configured=False,
        needs_sync=True
    )
    
    error_result = create_git_sync_result(
        success=False,
        message="Push failed due to network error",
        operation="push_to_remote",
        attempts=3,
        error_code="NETWORK_ERROR",
        repository_info=repo_info,
        branch_used="main"
    )
    
    # Verify error result
    assert error_result.success is False, "Error result should have success=False"
    assert error_result.error_code == "NETWORK_ERROR", "Error code should be set"
    assert error_result.attempts == 3, "Attempts should be recorded"
    assert error_result.repository_info is not None, "Repository info should be available even on error"
    assert error_result.branch_used == "main", "Branch used should be recorded even on error"
    
    print("  ✓ Error scenarios properly handled")
    print("  ✓ Repository info preserved in error cases")
    print("  ✓ Error codes and attempts properly recorded")
    
    return True


def run_all_tests():
    """Run all tests for enhanced GitSyncResult."""
    print("Enhanced GitSyncResult Test Suite")
    print("=" * 50)
    
    tests = [
        test_enhanced_git_sync_result_structure,
        test_git_sync_result_with_optional_fields,
        test_create_git_sync_result_helper,
        test_create_git_sync_result_with_defaults,
        test_repository_info_integration,
        test_error_scenarios
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
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All tests passed! Enhanced GitSyncResult is working correctly.")
        return True
    else:
        print("✗ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
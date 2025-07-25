"""Simple backward compatibility test for enhanced Git sync features."""

import logging
import tempfile
from pathlib import Path

from ..config import Config
from .manager import GitSyncManager, get_git_sync_manager
from .utils import GitSyncResult
from .compatibility import verify_git_sync_compatibility


def test_basic_backward_compatibility():
    """
    Test basic backward compatibility scenarios.
    
    Returns:
        bool: True if all tests pass
    """
    # Set up test config
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create minimal config like existing code would use
        class TestConfig:
            def __init__(self):
                self.enable_git_sync = True
                self.git_remote_url = None  # No remote for basic test
                self.git_retry_attempts = 3
                self.git_retry_delay = 1.0
                self.git_repo_dir = temp_path / "test_repo"
                self.memory_dir = temp_path / "memory"
                self.memory_dir.mkdir(exist_ok=True)
        
        config = TestConfig()
        
        try:
            # Test 1: Basic manager creation (should work like before)
            manager = GitSyncManager(config)
            print("✅ GitSyncManager creation works")
            
            # Test 2: Check essential methods exist
            assert hasattr(manager, 'sync_memory_with_retry')
            assert hasattr(manager, 'sync_memory_background')
            assert hasattr(manager, 'get_repository_status')
            assert hasattr(manager, 'is_initialized')
            print("✅ All essential methods exist")
            
            # Test 3: Repository status (should work without errors)
            status = manager.get_repository_status()
            assert isinstance(status, dict)
            assert 'initialized' in status
            assert 'git_sync_enabled' in status
            print("✅ Repository status works")
            
            # Test 4: Global manager access (should work like before)
            global_manager = get_git_sync_manager(config)
            assert global_manager is not None
            print("✅ Global manager access works")
            
            # Test 5: GitSyncResult compatibility
            test_result = GitSyncResult(
                success=True,
                message="Test message",
                operation="test"
            )
            # Old code expects these fields
            assert hasattr(test_result, 'success')
            assert hasattr(test_result, 'message')
            assert hasattr(test_result, 'operation')
            assert hasattr(test_result, 'attempts')
            assert hasattr(test_result, 'error_code')
            
            # New fields should default to None for compatibility
            assert test_result.repository_info is None
            assert test_result.branch_used is None
            print("✅ GitSyncResult backward compatibility verified")
            
            print("🎉 All backward compatibility tests passed!")
            return True
            
        except Exception as e:
            print(f"❌ Backward compatibility test failed: {e}")
            return False


def test_enhanced_features_fallback():
    """
    Test that enhanced features fail gracefully and fall back to basic functionality.
    
    Returns:
        bool: True if fallback works correctly
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        class TestConfig:
            def __init__(self):
                self.enable_git_sync = True
                self.git_remote_url = None
                self.git_retry_attempts = 3
                self.git_retry_delay = 1.0
                self.git_repo_dir = temp_path / "test_repo"
                self.memory_dir = temp_path / "memory"
                self.memory_dir.mkdir(exist_ok=True)
        
        config = TestConfig()
        
        try:
            # Create manager
            manager = GitSyncManager(config)
            
            # Test that enhanced features can be disabled/fail gracefully
            # Temporarily disable enhanced features
            original_error_handler = manager.error_handler
            original_perf_logger = manager.perf_logger
            
            manager.error_handler = None
            manager.perf_logger = None
            
            # Test that basic operations still work
            status = manager.get_repository_status()
            assert isinstance(status, dict)
            print("✅ Basic operations work with enhanced features disabled")
            
            # Test safe error handling fallback
            result = manager._safe_error_handling(
                "test error", "test_operation", "TEST_ERROR"
            )
            assert isinstance(result, GitSyncResult)
            assert not result.success
            assert result.message == "test error"
            print("✅ Safe error handling fallback works")
            
            # Test safe performance operation fallback
            with manager._safe_performance_operation("test_op"):
                pass  # Should not raise exception
            print("✅ Safe performance operation fallback works")
            
            # Restore enhanced features
            manager.error_handler = original_error_handler
            manager.perf_logger = original_perf_logger
            
            print("🎉 Enhanced features fallback test passed!")
            return True
            
        except Exception as e:
            print(f"❌ Enhanced features fallback test failed: {e}")
            return False


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    
    print("🧪 Running backward compatibility tests...")
    print()
    
    # Run tests
    basic_test = test_basic_backward_compatibility()
    print()
    
    fallback_test = test_enhanced_features_fallback()
    print()
    
    if basic_test and fallback_test:
        print("🎉 All backward compatibility tests PASSED!")
        print("Enhanced Git sync is fully backward compatible.")
    else:
        print("❌ Some backward compatibility tests FAILED!")
        print("Review the enhanced Git sync implementation.")
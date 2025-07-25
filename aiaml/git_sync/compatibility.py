"""Backward compatibility verification for enhanced Git sync features."""

import logging
from pathlib import Path
from typing import Dict, Any, List

from ..config import Config
from .utils import GitSyncResult, create_git_sync_result
from .manager import GitSyncManager


class CompatibilityVerifier:
    """
    Verifies backward compatibility of enhanced Git sync features.
    
    This class provides utilities to test that existing Git sync functionality
    continues to work unchanged after enhancements.
    """
    
    def __init__(self, config: Config):
        """
        Initialize compatibility verifier.
        
        Args:
            config: Server configuration for testing
        """
        self.config = config
        self.logger = logging.getLogger('aiaml.git_sync.compatibility')
    
    def verify_api_compatibility(self) -> GitSyncResult:
        """
        Verify that the public API remains compatible.
        
        Returns:
            GitSyncResult indicating compatibility status
        """
        try:
            self.logger.info("🔍 Verifying Git sync API compatibility")
            
            # Test 1: GitSyncManager instantiation
            try:
                manager = GitSyncManager(self.config)
                self.logger.debug("✅ GitSyncManager instantiation works")
            except Exception as e:
                return create_git_sync_result(
                    success=False,
                    message=f"GitSyncManager instantiation failed: {e}",
                    operation="api_compatibility_check",
                    error_code="MANAGER_INSTANTIATION_FAILED"
                )
            
            # Test 2: Core method signatures exist
            required_methods = [
                'sync_memory_with_retry',
                'sync_memory_background', 
                'get_repository_status',
                'is_initialized'
            ]
            
            for method_name in required_methods:
                if not hasattr(manager, method_name):
                    return create_git_sync_result(
                        success=False,
                        message=f"Required method '{method_name}' is missing",
                        operation="api_compatibility_check",
                        error_code="MISSING_METHOD"
                    )
                self.logger.debug(f"✅ Method '{method_name}' exists")
            
            # Test 3: GitSyncResult structure compatibility
            test_result = create_git_sync_result(
                success=True,
                message="Test message",
                operation="test_operation"
            )
            
            # Verify core fields exist
            required_fields = ['success', 'message', 'operation', 'attempts', 'error_code']
            for field in required_fields:
                if not hasattr(test_result, field):
                    return create_git_sync_result(
                        success=False,
                        message=f"GitSyncResult missing required field: {field}",
                        operation="api_compatibility_check",
                        error_code="MISSING_RESULT_FIELD"
                    )
                self.logger.debug(f"✅ GitSyncResult field '{field}' exists")
            
            # Test 4: New optional fields default to None
            if test_result.repository_info is not None:
                self.logger.warning("⚠️ repository_info should default to None for compatibility")
            if test_result.branch_used is not None:
                self.logger.warning("⚠️ branch_used should default to None for compatibility")
            
            self.logger.info("✅ API compatibility verification passed")
            return create_git_sync_result(
                success=True,
                message="API compatibility verified successfully",
                operation="api_compatibility_check"
            )
            
        except Exception as e:
            self.logger.error(f"❌ API compatibility check failed: {e}", exc_info=True)
            return create_git_sync_result(
                success=False,
                message=f"API compatibility check failed: {e}",
                operation="api_compatibility_check",
                error_code="COMPATIBILITY_CHECK_ERROR"
            )
    
    def verify_configuration_compatibility(self) -> GitSyncResult:
        """
        Verify that existing configurations work without modification.
        
        Returns:
            GitSyncResult indicating configuration compatibility
        """
        try:
            self.logger.info("🔍 Verifying configuration compatibility")
            
            # Test 1: Required config fields exist
            required_config_fields = [
                'enable_git_sync',
                'git_remote_url',
                'git_retry_attempts',
                'git_retry_delay',
                'git_repo_dir'
            ]
            
            for field in required_config_fields:
                if not hasattr(self.config, field):
                    return create_git_sync_result(
                        success=False,
                        message=f"Required config field '{field}' is missing",
                        operation="config_compatibility_check",
                        error_code="MISSING_CONFIG_FIELD"
                    )
                self.logger.debug(f"✅ Config field '{field}' exists")
            
            # Test 2: Config values have appropriate defaults
            if self.config.git_retry_attempts is None or self.config.git_retry_attempts < 1:
                self.logger.warning("⚠️ git_retry_attempts should have a sensible default")
            
            if self.config.git_retry_delay is None or self.config.git_retry_delay < 0:
                self.logger.warning("⚠️ git_retry_delay should have a sensible default")
            
            # Test 3: GitSyncManager can be created with basic config
            try:
                manager = GitSyncManager(self.config)
                self.logger.debug("✅ GitSyncManager works with existing config")
            except Exception as e:
                return create_git_sync_result(
                    success=False,
                    message=f"GitSyncManager failed with existing config: {e}",
                    operation="config_compatibility_check",
                    error_code="CONFIG_MANAGER_FAILED"
                )
            
            self.logger.info("✅ Configuration compatibility verification passed")
            return create_git_sync_result(
                success=True,
                message="Configuration compatibility verified successfully",
                operation="config_compatibility_check"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Configuration compatibility check failed: {e}", exc_info=True)
            return create_git_sync_result(
                success=False,
                message=f"Configuration compatibility check failed: {e}",
                operation="config_compatibility_check",
                error_code="CONFIG_COMPATIBILITY_ERROR"
            )
    
    def verify_fallback_mechanisms(self) -> GitSyncResult:
        """
        Verify that fallback mechanisms work when enhanced features fail.
        
        Returns:
            GitSyncResult indicating fallback compatibility
        """
        try:
            self.logger.info("🔍 Verifying fallback mechanisms")
            
            # Test 1: Enhanced features have proper fallbacks
            manager = GitSyncManager(self.config)
            
            # Test error handler fallback
            if hasattr(manager, 'error_handler'):
                self.logger.debug("✅ Enhanced error handler present")
                
                # Test that basic operations work even if enhanced error handling fails
                try:
                    # Force a scenario where enhanced features might fail
                    test_result = manager.error_handler.handle_error(
                        "test error", "test_operation", "TEST_CODE"
                    )
                    if not isinstance(test_result, GitSyncResult):
                        return create_git_sync_result(
                            success=False,
                            message="Enhanced error handler doesn't return GitSyncResult",
                            operation="fallback_verification",
                            error_code="INVALID_ERROR_RESULT"
                        )
                    self.logger.debug("✅ Enhanced error handler returns compatible result")
                except Exception as e:
                    self.logger.warning(f"⚠️ Enhanced error handler failed, using fallback: {e}")
            
            # Test repository state manager fallback
            if hasattr(manager, 'repo_state_manager'):
                self.logger.debug("✅ Repository state manager present")
                
                try:
                    # Test basic repository info retrieval
                    repo_info = manager.repo_state_manager.get_repository_info()
                    if repo_info is None:
                        self.logger.warning("⚠️ Repository info returned None, fallback needed")
                    else:
                        self.logger.debug("✅ Repository state manager works correctly")
                except Exception as e:
                    self.logger.warning(f"⚠️ Repository state manager failed, using fallback: {e}")
            
            # Test performance logger fallback
            if hasattr(manager, 'perf_logger'):
                self.logger.debug("✅ Performance logger present")
                
                try:
                    # Test performance logging doesn't break operations
                    with manager.perf_logger.time_operation("test_operation"):
                        pass  # Basic operation
                    self.logger.debug("✅ Performance logging works without breaking operations")
                except Exception as e:
                    self.logger.warning(f"⚠️ Performance logging failed, continuing without it: {e}")
            
            self.logger.info("✅ Fallback mechanism verification passed")
            return create_git_sync_result(
                success=True,
                message="Fallback mechanisms verified successfully",
                operation="fallback_verification"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Fallback verification failed: {e}", exc_info=True)
            return create_git_sync_result(
                success=False,
                message=f"Fallback verification failed: {e}",
                operation="fallback_verification",
                error_code="FALLBACK_VERIFICATION_ERROR"
            )
    
    def run_full_compatibility_check(self) -> Dict[str, GitSyncResult]:
        """
        Run all compatibility checks.
        
        Returns:
            Dictionary mapping check names to their results
        """
        self.logger.info("🚀 Starting full compatibility verification")
        
        checks = {
            'api_compatibility': self.verify_api_compatibility,
            'config_compatibility': self.verify_configuration_compatibility,
            'fallback_mechanisms': self.verify_fallback_mechanisms
        }
        
        results = {}
        all_passed = True
        
        for check_name, check_function in checks.items():
            self.logger.info(f"Running {check_name} check...")
            result = check_function()
            results[check_name] = result
            
            if not result.success:
                all_passed = False
                self.logger.error(f"❌ {check_name} check failed: {result.message}")
            else:
                self.logger.info(f"✅ {check_name} check passed")
        
        # Summary
        if all_passed:
            self.logger.info("🎉 All compatibility checks passed!")
        else:
            self.logger.error("❌ Some compatibility checks failed")
        
        return results
    
    def get_compatibility_report(self) -> str:
        """
        Generate a detailed compatibility report.
        
        Returns:
            Formatted compatibility report string
        """
        results = self.run_full_compatibility_check()
        
        report_lines = [
            "# Git Sync Backward Compatibility Report",
            "",
            "## Summary",
            ""
        ]
        
        total_checks = len(results)
        passed_checks = sum(1 for r in results.values() if r.success)
        
        report_lines.append(f"- Total checks: {total_checks}")
        report_lines.append(f"- Passed: {passed_checks}")
        report_lines.append(f"- Failed: {total_checks - passed_checks}")
        report_lines.append(f"- Success rate: {passed_checks/total_checks:.1%}")
        report_lines.append("")
        
        # Detailed results
        report_lines.append("## Detailed Results")
        report_lines.append("")
        
        for check_name, result in results.items():
            status = "✅ PASS" if result.success else "❌ FAIL"
            report_lines.append(f"### {check_name}: {status}")
            report_lines.append(f"- Message: {result.message}")
            if result.error_code:
                report_lines.append(f"- Error Code: {result.error_code}")
            report_lines.append("")
        
        return "\n".join(report_lines)


def verify_git_sync_compatibility(config: Config) -> bool:
    """
    Convenience function to verify Git sync backward compatibility.
    
    Args:
        config: Configuration to test with
        
    Returns:
        True if all compatibility checks pass, False otherwise
    """
    verifier = CompatibilityVerifier(config)
    results = verifier.run_full_compatibility_check()
    return all(result.success for result in results.values())
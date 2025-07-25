"""Simplified enhanced error handling and recovery for Git synchronization operations."""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any, Callable

from ..config import Config
from ..platform import get_git_executable, get_platform_info
from .utils import GitSyncResult, create_git_sync_result
from .error_types import ErrorCategory, RecoveryAction
from .error_strategies import build_error_strategies, build_error_patterns


class EnhancedErrorHandler:
    """
    Enhanced error handler with comprehensive recovery strategies.
    
    This class provides sophisticated error handling for Git synchronization
    operations, including automatic recovery, user-friendly error messages,
    and detailed resolution guidance.
    """
    
    def __init__(self, config: Config, git_repo_dir: Path):
        """
        Initialize enhanced error handler.
        
        Args:
            config: Server configuration containing Git settings
            git_repo_dir: Path to the Git repository directory
        """
        self.config = config
        self.git_repo_dir = git_repo_dir
        self.logger = logging.getLogger('aiaml.git_sync.error_recovery')
        
        # Error pattern mapping
        self._error_patterns = build_error_patterns()
        
        # Recovery strategies
        self._recovery_strategies = build_error_strategies()
    
    def categorize_error(self, error_message: str, error_code: Optional[str] = None) -> ErrorCategory:
        """
        Categorize an error based on its message and code.
        
        Args:
            error_message: The error message to categorize
            error_code: Optional error code
            
        Returns:
            ErrorCategory enum value
        """
        if not error_message:
            return ErrorCategory.UNKNOWN
        
        error_lower = error_message.lower()
        
        # Check error patterns
        for pattern, category in self._error_patterns.items():
            if pattern in error_lower:
                self.logger.debug(f"Categorized error as {category}: pattern '{pattern}' found")
                return category
        
        # Check error code patterns
        if error_code:
            code_lower = error_code.lower()
            if "timeout" in code_lower:
                return ErrorCategory.NETWORK
            elif "auth" in code_lower or "permission" in code_lower:
                return ErrorCategory.AUTHENTICATION
            elif "branch" in code_lower:
                return ErrorCategory.BRANCH_DETECTION
            elif "conflict" in code_lower:
                return ErrorCategory.MERGE_CONFLICT
        
        self.logger.debug(f"Could not categorize error: {error_message}")
        return ErrorCategory.UNKNOWN
    
    def handle_error(
        self, 
        error_message: str, 
        operation: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> GitSyncResult:
        """
        Handle an error with appropriate recovery strategy.
        
        Args:
            error_message: The error message
            operation: The operation that failed
            error_code: Optional error code
            context: Additional context information
            
        Returns:
            GitSyncResult with enhanced error information
        """
        category = self.categorize_error(error_message, error_code)
        resolution = self._recovery_strategies.get(category)
        
        if not resolution:
            # Handle unknown errors with generic strategy
            from .error_types import ErrorResolution
            resolution = ErrorResolution(
                category=ErrorCategory.UNKNOWN,
                action=RecoveryAction.USER_ACTION_REQUIRED,
                user_message="An unexpected error occurred",
                technical_message=error_message,
                resolution_steps=[
                    "Check the error details below",
                    "Ensure your Git configuration is correct",
                    "Try the operation again",
                    "Contact support if the problem persists"
                ]
            )
        
        # Log the error with category and resolution info
        self.logger.error(
            f"Git sync error in {operation}: {error_message} "
            f"(category: {category}, action: {resolution.action})"
        )
        
        # Create enhanced error message
        enhanced_message = self._create_enhanced_message(resolution, error_message, context)
        
        return create_git_sync_result(
            success=False,
            message=enhanced_message,
            operation=operation,
            error_code=f"{category.value.upper()}_{error_code or 'ERROR'}"
        )
    
    def _create_enhanced_message(
        self, 
        resolution, 
        original_error: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create an enhanced, user-friendly error message."""
        parts = [
            f"❌ {resolution.user_message}",
            "",
            "🔧 What you can do:",
        ]
        
        for i, step in enumerate(resolution.resolution_steps, 1):
            parts.append(f"   {i}. {step}")
        
        if resolution.action == RecoveryAction.RETRY and resolution.max_retries > 0:
            parts.extend([
                "",
                f"🔄 This operation will be retried automatically (up to {resolution.max_retries} times)"
            ])
        
        parts.extend([
            "",
            "📋 Technical details:",
            f"   • Error: {resolution.technical_message}",
            f"   • Category: {resolution.category.value}",
            f"   • Action: {resolution.action.value}"
        ])
        
        if context:
            parts.append("   • Context:")
            for key, value in context.items():
                parts.append(f"     - {key}: {value}")
        
        return "\n".join(parts)
    
    def attempt_recovery(
        self,
        error_category: ErrorCategory,
        recovery_function: Callable[[], GitSyncResult],
        context: Optional[Dict[str, Any]] = None
    ) -> GitSyncResult:
        """
        Attempt error recovery using the appropriate strategy.
        
        Args:
            error_category: The category of error to recover from
            recovery_function: Function to call for recovery attempt
            context: Additional context for recovery
            
        Returns:
            GitSyncResult indicating recovery success or failure
        """
        resolution = self._recovery_strategies.get(error_category)
        if not resolution:
            return create_git_sync_result(
                success=False,
                message=f"No recovery strategy available for {error_category}",
                operation="error_recovery"
            )
        
        if resolution.action == RecoveryAction.USER_ACTION_REQUIRED:
            return create_git_sync_result(
                success=False,
                message=resolution.user_message,
                operation="error_recovery",
                error_code="USER_ACTION_REQUIRED"
            )
        
        if resolution.action == RecoveryAction.ABORT:
            return create_git_sync_result(
                success=False,
                message="Operation aborted due to unrecoverable error",
                operation="error_recovery",
                error_code="OPERATION_ABORTED"
            )
        
        # Attempt recovery with retry logic
        for attempt in range(resolution.max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.info(f"Recovery attempt {attempt}/{resolution.max_retries}")
                    if resolution.retry_delay:
                        import time
                        time.sleep(resolution.retry_delay)
                
                result = recovery_function()
                if result.success:
                    self.logger.info(f"Recovery successful after {attempt + 1} attempts")
                    return result
                
            except Exception as e:
                self.logger.error(f"Recovery attempt {attempt + 1} failed: {e}")
        
        return create_git_sync_result(
            success=False,
            message=f"Recovery failed after {resolution.max_retries + 1} attempts",
            operation="error_recovery",
            error_code="RECOVERY_FAILED"
        )
    
    def validate_repository_integrity(self) -> GitSyncResult:
        """
        Validate the integrity of the local Git repository.
        
        Returns:
            GitSyncResult indicating repository health
        """
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            git_dir = self.git_repo_dir / ".git"
            
            if not git_dir.exists():
                return create_git_sync_result(
                    success=False,
                    message="No Git repository found",
                    operation="integrity_check",
                    error_code="NO_REPOSITORY"
                )
            
            # Check Git repository integrity
            result = subprocess.run(
                [git_executable, "fsck", "--quiet"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                return create_git_sync_result(
                    success=True,
                    message="Repository integrity check passed",
                    operation="integrity_check"
                )
            else:
                return create_git_sync_result(
                    success=False,
                    message=f"Repository integrity issues detected: {result.stderr}",
                    operation="integrity_check",
                    error_code="INTEGRITY_FAILED"
                )
                
        except subprocess.TimeoutExpired:
            return create_git_sync_result(
                success=False,
                message="Repository integrity check timed out",
                operation="integrity_check",
                error_code="INTEGRITY_TIMEOUT"
            )
        except Exception as e:
            return create_git_sync_result(
                success=False,
                message=f"Failed to check repository integrity: {e}",
                operation="integrity_check",
                error_code="INTEGRITY_ERROR"
            )
    
    def recover_corrupted_repository(self) -> GitSyncResult:
        """
        Attempt to recover from repository corruption.
        
        Returns:
            GitSyncResult indicating recovery success
        """
        try:
            self.logger.warning("Attempting to recover from repository corruption")
            
            # First, try to repair the repository
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Try git gc to clean up
            try:
                subprocess.run(
                    [git_executable, "gc", "--prune=now"],
                    capture_output=True,
                    text=True,
                    cwd=self.git_repo_dir,
                    timeout=60,
                    shell=platform_info.is_windows,
                    check=True
                )
                
                # Check if repair worked
                integrity_result = self.validate_repository_integrity()
                if integrity_result.success:
                    return create_git_sync_result(
                        success=True,
                        message="Repository corruption repaired successfully",
                        operation="corruption_recovery"
                    )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass  # Continue to reinitialize
            
            # If repair didn't work, reinitialize the repository
            self.logger.warning("Repository repair failed, reinitializing...")
            
            # Remove .git directory
            import shutil
            git_dir = self.git_repo_dir / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir)
            
            # Reinitialize repository
            subprocess.run(
                [git_executable, "init"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows,
                check=True
            )
            
            return create_git_sync_result(
                success=True,
                message="Repository reinitialized after corruption",
                operation="corruption_recovery"
            )
            
        except Exception as e:
            return create_git_sync_result(
                success=False,
                message=f"Failed to recover from repository corruption: {e}",
                operation="corruption_recovery",
                error_code="RECOVERY_FAILED"
            )
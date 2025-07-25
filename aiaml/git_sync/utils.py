"""Utility classes and functions for Git synchronization."""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .repository_info import RepositoryInfo


@dataclass
class GitSyncResult:
    """Result of a Git synchronization operation."""
    success: bool
    message: str
    operation: str
    attempts: int = 1
    error_code: Optional[str] = None
    repository_info: Optional["RepositoryInfo"] = None
    branch_used: Optional[str] = None


def create_git_sync_result(
    success: bool,
    message: str,
    operation: str,
    attempts: int = 1,
    error_code: Optional[str] = None,
    repository_info: Optional["RepositoryInfo"] = None,
    branch_used: Optional[str] = None
) -> GitSyncResult:
    """
    Helper function to create GitSyncResult instances with enhanced fields.
    
    This function provides a convenient way to create GitSyncResult instances
    while ensuring all new fields are properly handled.
    
    Args:
        success: Whether the operation was successful
        message: Descriptive message about the operation result
        operation: Name of the operation that was performed
        attempts: Number of attempts made (default: 1)
        error_code: Optional error code for failed operations
        repository_info: Optional repository information
        branch_used: Optional branch name that was used in the operation
        
    Returns:
        GitSyncResult instance with all fields populated
    """
    return GitSyncResult(
        success=success,
        message=message,
        operation=operation,
        attempts=attempts,
        error_code=error_code,
        repository_info=repository_info,
        branch_used=branch_used
    )
"""Error recovery strategies for Git synchronization operations."""

from typing import Dict
from .error_types import ErrorCategory, ErrorResolution, RecoveryAction


def build_error_strategies() -> Dict[ErrorCategory, ErrorResolution]:
    """Build recovery strategies for each error category."""
    return {
        ErrorCategory.NETWORK: ErrorResolution(
            category=ErrorCategory.NETWORK,
            action=RecoveryAction.RETRY,
            user_message="Network connection issue detected",
            technical_message="Failed to connect to remote Git repository",
            resolution_steps=[
                "Check your internet connection",
                "Verify the repository URL is accessible",
                "Try again in a few minutes",
                "Contact your network administrator if the problem persists"
            ],
            retry_delay=5.0,
            max_retries=3
        ),
        
        ErrorCategory.AUTHENTICATION: ErrorResolution(
            category=ErrorCategory.AUTHENTICATION,
            action=RecoveryAction.USER_ACTION_REQUIRED,
            user_message="Authentication failed - please check your credentials",
            technical_message="Git authentication failed for remote repository",
            resolution_steps=[
                "Verify your Git credentials are configured correctly",
                "Check if you have access to the repository",
                "For GitHub: ensure your personal access token has proper permissions",
                "Try running 'git config --global credential.helper' to check credential storage"
            ],
            max_retries=0
        ),
        
        ErrorCategory.REPOSITORY_ACCESS: ErrorResolution(
            category=ErrorCategory.REPOSITORY_ACCESS,
            action=RecoveryAction.USER_ACTION_REQUIRED,
            user_message="Repository not accessible - please verify the URL",
            technical_message="Cannot access the specified Git repository",
            resolution_steps=[
                "Verify the repository URL is correct",
                "Check if the repository exists and is public (or you have access)",
                "Ensure the repository URL format is correct (e.g., https://github.com/user/repo.git)",
                "Try accessing the repository in your web browser"
            ],
            max_retries=1
        ),
        
        ErrorCategory.BRANCH_DETECTION: ErrorResolution(
            category=ErrorCategory.BRANCH_DETECTION,
            action=RecoveryAction.FALLBACK,
            user_message="Unable to detect default branch - using fallback",
            technical_message="Branch detection failed, using fallback branch name",
            resolution_steps=[
                "Verify the repository has at least one branch",
                "Check if the default branch name is non-standard",
                "Ensure you have access to read repository metadata"
            ],
            retry_delay=1.0,
            max_retries=2
        ),
        
        ErrorCategory.MERGE_CONFLICT: ErrorResolution(
            category=ErrorCategory.MERGE_CONFLICT,
            action=RecoveryAction.FALLBACK,
            user_message="Merge conflicts detected during synchronization",
            technical_message="Git merge conflicts occurred during repository sync",
            resolution_steps=[
                "Conflicts have been automatically resolved using remote content",
                "Your local changes may have been overwritten",
                "Review the synchronized files for correctness",
                "Consider manually merging changes if needed"
            ],
            max_retries=1
        ),
        
        ErrorCategory.REPOSITORY_CORRUPTION: ErrorResolution(
            category=ErrorCategory.REPOSITORY_CORRUPTION,
            action=RecoveryAction.REINITIALIZE,
            user_message="Repository corruption detected - reinitializing",
            technical_message="Local Git repository appears to be corrupted",
            resolution_steps=[
                "The local repository will be reinitialized",
                "This will remove local Git history but preserve your files",
                "If you have important uncommitted changes, back them up first",
                "After reinitialization, the repository will sync with the remote"
            ],
            max_retries=1
        ),
        
        ErrorCategory.CONFIGURATION: ErrorResolution(
            category=ErrorCategory.CONFIGURATION,
            action=RecoveryAction.USER_ACTION_REQUIRED,
            user_message="Git configuration issue detected",
            technical_message="Git configuration is invalid or incomplete",
            resolution_steps=[
                "Check your Git configuration with 'git config --list'",
                "Ensure user.name and user.email are configured",
                "Verify repository remote configuration",
                "Consider running 'git config --global --edit' to fix configuration"
            ],
            max_retries=0
        )
    }


def build_error_patterns() -> Dict[str, ErrorCategory]:
    """Build mapping of error patterns to categories."""
    return {
        # Network errors
        "connection refused": ErrorCategory.NETWORK,
        "network is unreachable": ErrorCategory.NETWORK,
        "timeout": ErrorCategory.NETWORK,
        "connection timed out": ErrorCategory.NETWORK,
        "no route to host": ErrorCategory.NETWORK,
        "temporary failure in name resolution": ErrorCategory.NETWORK,
        
        # Authentication errors
        "authentication failed": ErrorCategory.AUTHENTICATION,
        "permission denied": ErrorCategory.AUTHENTICATION,
        "forbidden": ErrorCategory.AUTHENTICATION,
        "invalid credentials": ErrorCategory.AUTHENTICATION,
        "401": ErrorCategory.AUTHENTICATION,
        "403": ErrorCategory.AUTHENTICATION,
        
        # Repository access errors
        "repository not found": ErrorCategory.REPOSITORY_ACCESS,
        "remote repository does not exist": ErrorCategory.REPOSITORY_ACCESS,
        "could not read from remote repository": ErrorCategory.REPOSITORY_ACCESS,
        "not a git repository": ErrorCategory.REPOSITORY_CORRUPTION,
        "fatal: not a git repository": ErrorCategory.REPOSITORY_CORRUPTION,
        
        # Branch detection errors
        "branch does not exist": ErrorCategory.BRANCH_DETECTION,
        "no such branch": ErrorCategory.BRANCH_DETECTION,
        "unknown revision": ErrorCategory.BRANCH_DETECTION,
        "ambiguous argument": ErrorCategory.BRANCH_DETECTION,
        
        # Merge conflicts
        "automatic merge failed": ErrorCategory.MERGE_CONFLICT,
        "merge conflict": ErrorCategory.MERGE_CONFLICT,
        "unmerged paths": ErrorCategory.MERGE_CONFLICT,
        "conflict": ErrorCategory.MERGE_CONFLICT,
        
        # Repository corruption
        "corrupt": ErrorCategory.REPOSITORY_CORRUPTION,
        "broken": ErrorCategory.REPOSITORY_CORRUPTION,
        "invalid object": ErrorCategory.REPOSITORY_CORRUPTION,
        "loose object": ErrorCategory.REPOSITORY_CORRUPTION,
    }
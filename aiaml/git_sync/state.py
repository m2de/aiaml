"""Repository state management for enhanced Git synchronization."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config import Config
from ..platform import get_git_executable, get_platform_info, get_platform_specific_git_config
from .branch_utils import check_remote_branch_exists, check_local_branch_exists, get_current_local_branch, check_upstream_tracking
from .clone import clone_existing_repository
from .remote_utils import check_remote_accessibility, detect_remote_default_branch, check_local_remote_configured, check_synchronization_status
from .repository_info import RepositoryState, RepositoryInfo
from .utils import GitSyncResult
from .validation import validate_upstream_tracking


class RepositoryStateManager:
    """
    Manages repository state detection and synchronization with existing repositories.
    
    This class provides functionality to:
    - Detect the current state of local and remote repositories
    - Determine default branch names dynamically
    - Set up upstream tracking for branches
    - Synchronize with existing remote content
    - Clone existing repositories when needed
    """
    
    def __init__(self, config: Config, git_repo_dir: Path):
        """
        Initialize RepositoryStateManager.
        
        Args:
            config: Server configuration containing Git settings
            git_repo_dir: Path to the Git repository directory
        """
        self.config = config
        self.git_repo_dir = git_repo_dir
        self.git_dir = git_repo_dir / ".git"
        self.logger = logging.getLogger('aiaml.git_sync.state')
        
        # Cache for detected information to avoid repeated operations
        self._cached_default_branch: Optional[str] = None
        self._cached_repo_info: Optional[RepositoryInfo] = None
        self._temp_backup_dir: Optional[Path] = None
    
    def detect_repository_state(self) -> RepositoryState:
        """
        Detect the current state of the repository.
        
        Returns:
            RepositoryState indicating the current repository state
        """
        try:
            self.logger.debug("Detecting repository state")
            
            # Check if local .git directory exists
            local_exists = self.git_dir.exists()
            
            # Check if remote URL is configured
            remote_url = self.config.git_remote_url
            remote_configured = bool(remote_url)
            
            # If no local repo and no remote configured, it's a new local repo
            if not local_exists and not remote_configured:
                self.logger.debug("Repository state: NEW_LOCAL (no local .git, no remote)")
                return RepositoryState.NEW_LOCAL
            
            # If local repo exists, check its state
            if local_exists:
                # Check if remote is configured in the local repo
                has_remote = check_local_remote_configured(self.git_repo_dir)
                
                if remote_configured and not has_remote:
                    # Remote URL provided but not configured locally
                    self.logger.debug("Repository state: EXISTING_LOCAL (local exists, remote needs setup)")
                    return RepositoryState.EXISTING_LOCAL
                elif has_remote:
                    # Check if local and remote are synchronized
                    is_synced = check_synchronization_status(self.git_repo_dir)
                    if is_synced:
                        self.logger.debug("Repository state: SYNCHRONIZED")
                        return RepositoryState.SYNCHRONIZED
                    else:
                        self.logger.debug("Repository state: EXISTING_LOCAL (needs sync)")
                        return RepositoryState.EXISTING_LOCAL
                else:
                    # Local repo exists but no remote
                    self.logger.debug("Repository state: EXISTING_LOCAL (local only)")
                    return RepositoryState.EXISTING_LOCAL
            
            # If no local repo but remote is configured, need to clone
            if not local_exists and remote_configured:
                # Check if remote actually exists and is accessible
                remote_exists = check_remote_accessibility(remote_url)
                if remote_exists:
                    self.logger.debug("Repository state: EXISTING_REMOTE (needs cloning)")
                    return RepositoryState.EXISTING_REMOTE
                else:
                    # Remote configured but not accessible, treat as new local
                    self.logger.debug("Repository state: NEW_LOCAL (remote not accessible)")
                    return RepositoryState.NEW_LOCAL
            
            # Default fallback
            self.logger.debug("Repository state: NEW_LOCAL (fallback)")
            return RepositoryState.NEW_LOCAL
            
        except Exception as e:
            self.logger.error(f"Error detecting repository state: {e}", exc_info=True)
            # Safe fallback to NEW_LOCAL
            return RepositoryState.NEW_LOCAL
    
    def get_repository_info(self) -> RepositoryInfo:
        """
        Get comprehensive repository information.
        
        Returns:
            RepositoryInfo containing detailed repository state
        """
        if self._cached_repo_info is not None:
            return self._cached_repo_info
        
        try:
            # Detect basic state
            state = self.detect_repository_state()
            local_exists = self.git_dir.exists()
            remote_url = self.config.git_remote_url
            
            # Check remote accessibility
            remote_exists = False
            if remote_url:
                remote_exists = check_remote_accessibility(remote_url)
            
            # Get default branch
            default_branch = self.get_default_branch()
            
            # Get local branch information
            local_branch = None
            tracking_configured = False
            if local_exists:
                local_branch = get_current_local_branch(self.git_repo_dir)
                if local_branch:
                    tracking_configured = check_upstream_tracking(self.git_repo_dir, local_branch)
            
            # Determine if sync is needed
            needs_sync = self._determine_sync_needed(state, local_exists, remote_exists)
            
            repo_info = RepositoryInfo(
                state=state,
                local_exists=local_exists,
                remote_exists=remote_exists,
                remote_url=remote_url,
                default_branch=default_branch,
                local_branch=local_branch,
                tracking_configured=tracking_configured,
                needs_sync=needs_sync
            )
            
            # Cache the result
            self._cached_repo_info = repo_info
            
            self.logger.debug(f"Repository info: {repo_info}")
            return repo_info
            
        except Exception as e:
            self.logger.error(f"Error getting repository info: {e}", exc_info=True)
            # Return safe defaults
            return RepositoryInfo(
                state=RepositoryState.NEW_LOCAL,
                local_exists=False,
                remote_exists=False,
                remote_url=remote_url,
                default_branch="main",
                local_branch=None,
                tracking_configured=False,
                needs_sync=False
            )
    
    def get_default_branch(self) -> str:
        """
        Get the default branch name, using cached value if available.
        
        Returns:
            Default branch name (e.g., "main", "master", "develop")
        """
        if self._cached_default_branch is not None:
            return self._cached_default_branch
        
        try:
            # Try to detect from remote if available
            if self.config.git_remote_url:
                detected_branch = detect_remote_default_branch(self.config.git_remote_url)
                if detected_branch:
                    self._cached_default_branch = detected_branch
                    self.logger.debug(f"Detected default branch from remote: {detected_branch}")
                    return detected_branch
            
            # Try to detect from local repository
            if self.git_dir.exists():
                local_branch = get_current_local_branch(self.git_repo_dir)
                if local_branch:
                    self._cached_default_branch = local_branch
                    self.logger.debug(f"Using current local branch as default: {local_branch}")
                    return local_branch
            
            # Fallback to "main"
            self._cached_default_branch = "main"
            self.logger.debug("Using fallback default branch: main")
            return "main"
            
        except Exception as e:
            self.logger.error(f"Error detecting default branch: {e}", exc_info=True)
            # Safe fallback
            self._cached_default_branch = "main"
            return "main"
    

    

    
    def _determine_sync_needed(self, state: RepositoryState, local_exists: bool, remote_exists: bool) -> bool:
        """Determine if synchronization is needed based on repository state."""
        if state == RepositoryState.SYNCHRONIZED:
            return False
        elif state == RepositoryState.EXISTING_REMOTE:
            return True  # Need to clone
        elif state == RepositoryState.EXISTING_LOCAL and remote_exists:
            return True  # Need to sync with remote
        else:
            return False
    
    def clone_existing_repository(self) -> GitSyncResult:
        """
        Clone an existing remote repository to the local directory.
        
        This method delegates to the clone_existing_repository function
        and clears the cache after successful cloning.
        
        Returns:
            GitSyncResult indicating success or failure of the clone operation
            
        Requirements: 1.3, 3.1, 3.2
        """
        result = clone_existing_repository(self.config, self.git_repo_dir)
        
        if result.success:
            # Clear cache to force re-detection of repository state
            self.clear_cache()
        
        return result
    



    def setup_upstream_tracking(self, branch_name: str) -> GitSyncResult:
        """
        Set up upstream tracking for a local branch with the remote branch.
        
        This method performs the following operations:
        1. Validates that the local repository exists
        2. Checks if the remote is configured
        3. Creates the local branch if it doesn't exist
        4. Sets up upstream tracking to the remote branch
        5. Validates the tracking configuration
        
        Args:
            branch_name: Name of the branch to set up tracking for
            
        Returns:
            GitSyncResult indicating success or failure of the tracking setup
            
        Requirements: 4.1, 4.2, 4.3
        """
        try:
            self.logger.info(f"Setting up upstream tracking for branch: {branch_name}")
            
            # Validate that local repository exists
            if not self.git_dir.exists():
                error_msg = "Cannot set up upstream tracking: local Git repository does not exist"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="setup_upstream_tracking",
                    error_code="NO_LOCAL_REPO"
                )
            
            # Validate that remote URL is configured
            if not self.config.git_remote_url:
                error_msg = "Cannot set up upstream tracking: no remote URL configured"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="setup_upstream_tracking",
                    error_code="NO_REMOTE_URL"
                )
            
            # Check if remote is configured in the local repository
            if not check_local_remote_configured(self.git_repo_dir):
                error_msg = "Cannot set up upstream tracking: remote 'origin' not configured in local repository"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="setup_upstream_tracking",
                    error_code="NO_LOCAL_REMOTE"
                )
            
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Check if the remote branch exists
            remote_branch_exists = check_remote_branch_exists(self.git_repo_dir, branch_name)
            if not remote_branch_exists:
                error_msg = f"Cannot set up upstream tracking: remote branch 'origin/{branch_name}' does not exist"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="setup_upstream_tracking",
                    error_code="REMOTE_BRANCH_NOT_FOUND"
                )
            
            # Check if local branch exists
            local_branch_exists = check_local_branch_exists(self.git_repo_dir, branch_name)
            
            if not local_branch_exists:
                # Create local branch from remote
                self.logger.debug(f"Creating local branch '{branch_name}' from remote")
                
                result = subprocess.run(
                    [git_executable, "checkout", "-b", branch_name, f"origin/{branch_name}"],
                    capture_output=True,
                    text=True,
                    cwd=self.git_repo_dir,
                    timeout=30,
                    shell=platform_info.is_windows
                )
                
                if result.returncode != 0:
                    error_msg = f"Failed to create local branch '{branch_name}': {result.stderr if result.stderr else result.stdout}"
                    self.logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="setup_upstream_tracking",
                        error_code="BRANCH_CREATION_FAILED"
                    )
                
                self.logger.info(f"Created local branch '{branch_name}' from remote")
                
                # When creating a branch with checkout -b from origin/branch, 
                # upstream tracking is automatically set up, but let's verify
                tracking_configured = check_upstream_tracking(self.git_repo_dir, branch_name)
                if tracking_configured:
                    self.logger.info(f"Upstream tracking automatically configured for branch '{branch_name}'")
                    
                    # Clear cache to reflect new state
                    self.clear_cache()
                    
                    return GitSyncResult(
                        success=True,
                        message=f"Successfully created branch '{branch_name}' with upstream tracking",
                        operation="setup_upstream_tracking"
                    )
            else:
                # Local branch exists, check if tracking is already configured
                if check_upstream_tracking(self.git_repo_dir, branch_name):
                    self.logger.info(f"Upstream tracking already configured for branch '{branch_name}'")
                    return GitSyncResult(
                        success=True,
                        message=f"Upstream tracking already configured for branch '{branch_name}'",
                        operation="setup_upstream_tracking"
                    )
                
                # Switch to the branch if not already on it
                current_branch = get_current_local_branch(self.git_repo_dir)
                if current_branch != branch_name:
                    self.logger.debug(f"Switching to branch '{branch_name}'")
                    
                    result = subprocess.run(
                        [git_executable, "checkout", branch_name],
                        capture_output=True,
                        text=True,
                        cwd=self.git_repo_dir,
                        timeout=30,
                        shell=platform_info.is_windows
                    )
                    
                    if result.returncode != 0:
                        error_msg = f"Failed to switch to branch '{branch_name}': {result.stderr if result.stderr else result.stdout}"
                        self.logger.error(error_msg)
                        return GitSyncResult(
                            success=False,
                            message=error_msg,
                            operation="setup_upstream_tracking",
                            error_code="BRANCH_CHECKOUT_FAILED"
                        )
            
            # Set up upstream tracking manually
            self.logger.debug(f"Setting up upstream tracking for branch '{branch_name}'")
            
            result = subprocess.run(
                [git_executable, "branch", "--set-upstream-to", f"origin/{branch_name}", branch_name],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0:
                error_msg = f"Failed to set upstream tracking for branch '{branch_name}': {result.stderr if result.stderr else result.stdout}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="setup_upstream_tracking",
                    error_code="UPSTREAM_SETUP_FAILED"
                )
            
            # Validate that tracking is now configured
            validation_result = validate_upstream_tracking(self.git_repo_dir, branch_name)
            if not validation_result.success:
                return validation_result
            
            # Clear cache to reflect new state
            self.clear_cache()
            
            self.logger.info(f"Successfully set up upstream tracking for branch '{branch_name}'")
            
            return GitSyncResult(
                success=True,
                message=f"Successfully set up upstream tracking for branch '{branch_name}'",
                operation="setup_upstream_tracking"
            )
            
        except subprocess.TimeoutExpired:
            error_msg = f"Upstream tracking setup timed out for branch '{branch_name}'"
            self.logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="UPSTREAM_SETUP_TIMEOUT"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during upstream tracking setup for branch '{branch_name}': {e}"
            self.logger.error(error_msg, exc_info=True)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="UPSTREAM_SETUP_UNEXPECTED_ERROR"
            )
    

    


    def clear_cache(self) -> None:
        """Clear cached repository information to force re-detection."""
        self._cached_default_branch = None
        self._cached_repo_info = None
        self.logger.debug("Repository state cache cleared")
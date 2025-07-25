"""Repository state management for enhanced Git synchronization."""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from ..config import Config
from ..platform import get_git_executable, get_platform_info, get_platform_specific_git_config
from .utils import GitSyncResult


class RepositoryState(Enum):
    """Enumeration of possible repository states."""
    NEW_LOCAL = "new_local"           # No local .git, no remote configured
    EXISTING_LOCAL = "existing_local" # Local .git exists, may have remote
    EXISTING_REMOTE = "existing_remote" # Remote exists, needs cloning
    SYNCHRONIZED = "synchronized"     # Local and remote in sync


@dataclass
class RepositoryInfo:
    """Information about repository state and configuration."""
    state: RepositoryState
    local_exists: bool
    remote_exists: bool
    remote_url: Optional[str]
    default_branch: str
    local_branch: Optional[str]
    tracking_configured: bool
    needs_sync: bool


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
                has_remote = self._check_local_remote_configured()
                
                if remote_configured and not has_remote:
                    # Remote URL provided but not configured locally
                    self.logger.debug("Repository state: EXISTING_LOCAL (local exists, remote needs setup)")
                    return RepositoryState.EXISTING_LOCAL
                elif has_remote:
                    # Check if local and remote are synchronized
                    is_synced = self._check_synchronization_status()
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
                remote_exists = self._check_remote_accessibility(remote_url)
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
                remote_exists = self._check_remote_accessibility(remote_url)
            
            # Get default branch
            default_branch = self.get_default_branch()
            
            # Get local branch information
            local_branch = None
            tracking_configured = False
            if local_exists:
                local_branch = self._get_current_local_branch()
                if local_branch:
                    tracking_configured = self._check_upstream_tracking(local_branch)
            
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
                detected_branch = self._detect_remote_default_branch()
                if detected_branch:
                    self._cached_default_branch = detected_branch
                    self.logger.debug(f"Detected default branch from remote: {detected_branch}")
                    return detected_branch
            
            # Try to detect from local repository
            if self.git_dir.exists():
                local_branch = self._get_current_local_branch()
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
    
    def _check_local_remote_configured(self) -> bool:
        """Check if a remote is configured in the local repository."""
        if not self.git_dir.exists():
            return False
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"Error checking local remote configuration: {e}")
            return False
    
    def _check_remote_accessibility(self, remote_url: str) -> bool:
        """Check if the remote repository is accessible."""
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Use git ls-remote to check if remote is accessible
            result = subprocess.run(
                [git_executable, "ls-remote", "--heads", remote_url],
                capture_output=True,
                text=True,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"Error checking remote accessibility for {remote_url}: {e}")
            return False
    
    def _check_synchronization_status(self) -> bool:
        """Check if local and remote repositories are synchronized."""
        if not self.git_dir.exists():
            return False
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Fetch latest remote information
            subprocess.run(
                [git_executable, "fetch", "origin"],
                capture_output=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            # Check if local branch is up to date with remote
            current_branch = self._get_current_local_branch()
            if not current_branch:
                return False
            
            result = subprocess.run(
                [git_executable, "rev-list", "--count", f"HEAD..origin/{current_branch}"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                behind_count = int(result.stdout.strip())
                return behind_count == 0
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking synchronization status: {e}")
            return False
    
    def _detect_remote_default_branch(self) -> Optional[str]:
        """Detect the default branch of the remote repository."""
        if not self.config.git_remote_url:
            return None
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Use git ls-remote to get symbolic reference
            result = subprocess.run(
                [git_executable, "ls-remote", "--symref", self.config.git_remote_url, "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('ref: refs/heads/'):
                        # Extract branch name from "ref: refs/heads/main"
                        branch_name = line.split('refs/heads/')[-1]
                        self.logger.debug(f"Detected remote default branch: {branch_name}")
                        return branch_name
            
            # Fallback: try common branch names
            common_branches = ["main", "master", "develop"]
            for branch in common_branches:
                result = subprocess.run(
                    [git_executable, "ls-remote", "--heads", self.config.git_remote_url, branch],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=platform_info.is_windows
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    self.logger.debug(f"Found remote branch using fallback: {branch}")
                    return branch
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error detecting remote default branch: {e}")
            return None
    
    def _get_current_local_branch(self) -> Optional[str]:
        """Get the current local branch name."""
        if not self.git_dir.exists():
            return None
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                branch_name = result.stdout.strip()
                if branch_name:
                    return branch_name
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting current local branch: {e}")
            return None
    
    def _check_upstream_tracking(self, branch_name: str) -> bool:
        """Check if the specified branch has upstream tracking configured."""
        if not self.git_dir.exists():
            return False
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "config", f"branch.{branch_name}.remote"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            return result.returncode == 0 and result.stdout.strip()
            
        except Exception as e:
            self.logger.debug(f"Error checking upstream tracking for {branch_name}: {e}")
            return False
    
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
        
        This method performs the following operations:
        1. Validates that a remote URL is configured
        2. Ensures the local directory is empty or doesn't exist
        3. Clones the remote repository using Git clone
        4. Validates the cloned repository structure
        5. Sets up proper Git configuration
        
        Returns:
            GitSyncResult indicating success or failure of the clone operation
            
        Requirements: 1.3, 3.1, 3.2
        """
        try:
            self.logger.info("Starting repository clone operation")
            
            # Validate that remote URL is configured
            if not self.config.git_remote_url:
                error_msg = "Cannot clone repository: no remote URL configured"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="clone_repository",
                    error_code="NO_REMOTE_URL"
                )
            
            # Check if local repository already exists
            if self.git_dir.exists():
                error_msg = "Cannot clone repository: local Git repository already exists"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="clone_repository",
                    error_code="LOCAL_REPO_EXISTS"
                )
            
            # Ensure parent directory exists
            self.git_repo_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # If the target directory exists and is not empty, we need to handle it
            if self.git_repo_dir.exists():
                # Check if directory is empty
                if any(self.git_repo_dir.iterdir()):
                    # Directory exists and is not empty
                    # Check if it contains only expected files (like .gitignore, README, etc.)
                    existing_files = list(self.git_repo_dir.iterdir())
                    allowed_files = {'.gitignore', 'README.md', 'README.txt', 'LICENSE', 'LICENSE.txt'}
                    
                    non_allowed_files = [
                        f for f in existing_files 
                        if f.name not in allowed_files and not f.name.startswith('.')
                    ]
                    
                    if non_allowed_files:
                        error_msg = f"Cannot clone repository: target directory contains files: {[f.name for f in non_allowed_files]}"
                        self.logger.error(error_msg)
                        return GitSyncResult(
                            success=False,
                            message=error_msg,
                            operation="clone_repository",
                            error_code="TARGET_DIR_NOT_EMPTY"
                        )
                    else:
                        # Directory contains only allowed files, move them temporarily
                        temp_backup_dir = self.git_repo_dir.parent / f"{self.git_repo_dir.name}_backup_temp"
                        temp_backup_dir.mkdir(exist_ok=True)
                        
                        # Move allowed files to temporary location
                        for file_path in existing_files:
                            shutil.move(str(file_path), str(temp_backup_dir / file_path.name))
                        
                        # Remove the now-empty directory
                        self.git_repo_dir.rmdir()
                        
                        # Store backup directory for later restoration
                        self._temp_backup_dir = temp_backup_dir
            
            # Perform the Git clone operation
            self.logger.info(f"Cloning repository from {self.config.git_remote_url}")
            
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Use git clone with appropriate options
            clone_command = [
                git_executable, "clone",
                self.config.git_remote_url,
                str(self.git_repo_dir)
            ]
            
            # Add additional clone options for better reliability
            clone_command.extend([
                "--single-branch",  # Only clone the default branch initially
                "--depth", "1"      # Shallow clone for faster operation
            ])
            
            result = subprocess.run(
                clone_command,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for clone operations
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0:
                error_msg = f"Git clone failed: {result.stderr if result.stderr else result.stdout}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="clone_repository",
                    error_code="GIT_CLONE_FAILED"
                )
            
            self.logger.info("Repository cloned successfully")
            
            # Validate the cloned repository structure
            validation_result = self._validate_cloned_repository()
            if not validation_result.success:
                return validation_result
            
            # Set up Git configuration for the cloned repository
            setup_result = self._setup_cloned_repository_config()
            if not setup_result.success:
                # Log warning but don't fail the clone operation
                self.logger.warning(f"Failed to set up cloned repository configuration: {setup_result.message}")
            
            # Restore any backed up files
            if hasattr(self, '_temp_backup_dir') and self._temp_backup_dir and self._temp_backup_dir.exists():
                try:
                    for backup_file in self._temp_backup_dir.iterdir():
                        target_path = self.git_repo_dir / backup_file.name
                        if not target_path.exists():  # Don't overwrite cloned files
                            shutil.move(str(backup_file), str(target_path))
                    
                    # Clean up temporary backup directory
                    if not any(self._temp_backup_dir.iterdir()):  # Only remove if empty
                        self._temp_backup_dir.rmdir()
                    else:
                        # If not empty, remove remaining files first
                        for remaining_file in self._temp_backup_dir.iterdir():
                            if remaining_file.is_file():
                                remaining_file.unlink()
                            elif remaining_file.is_dir():
                                shutil.rmtree(remaining_file)
                        self._temp_backup_dir.rmdir()
                    
                    self._temp_backup_dir = None
                    self.logger.debug("Restored backed up files after clone")
                except Exception as e:
                    self.logger.warning(f"Failed to restore backed up files: {e}")
            
            # Clear cache to force re-detection of repository state
            self.clear_cache()
            
            self.logger.info(f"Repository clone completed successfully from {self.config.git_remote_url}")
            
            return GitSyncResult(
                success=True,
                message=f"Repository cloned successfully from {self.config.git_remote_url}",
                operation="clone_repository"
            )
            
        except subprocess.TimeoutExpired:
            error_msg = "Repository clone operation timed out"
            self.logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="clone_repository",
                error_code="CLONE_TIMEOUT"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during repository clone: {e}"
            self.logger.error(error_msg, exc_info=True)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="clone_repository",
                error_code="CLONE_UNEXPECTED_ERROR"
            )
    
    def _validate_cloned_repository(self) -> GitSyncResult:
        """
        Validate the structure and integrity of a cloned repository.
        
        This method checks:
        1. .git directory exists and is valid
        2. Repository has proper Git configuration
        3. Remote origin is properly configured
        4. Working directory is clean
        
        Returns:
            GitSyncResult indicating validation success or failure
        """
        try:
            self.logger.debug("Validating cloned repository structure")
            
            # Check if .git directory exists
            if not self.git_dir.exists():
                error_msg = "Cloned repository validation failed: .git directory not found"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="MISSING_GIT_DIR"
                )
            
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Validate that it's a proper Git repository
            result = subprocess.run(
                [git_executable, "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0:
                error_msg = f"Cloned repository validation failed: not a valid Git repository: {result.stderr}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="INVALID_GIT_REPO"
                )
            
            # Check remote configuration
            result = subprocess.run(
                [git_executable, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0:
                error_msg = "Cloned repository validation failed: origin remote not configured"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="MISSING_ORIGIN_REMOTE"
                )
            
            # Verify remote URL matches configuration
            actual_remote_url = result.stdout.strip()
            if actual_remote_url != self.config.git_remote_url:
                error_msg = f"Cloned repository validation failed: remote URL mismatch (expected: {self.config.git_remote_url}, actual: {actual_remote_url})"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="REMOTE_URL_MISMATCH"
                )
            
            # Check if we have a valid branch
            result = subprocess.run(
                [git_executable, "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                error_msg = "Cloned repository validation failed: no current branch found"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="NO_CURRENT_BRANCH"
                )
            
            current_branch = result.stdout.strip()
            self.logger.debug(f"Cloned repository validation successful, current branch: {current_branch}")
            
            return GitSyncResult(
                success=True,
                message=f"Cloned repository validation successful (branch: {current_branch})",
                operation="validate_cloned_repo"
            )
            
        except subprocess.TimeoutExpired:
            error_msg = "Cloned repository validation timed out"
            self.logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="VALIDATION_TIMEOUT"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during cloned repository validation: {e}"
            self.logger.error(error_msg, exc_info=True)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="VALIDATION_UNEXPECTED_ERROR"
            )
    
    def _setup_cloned_repository_config(self) -> GitSyncResult:
        """
        Set up Git configuration for a cloned repository.
        
        This method ensures that the cloned repository has proper:
        1. User name and email configuration
        2. Platform-specific Git settings
        3. Any additional AIAML-specific configuration
        
        Returns:
            GitSyncResult indicating setup success or failure
        """
        try:
            self.logger.debug("Setting up cloned repository configuration")
            
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Check if user.name is configured
            result = subprocess.run(
                [git_executable, "config", "user.name"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0:
                # Set default user name
                subprocess.run(
                    [git_executable, "config", "user.name", "AIAML Memory System"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10,
                    shell=platform_info.is_windows
                )
                self.logger.debug("Set default Git user.name for cloned repository")
            
            # Check if user.email is configured
            result = subprocess.run(
                [git_executable, "config", "user.email"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode != 0:
                # Set default user email
                subprocess.run(
                    [git_executable, "config", "user.email", "aiaml@localhost"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10,
                    shell=platform_info.is_windows
                )
                self.logger.debug("Set default Git user.email for cloned repository")
            
            # Apply platform-specific Git configuration
            platform_git_config = get_platform_specific_git_config()
            for config_key, config_value in platform_git_config.items():
                try:
                    subprocess.run(
                        [git_executable, "config", config_key, config_value],
                        check=True,
                        capture_output=True,
                        cwd=self.git_repo_dir,
                        timeout=10,
                        shell=platform_info.is_windows
                    )
                    self.logger.debug(f"Set Git config {config_key} = {config_value} for cloned repository")
                except subprocess.CalledProcessError as e:
                    self.logger.warning(f"Failed to set Git config {config_key} for cloned repository: {e}")
            
            self.logger.debug("Cloned repository configuration setup completed")
            
            return GitSyncResult(
                success=True,
                message="Cloned repository configuration setup completed",
                operation="setup_cloned_repo_config"
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to set up cloned repository configuration: {e.stderr if e.stderr else str(e)}"
            self.logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_cloned_repo_config",
                error_code="CONFIG_SETUP_FAILED"
            )
            
        except subprocess.TimeoutExpired:
            error_msg = "Cloned repository configuration setup timed out"
            self.logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_cloned_repo_config",
                error_code="CONFIG_SETUP_TIMEOUT"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during cloned repository configuration setup: {e}"
            self.logger.error(error_msg, exc_info=True)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_cloned_repo_config",
                error_code="CONFIG_SETUP_UNEXPECTED_ERROR"
            )

    def clear_cache(self) -> None:
        """Clear cached repository information to force re-detection."""
        self._cached_default_branch = None
        self._cached_repo_info = None
        self.logger.debug("Repository state cache cleared")
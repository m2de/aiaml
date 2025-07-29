"""Synchronization operations for Git repositories."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from git import Repo, GitCommandError
from ..platform import get_git_executable, get_platform_info
from .branch_utils import check_remote_branch_exists, check_local_branch_exists, get_current_local_branch, check_upstream_tracking
from .remote_utils import check_remote_accessibility, check_local_remote_configured
from .repository_sync import synchronize_with_remote as sync_with_remote_func
from .utils import GitSyncResult, create_git_sync_result


class SyncOperations:
    """Helper class for Git synchronization operations."""
    
    def __init__(self, git_repo_dir: Path, logger: logging.Logger):
        """
        Initialize sync operations.
        
        Args:
            git_repo_dir: Path to the Git repository directory
            logger: Logger instance for this class
        """
        self.git_repo_dir = git_repo_dir
        self.logger = logger
        self._temp_backup_dir: Optional[Path] = None
    
    def validate_existing_memory_files(self) -> GitSyncResult:
        """
        Validate existing memory files in the repository after synchronization.
        
        This method checks that memory files have valid format and can be parsed.
        Invalid files are logged but don't cause the sync to fail.
        
        Returns:
            GitSyncResult indicating validation status
        """
        try:
            self.logger.debug("Validating existing memory files")
            
            # Import here to avoid circular imports
            from ..memory.core import parse_memory_file_safe
            
            memory_files_dir = self.git_repo_dir / "files"
            if not memory_files_dir.exists():
                self.logger.debug("No memory files directory found, creating it")
                memory_files_dir.mkdir(parents=True, exist_ok=True)
                return GitSyncResult(
                    success=True,
                    message="No existing memory files to validate",
                    operation="validate_memory_files"
                )
            
            memory_files = list(memory_files_dir.glob("*.md"))
            if not memory_files:
                self.logger.debug("No memory files found to validate")
                return GitSyncResult(
                    success=True,
                    message="No memory files found to validate",
                    operation="validate_memory_files"
                )
            
            valid_files = 0
            invalid_files = 0
            validation_warnings = []
            
            for file_path in memory_files:
                try:
                    memory_data = parse_memory_file_safe(file_path)
                    if memory_data:
                        # Validate required fields
                        required_fields = ['id', 'timestamp', 'agent', 'user', 'topics', 'content']
                        missing_fields = [field for field in required_fields if not memory_data.get(field)]
                        
                        if missing_fields:
                            warning_msg = f"Memory file {file_path.name} missing fields: {missing_fields}"
                            validation_warnings.append(warning_msg)
                            self.logger.warning(warning_msg)
                            invalid_files += 1
                        else:
                            valid_files += 1
                    else:
                        warning_msg = f"Memory file {file_path.name} could not be parsed"
                        validation_warnings.append(warning_msg)
                        self.logger.warning(warning_msg)
                        invalid_files += 1
                        
                except Exception as e:
                    warning_msg = f"Error validating memory file {file_path.name}: {e}"
                    validation_warnings.append(warning_msg)
                    self.logger.warning(warning_msg)
                    invalid_files += 1
            
            total_files = valid_files + invalid_files
            self.logger.info(f"Memory file validation completed: {valid_files}/{total_files} files valid")
            
            if invalid_files > 0:
                warning_summary = f"Found {invalid_files} invalid memory files out of {total_files} total files"
                return GitSyncResult(
                    success=False,
                    message=warning_summary,
                    operation="validate_memory_files",
                    error_code="MEMORY_VALIDATION_WARNINGS"
                )
            else:
                return GitSyncResult(
                    success=True,
                    message=f"All {valid_files} memory files validated successfully",
                    operation="validate_memory_files"
                )
                
        except Exception as e:
            error_msg = f"Error during memory file validation: {e}"
            self.logger.error(error_msg, exc_info=True)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_memory_files",
                error_code="MEMORY_VALIDATION_ERROR"
            )
    
    def resolve_merge_conflicts(self, branch_name: str) -> GitSyncResult:
        """
        Resolve merge conflicts by prioritizing remote content.
        
        Args:
            branch_name: Name of the branch being merged
            
        Returns:
            GitSyncResult indicating conflict resolution status
        """
        try:
            self.logger.info("Attempting to resolve merge conflicts by prioritizing remote content")
            
            try:
                repo = Repo(self.git_repo_dir)
            except Exception as e:
                error_msg = f"Failed to access Git repository: {e}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="resolve_merge_conflicts",
                    error_code="REPO_ACCESS_ERROR"
                )
            
            # Get list of conflicted files
            try:
                # Get unmerged files (conflicts)
                conflicted_files = [item.a_path for item in repo.index.unmerged_blobs().keys()]
            except Exception as e:
                error_msg = f"Failed to get list of conflicted files: {e}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="resolve_merge_conflicts",
                    error_code="CONFLICT_LIST_FAILED"
                )
            
            if not conflicted_files:
                self.logger.info("No conflicted files found")
                return GitSyncResult(
                    success=True,
                    message="No conflicts to resolve",
                    operation="resolve_merge_conflicts"
                )
            
            self.logger.info(f"Resolving conflicts in {len(conflicted_files)} files: {conflicted_files}")
            
            # Resolve each conflict by accepting remote version
            for file_path in conflicted_files:
                self.logger.debug(f"Resolving conflict in {file_path} by accepting remote version")
                
                try:
                    # Accept the remote version (theirs) for this file
                    repo.git.checkout('--theirs', file_path)
                    # Stage the resolved file
                    repo.index.add([file_path])
                except GitCommandError as e:
                    error_msg = f"Failed to resolve conflict in {file_path}: {e}"
                    self.logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="resolve_merge_conflicts",
                        error_code="CONFLICT_RESOLUTION_FAILED"
                    )
                except Exception as e:
                    error_msg = f"Unexpected error resolving conflict in {file_path}: {e}"
                    self.logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="resolve_merge_conflicts",
                        error_code="CONFLICT_RESOLUTION_FAILED"
                    )
            
            # Complete the merge
            try:
                # Commit the merge with default merge message
                repo.index.commit("Merge conflicts resolved by accepting remote changes")
            except GitCommandError as e:
                error_msg = f"Failed to complete merge after conflict resolution: {e}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="resolve_merge_conflicts",
                    error_code="MERGE_COMMIT_FAILED"
                )
            except Exception as e:
                error_msg = f"Unexpected error completing merge: {e}"
                self.logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="resolve_merge_conflicts",
                    error_code="MERGE_COMMIT_FAILED"
                )
            
            self.logger.info(f"Successfully resolved conflicts in {len(conflicted_files)} files")
            
            return GitSyncResult(
                success=True,
                message=f"Successfully resolved conflicts in {len(conflicted_files)} files by prioritizing remote content",
                operation="resolve_merge_conflicts"
            )
            
        except GitCommandError as e:
            error_msg = f"Git command error during conflict resolution: {e}"
            self.logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="resolve_merge_conflicts",
                error_code="GIT_COMMAND_ERROR"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during conflict resolution: {e}"
            self.logger.error(error_msg, exc_info=True)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="resolve_merge_conflicts",
                error_code="CONFLICT_RESOLUTION_UNEXPECTED_ERROR"
            )
    
    def create_sync_backup(self) -> None:
        """Create a backup of the current repository state before synchronization."""
        try:
            if self._temp_backup_dir is not None:
                # Clean up any existing backup
                self.cleanup_sync_backup()
            
            self._temp_backup_dir = Path(tempfile.mkdtemp(prefix="aiaml_sync_backup_"))
            
            # Copy the entire repository to backup location
            shutil.copytree(self.git_repo_dir, self._temp_backup_dir / "repo_backup", dirs_exist_ok=True)
            
            self.logger.debug(f"Created sync backup at: {self._temp_backup_dir}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create sync backup: {e}")
            self._temp_backup_dir = None
    
    def restore_from_sync_backup(self) -> None:
        """Restore repository from backup if synchronization fails."""
        try:
            if self._temp_backup_dir is None or not self._temp_backup_dir.exists():
                self.logger.warning("No sync backup available for restoration")
                return
            
            backup_repo = self._temp_backup_dir / "repo_backup"
            if not backup_repo.exists():
                self.logger.warning("Backup repository directory not found")
                return
            
            # Remove current repository and restore from backup
            if self.git_repo_dir.exists():
                shutil.rmtree(self.git_repo_dir)
            
            shutil.copytree(backup_repo, self.git_repo_dir)
            
            self.logger.info("Successfully restored repository from sync backup")
            
        except Exception as e:
            self.logger.error(f"Failed to restore from sync backup: {e}")
    
    def cleanup_sync_backup(self) -> None:
        """Clean up temporary backup directory."""
        try:
            if self._temp_backup_dir is not None and self._temp_backup_dir.exists():
                shutil.rmtree(self._temp_backup_dir)
                self.logger.debug(f"Cleaned up sync backup: {self._temp_backup_dir}")
                self._temp_backup_dir = None
                
        except Exception as e:
            self.logger.warning(f"Failed to clean up sync backup: {e}")
    
    def synchronize_with_remote(self, config, get_default_branch_func, setup_upstream_tracking_func) -> GitSyncResult:
        """
        Synchronize the local repository with the remote repository.
        
        This method delegates to the synchronize_with_remote function.
        
        Args:
            config: Server configuration containing Git settings
            get_default_branch_func: Function to get the default branch name
            setup_upstream_tracking_func: Function to set up upstream tracking
        
        Returns:
            GitSyncResult indicating success or failure of the synchronization
            
        Requirements: 3.1, 3.2, 3.3
        """
        return sync_with_remote_func(
            self.git_repo_dir,
            config,
            get_default_branch_func,
            setup_upstream_tracking_func,
            self,
            self.logger
        )
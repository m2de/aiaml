"""Git sync operations for GitSyncManager."""

import logging
import threading
from typing import Optional

from ..config import Config
from .utils import GitSyncResult, create_git_sync_result
from .operations import execute_git_command_with_retry
from .manager_core import GitSyncManagerCore


class GitSyncManagerSync:
    """
    Git synchronization operations for the GitSyncManager.
    
    This class handles memory synchronization operations.
    """
    
    def __init__(self, core: GitSyncManagerCore):
        """
        Initialize sync manager with core functionality.
        
        Args:
            core: Core GitSyncManager functionality
        """
        self.core = core
        self.config = core.config
        self.logger = logging.getLogger('aiaml.git_sync.sync')
        self._sync_lock = threading.Lock()
    
    def sync_memory_with_retry(self, memory_id: str, filename: str) -> GitSyncResult:
        """
        Synchronize a memory file to Git with retry logic.
        
        This method performs the following operations:
        1. Add the memory file to Git
        2. Commit the changes
        3. Push to remote (if configured)
        
        Args:
            memory_id: Unique identifier for the memory
            filename: Name of the memory file
            
        Returns:
            GitSyncResult indicating success or failure
        """
        if not self.config.enable_git_sync:
            return create_git_sync_result(
                success=False,
                message="Git sync is disabled",
                operation="sync_memory",
                error_code="GIT_SYNC_DISABLED"
            )
        
        if not self.core.initialized:
            init_result = self.core.initialize()
            if not init_result.success:
                return init_result
        
        with self._sync_lock:
            try:
                with self.core._safe_performance_operation("memory_sync_complete", {
                    "memory_id": memory_id,
                    "filename": filename,
                    "has_remote": bool(self.config.git_remote_url)
                }):
                    self.logger.info(f"📝 Starting Git sync for memory {memory_id} (file: {filename})")
                    
                    # Step 1: Add the file to Git
                    with self.core._safe_performance_operation("git_add"):
                        add_result = execute_git_command_with_retry(
                            ["git", "add", f"files/{filename}"],
                            f"add memory file {filename}",
                            self.core.git_repo_dir,
                            self.config
                        )
                        
                        if add_result.attempts > 1:
                            self.logger.debug(f"🔄 Git add required {add_result.attempts} attempts")
                    
                    if not add_result.success:
                        return add_result
                    
                    # Step 2: Commit the changes
                    commit_message = f"Add memory {memory_id}"
                    with self.core._safe_performance_operation("git_commit"):
                        commit_result = execute_git_command_with_retry(
                            ["git", "commit", "-m", commit_message],
                            f"commit memory {memory_id}",
                            self.core.git_repo_dir,
                            self.config
                        )
                        
                        if commit_result.attempts > 1:
                            self.logger.debug(f"🔄 Git commit required {commit_result.attempts} attempts")
                    
                    if not commit_result.success:
                        return commit_result
                    
                    # Get repository information and branch name
                    with self.core._safe_performance_operation("get_repo_info"):
                        repo_info = self.core.repo_state_manager.get_repository_info()
                        branch_name = repo_info.default_branch
                        
                    self.logger.debug(f"🌿 Using branch: {branch_name}")
                    
                    # Step 3: Push to remote if configured
                    if self.config.git_remote_url:
                        with self.core._safe_performance_operation("git_push", {
                            "remote_url": self.config.git_remote_url,
                            "branch": branch_name
                        }):
                            push_result = execute_git_command_with_retry(
                                ["git", "push", "origin", branch_name],
                                f"push memory {memory_id} to remote",
                                self.core.git_repo_dir,
                                self.config,
                                timeout=60  # Longer timeout for network operations
                            )
                            
                            if push_result.attempts > 1:
                                self.logger.debug(f"🔄 Git push required {push_result.attempts} attempts")
                        
                        if not push_result.success:
                            # Log warning but don't fail the entire operation
                            self.logger.warning(f"⚠️ Failed to push memory {memory_id} to remote: {push_result.message}")
                            return create_git_sync_result(
                                success=True,
                                message=f"Memory {memory_id} committed locally (push failed: {push_result.message})",
                                operation="sync_memory",
                                attempts=push_result.attempts,
                                repository_info=repo_info,
                                branch_used=branch_name
                            )
                        
                        self.logger.info(f"✅ Memory {memory_id} synced to Git and pushed to remote successfully")
                        if self.core.perf_logger:
                            try:
                                self.core.perf_logger.log_network_performance(
                                    "git_push", 
                                    self.config.git_remote_url,
                                    0.0,  # Duration will be logged by time_operation
                                    success=True
                                )
                            except Exception as e:
                                self.logger.debug(f"Network performance logging failed: {e}")
                        
                        return create_git_sync_result(
                            success=True,
                            message=f"Memory {memory_id} synced to Git and pushed to remote",
                            operation="sync_memory",
                            attempts=max(add_result.attempts, commit_result.attempts, push_result.attempts),
                            repository_info=repo_info,
                            branch_used=branch_name
                        )
                    else:
                        self.logger.info(f"💾 Memory {memory_id} committed to Git locally (no remote configured)")
                        return create_git_sync_result(
                            success=True,
                            message=f"Memory {memory_id} committed to Git locally",
                            operation="sync_memory",
                            attempts=max(add_result.attempts, commit_result.attempts),
                            repository_info=repo_info,
                            branch_used=branch_name
                        )
                
            except Exception as e:
                error_msg = f"Unexpected error during Git sync for memory {memory_id}: {e}"
                self.logger.error(error_msg, exc_info=True)
                
                # Try to get repository info for error reporting
                try:
                    repo_info = self.core.repo_state_manager.get_repository_info()
                    branch_name = repo_info.default_branch
                except Exception:
                    repo_info = None
                    branch_name = None
                
                # Use enhanced error handling with context and fallback
                enhanced_result = self.core._safe_error_handling(
                    error_message=error_msg,
                    operation="sync_memory",
                    error_code="GIT_SYNC_UNEXPECTED_ERROR",
                    context={
                        "memory_id": memory_id,
                        "filename": filename,
                        "repository_info": str(repo_info) if repo_info else "unavailable",
                        "branch_name": branch_name
                    }
                )
                
                # Add repository info to the enhanced result
                enhanced_result.repository_info = repo_info
                enhanced_result.branch_used = branch_name
                
                return enhanced_result
    
    def sync_memory_background(self, memory_id: str, filename: str) -> None:
        """
        Synchronize a memory file to Git in a background thread.
        
        This method starts a background thread to perform Git synchronization
        without blocking the main memory storage operation.
        
        Args:
            memory_id: Unique identifier for the memory
            filename: Name of the memory file
        """
        if not self.config.enable_git_sync:
            self.logger.debug("Git sync disabled, skipping background sync")
            return
        
        def sync_worker():
            try:
                result = self.sync_memory_with_retry(memory_id, filename)
                if result.success:
                    self.logger.info(f"Background Git sync completed for memory {memory_id}")
                else:
                    self.logger.warning(f"Background Git sync failed for memory {memory_id}: {result.message}")
            except Exception as e:
                self.logger.error(f"Unexpected error in background Git sync for memory {memory_id}: {e}", exc_info=True)
        
        # Start background thread
        sync_thread = threading.Thread(
            target=sync_worker,
            name=f"GitSync-{memory_id}",
            daemon=True
        )
        sync_thread.start()
        
        self.logger.debug(f"Started background Git sync thread for memory {memory_id}")
"""
Cross-platform file locking utilities for AIAML.

This module provides file locking functionality to prevent concurrent
write conflicts and ensure data integrity during file operations.
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .platform import get_platform_info
from .config import Config


class FileLock:
    """
    Cross-platform file locking implementation.
    
    Provides exclusive file locking to prevent concurrent modifications
    of memory files and other critical resources.
    """
    
    def __init__(self, lock_file_path: Path, timeout: float = 30.0):
        """
        Initialize file lock.
        
        Args:
            lock_file_path: Path to the lock file
            timeout: Maximum time to wait for lock acquisition (seconds)
        """
        self.lock_file_path = lock_file_path
        self.timeout = timeout
        self.logger = logging.getLogger('aiaml.file_lock')
        self.platform_info = get_platform_info()
        self._lock_acquired = False
        self._lock_thread = threading.current_thread()
    
    def acquire(self) -> bool:
        """
        Acquire the file lock.
        
        Returns:
            True if lock was acquired, False if timeout occurred
        """
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                # Ensure lock directory exists
                self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                if self.platform_info.is_windows:
                    # Windows-specific locking
                    success = self._acquire_windows_lock()
                else:
                    # Unix-like systems
                    success = self._acquire_unix_lock()
                
                if success:
                    self._lock_acquired = True
                    self.logger.debug(f"Acquired lock: {self.lock_file_path}")
                    return True
                
                # Wait before retrying
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.warning(f"Error acquiring lock {self.lock_file_path}: {e}")
                time.sleep(0.1)
        
        self.logger.warning(f"Failed to acquire lock {self.lock_file_path} within {self.timeout}s")
        return False
    
    def _acquire_windows_lock(self) -> bool:
        """Acquire lock on Windows systems."""
        try:
            # On Windows, we use exclusive file creation
            # If the file already exists, this will fail
            with open(self.lock_file_path, 'x') as f:
                f.write(f"locked_by_pid_{os.getpid()}_thread_{threading.get_ident()}")
            return True
        except FileExistsError:
            # Lock file already exists, check if it's stale
            return self._check_and_cleanup_stale_lock()
        except Exception:
            return False
    
    def _acquire_unix_lock(self) -> bool:
        """Acquire lock on Unix-like systems."""
        try:
            # Use O_CREAT | O_EXCL for atomic lock creation
            fd = os.open(
                self.lock_file_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644
            )
            
            with os.fdopen(fd, 'w') as f:
                f.write(f"locked_by_pid_{os.getpid()}_thread_{threading.get_ident()}")
            
            return True
            
        except FileExistsError:
            # Lock file already exists, check if it's stale
            return self._check_and_cleanup_stale_lock()
        except Exception:
            return False
    
    def _check_and_cleanup_stale_lock(self) -> bool:
        """
        Check if an existing lock is stale and clean it up if necessary.
        
        Returns:
            True if lock was cleaned up and can be acquired, False otherwise
        """
        try:
            if not self.lock_file_path.exists():
                return True
            
            # Check lock file age
            lock_age = time.time() - self.lock_file_path.stat().st_mtime
            
            # If lock is older than 5 minutes, consider it stale
            if lock_age > 300:
                self.logger.warning(f"Cleaning up stale lock file: {self.lock_file_path}")
                self.lock_file_path.unlink()
                return True
            
            # Try to read lock content to check if process is still running
            try:
                lock_content = self.lock_file_path.read_text()
                if "locked_by_pid_" in lock_content:
                    pid_str = lock_content.split("locked_by_pid_")[1].split("_")[0]
                    pid = int(pid_str)
                    
                    # Check if process is still running
                    if not self._is_process_running(pid):
                        self.logger.warning(f"Cleaning up lock from dead process {pid}: {self.lock_file_path}")
                        self.lock_file_path.unlink()
                        return True
            except (ValueError, IndexError, OSError):
                # If we can't parse the lock file, consider it stale
                self.logger.warning(f"Cleaning up unparseable lock file: {self.lock_file_path}")
                self.lock_file_path.unlink()
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking stale lock {self.lock_file_path}: {e}")
            return False
    
    def _is_process_running(self, pid: int) -> bool:
        """
        Check if a process with given PID is still running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is running, False otherwise
        """
        try:
            if self.platform_info.is_windows:
                # On Windows, use tasklist command
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return str(pid) in result.stdout
            else:
                # On Unix-like systems, send signal 0 to check if process exists
                os.kill(pid, 0)
                return True
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    
    def release(self) -> bool:
        """
        Release the file lock.
        
        Returns:
            True if lock was released, False otherwise
        """
        try:
            if not self._lock_acquired:
                return True
            
            if self.lock_file_path.exists():
                self.lock_file_path.unlink()
                self.logger.debug(f"Released lock: {self.lock_file_path}")
            
            self._lock_acquired = False
            return True
            
        except Exception as e:
            self.logger.error(f"Error releasing lock {self.lock_file_path}: {e}")
            return False
    
    def is_locked(self) -> bool:
        """
        Check if the lock is currently held by this instance.
        
        Returns:
            True if lock is held, False otherwise
        """
        return self._lock_acquired
    
    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock {self.lock_file_path} within {self.timeout}s")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


class MemoryFileLock:
    """
    Specialized file lock for memory files.
    
    Provides memory-specific locking functionality with automatic
    lock file naming and cleanup.
    """
    
    def __init__(self, config: Config, memory_file_path: Path, timeout: float = 30.0):
        """
        Initialize memory file lock.
        
        Args:
            config: Server configuration
            memory_file_path: Path to the memory file to lock
            timeout: Maximum time to wait for lock acquisition
        """
        self.config = config
        self.memory_file_path = memory_file_path
        self.timeout = timeout
        
        # Create lock file path in locks directory
        lock_dir = config.lock_dir
        lock_filename = f"{memory_file_path.name}.lock"
        self.lock_file_path = lock_dir / lock_filename
        
        self.file_lock = FileLock(self.lock_file_path, timeout)
    
    def acquire(self) -> bool:
        """Acquire the memory file lock."""
        return self.file_lock.acquire()
    
    def release(self) -> bool:
        """Release the memory file lock."""
        return self.file_lock.release()
    
    def is_locked(self) -> bool:
        """Check if the memory file lock is held."""
        return self.file_lock.is_locked()
    
    def __enter__(self):
        """Context manager entry."""
        return self.file_lock.__enter__()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return self.file_lock.__exit__(exc_type, exc_val, exc_tb)


@contextmanager
def memory_file_lock(config: Config, memory_file_path: Path, timeout: float = 30.0):
    """
    Context manager for memory file locking.
    
    Args:
        config: Server configuration
        memory_file_path: Path to the memory file to lock
        timeout: Maximum time to wait for lock acquisition
        
    Yields:
        MemoryFileLock instance
        
    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    lock = MemoryFileLock(config, memory_file_path, timeout)
    
    try:
        if not lock.acquire():
            raise TimeoutError(f"Could not acquire lock for {memory_file_path} within {timeout}s")
        yield lock
    finally:
        lock.release()


def cleanup_stale_locks(config: Config, max_age_minutes: int = 10) -> int:
    """
    Clean up stale lock files.
    
    Args:
        config: Server configuration
        max_age_minutes: Maximum age of lock files to keep (minutes)
        
    Returns:
        Number of stale locks cleaned up
    """
    try:
        lock_dir = config.lock_dir
        
        if not lock_dir.exists():
            return 0
        
        cleaned_count = 0
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        
        for lock_file in lock_dir.glob("*.lock"):
            try:
                # Check file age
                file_age = current_time - lock_file.stat().st_mtime
                
                if file_age > max_age_seconds:
                    # Check if the lock is from a dead process
                    try:
                        lock_content = lock_file.read_text()
                        if "locked_by_pid_" in lock_content:
                            pid_str = lock_content.split("locked_by_pid_")[1].split("_")[0]
                            pid = int(pid_str)
                            
                            platform_info = get_platform_info()
                            
                            # Check if process is still running
                            process_running = False
                            try:
                                if platform_info.is_windows:
                                    import subprocess
                                    result = subprocess.run(
                                        ["tasklist", "/FI", f"PID eq {pid}"],
                                        capture_output=True,
                                        text=True,
                                        timeout=5
                                    )
                                    process_running = str(pid) in result.stdout
                                else:
                                    os.kill(pid, 0)
                                    process_running = True
                            except:
                                process_running = False
                            
                            if not process_running:
                                lock_file.unlink()
                                cleaned_count += 1
                                logging.getLogger('aiaml.file_lock').info(
                                    f"Cleaned up stale lock from dead process {pid}: {lock_file}"
                                )
                        else:
                            # Unparseable lock file, remove it
                            lock_file.unlink()
                            cleaned_count += 1
                    except:
                        # If we can't read or parse the lock file, remove it
                        lock_file.unlink()
                        cleaned_count += 1
                        
            except Exception as e:
                logging.getLogger('aiaml.file_lock').warning(
                    f"Error processing lock file {lock_file}: {e}"
                )
        
        if cleaned_count > 0:
            logging.getLogger('aiaml.file_lock').info(
                f"Cleaned up {cleaned_count} stale lock files"
            )
        
        return cleaned_count
        
    except Exception as e:
        logging.getLogger('aiaml.file_lock').error(f"Error during lock cleanup: {e}")
        return 0
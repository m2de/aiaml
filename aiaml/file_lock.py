"""Cross-platform file locking utilities."""

import os
import time
import logging
from pathlib import Path
from typing import Optional, Union
from datetime import datetime

from .platform import get_platform_info


class FileLock:
    """Cross-platform file locking implementation."""
    
    def __init__(self, lock_file_path: Union[str, Path], timeout: int = 10):
        """
        Initialize file lock.
        
        Args:
            lock_file_path: Path to the lock file
            timeout: Maximum time to wait for lock in seconds
        """
        self.lock_file_path = Path(lock_file_path)
        self.timeout = timeout
        self.lock_fd: Optional[int] = None
        self.platform_info = get_platform_info()
        self.logger = logging.getLogger('aiaml.file_lock')
    
    def __enter__(self):
        """Context manager entry."""
        if self.acquire():
            return self
        else:
            raise TimeoutError(f"Failed to acquire lock on {self.lock_file_path} within {self.timeout} seconds")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
    
    def acquire(self) -> bool:
        """
        Acquire the file lock.
        
        Returns:
            True if lock acquired successfully, False otherwise
        """
        try:
            # Create lock file if it doesn't exist
            if not self.lock_file_path.exists():
                self.lock_file_path.touch()
            
            if self.platform_info.is_windows:
                return self._acquire_windows()
            else:
                return self._acquire_unix()
                
        except Exception as e:
            self.logger.error(f"Failed to acquire file lock: {e}")
            return False
    
    def release(self) -> bool:
        """
        Release the file lock.
        
        Returns:
            True if lock released successfully, False otherwise
        """
        try:
            if self.lock_fd is not None:
                if self.platform_info.is_windows:
                    return self._release_windows()
                else:
                    return self._release_unix()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to release file lock: {e}")
            return False
        finally:
            self.lock_fd = None
    
    def _acquire_windows(self) -> bool:
        """Acquire lock on Windows using msvcrt."""
        try:
            import msvcrt
            
            # Open the lock file
            self.lock_fd = os.open(str(self.lock_file_path), os.O_RDWR | os.O_CREAT)
            
            # Try to acquire the lock with timeout
            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() < self.timeout:
                try:
                    # Try to lock the file (non-blocking)
                    msvcrt.locking(self.lock_fd, msvcrt.LK_NBLCK, 1)
                    return True  # Lock acquired
                except OSError:
                    # Lock is held by another process, wait and retry
                    time.sleep(0.1)
            
            # Timeout reached
            os.close(self.lock_fd)
            self.lock_fd = None
            return False
            
        except ImportError:
            # msvcrt not available, fall back to simple file-based locking
            return self._acquire_simple()
        except Exception as e:
            self.logger.error(f"Windows file locking failed: {e}")
            if self.lock_fd is not None:
                try:
                    os.close(self.lock_fd)
                except:
                    pass
                self.lock_fd = None
            return False
    
    def _acquire_unix(self) -> bool:
        """Acquire lock on Unix systems using fcntl."""
        try:
            import fcntl
            import errno
            
            # Open the lock file
            self.lock_fd = os.open(str(self.lock_file_path), os.O_RDWR)
            
            # Try to acquire the lock with timeout
            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() < self.timeout:
                try:
                    # Try non-blocking lock
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True  # Lock acquired
                except (IOError, OSError) as e:
                    # Check if it's a "would block" error
                    if e.errno != errno.EWOULDBLOCK:
                        os.close(self.lock_fd)
                        self.lock_fd = None
                        raise
                    # Wait a bit before retrying
                    time.sleep(0.1)
            
            # Timeout reached
            os.close(self.lock_fd)
            self.lock_fd = None
            return False
            
        except ImportError:
            # fcntl not available, fall back to simple file-based locking
            return self._acquire_simple()
        except Exception as e:
            self.logger.error(f"Unix file locking failed: {e}")
            if self.lock_fd is not None:
                try:
                    os.close(self.lock_fd)
                except:
                    pass
                self.lock_fd = None
            return False
    
    def _acquire_simple(self) -> bool:
        """Simple file-based locking fallback."""
        try:
            lock_info_file = self.lock_file_path.with_suffix('.lock_info')
            
            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() < self.timeout:
                try:
                    # Try to create lock info file exclusively
                    with open(lock_info_file, 'x') as f:
                        f.write(f"pid:{os.getpid()}\ntime:{datetime.now().isoformat()}\n")
                    
                    # Lock acquired
                    self.lock_fd = -1  # Use -1 to indicate simple locking
                    return True
                    
                except FileExistsError:
                    # Check if the lock is stale
                    if self._is_stale_lock(lock_info_file):
                        try:
                            lock_info_file.unlink()
                            continue  # Try again
                        except:
                            pass
                    
                    # Wait and retry
                    time.sleep(0.1)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Simple file locking failed: {e}")
            return False
    
    def _release_windows(self) -> bool:
        """Release lock on Windows."""
        try:
            if self.lock_fd == -1:
                return self._release_simple()
            
            import msvcrt
            
            # Unlock the file
            msvcrt.locking(self.lock_fd, msvcrt.LK_UNLCK, 1)
            os.close(self.lock_fd)
            return True
            
        except ImportError:
            return self._release_simple()
        except Exception as e:
            self.logger.error(f"Windows lock release failed: {e}")
            try:
                os.close(self.lock_fd)
            except:
                pass
            return False
    
    def _release_unix(self) -> bool:
        """Release lock on Unix systems."""
        try:
            if self.lock_fd == -1:
                return self._release_simple()
            
            import fcntl
            
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            os.close(self.lock_fd)
            return True
            
        except ImportError:
            return self._release_simple()
        except Exception as e:
            self.logger.error(f"Unix lock release failed: {e}")
            try:
                os.close(self.lock_fd)
            except:
                pass
            return False
    
    def _release_simple(self) -> bool:
        """Release simple file-based lock."""
        try:
            lock_info_file = self.lock_file_path.with_suffix('.lock_info')
            if lock_info_file.exists():
                lock_info_file.unlink()
            return True
        except Exception as e:
            self.logger.error(f"Simple lock release failed: {e}")
            return False
    
    def _is_stale_lock(self, lock_info_file: Path, max_age_seconds: int = 300) -> bool:
        """
        Check if a lock file is stale (older than max_age_seconds).
        
        Args:
            lock_info_file: Path to the lock info file
            max_age_seconds: Maximum age in seconds before considering stale
            
        Returns:
            True if the lock is stale, False otherwise
        """
        try:
            if not lock_info_file.exists():
                return True
            
            # Check file age
            file_age = time.time() - lock_info_file.stat().st_mtime
            if file_age > max_age_seconds:
                return True
            
            # Try to read PID and check if process is still running
            try:
                content = lock_info_file.read_text()
                for line in content.split('\n'):
                    if line.startswith('pid:'):
                        pid = int(line.split(':', 1)[1])
                        
                        # Check if process is still running
                        try:
                            os.kill(pid, 0)  # Signal 0 just checks if process exists
                            return False  # Process is still running
                        except (OSError, ProcessLookupError):
                            return True  # Process is dead, lock is stale
            except:
                pass
            
            return False
            
        except Exception:
            # If we can't determine, assume it's not stale to be safe
            return False


def acquire_file_lock(lock_file_path: Union[str, Path], timeout: int = 10) -> Optional[FileLock]:
    """
    Acquire a file lock in a cross-platform way.
    
    Args:
        lock_file_path: Path to the lock file
        timeout: Maximum time to wait for lock in seconds
        
    Returns:
        FileLock instance if successful, None if failed
    """
    file_lock = FileLock(lock_file_path, timeout)
    if file_lock.acquire():
        return file_lock
    else:
        return None


def release_file_lock(file_lock: FileLock) -> bool:
    """
    Release a file lock.
    
    Args:
        file_lock: FileLock instance to release
        
    Returns:
        True if released successfully, False otherwise
    """
    if file_lock:
        return file_lock.release()
    return True
"""Performance logging utilities for Git synchronization operations."""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Optional, Any, Generator
from pathlib import Path


@dataclass
class PerformanceMetrics:
    """Performance metrics for a Git sync operation."""
    operation: str
    duration: float
    start_time: float
    end_time: float
    context: Optional[Dict[str, Any]] = None
    success: bool = True


class PerformanceLogger:
    """
    Performance logger for Git synchronization operations.
    
    Provides timing utilities and performance metrics collection
    for monitoring Git sync operation performance.
    """
    
    def __init__(self, logger_name: str = 'aiaml.git_sync.performance'):
        """
        Initialize performance logger.
        
        Args:
            logger_name: Name for the logger instance
        """
        self.logger = logging.getLogger(logger_name)
        self._metrics: Dict[str, PerformanceMetrics] = {}
    
    @contextmanager
    def time_operation(
        self, 
        operation: str, 
        context: Optional[Dict[str, Any]] = None,
        log_level: int = logging.INFO
    ) -> Generator[None, None, None]:
        """
        Context manager for timing operations.
        
        Args:
            operation: Name of the operation being timed
            context: Additional context information
            log_level: Logging level for performance messages
            
        Yields:
            None
        """
        start_time = time.time()
        self.logger.log(log_level, f"⏱️ Starting {operation}")
        
        success = True
        try:
            yield
        except Exception as e:
            success = False
            self.logger.error(f"❌ {operation} failed after {time.time() - start_time:.3f}s: {e}")
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Store metrics
            metrics = PerformanceMetrics(
                operation=operation,
                duration=duration,
                start_time=start_time,
                end_time=end_time,
                context=context,
                success=success
            )
            self._metrics[operation] = metrics
            
            # Log completion
            if success:
                self.logger.log(
                    log_level, 
                    f"✅ {operation} completed in {duration:.3f}s"
                )
                
                # Log additional context if provided
                if context:
                    context_str = ", ".join(f"{k}={v}" for k, v in context.items())
                    self.logger.debug(f"📊 {operation} context: {context_str}")
    
    def log_git_command_performance(
        self, 
        command: str, 
        duration: float, 
        attempts: int = 1,
        success: bool = True
    ) -> None:
        """
        Log performance of Git command execution.
        
        Args:
            command: Git command that was executed
            duration: Duration in seconds
            attempts: Number of attempts made
            success: Whether the command succeeded
        """
        status_icon = "✅" if success else "❌"
        retry_info = f" (attempt {attempts})" if attempts > 1 else ""
        
        self.logger.info(
            f"{status_icon} Git command '{command}' completed in {duration:.3f}s{retry_info}"
        )
        
        # Log performance warnings for slow operations
        if duration > 10.0:
            self.logger.warning(f"⚠️ Slow Git operation detected: '{command}' took {duration:.3f}s")
        elif duration > 30.0:
            self.logger.error(f"🐌 Very slow Git operation: '{command}' took {duration:.3f}s")
    
    def log_repository_state_performance(
        self, 
        operation: str, 
        repository_path: Path,
        duration: float,
        state_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log performance of repository state operations.
        
        Args:
            operation: State operation that was performed
            repository_path: Path to the repository
            duration: Duration in seconds
            state_info: Additional state information
        """
        self.logger.info(
            f"🏠 Repository state operation '{operation}' completed in {duration:.3f}s "
            f"for {repository_path.name}"
        )
        
        if state_info:
            for key, value in state_info.items():
                self.logger.debug(f"📋 State info - {key}: {value}")
    
    def log_network_performance(
        self, 
        operation: str, 
        url: str, 
        duration: float,
        data_size: Optional[int] = None,
        success: bool = True
    ) -> None:
        """
        Log performance of network operations.
        
        Args:
            operation: Network operation performed
            url: Remote URL accessed
            duration: Duration in seconds
            data_size: Amount of data transferred (bytes)
            success: Whether the operation succeeded
        """
        status_icon = "✅" if success else "❌"
        size_info = f", {self._format_data_size(data_size)}" if data_size else ""
        
        self.logger.info(
            f"{status_icon} Network operation '{operation}' to {url} "
            f"completed in {duration:.3f}s{size_info}"
        )
        
        # Calculate and log transfer speed if data size is available
        if data_size and duration > 0:
            speed_mbps = (data_size * 8) / (duration * 1_000_000)  # Convert to Mbps
            self.logger.debug(f"📡 Transfer speed: {speed_mbps:.2f} Mbps")
        
        # Log warnings for slow network operations
        if duration > 15.0:
            self.logger.warning(f"⚠️ Slow network operation: '{operation}' took {duration:.3f}s")
    
    def log_file_system_performance(
        self, 
        operation: str, 
        path: Path, 
        duration: float,
        file_count: Optional[int] = None,
        total_size: Optional[int] = None
    ) -> None:
        """
        Log performance of file system operations.
        
        Args:
            operation: File system operation performed
            path: Path that was operated on
            duration: Duration in seconds
            file_count: Number of files processed
            total_size: Total size of files processed (bytes)
        """
        file_info = f" ({file_count} files)" if file_count else ""
        size_info = f", {self._format_data_size(total_size)}" if total_size else ""
        
        self.logger.info(
            f"📁 File system operation '{operation}' on {path.name} "
            f"completed in {duration:.3f}s{file_info}{size_info}"
        )
        
        # Log performance metrics
        if file_count and duration > 0:
            files_per_sec = file_count / duration
            self.logger.debug(f"📊 Processing rate: {files_per_sec:.1f} files/second")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of performance metrics.
        
        Returns:
            Dictionary containing performance summary
        """
        if not self._metrics:
            return {"total_operations": 0, "average_duration": 0.0}
        
        total_operations = len(self._metrics)
        total_duration = sum(m.duration for m in self._metrics.values())
        average_duration = total_duration / total_operations
        
        successful_ops = sum(1 for m in self._metrics.values() if m.success)
        success_rate = successful_ops / total_operations
        
        # Find slowest operation
        slowest_op = max(self._metrics.values(), key=lambda m: m.duration)
        
        return {
            "total_operations": total_operations,
            "total_duration": total_duration,
            "average_duration": average_duration,
            "success_rate": success_rate,
            "slowest_operation": {
                "name": slowest_op.operation,
                "duration": slowest_op.duration
            }
        }
    
    def log_performance_summary(self) -> None:
        """Log a summary of all performance metrics."""
        summary = self.get_performance_summary()
        
        if summary["total_operations"] == 0:
            self.logger.info("📊 No performance metrics available")
            return
        
        self.logger.info(
            f"📊 Performance Summary: {summary['total_operations']} operations, "
            f"avg {summary['average_duration']:.3f}s, "
            f"{summary['success_rate']:.1%} success rate"
        )
        
        slowest = summary["slowest_operation"]
        self.logger.info(
            f"🐌 Slowest operation: {slowest['name']} ({slowest['duration']:.3f}s)"
        )
    
    def _format_data_size(self, size_bytes: int) -> str:
        """Format data size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# Global performance logger instance
_performance_logger: Optional[PerformanceLogger] = None


def get_performance_logger() -> PerformanceLogger:
    """Get or create the global performance logger instance."""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger()
    return _performance_logger
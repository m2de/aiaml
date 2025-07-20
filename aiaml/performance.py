"""Performance monitoring and optimization utilities for AIAML."""

import logging
import threading
import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

from .config import Config


@dataclass
class OperationMetrics:
    """Metrics for a specific operation type."""
    total_operations: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    last_operation: Optional[datetime] = None
    
    def add_timing(self, duration: float, success: bool = True) -> None:
        """Add a timing measurement to the metrics."""
        self.total_operations += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.avg_time = self.total_time / self.total_operations
        self.recent_times.append(duration)
        self.last_operation = datetime.now()
        
        if not success:
            self.error_count += 1
    
    def get_recent_avg(self) -> float:
        """Get average time for recent operations."""
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times)
    
    def get_percentile(self, percentile: float) -> float:
        """Get percentile timing from recent operations."""
        if not self.recent_times:
            return 0.0
        sorted_times = sorted(self.recent_times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]


class PerformanceMonitor:
    """Comprehensive performance monitoring system."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('aiaml.performance')
        self._lock = threading.RLock()
        
        # Operation metrics
        self.metrics: Dict[str, OperationMetrics] = defaultdict(OperationMetrics)
        
        # System resource monitoring
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
        else:
            self.process = None
            self.logger.warning("psutil not available - system resource monitoring disabled")
        
        self.system_stats = {
            'start_time': datetime.now(),
            'peak_memory_mb': 0.0,
            'peak_cpu_percent': 0.0,
            'total_disk_reads': 0,
            'total_disk_writes': 0,
            'file_operations': 0
        }
        
        # Performance thresholds (from requirements)
        self.thresholds = {
            'memory_store_max_time': 1.0,  # Requirement 6.1
            'memory_search_max_time': 2.0,  # Requirement 6.2
            'memory_recall_max_time': 1.0,
            'file_operation_max_time': 0.5
        }
        
        # Start background monitoring
        self._start_background_monitoring()
    
    def _start_background_monitoring(self) -> None:
        """Start background thread for system resource monitoring."""
        def monitor_resources():
            while True:
                try:
                    # Update system resource stats if psutil is available
                    if self.process:
                        memory_info = self.process.memory_info()
                        memory_mb = memory_info.rss / 1024 / 1024
                        cpu_percent = self.process.cpu_percent()
                        
                        with self._lock:
                            self.system_stats['peak_memory_mb'] = max(
                                self.system_stats['peak_memory_mb'], memory_mb
                            )
                            self.system_stats['peak_cpu_percent'] = max(
                                self.system_stats['peak_cpu_percent'], cpu_percent
                            )
                    
                    # Check for performance threshold violations
                    self._check_performance_thresholds()
                    
                    time.sleep(30)  # Monitor every 30 seconds
                    
                except Exception as e:
                    self.logger.error(f"Error in resource monitoring: {e}")
                    time.sleep(60)  # Wait longer on error
        
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()
        self.logger.info("Performance monitoring background thread started")
    
    def _check_performance_thresholds(self) -> None:
        """Check if any operations are exceeding performance thresholds."""
        with self._lock:
            for operation, metrics in self.metrics.items():
                threshold_key = f"{operation}_max_time"
                if threshold_key in self.thresholds:
                    threshold = self.thresholds[threshold_key]
                    recent_avg = metrics.get_recent_avg()
                    
                    if recent_avg > threshold:
                        self.logger.warning(
                            f"Performance threshold exceeded for {operation}: "
                            f"{recent_avg:.3f}s > {threshold}s",
                            extra={
                                'operation': operation,
                                'actual_time': recent_avg,
                                'threshold': threshold,
                                'violation_type': 'average_time'
                            }
                        )
    
    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        start_time = time.time()
        success = True
        
        try:
            yield
        except Exception as e:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            
            with self._lock:
                self.metrics[operation_name].add_timing(duration, success)
                
                # Log slow operations
                threshold_key = f"{operation_name}_max_time"
                if threshold_key in self.thresholds:
                    threshold = self.thresholds[threshold_key]
                    if duration > threshold:
                        self.logger.warning(
                            f"Slow {operation_name} operation: {duration:.3f}s > {threshold}s",
                            extra={
                                'operation': operation_name,
                                'duration': duration,
                                'threshold': threshold,
                                'success': success
                            }
                        )
    
    def record_file_operation(self, operation_type: str, file_path: Path, size_bytes: int = 0) -> None:
        """Record file I/O operations for optimization tracking."""
        with self._lock:
            self.system_stats['file_operations'] += 1
            
            if operation_type in ['read', 'load']:
                self.system_stats['total_disk_reads'] += 1
            elif operation_type in ['write', 'store', 'save']:
                self.system_stats['total_disk_writes'] += 1
        
        self.logger.debug(
            f"File operation: {operation_type} on {file_path.name} ({size_bytes} bytes)",
            extra={
                'operation': 'file_io',
                'file_operation': operation_type,
                'file_path': str(file_path),
                'size_bytes': size_bytes
            }
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        with self._lock:
            # Calculate uptime
            uptime = datetime.now() - self.system_stats['start_time']
            
            # Get current system stats if psutil is available
            current_memory_mb = 0.0
            current_cpu_percent = 0.0
            
            if self.process:
                try:
                    memory_info = self.process.memory_info()
                    current_memory_mb = memory_info.rss / 1024 / 1024
                    current_cpu_percent = self.process.cpu_percent()
                except Exception as e:
                    self.logger.warning(f"Failed to get current system stats: {e}")
            
            # Build operation metrics
            operation_metrics = {}
            for operation, metrics in self.metrics.items():
                operation_metrics[operation] = {
                    'total_operations': metrics.total_operations,
                    'avg_time': metrics.avg_time,
                    'recent_avg_time': metrics.get_recent_avg(),
                    'min_time': metrics.min_time if metrics.min_time != float('inf') else 0.0,
                    'max_time': metrics.max_time,
                    'p95_time': metrics.get_percentile(95),
                    'p99_time': metrics.get_percentile(99),
                    'error_count': metrics.error_count,
                    'error_rate': metrics.error_count / max(1, metrics.total_operations),
                    'last_operation': metrics.last_operation.isoformat() if metrics.last_operation else None
                }
            
            return {
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': uptime.total_seconds(),
                'psutil_available': PSUTIL_AVAILABLE,
                'system_resources': {
                    'current_memory_mb': current_memory_mb,
                    'peak_memory_mb': self.system_stats['peak_memory_mb'],
                    'current_cpu_percent': current_cpu_percent,
                    'peak_cpu_percent': self.system_stats['peak_cpu_percent'],
                    'total_disk_reads': self.system_stats['total_disk_reads'],
                    'total_disk_writes': self.system_stats['total_disk_writes'],
                    'total_file_operations': self.system_stats['file_operations']
                },
                'operations': operation_metrics,
                'performance_thresholds': self.thresholds,
                'threshold_violations': self._get_threshold_violations()
            }
    
    def _get_threshold_violations(self) -> List[Dict[str, Any]]:
        """Get list of current performance threshold violations."""
        violations = []
        
        for operation, metrics in self.metrics.items():
            threshold_key = f"{operation}_max_time"
            if threshold_key in self.thresholds:
                threshold = self.thresholds[threshold_key]
                recent_avg = metrics.get_recent_avg()
                
                if recent_avg > threshold:
                    violations.append({
                        'operation': operation,
                        'threshold': threshold,
                        'actual_time': recent_avg,
                        'violation_ratio': recent_avg / threshold,
                        'recent_operations': len(metrics.recent_times)
                    })
        
        return violations
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        with self._lock:
            self.metrics.clear()
            self.system_stats.update({
                'start_time': datetime.now(),
                'peak_memory_mb': 0.0,
                'peak_cpu_percent': 0.0,
                'total_disk_reads': 0,
                'total_disk_writes': 0,
                'file_operations': 0
            })
        
        self.logger.info("Performance metrics reset")


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None
_monitor_lock = threading.Lock()


def get_performance_monitor(config: Config) -> PerformanceMonitor:
    """Get or create the global performance monitor instance."""
    global _performance_monitor
    
    with _monitor_lock:
        if _performance_monitor is None:
            _performance_monitor = PerformanceMonitor(config)
        return _performance_monitor


def time_operation(operation_name: str, config: Config):
    """Decorator for timing operations."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            monitor = get_performance_monitor(config)
            with monitor.time_operation(operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def record_file_operation(operation_type: str, file_path: Path, size_bytes: int = 0, config: Config = None) -> None:
    """Record a file I/O operation for performance tracking."""
    if config:
        monitor = get_performance_monitor(config)
        monitor.record_file_operation(operation_type, file_path, size_bytes)


def get_performance_stats(config: Config) -> Dict[str, Any]:
    """Get current performance statistics."""
    monitor = get_performance_monitor(config)
    return monitor.get_performance_report()


def reset_performance_stats(config: Config) -> None:
    """Reset performance statistics."""
    monitor = get_performance_monitor(config)
    monitor.reset_metrics()
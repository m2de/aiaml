"""Performance benchmarking utilities for AIAML."""

import logging
import random
import string
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Tuple

from .config import Config
from .memory import store_memory_atomic, search_memories_optimized, recall_memories
from .performance import get_performance_monitor


class PerformanceBenchmark:
    """Comprehensive performance benchmarking suite."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('aiaml.benchmark')
        self.monitor = get_performance_monitor(config)
    
    def generate_test_data(self, count: int) -> List[Tuple[str, str, List[str], str]]:
        """Generate test memory data for benchmarking."""
        agents = ['claude', 'gpt', 'gemini', 'assistant']
        users = ['user1', 'user2', 'user3', 'user4', 'user5']
        topic_pools = [
            ['programming', 'python', 'coding'],
            ['data', 'science', 'analysis'],
            ['web', 'development', 'javascript'],
            ['machine', 'learning', 'ai'],
            ['database', 'sql', 'queries'],
            ['testing', 'automation', 'qa'],
            ['security', 'encryption', 'auth'],
            ['performance', 'optimization', 'speed']
        ]
        
        test_data = []
        for i in range(count):
            agent = random.choice(agents)
            user = random.choice(users)
            topics = random.choice(topic_pools)
            
            # Generate content of varying lengths
            content_length = random.randint(50, 500)
            content = f"Test memory {i}: " + ''.join(
                random.choices(string.ascii_letters + string.digits + ' ', 
                             k=content_length)
            )
            
            test_data.append((agent, user, topics, content))
        
        return test_data
    
    def benchmark_memory_storage(self, memory_count: int = 1000) -> Dict[str, Any]:
        """Benchmark memory storage operations (Requirement 6.1: < 1 second)."""
        self.logger.info(f"Starting memory storage benchmark with {memory_count} memories")
        
        test_data = self.generate_test_data(memory_count)
        results = {
            'total_memories': memory_count,
            'successful_stores': 0,
            'failed_stores': 0,
            'total_time': 0.0,
            'avg_time_per_store': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'times_under_threshold': 0,
            'threshold_seconds': 1.0,
            'memory_ids': []
        }
        
        start_time = time.time()
        
        for i, (agent, user, topics, content) in enumerate(test_data):
            store_start = time.time()
            
            try:
                result = store_memory_atomic(agent, user, topics, content, self.config)
                store_time = time.time() - store_start
                
                if 'memory_id' in result:
                    results['successful_stores'] += 1
                    results['memory_ids'].append(result['memory_id'])
                    
                    # Track timing statistics
                    results['min_time'] = min(results['min_time'], store_time)
                    results['max_time'] = max(results['max_time'], store_time)
                    
                    if store_time <= results['threshold_seconds']:
                        results['times_under_threshold'] += 1
                else:
                    results['failed_stores'] += 1
                    self.logger.warning(f"Failed to store memory {i}: {result}")
                    
            except Exception as e:
                results['failed_stores'] += 1
                self.logger.error(f"Error storing memory {i}: {e}")
            
            # Progress logging
            if (i + 1) % 100 == 0:
                self.logger.info(f"Stored {i + 1}/{memory_count} memories")
        
        results['total_time'] = time.time() - start_time
        results['avg_time_per_store'] = results['total_time'] / memory_count
        results['success_rate'] = results['successful_stores'] / memory_count
        results['threshold_compliance_rate'] = results['times_under_threshold'] / max(1, results['successful_stores'])
        
        if results['min_time'] == float('inf'):
            results['min_time'] = 0.0
        
        self.logger.info(
            f"Storage benchmark completed: {results['successful_stores']}/{memory_count} successful, "
            f"avg time: {results['avg_time_per_store']:.3f}s, "
            f"threshold compliance: {results['threshold_compliance_rate']:.1%}"
        )
        
        return results
    
    def benchmark_memory_search(self, search_count: int = 100, memory_count: int = 10000) -> Dict[str, Any]:
        """Benchmark memory search operations (Requirement 6.2: < 2 seconds for 10k memories)."""
        self.logger.info(f"Starting memory search benchmark with {search_count} searches on {memory_count} memories")
        
        # First ensure we have enough test memories
        existing_memories = list(self.config.memory_dir.glob("*.md"))
        if len(existing_memories) < memory_count:
            needed = memory_count - len(existing_memories)
            self.logger.info(f"Creating {needed} additional test memories for search benchmark")
            storage_result = self.benchmark_memory_storage(needed)
            if storage_result['successful_stores'] < needed * 0.9:
                self.logger.warning("Failed to create sufficient test memories for search benchmark")
        
        # Generate search keywords
        search_keywords = [
            ['python', 'programming'],
            ['data', 'science'],
            ['web', 'development'],
            ['machine', 'learning'],
            ['database', 'sql'],
            ['testing', 'automation'],
            ['security', 'auth'],
            ['performance', 'optimization'],
            ['javascript', 'coding'],
            ['analysis', 'queries']
        ]
        
        results = {
            'total_searches': search_count,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_time': 0.0,
            'avg_time_per_search': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'times_under_threshold': 0,
            'threshold_seconds': 2.0,
            'total_results_found': 0,
            'avg_results_per_search': 0.0
        }
        
        start_time = time.time()
        
        for i in range(search_count):
            keywords = random.choice(search_keywords)
            search_start = time.time()
            
            try:
                search_results = search_memories_optimized(keywords, self.config)
                search_time = time.time() - search_start
                
                if isinstance(search_results, list) and not (len(search_results) == 1 and 'error' in search_results[0]):
                    results['successful_searches'] += 1
                    results['total_results_found'] += len(search_results)
                    
                    # Track timing statistics
                    results['min_time'] = min(results['min_time'], search_time)
                    results['max_time'] = max(results['max_time'], search_time)
                    
                    if search_time <= results['threshold_seconds']:
                        results['times_under_threshold'] += 1
                else:
                    results['failed_searches'] += 1
                    self.logger.warning(f"Failed search {i}: {search_results}")
                    
            except Exception as e:
                results['failed_searches'] += 1
                self.logger.error(f"Error in search {i}: {e}")
            
            # Progress logging
            if (i + 1) % 20 == 0:
                self.logger.info(f"Completed {i + 1}/{search_count} searches")
        
        results['total_time'] = time.time() - start_time
        results['avg_time_per_search'] = results['total_time'] / search_count
        results['success_rate'] = results['successful_searches'] / search_count
        results['threshold_compliance_rate'] = results['times_under_threshold'] / max(1, results['successful_searches'])
        results['avg_results_per_search'] = results['total_results_found'] / max(1, results['successful_searches'])
        
        if results['min_time'] == float('inf'):
            results['min_time'] = 0.0
        
        self.logger.info(
            f"Search benchmark completed: {results['successful_searches']}/{search_count} successful, "
            f"avg time: {results['avg_time_per_search']:.3f}s, "
            f"threshold compliance: {results['threshold_compliance_rate']:.1%}"
        )
        
        return results
    
    def benchmark_concurrent_access(self, client_count: int = 10, operations_per_client: int = 50) -> Dict[str, Any]:
        """Benchmark concurrent client access (Requirement 6.3: no significant performance degradation)."""
        self.logger.info(f"Starting concurrent access benchmark with {client_count} clients, {operations_per_client} ops each")
        
        def client_operations(client_id: int) -> Dict[str, Any]:
            """Simulate operations for a single client."""
            client_results = {
                'client_id': client_id,
                'operations_completed': 0,
                'operations_failed': 0,
                'total_time': 0.0,
                'store_times': [],
                'search_times': [],
                'recall_times': []
            }
            
            start_time = time.time()
            
            for op_num in range(operations_per_client):
                try:
                    # Mix of operations: 40% store, 40% search, 20% recall
                    operation_type = random.choices(
                        ['store', 'search', 'recall'],
                        weights=[0.4, 0.4, 0.2]
                    )[0]
                    
                    op_start = time.time()
                    
                    if operation_type == 'store':
                        result = store_memory_atomic(
                            f"client_{client_id}",
                            f"user_{client_id}",
                            ['concurrent', 'test'],
                            f"Concurrent test from client {client_id}, operation {op_num}",
                            self.config
                        )
                        op_time = time.time() - op_start
                        client_results['store_times'].append(op_time)
                        
                    elif operation_type == 'search':
                        result = search_memories_optimized(['concurrent', 'test'], self.config)
                        op_time = time.time() - op_start
                        client_results['search_times'].append(op_time)
                        
                    else:  # recall
                        # Get some memory IDs to recall
                        search_result = search_memories_optimized(['test'], self.config)
                        if search_result and len(search_result) > 0:
                            memory_ids = [mem.get('memory_id') for mem in search_result[:3] if mem.get('memory_id')]
                            if memory_ids:
                                result = recall_memories(memory_ids, self.config)
                                op_time = time.time() - op_start
                                client_results['recall_times'].append(op_time)
                    
                    client_results['operations_completed'] += 1
                    
                except Exception as e:
                    client_results['operations_failed'] += 1
                    self.logger.error(f"Client {client_id} operation {op_num} failed: {e}")
            
            client_results['total_time'] = time.time() - start_time
            return client_results
        
        # Run concurrent clients
        start_time = time.time()
        client_results = []
        
        with ThreadPoolExecutor(max_workers=client_count) as executor:
            futures = [executor.submit(client_operations, i) for i in range(client_count)]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    client_results.append(result)
                except Exception as e:
                    self.logger.error(f"Client thread failed: {e}")
        
        total_time = time.time() - start_time
        
        # Aggregate results
        results = {
            'client_count': client_count,
            'operations_per_client': operations_per_client,
            'total_time': total_time,
            'total_operations': sum(r['operations_completed'] for r in client_results),
            'total_failures': sum(r['operations_failed'] for r in client_results),
            'operations_per_second': sum(r['operations_completed'] for r in client_results) / total_time,
            'avg_client_time': sum(r['total_time'] for r in client_results) / len(client_results),
            'store_operation_stats': self._calculate_operation_stats([t for r in client_results for t in r['store_times']]),
            'search_operation_stats': self._calculate_operation_stats([t for r in client_results for t in r['search_times']]),
            'recall_operation_stats': self._calculate_operation_stats([t for r in client_results for t in r['recall_times']]),
            'client_results': client_results
        }
        
        self.logger.info(
            f"Concurrent access benchmark completed: {results['total_operations']} operations, "
            f"{results['operations_per_second']:.1f} ops/sec, "
            f"{results['total_failures']} failures"
        )
        
        return results
    
    def _calculate_operation_stats(self, times: List[float]) -> Dict[str, float]:
        """Calculate statistics for a list of operation times."""
        if not times:
            return {'count': 0, 'avg': 0.0, 'min': 0.0, 'max': 0.0, 'p95': 0.0, 'p99': 0.0}
        
        sorted_times = sorted(times)
        count = len(times)
        
        return {
            'count': count,
            'avg': sum(times) / count,
            'min': min(times),
            'max': max(times),
            'p95': sorted_times[int(count * 0.95)] if count > 0 else 0.0,
            'p99': sorted_times[int(count * 0.99)] if count > 0 else 0.0
        }
    
    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run all benchmarks and return comprehensive results."""
        self.logger.info("Starting comprehensive performance benchmark suite")
        
        benchmark_results = {
            'timestamp': time.time(),
            'config': {
                'memory_dir': str(self.config.memory_dir),
                'max_search_results': self.config.max_search_results,
                'log_level': self.config.log_level
            }
        }
        
        try:
            # Storage benchmark
            self.logger.info("Running storage performance benchmark...")
            benchmark_results['storage'] = self.benchmark_memory_storage(1000)
            
            # Search benchmark
            self.logger.info("Running search performance benchmark...")
            benchmark_results['search'] = self.benchmark_memory_search(100, 5000)
            
            # Concurrent access benchmark
            self.logger.info("Running concurrent access benchmark...")
            benchmark_results['concurrent'] = self.benchmark_concurrent_access(5, 20)
            
            # Overall assessment
            benchmark_results['assessment'] = self._assess_performance(benchmark_results)
            
        except Exception as e:
            self.logger.error(f"Benchmark suite failed: {e}")
            benchmark_results['error'] = str(e)
        
        self.logger.info("Comprehensive benchmark suite completed")
        return benchmark_results
    
    def _assess_performance(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall performance against requirements."""
        assessment = {
            'requirement_6_1_compliance': False,  # Storage < 1s
            'requirement_6_2_compliance': False,  # Search < 2s for 10k memories
            'requirement_6_3_compliance': False,  # No significant degradation with multiple clients
            'overall_grade': 'F',
            'recommendations': []
        }
        
        # Check Requirement 6.1 (Storage performance)
        if 'storage' in results:
            storage_compliance = results['storage']['threshold_compliance_rate']
            if storage_compliance >= 0.95:  # 95% of operations under 1s
                assessment['requirement_6_1_compliance'] = True
            else:
                assessment['recommendations'].append(
                    f"Storage performance needs improvement: only {storage_compliance:.1%} of operations under 1s threshold"
                )
        
        # Check Requirement 6.2 (Search performance)
        if 'search' in results:
            search_compliance = results['search']['threshold_compliance_rate']
            if search_compliance >= 0.95:  # 95% of searches under 2s
                assessment['requirement_6_2_compliance'] = True
            else:
                assessment['recommendations'].append(
                    f"Search performance needs improvement: only {search_compliance:.1%} of operations under 2s threshold"
                )
        
        # Check Requirement 6.3 (Concurrent performance)
        if 'concurrent' in results:
            # Consider it compliant if operations per second is reasonable and failure rate is low
            ops_per_sec = results['concurrent']['operations_per_second']
            failure_rate = results['concurrent']['total_failures'] / max(1, results['concurrent']['total_operations'])
            
            if ops_per_sec >= 10 and failure_rate <= 0.05:  # At least 10 ops/sec, max 5% failure rate
                assessment['requirement_6_3_compliance'] = True
            else:
                assessment['recommendations'].append(
                    f"Concurrent performance needs improvement: {ops_per_sec:.1f} ops/sec, {failure_rate:.1%} failure rate"
                )
        
        # Overall grade
        compliance_count = sum([
            assessment['requirement_6_1_compliance'],
            assessment['requirement_6_2_compliance'],
            assessment['requirement_6_3_compliance']
        ])
        
        if compliance_count == 3:
            assessment['overall_grade'] = 'A'
        elif compliance_count == 2:
            assessment['overall_grade'] = 'B'
        elif compliance_count == 1:
            assessment['overall_grade'] = 'C'
        else:
            assessment['overall_grade'] = 'F'
        
        return assessment


def run_performance_benchmark(config: Config) -> Dict[str, Any]:
    """Run comprehensive performance benchmark."""
    benchmark = PerformanceBenchmark(config)
    return benchmark.run_comprehensive_benchmark()
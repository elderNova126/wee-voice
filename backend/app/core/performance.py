"""
Performance and Scalability Configuration
Handles rate limiting, caching, and async operations for high-traffic scenarios
"""
import logging
import asyncio
import functools
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

# Simple in-memory cache (for production, use Redis)
_cache: Dict[str, tuple[Any, float]] = {}
_cache_lock = asyncio.Lock()

# Rate limiting tracker (for production, use Redis)
_rate_limit_tracker: Dict[str, list[float]] = {}
_rate_limit_lock = asyncio.Lock()


async def cached(ttl: int = 300):
    """
    Decorator for caching async function results
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            async with _cache_lock:
                if cache_key in _cache:
                    value, expiry = _cache[cache_key]
                    if time.time() < expiry:
                        logger.debug(f"Cache HIT: {func.__name__}")
                        return value
                    else:
                        # Remove expired entry
                        del _cache[cache_key]
            
            # Cache miss - call function
            logger.debug(f"Cache MISS: {func.__name__}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            async with _cache_lock:
                _cache[cache_key] = (result, time.time() + ttl)
                # Clean old entries if cache is too large
                if len(_cache) > 1000:
                    await _clean_cache()
            
            return result
        return wrapper
    return decorator


async def _clean_cache():
    """Remove expired cache entries"""
    current_time = time.time()
    expired_keys = [k for k, (_, expiry) in _cache.items() if current_time >= expiry]
    for key in expired_keys:
        del _cache[key]
    logger.info(f"Cleaned {len(expired_keys)} expired cache entries")


async def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Decorator for rate limiting async functions
    
    Args:
        max_requests: Maximum requests allowed in the time window
        window_seconds: Time window in seconds
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate key (use user_id or IP if available)
            # For now, use a simple key based on function name
            key = f"{func.__name__}"
            if args and hasattr(args[0], 'id'):
                key = f"{func.__name__}:{args[0].id}"
            
            current_time = time.time()
            
            async with _rate_limit_lock:
                if key not in _rate_limit_tracker:
                    _rate_limit_tracker[key] = []
                
                # Remove old requests outside the window
                _rate_limit_tracker[key] = [
                    req_time for req_time in _rate_limit_tracker[key]
                    if current_time - req_time < window_seconds
                ]
                
                # Check if rate limit exceeded
                if len(_rate_limit_tracker[key]) >= max_requests:
                    logger.warning(f"Rate limit exceeded for {key}")
                    raise Exception(f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s")
                
                # Add current request
                _rate_limit_tracker[key].append(current_time)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def run_in_executor(func: Callable):
    """
    Decorator to run synchronous blocking functions in a thread pool
    Useful for converting blocking I/O to async
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    return wrapper


class ConnectionPool:
    """Simple connection pool manager for external services"""
    
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(max_connections)
        self.active_connections = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a connection from the pool"""
        await self.semaphore.acquire()
        async with self._lock:
            self.active_connections += 1
            logger.debug(f"Connection acquired. Active: {self.active_connections}/{self.max_connections}")
    
    async def release(self):
        """Release a connection back to the pool"""
        async with self._lock:
            self.active_connections -= 1
            logger.debug(f"Connection released. Active: {self.active_connections}/{self.max_connections}")
        self.semaphore.release()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


# Global connection pools for external services
openai_pool = ConnectionPool(max_connections=50)
gemini_pool = ConnectionPool(max_connections=50)
smtp_pool = ConnectionPool(max_connections=20)


class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.request_times: Dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
    
    async def record_request(self, endpoint: str, duration: float):
        """Record request duration"""
        async with self._lock:
            if endpoint not in self.request_times:
                self.request_times[endpoint] = []
            
            self.request_times[endpoint].append(duration)
            
            # Keep only last 1000 requests per endpoint
            if len(self.request_times[endpoint]) > 1000:
                self.request_times[endpoint] = self.request_times[endpoint][-1000:]
    
    async def get_stats(self, endpoint: str) -> Dict[str, float]:
        """Get performance statistics for an endpoint"""
        async with self._lock:
            if endpoint not in self.request_times or not self.request_times[endpoint]:
                return {}
            
            times = self.request_times[endpoint]
            return {
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "count": len(times),
                "p50": sorted(times)[len(times) // 2],
                "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
                "p99": sorted(times)[int(len(times) * 0.99)] if len(times) > 100 else max(times)
            }
    
    async def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all endpoints"""
        async with self._lock:
            return {endpoint: await self.get_stats(endpoint) for endpoint in self.request_times}


# Global performance monitor
performance_monitor = PerformanceMonitor()


def monitor_performance(endpoint_name: str):
    """Decorator to monitor endpoint performance"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                await performance_monitor.record_request(endpoint_name, duration)
                if duration > 5.0:  # Log slow requests
                    logger.warning(f"Slow request: {endpoint_name} took {duration:.2f}s")
        return wrapper
    return decorator


async def get_performance_stats() -> Dict[str, Any]:
    """Get current performance statistics"""
    return {
        "cache_size": len(_cache),
        "rate_limit_tracked_keys": len(_rate_limit_tracker),
        "openai_connections": openai_pool.active_connections,
        "gemini_connections": gemini_pool.active_connections,
        "smtp_connections": smtp_pool.active_connections,
        "endpoint_stats": await performance_monitor.get_all_stats()
    }


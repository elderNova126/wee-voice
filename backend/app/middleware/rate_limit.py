"""
Rate Limiting Middleware
Prevents API overload by limiting requests per user/IP
"""
import time
import logging
from typing import Callable, Dict, List
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter (for production, use Redis)
_rate_limits: Dict[str, List[float]] = {}
_rate_limits_lock = asyncio.Lock()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware
    
    Limits:
    - 100 requests per minute per IP (general)
    - 30 requests per minute for expensive endpoints
    """
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        
        # Expensive endpoints get stricter limits
        self.expensive_endpoints = {
            '/api/v1/calls/': 30,  # List calls
            '/api/v1/agents/': 30,  # List agents
            '/generate-summary': 10,  # Summary generation
            '/upload': 20,  # File uploads
            '/sync': 20,  # Integration sync
        }
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks
        if request.url.path in ['/health', '/']:
            return await call_next(request)
        
        # Get client identifier (IP or user ID if authenticated)
        client_id = request.client.host if request.client else 'unknown'
        
        # Check if this is an expensive endpoint
        path = request.url.path
        limit = self.requests_per_minute
        for endpoint_pattern, endpoint_limit in self.expensive_endpoints.items():
            if endpoint_pattern in path:
                limit = endpoint_limit
                break
        
        # Check rate limit
        current_time = time.time()
        key = f"{client_id}:{path}"
        
        async with _rate_limits_lock:
            if key not in _rate_limits:
                _rate_limits[key] = []
            
            # Remove old requests outside the window
            _rate_limits[key] = [
                req_time for req_time in _rate_limits[key]
                if current_time - req_time < self.window_seconds
            ]
            
            # Check if rate limit exceeded
            if len(_rate_limits[key]) >= limit:
                logger.warning(
                    f"Rate limit exceeded for {client_id} on {path}: "
                    f"{len(_rate_limits[key])} requests in {self.window_seconds}s"
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded. Max {limit} requests per minute.",
                        "retry_after": int(self.window_seconds)
                    },
                    headers={
                        "Retry-After": str(self.window_seconds),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(current_time + self.window_seconds))
                    }
                )
            
            # Add current request
            _rate_limits[key].append(current_time)
            remaining = limit - len(_rate_limits[key])
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window_seconds))
        
        return response


async def cleanup_rate_limits():
    """
    Periodic cleanup of old rate limit data
    Should be called periodically (e.g., every 5 minutes)
    """
    while True:
        await asyncio.sleep(300)  # Run every 5 minutes
        try:
            current_time = time.time()
            async with _rate_limits_lock:
                # Remove entries with no recent requests
                keys_to_remove = []
                for key, requests in _rate_limits.items():
                    # Remove old requests
                    recent_requests = [
                        req_time for req_time in requests
                        if current_time - req_time < 300
                    ]
                    if not recent_requests:
                        keys_to_remove.append(key)
                    else:
                        _rate_limits[key] = recent_requests
                
                for key in keys_to_remove:
                    del _rate_limits[key]
                
                logger.info(f"Rate limit cleanup: removed {len(keys_to_remove)} inactive entries")
        except Exception as e:
            logger.error(f"Error in rate limit cleanup: {e}")


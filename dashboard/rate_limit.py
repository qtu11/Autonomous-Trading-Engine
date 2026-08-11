"""
Rate Limiting Middleware for FastAPI
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict, Tuple
import asyncio


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, client_id: str) -> Tuple[bool, int]:
        """Check if request is allowed, returns (allowed, remaining)"""
        async with self._lock:
            now = time.time()
            window = 60  # 1 minute window
            
            # Remove old requests
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if now - req_time < window
            ]
            
            # Check limit
            if len(self.requests[client_id]) >= self.requests_per_minute:
                return False, 0
            
            # Add request
            self.requests[client_id].append(now)
            remaining = self.requests_per_minute - len(self.requests[client_id])
            return True, remaining


class IPRateLimiter:
    """IP-based rate limiter"""
    
    def __init__(self):
        self.limiter = RateLimiter(requests_per_minute=100)
    
    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        
        allowed, remaining = await self.limiter.check_rate_limit(client_ip)
        
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in a few seconds.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"}
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# Global rate limiter instance
rate_limiter = IPRateLimiter()

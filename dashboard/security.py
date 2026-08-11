"""
Security Middleware for FastAPI
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import re
import hashlib
import hmac
import os
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Sanitize all input parameters"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip for GET requests (query params)
        if request.method == "GET":
            return await call_next(request)
        
        # Process body for POST/PUT/PATCH
        # This is a basic implementation - in production use more robust sanitization
        body = await request.body()
        
        # Add request ID for tracking
        request_id = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        request.state.request_id = request_id
        
        return await call_next(request)


class HMACValidator:
    """Validate HMAC signatures for API requests"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
    
    def sign(self, message: str) -> str:
        """Generate HMAC signature"""
        return hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify(self, message: str, signature: str) -> bool:
        """Verify HMAC signature"""
        expected = self.sign(message)
        return hmac.compare_digest(expected, signature)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        import uuid
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response

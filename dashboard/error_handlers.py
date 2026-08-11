"""
Comprehensive Error Handling for FastAPI
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Union
import traceback
import sys
import logging

logger = logging.getLogger(__name__)


class TradingSystemError(Exception):
    """Base exception for trading system"""
    def __init__(self, message: str, code: str = "SYSTEM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DataError(TradingSystemError):
    """Data-related errors"""
    def __init__(self, message: str):
        super().__init__(message, "DATA_ERROR")


class SignalError(TradingSystemError):
    """Signal generation errors"""
    def __init__(self, message: str):
        super().__init__(message, "SIGNAL_ERROR")


class RiskError(TradingSystemError):
    """Risk management errors"""
    def __init__(self, message: str):
        super().__init__(message, "RISK_ERROR")


class BrokerError(TradingSystemError):
    """Broker/execution errors"""
    def __init__(self, message: str):
        super().__init__(message, "BROKER_ERROR")


class MT5Error(TradingSystemError):
    """MT5 connection errors"""
    def __init__(self, message: str):
        super().__init__(message, "MT5_ERROR")


async def trading_system_error_handler(
    request: Request, exc: TradingSystemError
) -> JSONResponse:
    """Handle TradingSystemError"""
    logger.error(f"TradingSystemError: {exc.message} (code: {exc.code})")
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.code,
            "message": exc.message,
            "type": "TradingSystemError"
        }
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": str(exc.detail),
            "status_code": exc.status_code
        }
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": errors
        }
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle all other exceptions"""
    # Log the full traceback
    exc_traceback = "".join(traceback.format_exception(*sys.exc_info()))
    logger.error(f"Unhandled exception: {exc}\n{exc_traceback}")
    
    # Return safe error message
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "type": type(exc).__name__
        }
    )


def setup_error_handlers(app):
    """Setup all error handlers for the app"""
    from fastapi import FastAPI
    app.add_exception_handler(TradingSystemError, trading_system_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

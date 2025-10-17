"""
ATS-Friendly CV Builder API
Main application entry point using FastAPI
"""

import time
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import structlog

from app.config.settings import settings
from app.config.logging import configure_logging

# Configure structured logging
configure_logging()
logger = structlog.get_logger()

# Global state
startup_time: Optional[datetime] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events"""
    global startup_time

    # Startup
    logger.info("Starting ATS CV Builder API", version=settings.VERSION)
    startup_time = datetime.utcnow()

    # Initialize database connections, cache, etc.
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down ATS CV Builder API")

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Custom middleware for request logging and timing
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests with timing information"""
    start_time = time.time()

    # Log request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown"
    )

    try:
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=f"{process_time:.3f}s"
        )

        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)

        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            "Request failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            process_time=f"{process_time:.3f}s"
        )
        raise

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"

    return response

# API Key validation middleware for AI services
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Validate API keys for protected endpoints"""
    # Define paths that require API key validation
    protected_paths = ["/api/v1/ai/", "/api/v1/analytics/"]

    if any(request.url.path.startswith(path) for path in protected_paths):
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

        if not api_key or api_key != settings.OPENAI_API_KEY:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key"
            )

    return await call_next(request)

# Import routes after middleware setup to avoid circular imports
from app.routes import router

# Include API routes
app.include_router(router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global startup_time
    uptime = "unknown"
    if startup_time:
        uptime = str(datetime.utcnow() - startup_time)

    return {
        "status": "healthy",
        "version": settings.VERSION,
        "uptime": uptime,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ATS-Friendly CV Builder API",
        "docs": "/docs",
        "version": settings.VERSION,
        "health": "/health"
    }

@app.get("/api/v1/info")
async def api_info():
    """Get comprehensive API information"""
    global startup_time
    uptime = "unknown"
    if startup_time:
        uptime = str(datetime.utcnow() - startup_time)

    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "uptime": uptime,
        "start_time": startup_time.isoformat() if startup_time else None,
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": f"{settings.API_V1_STR}/openapi.json",
            "health": "/health",
            "info": "/api/v1/info"
        },
        "features": [
            "AI-powered CV analysis",
            "ATS-friendly CV generation",
            "Multiple CV templates",
            "PDF export",
            "Cloud storage integration"
        ]
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
"""
AI Fusion Core - API Gateway Service
Main application entry point for the microservices-based AI platform
"""

import time
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncio
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import structlog
import grpc
import httpx

from app.config.settings import settings
from app.config.logging import configure_logging

# Configure structured logging
configure_logging()
logger = structlog.get_logger()

# Enums and Data Classes for better type safety
class ServiceStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DISCONNECTED = "disconnected"
    STARTING = "starting"

@dataclass
class ServiceInfo:
    name: str
    host: str
    grpc_port: int
    http_port: int
    status: ServiceStatus = ServiceStatus.DISCONNECTED
    last_health_check: Optional[datetime] = None
    health_check_failures: int = 0

@dataclass
class ServiceResponse:
    service_name: str
    status_code: int
    response_data: Any
    response_time: float
    error: Optional[str] = None

# Global state
startup_time: Optional[datetime] = None
grpc_channels: Dict[str, grpc.aio.Channel] = {}
http_clients: Dict[str, httpx.AsyncClient] = {}
service_registry: Dict[str, ServiceInfo] = {}

# Service discovery configuration - now using environment-based configuration
def get_service_config() -> Dict[str, Dict[str, Any]]:
    """Get service configuration from environment variables or defaults"""
    base_host = settings.HOST
    services = {}

    # Define service configurations with environment variable support
    service_configs = {
        "ai-kernel": {"grpc_port": 50051, "http_port": 8001, "required": True},
        "identity": {"grpc_port": 50052, "http_port": 8002, "required": True},
        "cv-engine": {"grpc_port": 50053, "http_port": 8003, "required": True},
        "conversational": {"grpc_port": 50054, "http_port": 8004, "required": False},
        "analytics": {"grpc_port": 50055, "http_port": 8005, "required": False},
        "automation": {"grpc_port": 50056, "http_port": 8006, "required": False},
        "vision": {"grpc_port": 50057, "http_port": 8007, "required": False},
        "plugin": {"grpc_port": 50058, "http_port": 8008, "required": False},
    }

    for service_name, config in service_configs.items():
        # Allow override via environment variables
        host = os.getenv(f"{service_name.upper()}_HOST", base_host)
        grpc_port = int(os.getenv(f"{service_name.upper()}_GRPC_PORT", config["grpc_port"]))
        http_port = int(os.getenv(f"{service_name.upper()}_HTTP_PORT", config["http_port"]))

        services[service_name] = {
            "host": host,
            "grpc_port": grpc_port,
            "http_port": http_port,
            "required": config["required"]
        }

    return services

# Import os for environment variable access
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events"""
    global startup_time, grpc_channels, http_clients

    # Startup
    logger.info("Starting AI Fusion Core API Gateway", version=settings.VERSION)
    startup_time = datetime.utcnow()

    # Initialize service connections
    await initialize_service_connections()
    logger.info("Service connections initialized")

    # Health check all services
    await health_check_services()
    logger.info("All services healthy")

    # Start background tasks
    if settings.API_RATE_LIMIT_ENABLED:
        asyncio.create_task(cleanup_rate_limiter())
        logger.info("Rate limiter cleanup task started")

    yield

    # Shutdown
    logger.info("Shutting down AI Fusion Core API Gateway")

    # Close gRPC channels
    for service_name, channel in grpc_channels.items():
        logger.info(f"Closing gRPC channel for {service_name}")
        await channel.close()

    # Close HTTP clients
    for service_name, client in http_clients.items():
        logger.info(f"Closing HTTP client for {service_name}")
        await client.aclose()

async def initialize_service_connections():
    """Initialize connections to all microservices"""
    global grpc_channels, http_clients, service_registry

    services_config = get_service_config()

    for service_name, config in services_config.items():
        try:
            # Create service info object
            service_info = ServiceInfo(
                name=service_name,
                host=config["host"],
                grpc_port=config["grpc_port"],
                http_port=config["http_port"],
                status=ServiceStatus.STARTING
            )
            service_registry[service_name] = service_info

            # Initialize gRPC channel with better error handling
            channel = grpc.aio.insecure_channel(
                f"{config['host']}:{config['grpc_port']}",
                options=[
                    ('grpc.keepalive_time_ms', 30000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.keepalive_permit_without_calls', True),
                    ('grpc.http2.max_pings_without_data', 0),
                ]
            )
            grpc_channels[service_name] = channel

            # Initialize HTTP client for REST fallback with circuit breaker pattern
            client = httpx.AsyncClient(
                base_url=f"http://{config['host']}:{config['http_port']}",
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
            http_clients[service_name] = client

            logger.info(f"Initialized connection to {service_name}",
                       host=config['host'],
                       grpc_port=config['grpc_port'],
                       http_port=config['http_port'])

        except Exception as e:
            logger.error(f"Failed to connect to {service_name}", error=str(e))
            if config.get("required", False):
                raise

async def health_check_services() -> bool:
    """Health check all microservices with circuit breaker pattern"""
    global service_registry

    services_config = get_service_config()
    all_healthy = True

    for service_name, config in services_config.items():
        if service_name not in service_registry:
            logger.warning(f"Service {service_name} not in registry")
            continue

        service_info = service_registry[service_name]
        max_failures = 3

        try:
            # Check gRPC channel readiness
            if service_name in grpc_channels:
                await asyncio.wait_for(
                    grpc_channels[service_name].channel_ready(),
                    timeout=5.0
                )

            # Perform HTTP health check
            if service_name in http_clients:
                start_time = time.time()
                response = await http_clients[service_name].get("/health", timeout=5.0)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    service_info.status = ServiceStatus.HEALTHY
                    service_info.last_health_check = datetime.utcnow()
                    service_info.health_check_failures = 0

                    logger.info(f"Service {service_name} is healthy",
                               response_time=f"{response_time:.3f}s")
                else:
                    raise HTTPException(status_code=response.status_code, detail="Health check failed")

        except asyncio.TimeoutError:
            error_msg = f"Health check timeout for {service_name}"
            logger.error(error_msg)
            await handle_service_health_failure(service_info, error_msg, max_failures)
            all_healthy = False

        except Exception as e:
            error_msg = f"Health check failed for {service_name}: {str(e)}"
            logger.error(error_msg)
            await handle_service_health_failure(service_info, error_msg, max_failures)
            all_healthy = False

    return all_healthy

async def handle_service_health_failure(service_info: ServiceInfo, error: str, max_failures: int):
    """Handle service health check failure with circuit breaker logic"""
    service_info.health_check_failures += 1
    service_info.last_health_check = datetime.utcnow()

    if service_info.health_check_failures >= max_failures:
        service_info.status = ServiceStatus.UNHEALTHY
        logger.error(f"Service {service_info.name} marked as unhealthy after {service_info.health_check_failures} failures")
    else:
        service_info.status = ServiceStatus.DISCONNECTED
        logger.warning(f"Service {service_info.name} health check failed ({service_info.health_check_failures}/{max_failures})")

# Create FastAPI application
app = FastAPI(
    title="AI Fusion Core API Gateway",
    description="Microservices-based AI platform for ATS-friendly CV building and advanced AI capabilities",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount static files and templates for backward compatibility
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

# Set up rate limiting middleware
if settings.API_RATE_LIMIT_ENABLED:
    app.add_middleware(SlowAPIMiddleware, limiter=limiter)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Enhanced middleware for request logging and timing
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests with timing information"""
    start_time = time.time()

    # Log request
    logger.info(
        "Gateway request started",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown")
    )

    try:
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response
        logger.info(
            "Gateway request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=f"{process_time:.3f}s"
        )

        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Service-Name"] = "api-gateway"

        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            "Gateway request failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            process_time=f"{process_time:.3f}s"
        )
        raise

# Enhanced security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add comprehensive security headers to all responses"""
    response = await call_next(request)

    if settings.SECURITY_HEADERS_ENABLED:
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS header (only for HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains; preload"

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Additional security headers
        response.headers["X-DNS-Prefetch-Control"] = "off"
        response.headers["Expect-CT"] = f"max-age={settings.HSTS_MAX_AGE}, enforce"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    return response

# Service routing middleware
@app.middleware("http")
async def service_routing_middleware(request: Request, call_next):
    """Route requests to appropriate microservices"""
    # Define service routing rules
    path = request.url.path

    # Route to specific services based on path
    if path.startswith("/api/v1/ai/") or path.startswith("/api/v2/ai/"):
        # Route to AI Kernel service
        return await route_to_service(request, call_next, "ai-kernel")
    elif path.startswith("/api/v1/auth/") or path.startswith("/api/v1/users/"):
        # Route to Identity service
        return await route_to_service(request, call_next, "identity")
    elif path.startswith("/api/v1/cv/") or path.startswith("/api/v2/cv/"):
        # Route to CV Engine service
        return await route_to_service(request, call_next, "cv-engine")
    elif path.startswith("/api/v1/analytics/") or path.startswith("/api/v2/analytics/"):
        # Route to Analytics service
        return await route_to_service(request, call_next, "analytics")
    else:
        # Handle locally or return 404
        return await call_next(request)

async def route_to_service(request: Request, call_next, service_name: str) -> JSONResponse:
    """Route request to specific microservice with proper error handling"""
    global service_registry

    # Check if service is available
    if service_name not in service_registry:
        logger.error(f"Service {service_name} not found in registry")
        return JSONResponse(
            status_code=404,
            content={"detail": f"Service {service_name} not found"}
        )

    service_info = service_registry[service_name]

    # Check if service is healthy
    if service_info.status != ServiceStatus.HEALTHY:
        logger.error(f"Service {service_name} is not healthy (status: {service_info.status})")
        return JSONResponse(
            status_code=503,
            content={"detail": f"Service {service_name} is not available"}
        )

    try:
        # Get the request body if present
        body = await request.body()

        # Route based on service type and endpoint
        if service_name == "ai-kernel":
            return await route_to_ai_kernel(request, body)
        elif service_name == "identity":
            return await route_to_identity_service(request, body)
        elif service_name == "cv-engine":
            return await route_to_cv_engine(request, body)
        elif service_name == "analytics":
            return await route_to_analytics_service(request, body)
        else:
            # Generic routing for other services
            return await route_to_generic_service(request, service_name, body)

    except Exception as e:
        logger.error(f"Error routing to service {service_name}", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error communicating with {service_name}"}
        )

async def route_to_ai_kernel(request: Request, body: bytes) -> JSONResponse:
    """Route AI requests to AI Kernel service"""
    try:
        # Use HTTP client to forward request
        client = http_clients["ai-kernel"]
        path = request.url.path.replace("/api/v1/ai/", "").replace("/api/v2/ai/", "")

        # Reconstruct the request to AI Kernel service
        response = await client.post(f"/api/v2/ai/{path}", content=body)

        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else {},
            headers=dict(response.headers)
        )

    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"detail": "AI Kernel service timeout"}
        )
    except Exception as e:
        logger.error(f"Error communicating with AI Kernel", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": "AI Kernel service error"}
        )

async def route_to_identity_service(request: Request, body: bytes) -> JSONResponse:
    """Route identity/auth requests to Identity service"""
    try:
        client = http_clients["identity"]
        path = request.url.path.replace("/api/v1/auth/", "").replace("/api/v1/users/", "")

        # Handle different endpoints
        if request.url.path.startswith("/api/v1/auth/"):
            if request.method == "POST" and "login" in request.url.path:
                response = await client.post("/api/v1/auth/login", content=body)
            elif request.method == "POST" and "register" in request.url.path:
                response = await client.post("/api/v1/auth/register", content=body)
            else:
                response = await client.request(
                    method=request.method,
                    url=f"/api/v1/auth/{path}",
                    content=body
                )
        else:
            response = await client.request(
                method=request.method,
                url=f"/api/v1/users/{path}",
                content=body
            )

        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else {},
            headers=dict(response.headers)
        )

    except Exception as e:
        logger.error(f"Error communicating with Identity service", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": "Identity service error"}
        )

async def route_to_cv_engine(request: Request, body: bytes) -> JSONResponse:
    """Route CV requests to CV Engine service"""
    try:
        client = http_clients["cv-engine"]
        path = request.url.path.replace("/api/v1/cv/", "").replace("/api/v2/cv/", "")

        response = await client.request(
            method=request.method,
            url=f"/api/v1/cv/{path}",
            content=body
        )

        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else {},
            headers=dict(response.headers)
        )

    except Exception as e:
        logger.error(f"Error communicating with CV Engine", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": "CV Engine service error"}
        )

async def route_to_analytics_service(request: Request, body: bytes) -> JSONResponse:
    """Route analytics requests to Analytics service"""
    try:
        client = http_clients["analytics"]
        path = request.url.path.replace("/api/v1/analytics/", "").replace("/api/v2/analytics/", "")

        response = await client.request(
            method=request.method,
            url=f"/api/v1/analytics/{path}",
            content=body
        )

        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else {},
            headers=dict(response.headers)
        )

    except Exception as e:
        logger.error(f"Error communicating with Analytics service", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": "Analytics service error"}
        )

async def route_to_generic_service(request: Request, service_name: str, body: bytes) -> JSONResponse:
    """Generic routing for services without specific handlers"""
    try:
        client = http_clients[service_name]

        # Extract path after service-specific prefix
        path = request.url.path
        if f"/api/v1/{service_name}" in path:
            path = path.replace(f"/api/v1/{service_name}/", "")
        elif f"/api/v2/{service_name}" in path:
            path = path.replace(f"/api/v2/{service_name}/", "")

        response = await client.request(
            method=request.method,
            url=f"/api/v1/{path}",
            content=body
        )

        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.content else {},
            headers=dict(response.headers)
        )

    except Exception as e:
        logger.error(f"Error communicating with {service_name}", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"detail": f"{service_name} service error"}
        )

# Import routes after middleware setup to avoid circular imports
from app.routes import router
from app.routes.auth import router as auth_router

# Import GraphQL schema and utilities
from app.utils.graphql_schema import schema, get_graphql_context
from app.utils.rate_limit import rate_limiter, cleanup_rate_limiter, rate_limit_exceeded_handler
from app.utils.auth_utils import get_current_active_user

# Import new dependencies
import strawberry
from strawberry.fastapi import GraphQLRouter
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Create GraphQL router with authentication context
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
    graphiql=settings.DEBUG,  # Enable GraphiQL in development
    allow_queries_via_get=True
)

# Include API routes
app.include_router(router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["authentication"])

# Include GraphQL endpoint
app.include_router(
    graphql_app,
    prefix=f"{settings.API_V1_STR}/graphql",
    tags=["graphql"]
)

# Add v2 API routes for GraphQL
app.include_router(
    graphql_app,
    prefix=f"{settings.API_V2_STR}/graphql",
    tags=["graphql-v2"]
)

# Add service registry endpoints for monitoring and debugging
@app.get("/api/v2/services/registry")
async def get_service_registry():
    """Get detailed service registry information"""
    services_config = get_service_config()
    registry_info = {}

    for service_name, config in services_config.items():
        if service_name in service_registry:
            service_info = service_registry[service_name]
            registry_info[service_name] = {
                "name": service_info.name,
                "host": service_info.host,
                "grpc_port": service_info.grpc_port,
                "http_port": service_info.http_port,
                "status": service_info.status.value,
                "last_health_check": service_info.last_health_check.isoformat() if service_info.last_health_check else None,
                "health_check_failures": service_info.health_check_failures,
                "grpc_connected": service_name in grpc_channels,
                "http_connected": service_name in http_clients,
                "required": config.get("required", False)
            }
        else:
            registry_info[service_name] = {
                "name": service_name,
                "status": "not_initialized",
                "grpc_connected": False,
                "http_connected": False,
                "required": config.get("required", False)
            }

    return {
        "total_services": len(registry_info),
        "healthy_services": sum(1 for s in registry_info.values() if s.get("status") == "healthy"),
        "unhealthy_services": sum(1 for s in registry_info.values() if s.get("status") == "unhealthy"),
        "services": registry_info
    }

@app.post("/api/v2/services/{service_name}/health-check")
async def manual_health_check(service_name: str):
    """Manually trigger health check for a specific service"""
    if service_name not in service_registry:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    # Perform health check for specific service
    service_info = service_registry[service_name]
    max_failures = 3

    try:
        # Check gRPC channel
        if service_name in grpc_channels:
            await asyncio.wait_for(
                grpc_channels[service_name].channel_ready(),
                timeout=5.0
            )

        # Check HTTP endpoint
        if service_name in http_clients:
            response = await http_clients[service_name].get("/health", timeout=5.0)
            if response.status_code == 200:
                service_info.status = ServiceStatus.HEALTHY
                service_info.last_health_check = datetime.utcnow()
                service_info.health_check_failures = 0
            else:
                raise HTTPException(status_code=response.status_code)

        return {
            "service": service_name,
            "status": service_info.status.value,
            "message": f"Health check completed for {service_name}"
        }

    except Exception as e:
        await handle_service_health_failure(service_info, str(e), max_failures)
        return {
            "service": service_name,
            "status": service_info.status.value,
            "message": f"Health check failed for {service_name}: {str(e)}"
        }

# Gateway-specific endpoints
@app.get("/health")
async def gateway_health_check():
    """Enhanced health check endpoint for API Gateway"""
    global startup_time
    uptime = "unknown"
    if startup_time:
        uptime = str(datetime.utcnow() - startup_time)

    # Check service health using service registry
    service_status = {}
    services_config = get_service_config()

    for service_name, config in services_config.items():
        if service_name in service_registry:
            service_info = service_registry[service_name]
            service_status[service_name] = {
                "status": service_info.status.value,
                "host": service_info.host,
                "grpc_port": service_info.grpc_port,
                "http_port": service_info.http_port,
                "last_health_check": service_info.last_health_check.isoformat() if service_info.last_health_check else None,
                "health_check_failures": service_info.health_check_failures,
                "required": config.get("required", False)
            }
        else:
            service_status[service_name] = {
                "status": "not_initialized",
                "host": config["host"],
                "grpc_port": config["grpc_port"],
                "http_port": config["http_port"],
                "required": config.get("required", False)
            }

    return {
        "status": "healthy",
        "service": "api-gateway",
        "version": settings.VERSION,
        "uptime": uptime,
        "timestamp": datetime.utcnow().isoformat(),
        "services": service_status
    }

@app.get("/")
async def root():
    """Root endpoint with AI Fusion Core branding"""
    return {
        "message": "AI Fusion Core API Gateway",
        "description": "Microservices-based AI platform for ATS-friendly CV building and advanced AI capabilities",
        "docs": "/docs",
        "version": settings.VERSION,
        "health": "/health",
        "services": list(SERVICES.keys())
    }

@app.get("/api/v1/info")
async def api_info():
    """Get comprehensive API information"""
    global startup_time
    uptime = "unknown"
    if startup_time:
        uptime = str(datetime.utcnow() - startup_time)

    return {
        "name": "AI Fusion Core",
        "version": settings.VERSION,
        "description": "Microservices-based AI platform",
        "uptime": uptime,
        "start_time": startup_time.isoformat() if startup_time else None,
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": f"{settings.API_V1_STR}/openapi.json",
            "health": "/health",
            "info": "/api/v1/info"
        },
        "microservices": {
            name: {
                "host": config["host"],
                "grpc_port": config["grpc_port"],
                "http_port": config["http_port"],
                "status": service_registry.get(name, ServiceInfo(name, "", 0, 0)).status.value if name in service_registry else "not_initialized",
                "required": config.get("required", False)
            }
            for name, config in get_service_config().items()
        },
        "features": [
            "AI-powered CV analysis",
            "ATS-friendly CV generation",
            "Multiple CV templates",
            "PDF export",
            "Cloud storage integration",
            "Multi-agent AI orchestration",
            "Vector memory storage",
            "Real-time AI inference",
            "Plugin ecosystem",
            "Computer vision AI",
            "Dual REST + GraphQL API",
            "JWT authentication with refresh tokens",
            "OAuth2 integration (Google, GitHub)",
            "Role-based access control (RBAC)",
            "API rate limiting and security",
            "Comprehensive API documentation"
        ],
        "authentication": {
            "jwt": {
                "enabled": True,
                "access_token_expiry": f"{settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes",
                "refresh_token_expiry": f"{settings.REFRESH_TOKEN_EXPIRE_DAYS} days",
                "algorithm": settings.JWT_ALGORITHM
            },
            "oauth2": {
                "providers": ["google", "github"],
                "enabled": bool(settings.GOOGLE_CLIENT_ID or settings.GITHUB_CLIENT_ID)
            },
            "rbac": {
                "roles": ["guest", "user", "admin", "superuser"],
                "enabled": True
            }
        },
        "api": {
            "rest": {
                "base_url": settings.API_V1_STR,
                "enabled": True
            },
            "graphql": {
                "endpoints": [
                    f"{settings.API_V1_STR}/graphql",
                    f"{settings.API_V2_STR}/graphql"
                ],
                "enabled": settings.GRAPHQL_ENABLED,
                "graphiql": settings.DEBUG
            },
            "rate_limiting": {
                "enabled": settings.API_RATE_LIMIT_ENABLED,
                "requests_per_minute": settings.RATE_LIMIT_REQUESTS_PER_MINUTE
            }
        }
    }

# New v2 API endpoints for AI Fusion Core
@app.get("/api/v2/info")
async def api_v2_info():
    """Get AI Fusion Core v2 API information"""
    return {
        "name": "AI Fusion Core v2",
        "version": settings.VERSION,
        "architecture": "Microservices",
        "ai_engine": "Multi-agent orchestration with LangChain + AutoGen",
        "vector_storage": "Pinecone/Weaviate integration",
        "communication": "gRPC + REST",
        "services": list(SERVICES.keys()),
        "features": [
            "Dynamic AI Kernel",
            "Conversational AI Copilot",
            "Enhanced CV Engine",
            "Analytics Brain",
            "Automation Intelligence",
            "Computer Vision AI",
            "Plugin Framework"
        ]
    }

@app.get("/api/v2/services")
async def list_services():
    """List all available microservices"""
    services_config = get_service_config()
    return {
        "services": {
            name: {
                "description": get_service_description(name),
                "host": config["host"],
                "grpc_port": config["grpc_port"],
                "http_port": config["http_port"],
                "status": service_registry.get(name, ServiceInfo(name, "", 0, 0)).status.value if name in service_registry else "not_initialized",
                "required": config.get("required", False)
            }
            for name, config in services_config.items()
        }
    }

def get_service_description(service_name: str) -> str:
    """Get description for a service"""
    descriptions = {
        "ai-kernel": "Central AI orchestration and reasoning engine",
        "identity": "Authentication and user management",
        "cv-engine": "Extended CV and portfolio generation",
        "conversational": "AI Copilot and chat functionality",
        "analytics": "Data processing and insights",
        "automation": "Workflow and network automation",
        "vision": "Computer vision and media processing",
        "plugin": "Plugin management and extensibility"
    }
    return descriptions.get(service_name, "AI Fusion Core microservice")

# Exception handlers
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
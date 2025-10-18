# Docker Compose Orchestration Guide

This guide explains how to use the Docker Compose setup for local development and testing of the AI Fusion Core platform.

## Overview

The Docker Compose configuration provides:

- **Multi-environment support**: Development, Testing, and Production profiles
- **Service Mesh integration**: Full Linkerd service mesh with mTLS, observability, and reliability features
- **Comprehensive monitoring**: Prometheus, Grafana, Jaeger for metrics, visualization, and tracing
- **Database cluster**: PostgreSQL with Patroni, Redis Cluster, MongoDB Replica Set, Qdrant vector database
- **All microservices**: API Gateway, AI Kernel, Identity, CV Engine, Conversational, Analytics, Automation, Vision, and Plugin services

## Quick Start

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Git** for cloning repositories
3. **Environment variables** configured (see Environment Setup)

### Environment Setup

1. **Copy environment file**:
   ```bash
   cp .env.development .env
   ```

2. **Configure your API keys** in `.env`:
   ```bash
   OPENAI_API_KEY=your-openai-api-key-here
   PINECONE_API_KEY=your-pinecone-api-key-here
   SECRET_KEY=your-secret-key-here
   ```

## Development Workflow

### Start Development Environment

```bash
# Start all services with development profile
docker-compose --profile development up

# Or start specific services only
docker-compose --profile development up api-gateway ai-kernel postgres-dev redis-dev

# Start in background
docker-compose --profile development up -d

# View logs
docker-compose --profile development logs -f api-gateway

# Stop services
docker-compose --profile development down
```

### Development Profiles

The following profiles are available:

- **`development`**: Full development environment with hot reload, debug logging, and development tools
- **`testing`**: Isolated testing environment with separate databases
- **`production`**: Production-like environment with optimized settings
- **`monitoring`**: Monitoring stack only (Prometheus, Grafana, Jaeger)

### Service-Specific Development

Each service can be developed independently:

```bash
# Develop only API Gateway
docker-compose --profile development up api-gateway

# Develop AI Kernel service
docker-compose --profile development up ai-kernel

# Develop with file watching
docker-compose --profile development up -f docker-compose.yml -f docker-compose.override.yml
```

## Testing

### Run Tests

```bash
# Run all tests
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test-runner

# Run specific service tests
docker-compose -f docker-compose.yml -f docker-compose.test.yml run --rm test-runner python -m pytest services/ai-kernel-service/tests/

# Run integration tests
docker-compose --profile testing up api-gateway-test ai-kernel-test postgres-test redis-test
```

### Testing Profiles

- **`testing`**: Run tests against isolated test databases
- **`integration`**: Run integration tests with all services

## Production Deployment

```bash
# Start production environment
docker-compose --profile production up -d

# Start with monitoring
docker-compose --profile production --profile monitoring up -d

# Scale services
docker-compose --profile production up -d --scale api-gateway=3 --scale ai-kernel=2
```

## Service Architecture

### Core Services

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| API Gateway | 8000 | HTTP/gRPC | Main entry point and request routing |
| AI Kernel | 8001/50051 | HTTP/gRPC | Core AI processing and reasoning |
| Identity | 8002/50052 | HTTP/gRPC | Authentication and authorization |
| CV Engine | 8003/50053 | HTTP/gRPC | CV/Resume processing |
| Conversational | 8004/50054 | HTTP/gRPC | Chat and conversational AI |
| Analytics | 8005/50055 | HTTP/gRPC | Analytics and reporting |
| Automation | 8006/50056 | HTTP/gRPC | Workflow automation |
| Vision | 8007/50057 | HTTP/gRPC | Computer vision tasks |
| Plugin | 8008/50058 | HTTP/gRPC | Plugin system |

### Infrastructure Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL Cluster | 5432 | Primary database with Patroni HA |
| PgBouncer | 6432 | Connection pooling |
| Redis Cluster | 6379 | Caching and session storage |
| MongoDB Router | 27017 | Document database |
| Qdrant | 6333/6334 | Vector database |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Visualization dashboard |
| Jaeger | 16686 | Distributed tracing |
| Linkerd Dashboard | 8085 | Service mesh dashboard |

## Database Management

### PostgreSQL

```bash
# Connect to development database
docker-compose --profile development exec postgres-dev psql -U postgres -d ai_fusion_core_dev

# Connect to test database
docker-compose -f docker-compose.test.yml exec postgres-test psql -U postgres -d ai_fusion_core_test

# Backup database
docker-compose --profile development exec postgres-dev pg_dump -U postgres ai_fusion_core_dev > backup.sql
```

### Redis

```bash
# Connect to development Redis
docker-compose --profile development exec redis-dev redis-cli

# Connect to test Redis
docker-compose -f docker-compose.test.yml exec redis-test redis-cli
```

### MongoDB

```bash
# Connect to MongoDB
docker-compose exec mongodb-router mongosh

# Check replica set status
docker-compose exec mongodb-router mongosh --eval "rs.status()"
```

## Monitoring and Observability

### Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686
- **Prometheus**: http://localhost:9090
- **Linkerd Dashboard**: http://localhost:8085

### View Service Metrics

```bash
# Check service health
curl http://localhost:8000/health
curl http://localhost:8001/health

# View Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up

# Check Linkerd service mesh
curl http://localhost:8085/api/v1/stat
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Use different ports for development
   ```bash
   API_GATEWAY_PORT=8001 docker-compose --profile development up
   ```

2. **Database connection issues**: Wait for services to be healthy
   ```bash
   docker-compose --profile development ps
   ```

3. **Service mesh issues**: Check Linkerd status
   ```bash
   curl http://localhost:8085/api/v1/version
   ```

4. **Memory issues**: Reduce service count for development
   ```bash
   docker-compose --profile development up api-gateway ai-kernel postgres-dev
   ```

### Logs and Debugging

```bash
# View all logs
docker-compose --profile development logs -f

# View specific service logs
docker-compose --profile development logs -f api-gateway

# View last 100 lines
docker-compose --profile development logs --tail=100 api-gateway

# Debug service
docker-compose --profile development exec api-gateway bash
```

## Performance Optimization

### Development Optimizations

- Use `docker-compose.override.yml` for development-specific settings
- Enable hot reload for faster development cycles
- Use separate databases for development and testing
- Run only required services during development

### Production Optimizations

- Use production profile for optimized settings
- Enable monitoring for performance insights
- Configure proper resource limits
- Use health checks for service reliability

## Security Considerations

- Change default passwords in production
- Use proper secret management
- Configure TLS/SSL certificates
- Set up proper firewall rules
- Regular security updates

## Contributing

When adding new services:

1. Add service definition to `docker-compose.yml`
2. Create development overrides in `docker-compose.override.yml`
3. Add testing configuration to `docker-compose.test.yml`
4. Update environment variables in `.env.development`
5. Document the service in this README

## Support

For issues and questions:

1. Check the logs: `docker-compose logs`
2. Verify service health: `docker-compose ps`
3. Check network connectivity: `docker-compose exec service ping other-service`
4. Review configuration files for errors
5. Consult service-specific documentation
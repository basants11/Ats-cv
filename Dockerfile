# Multi-stage Dockerfile for AI Fusion Core API Gateway

# Base stage with Python
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM base as production

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Development stage
FROM base as development

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest==7.4.4 \
    pytest-asyncio==0.21.1 \
    black==23.12.1 \
    flake8==6.1.0 \
    mypy==1.8.0

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose ports
EXPOSE 8000

# Run the application in development mode
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
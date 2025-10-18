# AI Fusion Core Database Cluster Configuration

## Overview

This document describes the comprehensive database cluster configuration implemented for the AI Fusion Core system, providing persistent storage, caching, and vector operations with high availability, monitoring, and backup capabilities.

## Architecture Overview

The database layer consists of three main clusters:

1. **PostgreSQL Cluster** - Primary relational database for users, CVs, and sessions
2. **Redis Cluster** - High-performance caching and session management
3. **MongoDB Cluster** - Flexible document storage for AI features and analytics

## PostgreSQL Cluster Configuration

### Cluster Setup
- **3-node PostgreSQL cluster** using Patroni for automated failover and management
- **etcd** for cluster coordination and service discovery
- **PgBouncer** for connection pooling and load balancing
- **Automated backups** with daily, weekly, and monthly schedules

### Components

#### PostgreSQL Nodes (postgres01, postgres02, postgres03)
- **Image**: postgres:15-alpine
- **Replication**: Streaming replication with automatic failover
- **Configuration**:
  - WAL level: replica
  - Hot standby: enabled
  - Max connections: 1000 per node
  - Shared buffers: 256MB per node

#### Patroni Management (patroni01, patroni02, patroni03)
- **Image**: patroni/patroni:latest
- **Role**: Automated cluster management and failover
- **REST API**: Available on port 8008 for monitoring and control
- **Features**:
  - Automatic leader election
  - Failover management
  - Configuration management

#### etcd Cluster Coordination
- **Image**: bitnami/etcd:latest
- **Role**: Distributed configuration store for cluster state
- **Endpoints**: etcd:2379 (client), etcd:2380 (peer)

#### PgBouncer Connection Pooling
- **Image**: pgbouncer/pgbouncer:latest
- **Port**: 6432
- **Configuration**:
  - Pool mode: transaction
  - Max client connections: 1000
  - Default pool size: 25
  - Max DB connections per pool: 50

### Database Schema
```sql
-- Users table for authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    username VARCHAR UNIQUE NOT NULL,
    full_name VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- CVs table for CV management
CREATE TABLE cvs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR NOT NULL DEFAULT 'My CV',
    full_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    phone VARCHAR,
    location VARCHAR,
    summary TEXT,
    skills JSONB,
    template VARCHAR DEFAULT 'modern',
    is_public BOOLEAN DEFAULT false,
    ats_score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- CV sections for flexible structure
CREATE TABLE cv_sections (
    id SERIAL PRIMARY KEY,
    cv_id INTEGER REFERENCES cvs(id),
    section_type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    subtitle VARCHAR,
    start_date VARCHAR,
    end_date VARCHAR,
    location VARCHAR,
    description TEXT,
    order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Redis Cluster Configuration

### Cluster Setup
- **6-node Redis cluster** (3 masters, 3 replicas) for high availability
- **Automatic failover** and data partitioning
- **AOF (Append-Only File)** enabled for data persistence
- **Cluster bus** for node communication

### Components

#### Redis Nodes (redis01-redis06)
- **Image**: redis:7-alpine
- **Configuration**:
  - Cluster enabled
  - AOF persistence
  - Node timeout: 5000ms
  - Cluster bus port: 16379

#### Redis Cluster Manager
- **Role**: Automated cluster setup and configuration
- **Script**: `redis/setup-cluster.sh`

### Usage Patterns
```bash
# Connect to Redis cluster
redis-cli -c -h redis-cluster-proxy -p 6379

# Cluster information
CLUSTER NODES
CLUSTER INFO
CLUSTER SLOTS
```

## MongoDB Cluster Configuration

### Cluster Setup
- **3-node replica set** (rs0) for high availability
- **mongos router** for load balancing and sharding
- **Oplog** for replication tracking
- **Automated initialization** script

### Components

#### MongoDB Nodes (mongodb01, mongodb02, mongodb03)
- **Image**: mongo:7-jammy
- **Replica Set**: rs0
- **Priority**: Node 1 (priority: 3), Node 2 (priority: 2), Node 3 (priority: 1)

#### MongoDB Router (mongodb-router)
- **Image**: mongo:7-jammy
- **Role**: Query routing and load balancing
- **Port**: 27017

#### MongoDB Setup Service
- **Script**: `mongodb/setup-replica-set.js`
- **Role**: Automated replica set initialization and database setup

### Collections and Indexes
```javascript
// Documents collection
db.createCollection('documents');
db.documents.createIndex({ "user_id": 1 });
db.documents.createIndex({ "created_at": -1 });
db.documents.createIndex({ "type": 1 });

// Vectors collection for AI embeddings
db.createCollection('vectors');
db.vectors.createIndex({ "vector": "2dsphere" });
db.vectors.createIndex({ "metadata.user_id": 1 });

// Analytics collection
db.createCollection('analytics');
db.analytics.createIndex({ "timestamp": -1 });
db.analytics.createIndex({ "event_type": 1 });

// Cache collection with TTL
db.createCollection('cache');
db.cache.createIndex({ "key": 1 }, { unique: true });
db.cache.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 });
```

## Monitoring and Alerting

### Prometheus Exporters
- **PostgreSQL Exporter**: `postgres-exporter:9187`
- **MongoDB Exporter**: `mongodb-exporter:9216`
- **Redis Exporter**: `redis-exporter:9121`

### Alertmanager
- **Port**: 9093
- **Configuration**: `alertmanager/alertmanager.yml`
- **Email notifications** for critical alerts

### Key Alerts
- Database service availability
- High connection counts
- Replication lag
- Memory usage thresholds
- Backup failures
- Response time degradation

## Backup and Recovery

### Automated Backup Schedule
- **Daily**: 2:00 AM - Full database dumps
- **Weekly**: Sunday 3:00 AM - Archive of daily backups
- **Monthly**: 1st of month 4:00 AM - Long-term archive

### Backup Contents
- **PostgreSQL**: Custom format dumps with compression
- **MongoDB**: Complete database dumps
- **Redis**: RDB snapshot files
- **Vector DB**: Qdrant storage directory copy

### Backup Locations
```
/backups/
├── daily/     # Daily backups (7 days retention)
├── weekly/    # Weekly backups (30 days retention)
└── monthly/   # Monthly backups (365 days retention)
```

### Manual Recovery
```bash
# PostgreSQL recovery
pg_restore -h postgres01 -U postgres -d ai_fusion_core /backups/daily/postgres_backup_*.dump

# MongoDB recovery
mongorestore --host mongodb01:27017 /backups/daily/mongodb_backup_*/

# Redis recovery
redis-cli -h redis01 FLUSHALL
cat /backups/daily/redis_backup_*.rdb | redis-cli -h redis01 --pipe
```

## Security Considerations

### Network Security
- All database clusters are on isolated Docker network
- Service mesh (Linkerd) provides mTLS encryption
- No direct external access to database ports

### Authentication
- PostgreSQL: Password-based authentication
- MongoDB: Disabled for development (enable in production)
- Redis: Password protection recommended for production

### Access Control
- Application services use dedicated database users
- Read-only users for reporting services
- Admin users for maintenance operations

## Performance Optimization

### PostgreSQL Optimizations
- Shared buffers: 256MB per node
- Effective cache size: 1GB per node
- WAL buffers: 16MB
- Checkpoint completion target: 90%
- Parallel workers: 4 per node

### Redis Optimizations
- AOF persistence for durability
- Cluster pipeline optimization
- Connection pooling via cluster proxy
- Memory-based eviction policies

### MongoDB Optimizations
- Replica set for read scaling
- Router-based load distribution
- Indexed collections for query performance
- TTL indexes for cache management

## High Availability Features

### PostgreSQL HA
- 3-node cluster with automatic failover
- Patroni manages leader election
- etcd provides distributed consensus
- PgBouncer handles connection routing

### Redis HA
- 6-node cluster (3 masters + 3 replicas)
- Automatic failover on node failure
- Data partitioning across nodes
- Cluster bus for node coordination

### MongoDB HA
- 3-node replica set
- Automatic failover with priority-based election
- Oplog for consistency
- Router for load balancing

## Service Integration

### Application Connection Strings
```python
# PostgreSQL (via PgBouncer)
DATABASE_URL = "postgresql://postgres:password@pgbouncer:6432/ai_fusion_core"

# Redis (via cluster proxy)
REDIS_URL = "redis://redis-cluster-proxy:6379/0"

# MongoDB (via router)
MONGODB_URL = "mongodb://mongodb-router:27017/ai_fusion_core"
```

### Service Dependencies
All application services depend on:
- PostgreSQL cluster (via PgBouncer)
- Redis cluster (via proxy)
- MongoDB cluster (via router)

## Operational Procedures

### Starting the Clusters
```bash
# Start all services
docker-compose up -d

# Initialize MongoDB replica set (runs automatically)
# MongoDB setup service handles initialization

# Initialize Redis cluster (runs automatically)
# Redis cluster manager handles setup
```

### Monitoring Cluster Health
```bash
# PostgreSQL cluster status
curl http://patroni01:8008/cluster

# Redis cluster status
redis-cli -h redis-cluster-proxy -p 6379 CLUSTER INFO

# MongoDB replica set status
mongosh mongodb-router:27017 --eval "rs.status()"
```

### Scaling Considerations
- **PostgreSQL**: Add more read replicas via Patroni
- **Redis**: Add more nodes to cluster (must be in pairs)
- **MongoDB**: Add shards for horizontal scaling

## Troubleshooting

### Common Issues

#### PostgreSQL Cluster Issues
```bash
# Check cluster status
curl http://patroni01:8008/leader

# View cluster logs
docker-compose logs postgres01 patroni01

# Manual failover
curl -X POST http://patroni01:8008/failover
```

#### Redis Cluster Issues
```bash
# Check cluster state
redis-cli -h redis01 -p 6379 CLUSTER INFO

# View cluster nodes
redis-cli -h redis01 -p 6379 CLUSTER NODES

# Fix cluster slots
redis-cli -h redis01 -p 6379 CLUSTER FIX
```

#### MongoDB Cluster Issues
```bash
# Check replica set status
mongosh mongodb01:27017 --eval "rs.status()"

# Check router status
mongosh mongodb-router:27017 --eval "db.adminCommand('ismaster')"
```

## Production Deployment Notes

### Required Changes for Production
1. **Enable authentication** on all databases
2. **Configure SSL/TLS** encryption
3. **Set up proper firewall rules**
4. **Configure external monitoring**
5. **Set up log aggregation**
6. **Configure backup to external storage**
7. **Set up automated failover testing**

### Environment Variables
```bash
# Production database passwords
POSTGRES_PASSWORD=<strong-password>
MONGODB_ROOT_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>

# Monitoring configuration
SMTP_HOST=<smtp-server>
SMTP_USER=<email-username>
SMTP_PASSWORD=<email-password>
```

## Conclusion

This database cluster configuration provides a robust, scalable, and highly available data layer for the AI Fusion Core system. The combination of PostgreSQL, Redis, and MongoDB clusters with comprehensive monitoring, backup, and security features ensures reliable operation for AI-powered CV building and analysis workloads.

The architecture supports both the current requirements and future scaling needs, with built-in redundancy, automated failover, and performance optimization features.
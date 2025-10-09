# Production Deployment Guide

This guide covers deploying VoiceAgent SaaS to production environments.

## Pre-Deployment Checklist

- [ ] Domain name registered and DNS configured
- [ ] SSL certificate obtained (Let's Encrypt recommended)
- [ ] Google Cloud API key with production quota
- [ ] PostgreSQL database provisioned
- [ ] Redis instance provisioned
- [ ] Environment variables configured
- [ ] Backup strategy implemented
- [ ] Monitoring tools set up

## Deployment Options

### Option 1: Docker Compose (Simple)

Best for: Small to medium deployments, single server

```bash
# 1. Clone repository
git clone https://github.com/yourusername/voiceagent-saas.git
cd voiceagent-saas

# 2. Configure environment
cp .env.example .env
# Edit .env with production values

# 3. Run deployment script
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Option 2: Kubernetes (Scalable)

Best for: Large deployments, high availability

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voiceagent-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voiceagent-backend
  template:
    metadata:
      labels:
        app: voiceagent-backend
    spec:
      containers:
      - name: backend
        image: yourdockerhub/voiceagent-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: voiceagent-secrets
              key: database-url
```

### Option 3: Cloud Platform (Managed)

#### AWS Deployment

**Services Used:**
- ECS/Fargate for containers
- RDS PostgreSQL for database
- ElastiCache Redis for cache
- ALB for load balancing
- CloudFront for CDN
- S3 for storage

```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure

# Deploy using CloudFormation
aws cloudformation create-stack \
  --stack-name voiceagent-saas \
  --template-body file://aws/cloudformation.yaml \
  --parameters ParameterKey=GoogleApiKey,ParameterValue=your-key
```

#### Google Cloud Deployment

**Services Used:**
- Cloud Run for containers
- Cloud SQL for PostgreSQL
- Memorystore for Redis
- Cloud Load Balancing
- Cloud CDN

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Login and set project
gcloud auth login
gcloud config set project your-project-id

# Deploy backend
gcloud run deploy voiceagent-backend \
  --image gcr.io/your-project/voiceagent-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# Deploy frontend
gcloud run deploy voiceagent-frontend \
  --image gcr.io/your-project/voiceagent-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Environment Configuration

### Production .env

```env
# Application
SECRET_KEY=<generate-with-openssl-rand-hex-32>
DEBUG=False
APP_NAME=VoiceAgent SaaS

# Database (use managed service)
DATABASE_URL=postgresql://user:pass@db.region.rds.amazonaws.com:5432/voiceagent

# Redis (use managed service)
REDIS_URL=redis://:password@cache.region.cache.amazonaws.com:6379/0

# Google Cloud
GOOGLE_API_KEY=your-production-key

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Monitoring
SENTRY_DSN=https://...@sentry.io/...

# CORS (update with your domain)
BACKEND_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]

# Frontend
FRONTEND_API_URL=https://api.yourdomain.com
```

## SSL/TLS Configuration

### Using Let's Encrypt (Free)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (add to crontab)
0 12 * * * /usr/bin/certbot renew --quiet
```

### Nginx SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    
    # ... rest of configuration
}
```

## Database Setup

### PostgreSQL Production Settings

```sql
-- Create database
CREATE DATABASE voiceagent_db;

-- Create user with strong password
CREATE USER voiceagent WITH ENCRYPTED PASSWORD 'very-strong-password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE voiceagent_db TO voiceagent;

-- Optimize settings (adjust based on your hardware)
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET work_mem = '20MB';

-- Reload configuration
SELECT pg_reload_conf();
```

### Database Backup Strategy

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR=/backups/postgres
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME=voiceagent_db

# Create backup
pg_dump -Fc $DB_NAME > $BACKUP_DIR/backup_$DATE.dump

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.dump" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/backup_$DATE.dump s3://your-bucket/backups/
```

## Monitoring & Logging

### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'voiceagent-backend'
    static_configs:
      - targets: ['backend:8000']
```

### Grafana Dashboard

Import dashboard from `monitoring/grafana-dashboard.json`

Key metrics to monitor:
- Request latency (p50, p95, p99)
- Error rate
- Active WebSocket connections
- Database connection pool usage
- Memory and CPU usage
- Call duration average

### Centralized Logging (ELK Stack)

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: elasticsearch:8.10.0
    environment:
      - discovery.type=single-node
    volumes:
      - es_data:/usr/share/elasticsearch/data

  logstash:
    image: logstash:8.10.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline

  kibana:
    image: kibana:8.10.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## Security Hardening

### 1. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 2. Rate Limiting

Already configured in `nginx/conf.d/default.conf`:
- API: 10 requests/second per IP
- WebSocket: 5 connections/second per IP

### 3. Secret Management

Use secret management service:
- AWS Secrets Manager
- Google Cloud Secret Manager
- HashiCorp Vault
- Azure Key Vault

Example with AWS Secrets Manager:

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# In your config.py
secrets = get_secret('voiceagent-prod-secrets')
GOOGLE_API_KEY = secrets['google_api_key']
```

### 4. Database Security

- Use SSL connections
- Restrict IP access
- Regular security updates
- Strong passwords
- Principle of least privilege

## CI/CD Pipeline

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build Docker images
        run: |
          docker build -t voiceagent-backend ./backend
          docker build -t voiceagent-frontend ./frontend
      - name: Push to registry
        run: |
          docker tag voiceagent-backend ${{ secrets.DOCKER_REGISTRY }}/voiceagent-backend:latest
          docker push ${{ secrets.DOCKER_REGISTRY }}/voiceagent-backend:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          ssh ${{ secrets.PRODUCTION_SERVER }} "cd /opt/voiceagent && docker-compose pull && docker-compose up -d"
```

## Scaling Strategies

### Horizontal Scaling

1. **Multiple Backend Instances**
   ```yaml
   # docker-compose.prod.yml
   backend:
     deploy:
       replicas: 3
   ```

2. **Load Balancer**
   - Nginx (shown in configuration)
   - HAProxy
   - Cloud provider load balancer

3. **Database Read Replicas**
   ```python
   # Use read replicas for SELECT queries
   from sqlalchemy import create_engine
   
   read_engine = create_engine(READ_REPLICA_URL)
   write_engine = create_engine(MASTER_URL)
   ```

### Vertical Scaling

Increase resources for containers:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Performance Optimization

### 1. CDN for Static Assets

Configure CloudFront, Cloudflare, or similar:

```nginx
# Cache static assets
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 2. Database Query Optimization

```python
# Use connection pooling
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### 3. Redis Caching

```python
# Cache expensive queries
@cache.cached(timeout=300, key_prefix='user_stats')
def get_user_stats(user_id):
    # Expensive query
    return stats
```

## Disaster Recovery

### Backup Strategy

1. **Database**
   - Automated daily backups
   - Point-in-time recovery enabled
   - Cross-region replication

2. **Application Data**
   - S3 versioning enabled
   - Lifecycle policies for old data
   - Cross-region backup

3. **Configuration**
   - Version control (Git)
   - Infrastructure as Code
   - Secret backup

### Recovery Procedures

```bash
# Restore database from backup
pg_restore -d voiceagent_db backup_20250101.dump

# Restore from S3
aws s3 cp s3://backup-bucket/latest/ ./restore/ --recursive

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

## Maintenance

### Regular Tasks

- [ ] Weekly: Review logs and errors
- [ ] Weekly: Check disk space
- [ ] Monthly: Update dependencies
- [ ] Monthly: Review access logs
- [ ] Monthly: Backup validation
- [ ] Quarterly: Security audit
- [ ] Quarterly: Performance review

### Update Procedure

```bash
# 1. Backup
./scripts/backup.sh

# 2. Pull latest code
git pull origin main

# 3. Rebuild images
docker-compose -f docker-compose.prod.yml build

# 4. Rolling update
docker-compose -f docker-compose.prod.yml up -d --no-deps backend
docker-compose -f docker-compose.prod.yml up -d --no-deps frontend

# 5. Verify health
curl http://localhost/health
```

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   ```bash
   # Check container stats
   docker stats
   
   # Optimize database connections
   ALTER SYSTEM SET max_connections = 100;
   ```

2. **Slow Response Times**
   ```bash
   # Check database queries
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   
   # Enable query logging
   ALTER SYSTEM SET log_min_duration_statement = 1000;
   ```

3. **WebSocket Disconnections**
   ```nginx
   # Increase timeouts in nginx
   proxy_read_timeout 7d;
   proxy_send_timeout 7d;
   ```

## Support

For deployment issues:
- Email: devops@voiceagent.com
- Slack: #deployment channel
- Documentation: https://docs.voiceagent.com/deployment

## References

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Nginx Best Practices](https://nginx.org/en/docs/)
- [Docker Production Best Practices](https://docs.docker.com/develop/dev-best-practices/)


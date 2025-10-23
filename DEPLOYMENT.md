# Deployment Guide - MCP Security Gateway

This guide covers deploying the MCP Security Gateway to various platforms including cloud providers, Kubernetes, and traditional servers.

## Table of Contents

- [Quick Deploy (Docker Compose)](#quick-deploy-docker-compose)
- [Production Docker Compose](#production-docker-compose)
- [Kubernetes Deployment](#kubernetes-deployment)
- [AWS ECS Deployment](#aws-ecs-deployment)
- [Google Cloud Run](#google-cloud-run)
- [DigitalOcean App Platform](#digitalocean-app-platform)
- [Traditional Server (Systemd)](#traditional-server-systemd)
- [CI/CD Setup](#cicd-setup)
- [Monitoring & Maintenance](#monitoring--maintenance)

---

## Quick Deploy (Docker Compose)

For development and testing:

```bash
# Clone repository
git clone <your-repo>
cd mcp-security-gateway

# Copy environment file
cp .env.example .env

# Edit .env with your settings
nano .env

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f gateway

# Access at http://localhost:8000
```

---

## Production Docker Compose

For production deployments with nginx and SSL:

### 1. Prepare Environment

```bash
# Create production environment file
cp .env.example .env.production

# Edit with production values
nano .env.production
```

**Required environment variables:**
```bash
# Strong passwords (generate with: openssl rand -base64 32)
POSTGRES_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
JWT_SECRET=<64-char-secret>
DEFAULT_ADMIN_PASSWORD=<admin-password>

# Database
POSTGRES_USER=mcp_user
POSTGRES_DB=mcp_gateway

# Optional customization
LOG_LEVEL=WARNING
RATE_LIMIT_REQUESTS=1000
AUDIT_LOG_RETENTION_DAYS=90
```

### 2. Prepare SSL Certificates

```bash
# Using Let's Encrypt with Certbot
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
mkdir -p deploy/ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deploy/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem deploy/ssl/key.pem
```

### 3. Deploy

```bash
# Start production stack
docker-compose -f deploy/docker-compose.prod.yml --env-file .env.production up -d

# Verify deployment
curl https://your-domain.com/health

# Check logs
docker-compose -f deploy/docker-compose.prod.yml logs -f
```

### 4. Backup & Maintenance

```bash
# Backup database
docker-compose -f deploy/docker-compose.prod.yml exec postgres \
  pg_dump -U mcp_user mcp_gateway > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose -f deploy/docker-compose.prod.yml exec -T postgres \
  psql -U mcp_user mcp_gateway < backup_20250123.sql

# Update deployment
docker-compose -f deploy/docker-compose.prod.yml pull
docker-compose -f deploy/docker-compose.prod.yml up -d
```

---

## Kubernetes Deployment

Deploy to any Kubernetes cluster (GKE, EKS, AKS, etc.):

### 1. Create Namespace

```bash
kubectl apply -f deploy/kubernetes/namespace.yaml
```

### 2. Configure Secrets

```bash
# Generate secrets
kubectl create secret generic mcp-gateway-secrets \
  --namespace=mcp-gateway \
  --from-literal=postgres-user=mcp_user \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --from-literal=database-url=postgresql://mcp_user:PASSWORD@postgres:5432/mcp_gateway \
  --from-literal=redis-password=$(openssl rand -base64 32) \
  --from-literal=redis-url=redis://:PASSWORD@redis:6379/0 \
  --from-literal=jwt-secret=$(openssl rand -base64 64) \
  --from-literal=default-admin-password=$(openssl rand -base64 16)
```

### 3. Deploy PostgreSQL & Redis

```bash
kubectl apply -f deploy/kubernetes/postgres.yaml
kubectl apply -f deploy/kubernetes/redis.yaml

# Wait for databases to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n mcp-gateway --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n mcp-gateway --timeout=300s
```

### 4. Deploy Gateway

```bash
# Apply ConfigMap
kubectl apply -f deploy/kubernetes/configmap.yaml

# Deploy gateway
kubectl apply -f deploy/kubernetes/deployment.yaml

# Check deployment
kubectl get pods -n mcp-gateway
kubectl logs -f deployment/mcp-gateway -n mcp-gateway
```

### 5. Access the Gateway

```bash
# Get LoadBalancer IP
kubectl get service mcp-gateway -n mcp-gateway

# Or use port forwarding for testing
kubectl port-forward service/mcp-gateway 8000:80 -n mcp-gateway

# Access at http://localhost:8000
```

### 6. Enable Auto-scaling

The HPA (Horizontal Pod Autoscaler) is already configured in `deployment.yaml`:
- Scales from 3 to 10 pods
- Based on CPU (70%) and memory (80%) utilization

```bash
# Check HPA status
kubectl get hpa -n mcp-gateway
```

---

## AWS ECS Deployment

Deploy to AWS Elastic Container Service with Fargate:

### 1. Prerequisites

```bash
# Install AWS CLI
aws configure

# Install ECS CLI
ecs-cli configure
```

### 2. Create ECR Repository

```bash
# Create repository
aws ecr create-repository --repository-name mcp-gateway

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push image
docker build -t mcp-gateway .
docker tag mcp-gateway:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mcp-gateway:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/mcp-gateway:latest
```

### 3. Create RDS PostgreSQL

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier mcp-gateway-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username mcpuser \
  --master-user-password <strong-password> \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxxxx
```

### 4. Create ElastiCache Redis

```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id mcp-gateway-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1
```

### 5. Store Secrets in AWS Secrets Manager

```bash
# Database URL
aws secretsmanager create-secret \
  --name mcp-gateway/database-url \
  --secret-string "postgresql://mcpuser:PASSWORD@mcp-gateway-db.xxxxx.us-east-1.rds.amazonaws.com:5432/mcp_gateway"

# Redis URL
aws secretsmanager create-secret \
  --name mcp-gateway/redis-url \
  --secret-string "redis://mcp-gateway-redis.xxxxx.cache.amazonaws.com:6379/0"

# JWT Secret
aws secretsmanager create-secret \
  --name mcp-gateway/jwt-secret \
  --secret-string "$(openssl rand -base64 64)"
```

### 6. Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name mcp-gateway-cluster
```

### 7. Register Task Definition

```bash
# Update deploy/aws-ecs/task-definition.json with your values
aws ecs register-task-definition --cli-input-json file://deploy/aws-ecs/task-definition.json
```

### 8. Create ECS Service

```bash
aws ecs create-service \
  --cluster mcp-gateway-cluster \
  --service-name mcp-gateway \
  --task-definition mcp-gateway \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=mcp-gateway,containerPort=8000"
```

### 9. Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name mcp-gateway-alb \
  --subnets subnet-xxxxx subnet-yyyyy \
  --security-groups sg-xxxxx

# Create target group
aws elbv2 create-target-group \
  --name mcp-gateway-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxx \
  --target-type ip

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

---

## Google Cloud Run

Serverless deployment to Google Cloud Run:

### 1. Build and Push to GCR

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/mcp-gateway

# Or use local Docker
docker build -t gcr.io/YOUR_PROJECT_ID/mcp-gateway .
docker push gcr.io/YOUR_PROJECT_ID/mcp-gateway
```

### 2. Create Cloud SQL PostgreSQL

```bash
gcloud sql instances create mcp-gateway-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1

gcloud sql databases create mcp_gateway --instance=mcp-gateway-db

gcloud sql users create mcpuser \
  --instance=mcp-gateway-db \
  --password=<strong-password>
```

### 3. Create Memorystore Redis

```bash
gcloud redis instances create mcp-gateway-redis \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy mcp-gateway \
  --image gcr.io/YOUR_PROJECT_ID/mcp-gateway \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances YOUR_PROJECT_ID:us-central1:mcp-gateway-db \
  --set-env-vars DATABASE_URL="postgresql://mcpuser:PASSWORD@/mcp_gateway?host=/cloudsql/YOUR_PROJECT_ID:us-central1:mcp-gateway-db" \
  --set-secrets JWT_SECRET=mcp-gateway-jwt:latest,REDIS_URL=mcp-gateway-redis-url:latest \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10
```

---

## DigitalOcean App Platform

Deploy to DigitalOcean's PaaS:

### 1. Create App via CLI

```yaml
# Create app.yaml
name: mcp-gateway
region: nyc
services:
- name: gateway
  github:
    repo: your-username/mcp-security-gateway
    branch: main
  dockerfile_path: Dockerfile
  http_port: 8000
  instance_count: 2
  instance_size_slug: professional-xs
  envs:
  - key: DATABASE_URL
    scope: RUN_TIME
    type: SECRET
  - key: REDIS_URL
    scope: RUN_TIME
    type: SECRET
  - key: JWT_SECRET
    scope: RUN_TIME
    type: SECRET
  health_check:
    http_path: /health

databases:
- name: mcp-gateway-db
  engine: PG
  version: "16"
  size: db-s-1vcpu-1gb

- name: mcp-gateway-redis
  engine: REDIS
  version: "7"
  size: db-s-1vcpu-1gb
```

```bash
# Deploy
doctl apps create --spec app.yaml

# Get app info
doctl apps list

# View logs
doctl apps logs <app-id>
```

---

## Traditional Server (Systemd)

Deploy to a traditional Linux server:

### 1. Install Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3-pip postgresql redis-server nginx

# Start services
sudo systemctl start postgresql redis-server
sudo systemctl enable postgresql redis-server
```

### 2. Create Database

```bash
sudo -u postgres psql
CREATE DATABASE mcp_gateway;
CREATE USER mcp_user WITH PASSWORD 'strong-password';
GRANT ALL PRIVILEGES ON DATABASE mcp_gateway TO mcp_user;
\q
```

### 3. Install Application

```bash
# Create app user
sudo useradd -m -s /bin/bash mcp

# Clone repository
sudo -u mcp git clone <repo> /home/mcp/mcp-gateway
cd /home/mcp/mcp-gateway

# Install dependencies
sudo -u mcp python3.11 -m venv venv
sudo -u mcp ./venv/bin/pip install -r requirements.txt

# Configure environment
sudo -u mcp cp .env.example .env
sudo -u mcp nano .env
```

### 4. Create Systemd Service

```bash
sudo nano /etc/systemd/system/mcp-gateway.service
```

```ini
[Unit]
Description=MCP Security Gateway
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=mcp
WorkingDirectory=/home/mcp/mcp-gateway
Environment="PATH=/home/mcp/mcp-gateway/venv/bin"
EnvironmentFile=/home/mcp/mcp-gateway/.env
ExecStart=/home/mcp/mcp-gateway/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl daemon-reload
sudo systemctl start mcp-gateway
sudo systemctl enable mcp-gateway

# Check status
sudo systemctl status mcp-gateway
sudo journalctl -u mcp-gateway -f
```

### 5. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/mcp-gateway
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/mcp-gateway /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Install SSL with Certbot
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## CI/CD Setup

### GitHub Actions (Included)

The repository includes `.github/workflows/ci.yml` which:
- Runs tests on every push and PR
- Builds Docker image
- Deploys to preview/production environments

### GitLab CI/CD

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  image: python:3.11
  services:
    - postgres:16
    - redis:7
  script:
    - pip install -r requirements.txt
    - pytest

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    - kubectl set image deployment/mcp-gateway gateway=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

---

## Monitoring & Maintenance

### Prometheus Monitoring

```bash
# Scrape metrics from /metrics endpoint
curl http://localhost:8000/metrics

# Example Prometheus config
scrape_configs:
  - job_name: 'mcp-gateway'
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Grafana Dashboard

Import dashboard for:
- Request rate and latency
- Blocked requests
- Error rates
- Resource usage

### Health Checks

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready

# Metrics
curl http://localhost:8000/metrics
```

### Log Management

```bash
# View logs (Docker)
docker logs -f mcp-gateway --tail=100

# View logs (Systemd)
journalctl -u mcp-gateway -f

# Export logs
docker logs mcp-gateway > logs_$(date +%Y%m%d).log
```

### Database Maintenance

```bash
# Vacuum database
docker exec mcp-gateway-db vacuumdb -U mcp_user -d mcp_gateway

# Clean old audit logs (automatic via cron)
0 2 * * * docker exec mcp-gateway-db psql -U mcp_user -d mcp_gateway -c "DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '90 days'"
```

---

## Troubleshooting

### Common Issues

1. **Gateway won't start**
   - Check database connection: `psql -h localhost -U mcp_user -d mcp_gateway`
   - Check Redis: `redis-cli ping`
   - Review logs: `docker logs mcp-gateway`

2. **High memory usage**
   - Reduce worker processes
   - Increase log rotation frequency
   - Clean old audit logs

3. **Slow response times**
   - Check database indexes
   - Monitor Redis performance
   - Review rate limiting settings

---

For more help, see:
- [README.md](README.md) - General documentation
- [SECURITY.md](SECURITY.md) - Security best practices
- [GitHub Issues](https://github.com/your-repo/issues) - Report bugs

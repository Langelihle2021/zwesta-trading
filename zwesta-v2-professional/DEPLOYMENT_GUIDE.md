# 🚀 Production Deployment Guide - Zwesta Trading System v2

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Local Docker Deployment](#local-docker-deployment)
3. [Cloud Deployment (AWS EC2)](#aws-ec2-deployment)
4. [Cloud Deployment (Azure App Service)](#azure-app-service-deployment)
5. [Cloud Deployment (DigitalOcean)](#digitalocean-deployment)
6. [CI/CD Pipeline Setup](#cicd-pipeline)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### Security
- [ ] Change all default passwords (database, JWT secret)
- [ ] Generate new JWT secret: `openssl rand -hex 32`
- [ ] Set strong database password
- [ ] Configure SSL/TLS certificates
- [ ] Enable HTTPS only
- [ ] Setup firewall rules
- [ ] Enable database backups

### Configuration
- [ ] Update `.env` with production values
- [ ] Verify MT5 credentials are correct
- [ ] Set proper API rate limits
- [ ] Configure email for alerts
- [ ] Setup WhatsApp credentials (Twilio)
- [ ] Configure logging and monitoring

### Testing
- [ ] Run all unit tests: `pytest tests/`
- [ ] Load testing: `locust -f locustfile.py`
- [ ] Security scan: `bandit -r ./`
- [ ] Dependency audit: `pip audit`
- [ ] Database migrations tested
- [ ] Frontend builds successfully
- [ ] Mobile app builds and installs correctly

### Resources
- [ ] Calculate required server resources
- [ ] Review quota limits
- [ ] Plan for scaling
- [ ] Setup CDN for static files
- [ ] Configure caching strategy

---

## Local Docker Deployment

### 1. Build Docker Images

```bash
# Build all images
docker-compose build

# Or build individually
docker build -f docker/Dockerfile.backend -t zwesta/backend:latest .
docker build -f docker/Dockerfile.frontend -t zwesta/frontend:latest .
docker build -f docker/Dockerfile.mobile -t zwesta/mobile:latest .
```

### 2. Create Production Environment File

```bash
# Copy and customize environment
cp .env.example .env.prod

# Edit .env.prod with production values
nano .env.prod
```

**Required Production Settings:**
```env
# Database
DATABASE_USER=postgres
DATABASE_PASSWORD=<strong-password-here>
DATABASE_NAME=xm_trader_prod
DATABASE_HOST=postgres

# MT5
MT5_ACCOUNT=136372035
MT5_PASSWORD=<your-mt5-password>
MT5_SERVER=MetaQuotes-Demo

# JWT
JWT_SECRET=<generate-with-openssl>

# Email
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=<your-account-sid>
TWILIO_AUTH_TOKEN=<your-auth-token>
TWILIO_PHONE_NUMBER=+1234567890

# Sentry (Error Tracking)
SENTRY_DSN=<your-sentry-dsn>

# AWS (if using S3)
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_S3_BUCKET=zwesta-trading-prod
AWS_REGION=us-east-1
```

### 3. Start Services

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Or start in production mode
docker-compose -f docker/docker-compose.prod.yml up -d
```

### 4. Initialize Database

```bash
# Enter backend container
docker exec zwesta_backend /bin/bash

# Run migrations
python -c "from app.database import init_db; init_db()"

# Load demo data (optional)
python scripts/load_demo_data.py
```

### 5. Verify Deployment

```bash
# Check all containers running
docker ps

# Check logs
docker logs zwesta_backend
docker logs zwesta_frontend
docker logs zwesta_postgres

# Test API
curl http://localhost:8000/docs

# Test Frontend
# Open browser: http://localhost:3000
```

---

## AWS EC2 Deployment

### 1. Launch EC2 Instance

**Recommended Specs:**
- **Instance Type:** t3.medium (for production)
- **OS:** Ubuntu 22.04 LTS
- **Storage:** 50GB EBS (gp3)
- **Network:** VPC with security group allowing ports 80, 443, 5432

### 2. Setup Instance

```bash
# SSH into instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Clone Repository

```bash
# Clone
git clone https://github.com/your-username/zwesta-v2-professional.git
cd zwesta-v2-professional

# Setup environment
cp .env.example .env.prod
```

### 4. Deploy with Docker Compose

```bash
# Start services
docker-compose -f docker/docker-compose.prod.yml up -d

# Setup database
docker exec zwesta_backend_prod python -c "from app.database import init_db; init_db()"
```

### 5. Configure DNS & SSL

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Update nginx.conf with certificate paths
# Restart nginx
docker restart zwesta_nginx_prod
```

### 6. Setup Auto-Scaling (Optional)

```bash
# Create AMI from instance
# Setup Auto Scaling Group with minimum 2, maximum 4 instances
# Configure load balancer (ALB)
```

---

## Azure App Service Deployment

### 1. Create Resources

```bash
# Login to Azure
az login

# Create resource group
az group create --name zwesta-rg --location eastus

# Create App Service Plan
az appservice plan create \
  --name zwesta-app-plan \
  --resource-group zwesta-rg \
  --sku B2 \
  --is-linux

# Create Web App for Container
az webapp create \
  --resource-group zwesta-rg \
  --plan zwesta-app-plan \
  --name zwesta-app \
  --deployment-container-image-name-user your-username

# Create PostgreSQL Database
az postgres server create \
  --resource-group zwesta-rg \
  --name zwesta-postgres \
  --admin-user postgres \
  --admin-password <strong-password> \
  --sku-name B_Gen5_1 \
  --storage-size 51200
```

### 2. Configure Database

```bash
# Create database
az postgres db create \
  --resource-group zwesta-rg \
  --server-name zwesta-postgres \
  --name xm_trader_prod

# Allow Azure services to access
az postgres server firewall-rule create \
  --resource-group zwesta-rg \
  --server-name zwesta-postgres \
  --name allow-azure-services \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### 3. Push Docker Images to Registry

```bash
# Login to ACR
az acr login --name your-registry

# Tag and push images
docker tag zwesta/backend your-registry.azurecr.io/zwesta/backend:latest
docker push your-registry.azurecr.io/zwesta/backend:latest

docker tag zwesta/frontend your-registry.azurecr.io/zwesta/frontend:latest
docker push your-registry.azurecr.io/zwesta/frontend:latest
```

### 4. Configure App Service

```bash
# Set docker image
az webapp config container set \
  --name zwesta-app \
  --resource-group zwesta-rg \
  --docker-custom-image-name your-registry.azurecr.io/zwesta/backend:latest \
  --docker-registry-server-url https://your-registry.azurecr.io \
  --docker-registry-server-user <username> \
  --docker-registry-server-password <password>

# Set environment variables
az webapp config appsettings set \
  --resource-group zwesta-rg \
  --name zwesta-app \
  --settings \
    DATABASE_URL="postgresql://postgres:password@zwesta-postgres.postgres.database.azure.com:5432/xm_trader_prod" \
    MT5_ACCOUNT="136372035" \
    JWT_SECRET="<your-secret>"
```

### 5. Deploy

```bash
# Restart app service
az webapp restart --resource-group zwesta-rg --name zwesta-app

# View logs
az webapp log tail --resource-group zwesta-rg --name zwesta-app
```

---

## DigitalOcean Deployment

### 1. Create Droplet

```bash
# Create droplet (via UI or CLI)
# - Size: $12/month (2GB RAM, 1 CPU, 50GB SSD)
# - Image: Ubuntu 22.04 LTS
# - Region: New York or your preference
```

### 2. Initial Setup

```bash
# SSH into droplet
ssh root@your-droplet-ip

# Create user
adduser trading
usermod -aG sudo trading
su - trading

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 3. Setup Firewall

```bash
# Enable UFW
sudo ufw enable

# Allow ports
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5432/tcp

# Check rules
sudo ufw status
```

### 4. Deploy Application

```bash
# Clone repository
git clone https://github.com/your-username/zwesta-v2-professional.git
cd zwesta-v2-professional

# Setup environment
cp .env.example .env.prod
nano .env.prod  # Edit values

# Deploy
docker-compose -f docker/docker-compose.prod.yml up -d

# Setup database
docker exec zwesta_backend_prod python -c "from app.database import init_db; init_db()"
```

### 5. Setup SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install snapd
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Configure auto-renewal
sudo systemctl enable snap.certbot.renew.timer
sudo systemctl start snap.certbot.renew.timer
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
    
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Tests
        run: |
          cd backend
          pip install -r requirements-minimal.txt
          pytest tests/
      
      - name: Lint
        run: |
          pip install flake8
          flake8 backend/app
      
      - name: Security Scan
        run: |
          pip install bandit
          bandit -r backend/app

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker Images
        run: |
          docker build -f docker/Dockerfile.backend -t ${{ secrets.REGISTRY }}/backend:${{ github.sha }} .
          docker build -f docker/Dockerfile.frontend -t ${{ secrets.REGISTRY }}/frontend:${{ github.sha }} .
      
      - name: Push to Registry
        run: |
          docker login -u ${{ secrets.REGISTRY_USERNAME }} -p ${{ secrets.REGISTRY_PASSWORD }}
          docker push ${{ secrets.REGISTRY }}/backend:${{ github.sha }}
          docker push ${{ secrets.REGISTRY }}/frontend:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to AWS
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          # SSH to EC2 and pull latest images
          # Update docker-compose
          # Restart services
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# API Health
curl http://your-domain/health

# Database Health
docker exec zwesta_postgres_prod pg_isready

# Container Health
docker ps --filter health=unhealthy
```

### Logs

```bash
# View logs
docker logs -f zwesta_backend_prod
docker logs -f zwesta_frontend_prod

# Export logs for analysis
docker logs zwesta_backend_prod > backend.log 2>&1
```

### Backups

```bash
# Backup database
docker exec zwesta_postgres_prod pg_dump -U postgres xm_trader_prod > backup.sql

# Restore database
docker exec -i zwesta_postgres_prod psql -U postgres xm_trader_prod < backup.sql

# Backup persistent volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

### Scaling

```bash
# Increase container resources
docker update --memory="2g" --cpus="1" zwesta_backend_prod
docker restart zwesta_backend_prod

# Or update docker-compose resource limits
# Rebuild and deploy
```

---

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Database Connection Failed

```bash
# Check if postgres is running
docker ps | grep postgres

# Check postgres logs
docker logs zwesta_postgres_prod

# Test connection
docker exec zwesta_backend_prod psql -h postgres -U postgres -d xm_trader_prod
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Increase swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### SSL Certificate Issues

```bash
# Check certificate
openssl x509 -in /etc/letsencrypt/live/your-domain/cert.pem -text -noout

# Renew manually
sudo certbot renew --dry-run

# If renewal fails
sudo certbot renew --force-renewal
```

---

## Performance Optimization

### Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_trades_created_at ON trades(created_at);

-- VACUUM regularly
VACUUM ANALYZE;
```

### API Optimization

```python
# Enable response caching
from fastapi_cache import FastAPICache
from fastapi_cache.decoration import cache

@cache(expire=300)  # 5 minute cache
async def get_market_data():
    ...
```

### Frontend Optimization

```bash
# Enable gzip compression
# Enable HTTP/2 push
# Minify CSS/JS
# Lazy load images
# Use service workers for offline support
```

---

**✅ Your system is ready for production deployment!**

For questions or issues, consult the monitoring logs and health endpoints.

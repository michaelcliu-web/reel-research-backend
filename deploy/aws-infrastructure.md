# AWS Infrastructure Setup Guide

This guide walks you through setting up the AWS infrastructure for MyApp.

## Prerequisites

- AWS Account
- AWS CLI installed and configured (`aws configure`)
- Your domain DNS access (for api.example.com)

---

## Step 1: Create Security Groups

### 1.1 EC2 Security Group

Go to **EC2 > Security Groups > Create Security Group**

- **Name**: `myapp-ec2-sg`
- **Description**: Security group for MyApp EC2 instance
- **Inbound Rules**:
  | Type | Port | Source | Description |
  |------|------|--------|-------------|
  | SSH | 22 | Your IP | SSH access |
  | HTTP | 80 | 0.0.0.0/0 | HTTP traffic |
  | HTTPS | 443 | 0.0.0.0/0 | HTTPS traffic |

### 1.2 RDS Security Group

- **Name**: `myapp-rds-sg`
- **Description**: Security group for MyApp RDS
- **Inbound Rules**:
  | Type | Port | Source | Description |
  |------|------|--------|-------------|
  | PostgreSQL | 5432 | myapp-ec2-sg | DB access from EC2 |

---

## Step 2: Create RDS PostgreSQL Instance

Go to **RDS > Create database**

### Configuration:
- **Engine**: PostgreSQL
- **Engine Version**: 15.x
- **Templates**: Free tier (or Production for better performance)
- **DB Instance Identifier**: `myapp-db`
- **Master Username**: `postgres`
- **Master Password**: (save this securely!)

### Instance Configuration:
- **DB Instance Class**: `db.t3.micro` (Free Tier) or `db.t3.small`
- **Storage Type**: gp2
- **Allocated Storage**: 20 GB

### Connectivity:
- **VPC**: Default VPC
- **Public Access**: No (recommended) or Yes (if needed for migration)
- **VPC Security Group**: `myapp-rds-sg`

### Additional Configuration:
- **Initial Database Name**: `myapp`
- **Backup Retention**: 7 days
- **Enable deletion protection**: Yes (for production)

**Save the endpoint** - it will look like: `myapp-db.xxxx.us-east-1.rds.amazonaws.com`

---

## Step 3: Launch EC2 Instance

Go to **EC2 > Launch Instance**

### Configuration:
- **Name**: `myapp-api`
- **AMI**: Amazon Linux 2023 or Ubuntu 22.04 LTS
- **Instance Type**: `t3.small` (recommended) or `t3.micro` (Free Tier)
- **Key Pair**: Create new or use existing (save the .pem file!)
- **Network Settings**:
  - VPC: Default
  - Auto-assign Public IP: Enable
  - Security Group: `myapp-ec2-sg`
- **Storage**: 20 GB gp3

### Launch the instance

---

## Step 4: Allocate Elastic IP

Go to **EC2 > Elastic IPs > Allocate Elastic IP address**

1. Click **Allocate**
2. Select the new Elastic IP
3. Click **Actions > Associate Elastic IP address**
4. Select your EC2 instance
5. Click **Associate**

**Save this IP address** - this will be your server's permanent IP.

---

## Step 5: Update DNS

In your DNS provider (e.g., Cloudflare, Route 53, GoDaddy):

1. Create/Update an **A record**:
   - **Name**: `api` (for api.example.com)
   - **Type**: A
   - **Value**: Your Elastic IP address
   - **TTL**: 300 (or Auto)

2. Wait for DNS propagation (usually 5-30 minutes)

---

## Step 6: Connect to EC2

```bash
# Make your key file secure
chmod 400 your-key.pem

# Connect to EC2
ssh -i your-key.pem ec2-user@your-elastic-ip
# For Ubuntu: ssh -i your-key.pem ubuntu@your-elastic-ip
```

---

## Step 7: Run Setup Script

Once connected to EC2:

```bash
# Download and run the setup script
curl -O https://raw.githubusercontent.com/your-repo/app-backend/deploy/ec2-setup.sh
bash ec2-setup.sh

# Log out and back in for docker permissions
exit
ssh -i your-key.pem ec2-user@your-elastic-ip
```

---

## Step 8: Deploy Application

```bash
# Clone your repository
cd /opt/myapp
git clone https://github.com/your-username/your-repo.git .

# Create production environment file
cd app-backend
cp .env.example .env.prod
nano .env.prod  # Edit with your actual values

# Set up Nginx
sudo cp deploy/nginx.conf /etc/nginx/conf.d/myapp.conf
sudo nginx -t
sudo systemctl reload nginx

# Build and start the application
docker-compose -f docker-compose.prod.yml up -d --build

# Check if it's running
docker-compose -f docker-compose.prod.yml logs -f
```

---

## Step 9: Set Up SSL

```bash
sudo certbot --nginx -d api.example.com
```

Follow the prompts. Certbot will automatically:
- Obtain SSL certificate
- Configure Nginx for HTTPS
- Set up auto-renewal

---

## Step 10: Verify Deployment

```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs web

# Test the API
curl https://api.example.com/health
```

---

## Useful Commands

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart application
docker-compose -f docker-compose.prod.yml restart

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# Stop application
docker-compose -f docker-compose.prod.yml down

# Run Django management commands
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Check SSL certificate renewal
sudo certbot renew --dry-run
```

--- 

## Estimated Monthly Costs

| Service | Specification | Est. Cost |
|---------|--------------|-----------|
| EC2 | t3.small | ~$15/mo |
| RDS | db.t3.micro | ~$12/mo |
| Elastic IP | (when attached) | ~$0/mo |
| Data Transfer | ~10GB | ~$1/mo |
| **Total** | | **~$28/mo** |

*Note: Costs vary by region and usage. Use AWS Cost Explorer for accurate estimates.*

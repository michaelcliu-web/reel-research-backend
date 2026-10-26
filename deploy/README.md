# MyApp AWS Deployment Guide

## Infrastructure Overview

| Service | Details |
|---------|---------|
| **Compute** | EC2 `t3.medium` (or your chosen size) |
| **Database** | RDS PostgreSQL 15 |
| **Web Server** | Nginx (reverse proxy) + Daphne (ASGI) |
| **SSL** | Let's Encrypt via Certbot |
| **Container** | Docker + Docker Compose |
| **Email** | Twilio SendGrid (SMTP) |

### Key Information

| Resource | Value |
|----------|-------|
| EC2 Elastic IP | `your-elastic-ip` |
| RDS Endpoint | `myapp-db.xxxxx.us-east-2.rds.amazonaws.com` |
| API URL | `https://api.example.com` |
| Admin Panel | `https://api.example.com/admin/` |

---

## Quick Commands Reference

### SSH into EC2

```bash
ssh -i ~/Downloads/myapp-key.pem ec2-user@your-elastic-ip
```

Edit env:
```bash
nano /opt/myapp/app-backend/.env.prod
```

### Deploy Updates

**On your local machine (push changes):**
```bash
cd /path/to/your-repo/app-backend
git add .
git commit -m "Your commit message"
git push origin main
```

**On EC2 (pull and deploy — code changes only, fast):**
```bash
cd /opt/myapp/app-backend
git pull origin main
docker-compose -f docker-compose.prod.yml down
DOCKER_BUILDKIT=0 docker build -t myapp-web .
docker-compose -f docker-compose.prod.yml up -d
```

**If requirements.txt changed (full rebuild, slow):**
```bash
cd /opt/myapp/app-backend
git pull origin main
docker-compose -f docker-compose.prod.yml down
DOCKER_BUILDKIT=0 docker build --no-cache -t myapp-web .
docker-compose -f docker-compose.prod.yml up -d
```

> **Note:** `DOCKER_BUILDKIT=0` is required on this EC2 instance due to a broken buildx plugin. Without it, builds will fail with `exec format error`. Only use `--no-cache` when `requirements.txt` changes — otherwise Docker caches the pip install layer and builds are fast (seconds instead of minutes).


### How to reset on AWS website


The EC2 instance is unresponsive. Go to the AWS Console to reboot it:
Go to https://console.aws.amazon.com/ec2/
Make sure you're in the correct region (top right dropdown)
Click Instances in the left sidebar
Select your instance
Click Instance state dropdown (top right) → Reboot instance
Wait 1-2 minutes, then try SSH again
If reboot doesn't work, try Stop instance → wait until it shows "Stopped" → Start instance. (The Elastic IP will stay attached so your IP won't change.)
Once you can SSH back in, the Docker container should auto-start since it has restart: always. If not:
cd /opt/myapp
docker-compose -f docker-compose.prod.yml up -d
cd /opt/myapp



### Container Management

```bash
# View container status
docker-compose -f docker-compose.prod.yml ps

# View logs (live)
docker-compose -f docker-compose.prod.yml logs -f

# View last 100 lines of logs
docker-compose -f docker-compose.prod.yml logs --tail=100

# Restart container
docker-compose -f docker-compose.prod.yml restart

# Stop container
docker-compose -f docker-compose.prod.yml down

# Rebuild and start (code changes only)
docker-compose -f docker-compose.prod.yml down
DOCKER_BUILDKIT=0 docker build -t myapp-web .
docker-compose -f docker-compose.prod.yml up -d
```

### Django Management Commands

```bash
# Run migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create superuser
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Change user password
docker-compose -f docker-compose.prod.yml exec web python manage.py changepassword user@email.com

# Open Django shell
docker-compose -f docker-compose.prod.yml exec web python manage.py shell

# Collect static files
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

### Database Commands

```bash
# Connect to RDS database
psql --host=myapp-db.xxxxx.us-east-2.rds.amazonaws.com \
  --port=5432 --username=postgres --dbname=myapp

# Quick query (e.g., count users)
psql --host=myapp-db.xxxxx.us-east-2.rds.amazonaws.com \
  --port=5432 --username=postgres --dbname=myapp \
  -c "SELECT COUNT(*) FROM api_customuser;"

# Backup database
pg_dump --host=myapp-db.xxxxx.us-east-2.rds.amazonaws.com \
  --port=5432 --username=postgres --dbname=myapp \
  --no-owner --no-privileges -f backup_$(date +%Y%m%d).sql

# Restore database (WARNING: destructive)
psql --host=myapp-db.xxxxx.us-east-2.rds.amazonaws.com \
  --port=5432 --username=postgres --dbname=myapp \
  -f backup_file.sql
```

### Nginx Commands

```bash
# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Restart nginx
sudo systemctl restart nginx

# View nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### SSL Certificate

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate (auto-renews, but manual if needed)
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

---

## Debugging Guide

### Container Won't Start

```bash
# Check logs for errors
docker-compose -f docker-compose.prod.yml logs --tail=200

# Check if port 8000 is in use
sudo lsof -i :8000

# Rebuild from scratch
docker-compose -f docker-compose.prod.yml down
docker system prune -f
DOCKER_BUILDKIT=0 docker build --no-cache -t myapp-web .
docker-compose -f docker-compose.prod.yml up -d
```

### Database Connection Issues

```bash
# Test RDS connectivity from EC2
psql --host=myapp-db.xxxxx.us-east-2.rds.amazonaws.com \
  --port=5432 --username=postgres --dbname=myapp -c "SELECT 1;"

# Check security groups in AWS Console:
# - EC2 security group must allow outbound to RDS
# - RDS security group must allow inbound from EC2 security group
```

### API Returns 502 Bad Gateway

```bash
# Check if container is running
docker-compose -f docker-compose.prod.yml ps

# Check container logs
docker-compose -f docker-compose.prod.yml logs --tail=100

# Check nginx error log
sudo tail -50 /var/log/nginx/error.log

# Restart everything
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
sudo systemctl restart nginx
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal

# Check nginx SSL config
sudo cat /etc/nginx/conf.d/myapp.conf
```

### Health Check

```bash
# Test from EC2
curl http://localhost:8000/health/
curl https://api.example.com/health/

# Test from anywhere
curl https://api.example.com/health/
```

### Reset Admin Password

```bash
docker-compose -f docker-compose.prod.yml exec web python manage.py shell
```

```python
from api.models import CustomUser
user = CustomUser.objects.get(email='your@email.com')
user.set_password('new_password')
user.is_staff = True
user.is_superuser = True
user.save()
exit()
```

---

## Environment Variables

The `.env.prod` file contains all environment variables. Key ones:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | Full PostgreSQL connection string |
| `AUTH0_AUDIENCE` | Auth0 API identifier |
| `AUTH0_DOMAIN` | Auth0 domain |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SENDGRID_API_KEY` | Twilio SendGrid API key (for emails) |
| `FRONTEND_URL` | Frontend URL for CORS |

**Never commit `.env.prod` to git!**

---

## File Locations on EC2

| Path | Description |
|------|-------------|
| `/opt/myapp/app-backend` | Application root |
| `/opt/myapp/.env.prod` | Environment variables |
| `/etc/nginx/conf.d/myapp.conf` | Nginx config |
| `/etc/letsencrypt/` | SSL certificates |

---

## AWS Resources

### Security Groups

| Name | Purpose | Key Rules |
|------|---------|-----------|
| `myapp-ec2-sg` | EC2 instance | SSH (22), HTTP (80), HTTPS (443) |
| `myapp-rds-sg` | RDS database | PostgreSQL (5432) from EC2 SG only |

### Updating Security Groups

If your IP changes and you can't SSH:
1. Go to AWS Console → EC2 → Security Groups
2. Find `myapp-ec2-sg`
3. Edit inbound rules → Update SSH rule with your new IP

---

## Costs (Estimated Monthly)

| Service | Specification | Cost |
|---------|---------------|------|
| EC2 | t3.medium | ~$30 |
| RDS | db.m5.large | ~$70 |
| Elastic IP | (attached) | $0 |
| Data Transfer | ~50GB | ~$5 |
| **Total** | | **~$105/mo** |

---

## Maintenance Tasks

### Weekly
- Check container logs for errors
- Review AWS CloudWatch metrics

### Monthly
- Review and rotate API keys if needed
- Check for security updates: `sudo yum update -y`
- Verify SSL certificate renewal is working

### As Needed
- Scale EC2/RDS instance sizes based on traffic

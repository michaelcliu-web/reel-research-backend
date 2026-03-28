#!/bin/bash
# EC2 Instance Setup Script for MyApp
# Run this script after SSH-ing into your EC2 instance
# Usage: bash ec2-setup.sh

set -e

echo "=== MyApp EC2 Setup Script ==="
echo ""

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Detected OS: $OS"
echo ""

# Update system packages
echo "=== Updating system packages ==="
if [ "$OS" = "amzn" ] || [ "$OS" = "rhel" ] || [ "$OS" = "centos" ]; then
    sudo yum update -y
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get update && sudo apt-get upgrade -y
fi

# Install Docker
echo ""
echo "=== Installing Docker ==="
if [ "$OS" = "amzn" ]; then
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
fi

# Add current user to docker group
sudo usermod -aG docker $USER
echo "Added $USER to docker group (re-login required for this to take effect)"

# Install Docker Compose
echo ""
echo "=== Installing Docker Compose ==="
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version

# Install Nginx
echo ""
echo "=== Installing Nginx ==="
if [ "$OS" = "amzn" ]; then
    sudo yum install -y nginx
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get install -y nginx
fi
sudo systemctl start nginx
sudo systemctl enable nginx

# Install Certbot for SSL
echo ""
echo "=== Installing Certbot ==="
if [ "$OS" = "amzn" ]; then
    sudo yum install -y certbot python3-certbot-nginx
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get install -y certbot python3-certbot-nginx
fi

# Install Git
echo ""
echo "=== Installing Git ==="
if [ "$OS" = "amzn" ]; then
    sudo yum install -y git
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get install -y git
fi

# Install PostgreSQL client (for database operations)
echo ""
echo "=== Installing PostgreSQL client ==="
if [ "$OS" = "amzn" ]; then
    sudo yum install -y postgresql15
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    sudo apt-get install -y postgresql-client
fi

# Create app directory
echo ""
echo "=== Creating app directory ==="
sudo mkdir -p /opt/myapp
sudo chown $USER:$USER /opt/myapp

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Next steps:"
echo "1. Log out and log back in (for docker group permissions)"
echo "2. Clone your repository: git clone <repo-url> /opt/myapp"
echo "3. Create .env.prod file in /opt/myapp/app-backend/"
echo "4. Copy nginx config: sudo cp /opt/myapp/app-backend/deploy/nginx.conf /etc/nginx/conf.d/myapp.conf"
echo "5. Test nginx: sudo nginx -t"
echo "6. Reload nginx: sudo systemctl reload nginx"
echo "7. Set up SSL: sudo certbot --nginx -d api.example.com"
echo "8. Deploy: cd /opt/myapp/app-backend && docker-compose -f docker-compose.prod.yml up -d --build"
echo ""

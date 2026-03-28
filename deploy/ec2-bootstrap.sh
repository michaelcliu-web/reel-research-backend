#!/bin/bash
# Full EC2 bootstrap: installs all dependencies, clones repo, sets up nginx/SSL, deploys
# Run this ONCE after first SSH into a fresh EC2 instance:
#   bash ec2-bootstrap.sh <GITHUB_REPO_URL>
#
# Example: bash ec2-bootstrap.sh https://github.com/youruser/your-repo.git

set -e

REPO_URL=${1:-""}
APP_DIR="/opt/myapp"

if [ -z "$REPO_URL" ]; then
    echo "Usage: bash ec2-bootstrap.sh <GITHUB_REPO_URL>"
    exit 1
fi

echo "=== MyApp EC2 Bootstrap ==="
echo ""

# 1. System packages
echo "--- Installing system packages ---"
sudo yum update -y
sudo yum install -y docker git nginx postgresql15

# 2. Docker
echo ""
echo "--- Setting up Docker ---"
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 3. Docker Compose
echo ""
echo "--- Installing Docker Compose ---"
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Certbot
echo ""
echo "--- Installing Certbot ---"
sudo yum install -y certbot python3-certbot-nginx

# 5. Clone repo
echo ""
echo "--- Cloning repository ---"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR
git clone $REPO_URL $APP_DIR

# 6. Nginx setup
echo ""
echo "--- Configuring Nginx ---"
sudo cp $APP_DIR/app-backend/deploy/nginx.conf /etc/nginx/conf.d/myapp.conf

# Remove default nginx config if it exists
sudo rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true

sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "IMPORTANT: You must log out and back in for Docker group permissions."
echo ""
echo "After re-login, continue with:"
echo "  1. Create .env.prod:  nano $APP_DIR/app-backend/.env.prod"
echo "  2. Set up SSL:        sudo certbot --nginx -d api.example.com"
echo "  3. Build & deploy:    cd $APP_DIR/app-backend && DOCKER_BUILDKIT=0 docker build -t myapp-web . && docker-compose -f docker-compose.prod.yml up -d"
echo "  4. Create superuser:  docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser"

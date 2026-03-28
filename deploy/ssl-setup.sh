#!/bin/bash
# SSL Setup Script for MyApp
# Run this after DNS is configured and pointing to your EC2 instance

set -e

DOMAIN="${1:-api.example.com}"

echo "=== SSL Setup for $DOMAIN ==="
echo ""

# Check if nginx config exists
if [ ! -f "/etc/nginx/conf.d/myapp.conf" ]; then
    echo "Error: Nginx config not found at /etc/nginx/conf.d/myapp.conf"
    echo "Please copy the nginx config first:"
    echo "  sudo cp /opt/myapp/app-backend/deploy/nginx.conf /etc/nginx/conf.d/myapp.conf"
    exit 1
fi

# Test nginx configuration
echo "Testing nginx configuration..."
sudo nginx -t

# Reload nginx
echo "Reloading nginx..."
sudo systemctl reload nginx

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Error: certbot is not installed"
    echo "Run the ec2-setup.sh script first or install manually:"
    echo "  sudo yum install -y certbot python3-certbot-nginx"
    exit 1
fi

# Run certbot
echo ""
echo "Running Certbot for $DOMAIN..."
echo "You will be prompted for your email and to agree to terms."
echo ""

sudo certbot --nginx -d "$DOMAIN"

# Verify SSL renewal
echo ""
echo "Testing SSL certificate renewal..."
sudo certbot renew --dry-run

echo ""
echo "=== SSL Setup Complete! ==="
echo ""
echo "Your site should now be accessible at:"
echo "  https://$DOMAIN"
echo ""
echo "Certificate auto-renewal is configured via systemd timer."
echo "Check status: sudo systemctl status certbot.timer"

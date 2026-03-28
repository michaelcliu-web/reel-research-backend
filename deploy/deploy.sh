#!/bin/bash
# Deployment script for MyApp on AWS EC2
# Run this from /opt/myapp/app-backend on EC2

set -e

echo "=== MyApp Deployment Script ==="
echo ""

# Configuration
APP_DIR="/opt/myapp/app-backend"
COMPOSE_FILE="docker-compose.prod.yml"

cd "$APP_DIR"

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo "Error: .env.prod file not found!"
    echo "Please create .env.prod with your production environment variables."
    echo "See deploy/env.example for reference."
    exit 1
fi

# Parse command line arguments
ACTION=${1:-"deploy"}

case $ACTION in
    "deploy")
        echo "=== Pulling latest code ==="
        git pull origin main

        echo ""
        echo "=== Building and starting containers ==="
        docker-compose -f "$COMPOSE_FILE" up -d --build

        echo ""
        echo "=== Running migrations ==="
        docker-compose -f "$COMPOSE_FILE" exec -T web python manage.py migrate --noinput

        echo ""
        echo "=== Collecting static files ==="
        docker-compose -f "$COMPOSE_FILE" exec -T web python manage.py collectstatic --noinput

        echo ""
        echo "=== Deployment complete! ==="
        docker-compose -f "$COMPOSE_FILE" ps
        ;;

    "restart")
        echo "=== Restarting containers ==="
        docker-compose -f "$COMPOSE_FILE" restart
        docker-compose -f "$COMPOSE_FILE" ps
        ;;

    "stop")
        echo "=== Stopping containers ==="
        docker-compose -f "$COMPOSE_FILE" down
        ;;

    "logs")
        echo "=== Showing logs ==="
        docker-compose -f "$COMPOSE_FILE" logs -f
        ;;

    "status")
        echo "=== Container status ==="
        docker-compose -f "$COMPOSE_FILE" ps
        ;;

    "migrate")
        echo "=== Running migrations ==="
        docker-compose -f "$COMPOSE_FILE" exec -T web python manage.py migrate
        ;;

    "shell")
        echo "=== Opening Django shell ==="
        docker-compose -f "$COMPOSE_FILE" exec web python manage.py shell
        ;;

    "bash")
        echo "=== Opening bash shell ==="
        docker-compose -f "$COMPOSE_FILE" exec web bash
        ;;

    "rebuild")
        echo "=== Rebuilding without cache ==="
        docker-compose -f "$COMPOSE_FILE" build --no-cache
        docker-compose -f "$COMPOSE_FILE" up -d
        ;;

    *)
        echo "Usage: $0 {deploy|restart|stop|logs|status|migrate|shell|bash|rebuild}"
        echo ""
        echo "Commands:"
        echo "  deploy   - Pull code, build, and deploy (default)"
        echo "  restart  - Restart containers"
        echo "  stop     - Stop all containers"
        echo "  logs     - Show container logs"
        echo "  status   - Show container status"
        echo "  migrate  - Run database migrations"
        echo "  shell    - Open Django shell"
        echo "  bash     - Open bash shell in container"
        echo "  rebuild  - Rebuild containers without cache"
        exit 1
        ;;
esac

echo ""
echo "Done!"

#!/bin/bash
# Database Migration Script: Heroku PostgreSQL to AWS RDS
# This script helps migrate your database from Heroku to AWS RDS

set -e

echo "=== MyApp Database Migration Script ==="
echo ""

# Check for required tools
command -v heroku >/dev/null 2>&1 || { echo "Error: Heroku CLI is required. Install from https://devcenter.heroku.com/articles/heroku-cli"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "Error: PostgreSQL client is required."; exit 1; }
command -v pg_restore >/dev/null 2>&1 || { echo "Error: pg_restore is required."; exit 1; }

# Configuration - UPDATE THESE VALUES
HEROKU_APP_NAME="${HEROKU_APP_NAME:-your-heroku-app-name}"
RDS_HOST="${RDS_HOST:-your-rds-endpoint.rds.amazonaws.com}"
RDS_PORT="${RDS_PORT:-5432}"
RDS_USER="${RDS_USER:-postgres}"
RDS_PASSWORD="${RDS_PASSWORD:-}"
RDS_DATABASE="${RDS_DATABASE:-myapp}"
BACKUP_FILE="heroku_backup_$(date +%Y%m%d_%H%M%S).dump"

echo "Configuration:"
echo "  Heroku App: $HEROKU_APP_NAME"
echo "  RDS Host: $RDS_HOST"
echo "  RDS Database: $RDS_DATABASE"
echo ""

# Step 1: Create backup from Heroku
echo "=== Step 1: Creating Heroku backup ==="
read -p "Create new Heroku backup? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    heroku pg:backups:capture --app "$HEROKU_APP_NAME"
    echo "Backup created successfully"
fi

# Step 2: Download the backup
echo ""
echo "=== Step 2: Downloading backup ==="
read -p "Download backup to $BACKUP_FILE? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    heroku pg:backups:download --app "$HEROKU_APP_NAME" -o "$BACKUP_FILE"
    echo "Backup downloaded to $BACKUP_FILE"
fi

# Step 3: Verify backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file $BACKUP_FILE not found"
    echo "You can also use an existing backup file by setting BACKUP_FILE environment variable"
    exit 1
fi

echo ""
echo "Backup file size: $(ls -lh $BACKUP_FILE | awk '{print $5}')"

# Step 4: Test RDS connection
echo ""
echo "=== Step 3: Testing RDS connection ==="
if [ -z "$RDS_PASSWORD" ]; then
    read -s -p "Enter RDS password: " RDS_PASSWORD
    echo
fi

export PGPASSWORD="$RDS_PASSWORD"
if psql -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USER" -d "$RDS_DATABASE" -c "SELECT 1" > /dev/null 2>&1; then
    echo "Successfully connected to RDS"
else
    echo "Error: Could not connect to RDS"
    echo "Make sure:"
    echo "  1. RDS instance is running"
    echo "  2. Security group allows your IP"
    echo "  3. Database '$RDS_DATABASE' exists"
    exit 1
fi

# Step 5: Restore to RDS
echo ""
echo "=== Step 4: Restoring to RDS ==="
echo "WARNING: This will overwrite data in the $RDS_DATABASE database!"
read -p "Continue with restore? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restoring database (this may take several minutes)..."
    
    # Use pg_restore with options for cleaner restore
    pg_restore \
        -h "$RDS_HOST" \
        -p "$RDS_PORT" \
        -U "$RDS_USER" \
        -d "$RDS_DATABASE" \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists \
        -v \
        "$BACKUP_FILE" 2>&1 | tee restore_log.txt
    
    echo ""
    echo "Database restore completed!"
    echo "Check restore_log.txt for any errors"
fi

# Step 6: Verify migration
echo ""
echo "=== Step 5: Verifying migration ==="
echo "Table counts in RDS:"
psql -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USER" -d "$RDS_DATABASE" -c "
SELECT schemaname, relname as table_name, n_live_tup as row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC
LIMIT 20;
"

# Cleanup
unset PGPASSWORD

echo ""
echo "=== Migration Complete ==="
echo ""
echo "Next steps:"
echo "1. Verify your application works with the new database"
echo "2. Update your environment variables to point to RDS"
echo "3. Test all critical functionality"
echo "4. Once verified, you can decommission Heroku"
echo ""
echo "Backup file saved: $BACKUP_FILE"
echo "Restore log saved: restore_log.txt"

#!/bin/bash
# Enable error logging
set -e
exec > >(tee /var/log/codedeploy-after-install.log) 2>&1

echo "Starting after_install.sh at $(date)"
echo "Setting permissions on /var/www/html/fsx-analyzer..."
chmod -R 755 /var/www/html/fsx-analyzer
chown -R nginx:nginx /var/www/html/fsx-analyzer

# Verify nginx configuration
echo "Checking nginx configuration..."
nginx -t || echo "Warning: Nginx configuration test failed"

echo "after_install.sh completed at $(date)"

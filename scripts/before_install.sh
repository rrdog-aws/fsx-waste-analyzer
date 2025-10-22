#!/bin/bash
# Enable error logging
set -e
exec > >(tee /var/log/codedeploy-before-install.log) 2>&1

echo "Starting before_install.sh at $(date)"
echo "Creating necessary directories..."
mkdir -p /var/www/html/fsx-analyzer
mkdir -p /etc/nginx/conf.d

echo "Stopping nginx service..."
systemctl stop nginx || echo "Failed to stop nginx, continuing anyway"
echo "before_install.sh completed at $(date)"

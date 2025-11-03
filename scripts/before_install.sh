#!/bin/bash
echo "Stopping Nginx and cleaning up old files..."
systemctl stop nginx || true

# Clean up old deployment files
rm -rf /var/www/html/fsx-analyzer || true
rm -rf /opt/deployment/scripts/* || true

# Create necessary directories
mkdir -p /var/www/html/fsx-analyzer
mkdir -p /opt/deployment/scripts

echo "Cleanup completed."

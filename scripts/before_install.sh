#!/bin/bash
echo "Stopping Nginx and cleaning up old files..."
systemctl stop nginx || true
rm -rf /var/www/html/fsx-analyzer || true

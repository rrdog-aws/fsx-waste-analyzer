#!/bin/bash
echo "Setting permissions for web directory..."
chmod -R 755 /var/www/html/fsx-analyzer
chown -R nginx:nginx /var/www/html/fsx-analyzer || true

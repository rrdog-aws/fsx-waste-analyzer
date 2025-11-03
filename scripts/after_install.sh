#!/bin/bash
echo "Running after install tasks..."

# Ensure nginx user exists
id -u nginx &>/dev/null || useradd nginx

# Set permissions
echo "Setting permissions for web directory..."
chmod -R 755 /var/www/html/fsx-analyzer
chown -R nginx:nginx /var/www/html/fsx-analyzer

echo "After install tasks completed."

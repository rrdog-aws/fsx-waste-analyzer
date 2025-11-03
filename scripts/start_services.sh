#!/bin/bash
echo "Starting Nginx service..."

# Ensure nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "Installing nginx..."
    yum install -y nginx
fi

# Start and enable nginx
systemctl start nginx || echo "Failed to start nginx"
systemctl enable nginx || echo "Failed to enable nginx"

# Verify nginx is running
if systemctl is-active nginx >/dev/null 2>&1; then
    echo "Nginx is running successfully"
else
    echo "Warning: Nginx failed to start"
    exit 1
fi

echo "Deployment complete."

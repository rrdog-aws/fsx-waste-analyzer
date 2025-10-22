#!/bin/bash
echo "Starting Nginx service..."
systemctl start nginx
systemctl enable nginx
echo "Deployment complete."

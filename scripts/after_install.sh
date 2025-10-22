#!/bin/bash
set -e
exec > >(tee /var/log/codedeploy-after-install.log) 2>&1

echo "Starting after_install.sh at $(date)"

# Find the deployment directory
DEPLOYMENT_DIR=$(find /opt/codedeploy-agent/deployment-root -name "deployment-archive" -type d | sort -r | head -n 1)
echo "Deployment directory: $DEPLOYMENT_DIR"

# Manually copy ONLY the fsx-analyzer files, NOT nginx config
echo "Manually copying files..."
if [ -d "$DEPLOYMENT_DIR/artifacts/ec2-app/fsx-analyzer" ]; then
  echo "Copying fsx-analyzer files..."
  cp -rfv "$DEPLOYMENT_DIR/artifacts/ec2-app/fsx-analyzer/"* /var/www/html/fsx-analyzer/
else
  echo "Source directory not found: $DEPLOYMENT_DIR/artifacts/ec2-app/fsx-analyzer"
  ls -la $DEPLOYMENT_DIR/artifacts/ec2-app/ || echo "Parent directory listing failed"
fi

# Set permissions
echo "Setting permissions..."
chmod -R 755 /var/www/html/fsx-analyzer
chown -R nginx:nginx /var/www/html/fsx-analyzer

echo "after_install.sh completed at $(date)"

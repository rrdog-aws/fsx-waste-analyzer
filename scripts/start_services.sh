#!/bin/bash
# Enable error logging
set -e
exec > >(tee /var/log/codedeploy-start-services.log) 2>&1

echo "Starting start_services.sh at $(date)"
echo "Restarting nginx service..."
systemctl restart nginx || {
  echo "Failed to restart nginx. Checking status:"
  systemctl status nginx
  echo "Checking configuration:"
  nginx -t
  exit 1
}
echo "start_services.sh completed at $(date)"

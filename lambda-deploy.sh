#!/bin/bash
# This script is used by CodeBuild to deploy Lambda functions

FUNCTION_NAME="your-lambda-function-name"
ARTIFACT_PATH="artifacts/lambda/function.zip"

# Check if we should deploy Lambda
if grep -q '"lambda": true' artifacts/deploy-config.json; then
  echo "Deploying Lambda function..."
  aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb://$ARTIFACT_PATH
  echo "Lambda deployment completed"
else
  echo "No Lambda changes detected, skipping deployment"
fi

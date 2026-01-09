#!/bin/bash

set -e
set -o pipefail

NAMESPACE="/app/customersupport"
REGION=$(aws configure get region || echo "${AWS_DEFAULT_REGION:-us-east-1}")

echo "🔍 名前空間 $NAMESPACE/* 配下の SSM パラメータを一覧表示中"
echo "📍 リージョン: $REGION"
echo ""

# Fetch and paginate through all parameters under the given path
aws ssm get-parameters-by-path \
  --path "$NAMESPACE" \
  --recursive \
  --with-decryption \
  --region "$REGION" \
  --query "Parameters[*].{Name:Name,Value:Value}" \
  --output table

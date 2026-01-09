#!/bin/bash

# Script to set API keys in AWS Systems Manager Parameter Store
# Usage: ./scripts/set-api-keys.sh

REGION="us-east-1"

echo "🔑 AWS Systems Manager Parameter Store に API キーを設定しています..."
echo ""

# OpenWeather API Key
read -p "OpenWeather API キーを入力してください (スキップするには Enter を押してください): " OPENWEATHER_KEY
if [ ! -z "$OPENWEATHER_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/travel/openweather-api-key" \
    --value "$OPENWEATHER_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ OpenWeather API キーを設定しました"
fi

# SERP API Key (Internet Search)
read -p "SERP API キーを入力してください (スキップするには Enter を押してください): " SERP_KEY
if [ ! -z "$SERP_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/travel/serp-api-key" \
    --value "$SERP_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ SERP API キーを設定しました"
fi

# Google Maps API Key
read -p "Google Maps API キーを入力してください (スキップするには Enter を押してください): " GOOGLE_KEY
if [ ! -z "$GOOGLE_KEY" ]; then
  aws ssm put-parameter \
    --name "/concierge-agent/travel/google-maps-key" \
    --value "$GOOGLE_KEY" \
    --type "SecureString" \
    --overwrite \
    --region $REGION
  echo "✅ Google Maps API キーを設定しました"
fi

echo ""
echo "🎉 API キーの設定が完了しました！"
echo ""
echo "注意: キーを設定した後、MCP サーバーを再デプロイする必要があります:"
echo "  cd infrastructure/mcp-servers && cdk deploy TravelStack"

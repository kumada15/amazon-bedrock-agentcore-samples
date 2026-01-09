#!/bin/bash
# cognito/refresh_token.sh

# Check if config file exists
if [ ! -f "cognito_config.json" ]; then
    echo "エラー: cognito_config.json が見つかりません。先に setup_cognito.sh を実行してください。"
    exit 1
fi

# Read config from JSON file
CLIENT_ID=$(jq -r '.client_id' cognito_config.json)
USERNAME=$(jq -r '.username' cognito_config.json)
PASSWORD=$(jq -r '.password' cognito_config.json)
REGION=$(jq -r '.region' cognito_config.json)

# Get new token
NEW_TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
  --region "$REGION" | jq -r '.AuthenticationResult.AccessToken')

# Update config file with new token
jq --arg token "$NEW_TOKEN" '.bearer_token = $token' cognito_config.json > temp.json && mv temp.json cognito_config.json

echo "新しい Bearer トークン: $NEW_TOKEN"
echo "設定が cognito_config.json に更新されました"

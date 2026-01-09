#!/bin/bash

################################################################################
# Device Management Agent Runtime - Cognito OAuth2 Setup Script
#
# This script automates the creation of an Amazon Cognito OAuth2 credential
# provider for the Device Management Agent Runtime. It validates environment
# configuration, installs required Python dependencies, and creates the
# credential provider using the AgentCore identity management system.
#
# PURPOSE:
#   Configure OAuth2 authentication for the agent runtime to communicate
#   with the Bedrock AgentCore Gateway using Cognito credentials.
#
# PREREQUISITES:
#   - Python 3 installed and available in PATH
#   - .env file with required Cognito configuration
#   - AWS credentials configured (aws configure)
#   - boto3, click, and python-dotenv packages (auto-installed)
#
# REQUIRED ENVIRONMENT VARIABLES (.env file):
#   COGNITO_CLIENT_ID       - OAuth client ID from Cognito App Client
#   COGNITO_CLIENT_SECRET   - OAuth client secret from Cognito App Client
#   COGNITO_DISCOVERY_URL   - OIDC discovery endpoint URL
#   COGNITO_AUTH_URL        - Authorization endpoint URL
#   COGNITO_TOKEN_URL       - Token endpoint URL
#   AWS_REGION              - AWS region for AgentCore operations
#
# WHAT THIS SCRIPT DOES:
#   1. Validates .env file exists with required variables
#   2. Checks Python 3 installation
#   3. Installs required Python packages from requirements-runtime.txt
#   4. Creates Cognito OAuth2 credential provider via CLI tool
#   5. Stores provider name in .env file for future reference
#
# CREDENTIAL PROVIDER:
#   - Default name: device-management-cognito-provider-29-jul
#   - Custom name: Pass as argument (./setup.sh my-custom-name)
#   - Stored in: .env file as COGNITO_PROVIDER_NAME
#
# USAGE:
#   Using default provider name:
#   ./setup.sh
#
#   Using custom provider name:
#   ./setup.sh my-custom-provider-name
#
# EXIT CODES:
#   0 - Setup completed successfully
#   1 - .env file not found or missing required variables
#   1 - Python 3 not installed
#   1 - Credential provider creation failed
#
# OUTPUTS:
#   - Credential provider created in AWS
#   - Provider name stored in .env file
#   - Success message with next steps
#
# NEXT STEPS:
#   1. Run the agent runtime: python3 strands-agent-runtime.py
#   2. Check CloudWatch Logs: /aws/bedrock-agentcore/device-management-agent
#   3. View X-Ray traces for performance monitoring
#
# NOTES:
#   - Provider name is stored in .env for easy reference
#   - Can be deleted later using: python3 cognito_credentials_provider.py delete
#   - Requires appropriate IAM permissions for AgentCore operations
#
################################################################################

set -e  # Exit on any error

echo "🚀 Device Management Agent Runtime セットアップ"
echo "================================================"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ エラー: .env ファイルが見つかりません！"
    echo "   以下の Cognito 設定変数を含む .env ファイルを作成してください:"
    echo "   - COGNITO_CLIENT_ID"
    echo "   - COGNITO_CLIENT_SECRET"
    echo "   - COGNITO_DISCOVERY_URL"
    echo "   - COGNITO_AUTH_URL"
    echo "   - COGNITO_TOKEN_URL"
    echo "   - AWS_REGION"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ エラー: Python 3 がインストールされていないか PATH に含まれていません"
    exit 1
fi

# Check if required Python packages are installed
echo "📦 Python 依存関係を確認中..."
if ! python3 -c "import boto3, click, dotenv" 2>/dev/null; then
    echo "⚠️  必要な Python パッケージをインストール中..."
    pip3 install -r requirements-runtime.txt
fi

# Default provider name
PROVIDER_NAME="device-management-cognito-provider-29-jul"

# Allow custom provider name via command line argument
if [ $# -eq 1 ]; then
    PROVIDER_NAME="$1"
    echo "📝 カスタムプロバイダー名を使用: $PROVIDER_NAME"
else
    echo "📝 デフォルトのプロバイダー名を使用: $PROVIDER_NAME"
    echo "   （カスタム名を指定できます: ./setup.sh <プロバイダー名>）"
fi

echo ""
echo "🔧 Cognito OAuth2 認証情報プロバイダーを作成中..."

# Invoke the create_cognito_provider function via the CLI
python3 cognito_credentials_provider.py create --name "$PROVIDER_NAME"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ セットアップが正常に完了しました！"
    echo "🎉 Device Management Agent Runtime の使用準備ができました。"
    echo ""
    echo "次のステップ:"
    echo "  1. Agent Runtime を実行: python3 strands-agent-runtime.py"
    echo "  2. CloudWatch でログを確認: /aws/bedrock-agentcore/device-management-agent"
    echo "  3. X-Ray トレースでパフォーマンス監視を確認"
else
    echo ""
    echo "❌ セットアップに失敗しました。上記のエラーメッセージを確認してください。"
    exit 1
fi

#!/bin/bash

# Deploy MCP Tool Lambda function using ZIP-based SAM (no Docker)
echo "🚀 MCP ツール Lambda 関数をデプロイ中 (ZIP ベース、Docker 不要)..."

# Configuration - Get project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels to reach AgentCore root
RUNTIME_DIR="$(dirname "$SCRIPT_DIR")"  # agentcore-runtime directory
MCP_TOOL_DIR="${PROJECT_DIR}/mcp-tool-lambda"

# Load configuration from consolidated config files
CONFIG_DIR="${PROJECT_DIR}/config"

# Check if static config exists
if [[ ! -f "${CONFIG_DIR}/static-config.yaml" ]]; then
    echo "❌ 設定ファイルが見つかりません: ${CONFIG_DIR}/static-config.yaml"
    exit 1
fi

# Extract values from YAML (fallback method if yq not available)
get_yaml_value() {
    local key="$1"
    local file="$2"
    # Handle nested YAML keys with proper indentation
    grep "  $key:" "$file" | head -1 | sed 's/.*: *["'\'']*\([^"'\'']*\)["'\'']*$/\1/' | xargs
}

REGION=$(get_yaml_value "region" "${CONFIG_DIR}/static-config.yaml")
ACCOUNT_ID=$(get_yaml_value "account_id" "${CONFIG_DIR}/static-config.yaml")

if [[ -z "$REGION" || -z "$ACCOUNT_ID" ]]; then
    echo "❌ static-config.yaml から region または account_id を読み取れませんでした"
    exit 1
fi

STACK_NAME="bac-mcp-stack"

echo "📝 設定:"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo "   スタック名: $STACK_NAME"
echo "   デプロイタイプ: ZIP ベース (Docker 不要)"
echo "   MCP ツールディレクトリ: $MCP_TOOL_DIR"
echo ""

# Check if MCP tool directory exists
if [[ ! -d "$MCP_TOOL_DIR" ]]; then
    echo "❌ MCP ツールディレクトリが見つかりません: $MCP_TOOL_DIR"
    exit 1
fi

# Function to setup virtual environment
setup_virtual_environment() {
    echo "🐍 Python 仮想環境をセットアップ中..."

    cd "$MCP_TOOL_DIR"

    # Check if .venv exists
    if [[ ! -d ".venv" ]]; then
        echo "   新しい仮想環境を作成中..."
        python3 -m venv .venv
        if [[ $? -ne 0 ]]; then
            echo "❌ 仮想環境の作成に失敗しました"
            exit 1
        fi
        echo "   ✅ 仮想環境を作成しました"
    else
        echo "   ✅ 仮想環境は既に存在します"
    fi

    # Activate virtual environment
    echo "   仮想環境をアクティベート中..."
    source .venv/bin/activate
    if [[ $? -ne 0 ]]; then
        echo "❌ 仮想環境のアクティベートに失敗しました"
        exit 1
    fi
    echo "   ✅ 仮想環境をアクティベートしました"

    # Verify Python version
    PYTHON_VERSION=$(python3 --version)
    echo "   Python バージョン: $PYTHON_VERSION"
}

# Function to install dependencies
install_dependencies() {
    echo "📦 Lambda 依存関係をインストール中..."

    cd "$MCP_TOOL_DIR"
    source .venv/bin/activate

    # Check if requirements.txt exists
    if [[ ! -f "lambda/requirements.txt" ]]; then
        echo "❌ requirements ファイルが見つかりません: lambda/requirements.txt"
        exit 1
    fi

    # Create packaging directory if it doesn't exist
    mkdir -p ./packaging/python

    # Install dependencies with Lambda-compatible settings
    echo "   Lambda ランタイム用の依存関係をインストール中..."
    pip install -r lambda/requirements.txt \
        --python-version 3.12 \
        --platform manylinux2014_x86_64 \
        --target ./packaging/python \
        --only-binary=:all: \
        --upgrade

    if [[ $? -ne 0 ]]; then
        echo "❌ 依存関係のインストールに失敗しました"
        exit 1
    fi

    echo "   ✅ 依存関係を正常にインストールしました"
}

# Function to package Lambda function
package_lambda() {
    echo "📦 Lambda 関数をパッケージング中..."

    cd "$MCP_TOOL_DIR"
    source .venv/bin/activate

    # Check if packaging script exists
    if [[ ! -f "package_for_lambda.py" ]]; then
        echo "❌ パッケージングスクリプトが見つかりません: package_for_lambda.py"
        exit 1
    fi

    # Run packaging script
    python3 package_for_lambda.py
    if [[ $? -ne 0 ]]; then
        echo "❌ Lambda 関数のパッケージングに失敗しました"
        exit 1
    fi

    echo "   ✅ Lambda 関数を正常にパッケージングしました"
}

# Function to deploy with SAM
deploy_with_sam() {
    echo "🚀 SAM でデプロイ中..."

    cd "$MCP_TOOL_DIR"

    # Check if deployment script exists
    if [[ ! -f "deploy-mcp-tool-zip.sh" ]]; then
        echo "❌ デプロイスクリプトが見つかりません: deploy-mcp-tool-zip.sh"
        exit 1
    fi

    # Make sure deployment script is executable
    chmod +x deploy-mcp-tool-zip.sh

    # Run deployment script
    ./deploy-mcp-tool-zip.sh
    if [[ $? -ne 0 ]]; then
        echo "❌ SAM デプロイに失敗しました"
        exit 1
    fi

    echo "   ✅ SAM デプロイが正常に完了しました"
}

# Main execution
echo "🔄 完全な ZIP ベースデプロイパイプラインを開始中..."
echo ""

# Step 1: Setup virtual environment
setup_virtual_environment
echo ""

# Step 2: Install dependencies
install_dependencies
echo ""

# Step 3: Package Lambda function
package_lambda
echo ""

# Step 4: Deploy with SAM
deploy_with_sam
echo ""

echo "🎉 MCP ツール Lambda のデプロイに成功しました！"
echo "=================================================="
echo ""
echo "✅ 仮想環境: 作成/確認済み"
echo "✅ 依存関係: Lambda ランタイム用にインストール済み"
echo "✅ Lambda パッケージ: すべての依存関係を含めて作成済み"
echo "✅ SAM デプロイ: 正常に完了"
echo ""
echo "🎯 このデプロイ方法のメリット:"
echo "   • Docker キャッシュの問題なし"
echo "   • より高速なデプロイ"
echo "   • Docker デーモン不要"
echo "   • アーキテクチャ固有の依存関係処理"
echo "   • 自動化された仮想環境管理"
echo "   • 完全な依存関係の分離"
echo ""
echo "📋 次のステップ:"
echo "   • ../05-create-gateway-targets.sh を実行して AgentCore Gateway を作成"
echo "   • MCP ツールで Lambda 関数をテスト"
echo "   • DIY または SDK エージェントをデプロイして MCP ツールを使用"
echo ""
echo "🔧 トラブルシューティング:"
echo "   • CloudWatch ログを確認: /aws/lambda/bac-mcp-tool"
echo "   • Cost Explorer と Budgets の IAM 権限を確認"
echo "   • 個別のツールで Lambda 関数をテスト"

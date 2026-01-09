#!/bin/bash

# Exit on error
set -e

# --help が渡された場合に使用法を表示
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "使用法: $0 [ECR_REPO_NAME]"
    echo ""
    echo "引数:"
    echo "  ECR_REPO_NAME    ECR リポジトリの名前 (デフォルト: sre_agent)"
    echo ""
    echo "環境変数:"
    echo "  LOCAL_BUILD      'true' に設定すると ECR プッシュなしでローカルコンテナビルド"
    echo "  PLATFORM         'x86_64' に設定するとローカルテスト用にビルド (デフォルト: AgentCore 用に arm64)"
    echo "  DEBUG            'true' に設定するとデプロイされたエージェントでデバッグモードを有効化"
    echo "  LLM_PROVIDER     'anthropic' または 'bedrock' に設定 (デフォルト: bedrock)"
    echo "  ANTHROPIC_API_KEY anthropic プロバイダー使用時に必要"
    echo ""
    echo "例:"
    echo "  # デフォルトのリポジトリ名でデプロイ"
    echo "  ./build_and_deploy.sh"
    echo ""
    echo "  # カスタムリポジトリ名でデプロイ"
    echo "  ./build_and_deploy.sh my_custom_sre_agent"
    echo ""
    echo "  # テスト用のローカルビルド"
    echo "  LOCAL_BUILD=true ./build_and_deploy.sh"
    echo ""
    echo "  # デバッグと anthropic プロバイダーでデプロイ"
    echo "  DEBUG=true LLM_PROVIDER=anthropic ./build_and_deploy.sh my_sre_agent"
    exit 0
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO_NAME="${1:-sre_agent}"
RUNTIME_NAME="${RUNTIME_NAME:-$ECR_REPO_NAME}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ] || [ -z "$AWS_ACCOUNT_ID" ] || [ "$AWS_ACCOUNT_ID" = "None" ]; then
    echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
    echo "エラー: $AWS_ACCOUNT_ID"
    exit 1
fi

ECR_REPO_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"

# Platform configuration (default to ARM64 for AgentCore)
PLATFORM="${PLATFORM:-arm64}"
LOCAL_BUILD="${LOCAL_BUILD:-false}"

# Get current caller identity and construct role ARN
CALLER_IDENTITY=$(aws sts get-caller-identity --output json)
CURRENT_ARN=$(echo $CALLER_IDENTITY | jq -r '.Arn')

# Extract role name from ARN and construct role ARN
# This handles both assumed-role and user scenarios
if [[ $CURRENT_ARN == *":assumed-role/"* ]]; then
    # 引き受けたロール ARN からロール名を抽出
    ROLE_NAME=$(echo $CURRENT_ARN | sed 's/.*:assumed-role\/\([^\/]*\).*/\1/')
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
else
    # 引き受けたロールで実行していない場合のデフォルトロール
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/BedrockAgentCoreRole"
    echo "⚠️  引き受けたロールで実行していません。デフォルトロールを使用します: $ROLE_ARN"
fi

# Allow override via environment variable
ROLE_ARN="${AGENT_ROLE_ARN:-$ROLE_ARN}"

echo "🔐 Amazon ECR にログイン中..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# リポジトリが存在しない場合は作成
echo "📦 ECR リポジトリが存在しない場合は作成中..."
aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" || \
    aws ecr create-repository --repository-name "$ECR_REPO_NAME" --region "$AWS_REGION"

# 使用する Dockerfile を決定し、ビルド環境をセットアップ
if [ "$PLATFORM" = "x86_64" ] || [ "$LOCAL_BUILD" = "true" ]; then
    echo "🏗️ linux/amd64 (x86_64) 用の Docker イメージをビルド中..."
    DOCKERFILE="$PARENT_DIR/Dockerfile.x86_64"
    # x86_64 ビルド用にプラットフォームを linux/amd64 に強制
    docker build --platform linux/amd64 -f "$DOCKERFILE" -t "$ECR_REPO_NAME" "$PARENT_DIR"
else
    # ARM64 エミュレーション用に QEMU をセットアップ
    echo "🔧 ARM64 エミュレーション用に QEMU をセットアップ中..."
    docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

    # ARM64 用の Docker イメージをビルド (Dockerfile はルートレベル)
    echo "🏗️ linux/arm64 用の Docker イメージをビルド中 (エミュレーションのため時間がかかる場合があります)..."
    DOCKERFILE="$PARENT_DIR/Dockerfile"
    # ARM64 用にプラットフォームを明示的に設定
    DOCKER_BUILDKIT=0 docker build --platform linux/arm64 -f "$DOCKERFILE" -t "$ECR_REPO_NAME" "$PARENT_DIR"
fi

# ローカルビルドの場合、ECR プッシュとデプロイをスキップ
if [ "$LOCAL_BUILD" = "true" ]; then
    echo "✅ ローカルイメージのビルドに成功しました: $ECR_REPO_NAME:latest"
    echo ""
    echo "📝 コンテナをローカルで実行するには:"
    echo "docker run -p 8080:8080 --env-file $PARENT_DIR/sre_agent/.env $ECR_REPO_NAME:latest"
    echo ""
    echo "または AWS 認証情報を使用 (bedrock プロバイダー - デフォルト):"
    echo "docker run -p 8080:8080 -v ~/.aws:/root/.aws:ro -e AWS_PROFILE=default -e GATEWAY_ACCESS_TOKEN=\$GATEWAY_ACCESS_TOKEN $ECR_REPO_NAME:latest"
    echo ""
    echo "または Anthropic プロバイダーを使用:"
    echo "docker run -p 8080:8080 -e LLM_PROVIDER=anthropic -e ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY -e GATEWAY_ACCESS_TOKEN=\$GATEWAY_ACCESS_TOKEN $ECR_REPO_NAME:latest"
    exit 0
fi

# イメージにタグ付け
echo "🏷️ イメージにタグ付け中..."
docker tag "$ECR_REPO_NAME":latest "$ECR_REPO_URI":latest

# イメージを ECR にプッシュ
echo "⬆️ イメージを ECR にプッシュ中..."
docker push "$ECR_REPO_URI":latest

echo "✅ イメージのビルドとプッシュに成功しました:"
echo "$ECR_REPO_URI:latest"

# コンテナ URI をスクリプトディレクトリのファイルに保存
echo "💾 コンテナ URI を .sre_agent_uri ファイルに保存中..."
echo "$ECR_REPO_URI:latest" > "$SCRIPT_DIR/.sre_agent_uri"
echo "コンテナ URI は $SCRIPT_DIR/.sre_agent_uri に保存されました"

# エージェントランタイムをデプロイ
echo ""
echo "🚀 エージェントランタイムをデプロイ中..."
echo "使用するロール ARN: $ROLE_ARN"
echo "使用するランタイム名: $RUNTIME_NAME"
echo "使用するリージョン: $AWS_REGION"

# .env ファイルが存在するか確認
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "❌ エラー: .env ファイルが見つかりません: $SCRIPT_DIR/.env"
    echo "ANTHROPIC_API_KEY と GATEWAY_ACCESS_TOKEN を含む .env ファイルを作成してください"
    echo "テンプレートとして .env.example を使用できます"
    exit 1
fi

echo ".env ファイルが見つかりました: $SCRIPT_DIR/.env"

# Deploy using the Python script
cd "$SCRIPT_DIR"

# 出力をキャプチャするための一時ファイルを作成
TEMP_OUTPUT=$(mktemp)

# 渡される環境変数をログ出力
echo "🔧 デプロイ用の環境変数:"
echo "   DEBUG: ${DEBUG:-未設定}"
echo "   LLM_PROVIDER: ${LLM_PROVIDER:-bedrock (デフォルト)}"
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "   ANTHROPIC_API_KEY: ***...${ANTHROPIC_API_KEY: -8}"
else
    echo "   ANTHROPIC_API_KEY: 未設定"
fi

# uv を使用するために親ディレクトリに移動
cd "$PARENT_DIR"

# Python スクリプトを実行し、戻り値と出力の両方をキャプチャ
# DEBUG、LLM_PROVIDER、ANTHROPIC_API_KEY 環境変数を渡す
if DEBUG="$DEBUG" LLM_PROVIDER="${LLM_PROVIDER:-bedrock}" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" uv run python deployment/deploy_agent_runtime.py \
    --container-uri "$ECR_REPO_URI:latest" \
    --role-arn "$ROLE_ARN" \
    --runtime-name "$RUNTIME_NAME" \
    --region "$AWS_REGION" \
    --force-recreate > "$TEMP_OUTPUT" 2>&1; then

    # 成功 - 出力を表示
    DEPLOY_OUTPUT=$(cat "$TEMP_OUTPUT")
    echo "$DEPLOY_OUTPUT"
else
    # 失敗 - エラー出力を表示して終了
    echo "❌ エージェントランタイムのデプロイに失敗しました！"
    echo "エラー出力:"
    cat "$TEMP_OUTPUT"
    rm -f "$TEMP_OUTPUT"
    exit 1
fi

# 一時ファイルをクリーンアップ
rm -f "$TEMP_OUTPUT"

echo ""
echo "🎉 ビルドとデプロイが完了しました！"
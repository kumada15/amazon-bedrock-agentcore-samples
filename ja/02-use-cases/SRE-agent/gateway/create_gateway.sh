#!/bin/bash

# DevOps Multi-Agent Demo Gateway Creation Script for Cognito
# Creates gateway with multiple OpenAPI targets for K8s, Logs, Metrics, and Runbooks APIs
# Uses allowedClients instead of allowedAudience for Cognito

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to generate UUID for bucket naming
_generate_bucket_name() {
    # Generate UUID and format as sreagent-{uuid}
    # Format complies with S3 naming restrictions:
    # - 3-63 characters
    # - lowercase letters, numbers, hyphens only
    # - starts and ends with letter/number
    if command -v uuidgen &> /dev/null; then
        # Use uuidgen if available (macOS, Linux with uuid-runtime)
        UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
    else
        # Fall back to Python for UUID generation
        UUID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
    fi
    echo "sreagent-${UUID}"
}

# Function to create S3 bucket if needed
_create_s3_bucket() {
    local bucket_name=$1
    local region=$2

    echo "S3 バケット設定を確認中..."

    # If bucket name is empty or contains placeholder text, create one
    if [ -z "$bucket_name" ] || [ "$bucket_name" = "your-agentcore-schemas-bucket" ] || [ "$bucket_name" = "your-bucket-name" ]; then
        echo "S3 バケットが設定されていません。自動的にバケットを作成中..."
        BUCKET_NAME=$(_generate_bucket_name)

        echo "S3 バケットを作成中: ${BUCKET_NAME}"

        # Create bucket with region-appropriate command
        if [ "$region" = "us-east-1" ]; then
            # us-east-1 doesn't need LocationConstraint
            if aws s3api create-bucket \
                --bucket "${BUCKET_NAME}" \
                --region "${region}"; then
                echo "S3 バケットの作成に成功しました: ${BUCKET_NAME}"
            else
                echo "S3 バケットの作成に失敗しました"
                exit 1
            fi
        else
            # Other regions need LocationConstraint
            if aws s3api create-bucket \
                --bucket "${BUCKET_NAME}" \
                --region "${region}" \
                --create-bucket-configuration LocationConstraint="${region}"; then
                echo "S3 バケットの作成に成功しました: ${BUCKET_NAME}"
            else
                echo "S3 バケットの作成に失敗しました"
                exit 1
            fi
        fi

        echo "${BUCKET_NAME}"
    else
        echo "設定済みの S3 バケットを使用: ${bucket_name}"
        echo "${bucket_name}"
    fi
}

# Check if config.yaml exists in the script directory
if [ ! -f "${SCRIPT_DIR}/config.yaml" ]; then
    echo "エラー: ${SCRIPT_DIR} に config.yaml が見つかりません！"
    echo "config.yaml.example から config.yaml を作成し、値を更新してください"
    exit 1
fi

# Function to read value from YAML
get_config() {
    local key=$1
    local line=$(grep "^${key}:" "${SCRIPT_DIR}/config.yaml" | cut -d':' -f2-)
    local result
    
    # Remove leading whitespace
    line=$(echo "$line" | sed 's/^[ \t]*//')
    
    # Handle quoted values - extract content between first pair of quotes, ignore comments after
    if echo "$line" | grep -q '^".*"'; then
        result=$(echo "$line" | sed 's/^"\([^"]*\)".*/\1/')
    else
        # Handle unquoted values - extract everything before comment or end of line, trim trailing whitespace
        result=$(echo "$line" | sed 's/[ \t]*#.*//' | sed 's/[ \t]*$//')
    fi
    
    # For critical AWS identifiers, remove all whitespace to prevent copy-paste errors
    case "$key" in
        account_id|role_name|user_pool_id|client_id|s3_bucket|credential_provider_name)
            result=$(echo "$result" | tr -d ' \t')
            ;;
    esac
    
    echo "$result"
}

# Read configuration from config.yaml
ACCOUNT_ID=$(get_config "account_id")
REGION=$(get_config "region")
ROLE_NAME=$(get_config "role_name")
ENDPOINT_URL=$(get_config "endpoint_url")
CREDENTIAL_PROVIDER_ENDPOINT_URL=$(get_config "credential_provider_endpoint_url")
USER_POOL_ID=$(get_config "user_pool_id")
CLIENT_ID=$(get_config "client_id")
S3_BUCKET=$(get_config "s3_bucket")
S3_PATH_PREFIX=$(get_config "s3_path_prefix")
PROVIDER_ARN=$(get_config "provider_arn")
GATEWAY_NAME=$(get_config "gateway_name")
GATEWAY_DESCRIPTION=$(get_config "gateway_description")
TARGET_DESCRIPTION=$(get_config "target_description")
CREDENTIAL_PROVIDER_NAME=$(get_config "credential_provider_name")

# Create S3 bucket if not configured, or use the configured one
S3_BUCKET=$(_create_s3_bucket "$S3_BUCKET" "$REGION" 2>/dev/null | tail -1)

# Extract Cognito region from User Pool ID (format: region_poolId)
COGNITO_REGION=$(echo "$USER_POOL_ID" | cut -d'_' -f1)

# Construct derived values using Cognito region instead of AWS region
DISCOVERY_URL="https://cognito-idp.${COGNITO_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration"

# Define API schema filenames
API_SCHEMAS=(
    "k8s_api.yaml"
    "logs_api.yaml"
    "metrics_api.yaml"
    "runbooks_api.yaml"
)

# Build S3 URIs dynamically from configuration
S3_URIS=()
for schema in "${API_SCHEMAS[@]}"; do
    S3_URIS+=("s3://${S3_BUCKET}/${S3_PATH_PREFIX}/${schema}")
done

# Define corresponding descriptions for each API
TARGET_DESCRIPTIONS=(
    "Kubernetes Analysis API for cluster monitoring and troubleshooting"
    "Application Logs API for log search and analysis"
    "Application Metrics API for performance monitoring"
    "DevOps Runbooks API for incident response and troubleshooting guides"
)

# Display configuration (with sensitive values partially hidden)
echo "config.yaml から設定を読み込みました:"
echo "  Gateway 名: ${GATEWAY_NAME}"
echo "  リージョン: ${REGION}"
echo "  アカウント ID: ${ACCOUNT_ID:0:4}****"
echo "  S3 バケット: ${S3_BUCKET} (未設定の場合は自動作成)"
echo "  S3 パスプレフィックス: ${S3_PATH_PREFIX}"
echo "  プロバイダー ARN: ${PROVIDER_ARN}"
echo ""

# Load environment variables from .env file
if [ -f "${SCRIPT_DIR}/.env" ]; then
    echo "環境変数を gateway/.env ファイルから読み込み中..."
    # Source the .env file safely
    set -a  # automatically export all variables
    source "${SCRIPT_DIR}/.env"
    set +a  # stop automatically exporting
else
    echo "警告: gateway ディレクトリに .env ファイルが見つかりません。config からデフォルトの API キーを使用します。"
fi

# Create credential provider with parameters
echo "API キー認証プロバイダーを作成中..."

# Check if BACKEND_API_KEY is set
if [ -z "$BACKEND_API_KEY" ]; then
    echo "エラー: 環境変数に BACKEND_API_KEY が見つかりません"
    echo ".env ファイルに BACKEND_API_KEY を設定してください"
    exit 1
fi

cd "${SCRIPT_DIR}"
if python create_credentials_provider.py \
    --credential-provider-name "${CREDENTIAL_PROVIDER_NAME}" \
    --api-key "${BACKEND_API_KEY}" \
    --region "${REGION}" \
    --endpoint-url "${CREDENTIAL_PROVIDER_ENDPOINT_URL}"; then
    echo "認証プロバイダーの作成に成功しました！"

    # Read the generated ARN from .credentials_provider file
    if [ -f "${SCRIPT_DIR}/.credentials_provider" ]; then
        GENERATED_PROVIDER_ARN=$(cat "${SCRIPT_DIR}/.credentials_provider")
        echo "生成されたプロバイダー ARN を使用: ${GENERATED_PROVIDER_ARN}"
        # Override the ARN from config with the generated one
        PROVIDER_ARN="${GENERATED_PROVIDER_ARN}"
    else
        echo "警告: .credentials_provider ファイルが見つかりません。config の ARN を使用します"
    fi
else
    echo "認証プロバイダーの作成に失敗しました"
    exit 1
fi

echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "AWS CLI がインストールされていないか、PATH に含まれていません"
    echo "OpenAPI スキーマファイルを S3 にアップロードするには AWS CLI をインストールしてください"
    exit 1
fi

# Upload OpenAPI schema files to S3
echo "OpenAPI スキーマファイルを S3 にアップロード中..."
OPENAPI_SPECS_DIR="${SCRIPT_DIR}/../backend/openapi_specs"

if [ ! -d "$OPENAPI_SPECS_DIR" ]; then
    echo "OpenAPI specs ディレクトリが見つかりません: $OPENAPI_SPECS_DIR"
    exit 1
fi

# Upload each schema file
upload_success=true
for schema in "${API_SCHEMAS[@]}"; do
    local_file="${OPENAPI_SPECS_DIR}/${schema}"
    s3_key="${S3_PATH_PREFIX}/${schema}"

    if [ ! -f "$local_file" ]; then
        echo "スキーマファイルが見つかりません: $local_file"
        upload_success=false
        continue
    fi

    file_size=$(ls -lh "$local_file" | awk '{print $5}')
    echo "${schema} (${file_size}) を s3://${S3_BUCKET}/${s3_key} にアップロード中"

    # Upload with metadata and force overwrite
    if aws s3 cp "$local_file" "s3://${S3_BUCKET}/${s3_key}" \
        --region "${REGION}" \
        --metadata "source=sre-agent,timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --content-type "application/x-yaml"; then
        echo "${schema} のアップロードに成功しました"
    else
        echo "${schema} のアップロードに失敗しました"
        upload_success=false
    fi
done

if [ "$upload_success" = false ]; then
    echo "一部のファイルのアップロードに失敗しました。AWS 認証情報と S3 バケットの権限を確認してください。"
    exit 1
fi

echo "すべての OpenAPI スキーマファイルのアップロードに成功しました！"
echo ""

# Generate Cognito access token
echo "Cognito アクセストークンを生成中..."
echo ".env ファイルに COGNITO_* 変数が設定されていることを確認してください"
cd "${SCRIPT_DIR}"
python generate_token.py

echo ""
# Build the command with multiple S3 URIs and descriptions
echo "DevOps マルチエージェントデモ用に複数の S3 ターゲットを持つ AgentCore Gateway を作成中..."
echo "設定する API:"
for i in "${!S3_URIS[@]}"; do
    api_name=$(basename "${S3_URIS[$i]}" .yaml)
    echo "  $((i+1)). ${api_name^^} API: ${S3_URIS[$i]}"
done
echo ""

# Construct the command with all S3 URIs and descriptions
CMD=(python main.py "${GATEWAY_NAME}")
CMD+=(--region "${REGION}")
CMD+=(--endpoint-url "${ENDPOINT_URL}")
CMD+=(--role-arn "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}")
CMD+=(--discovery-url "${DISCOVERY_URL}")
CMD+=(--allowed-clients "${CLIENT_ID}")
CMD+=(--description-for-gateway "${GATEWAY_DESCRIPTION}")

# Add all S3 URIs
for s3_uri in "${S3_URIS[@]}"; do
    CMD+=(--s3-uri "${s3_uri}")
done

# Add all target descriptions
for description in "${TARGET_DESCRIPTIONS[@]}"; do
    CMD+=(--description-for-target "${description}")
done

# Add remaining flags
CMD+=(--create-s3-target)
CMD+=(--provider-arn "${PROVIDER_ARN}")
CMD+=(--save-gateway-url)
CMD+=(--delete-gateway-if-exists)
CMD+=(--output-json)

# Execute the command
echo "コマンドを実行中:"
echo "${CMD[@]}"
echo ""
cd "${SCRIPT_DIR}"
"${CMD[@]}"

echo ""
echo "アクセストークンを .access_token に保存しました"
echo "Gateway URL を .gateway_uri に保存しました"
echo "DevOps マルチエージェントデモ Gateway の作成が完了しました！"
echo ""
echo "概要:"
echo "   - S3 にアップロードした OpenAPI スキーマ: ${#API_SCHEMAS[@]} ファイル"
echo "   - ${#S3_URIS[@]} 個の API ターゲットを持つ Gateway を作成"
echo "   - API: Kubernetes, Logs, Metrics, Runbooks"
echo "   - すべてのターゲットは Cognito 認証で設定済み"
echo "   - AgentCore Gateway との MCP 統合の準備完了"
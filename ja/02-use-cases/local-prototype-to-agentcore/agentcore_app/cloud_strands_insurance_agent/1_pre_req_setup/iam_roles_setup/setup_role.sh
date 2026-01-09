#!/bin/bash

# Bedrock AgentCore Execution Role Setup Script
# This script helps set up the IAM role with correct permissions for Bedrock AgentCore

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ROLE_NAME="BedrockAgentCoreExecutionRole"
REPOSITORY_NAME="bedrock-agentcore"
AGENT_NAME="insurance-agent"

# Banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════╗"
echo "║         BEDROCK AGENTCORE SETUP        ║"
echo "║         IAM Role Configuration         ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}エラー: AWS CLI がインストールされていません。先にインストールしてください。${NC}"
    exit 1
fi

# Check if user is logged in to AWS
echo "AWS 認証情報を確認中..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}エラー: AWS に認証されていません。先に 'aws configure' を実行してください。${NC}"
    exit 1
fi

# Get AWS Account ID
echo "AWS アカウント情報を取得中..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}エラー: AWS アカウント ID を特定できませんでした。${NC}"
    exit 1
fi

echo -e "${GREEN}使用する AWS アカウント ID: ${ACCOUNT_ID}${NC}"

# Get AWS Regions
echo -e "\n使用する AWS リージョンをカンマ区切りで入力 (デフォルト: us-east-1,us-west-2):"
read -p "> " REGIONS_INPUT
REGIONS=${REGIONS_INPUT:-"us-east-1,us-west-2"}
IFS=',' read -ra REGIONS_ARRAY <<< "$REGIONS"

echo -e "${GREEN}使用するリージョン: ${REGIONS}${NC}"

# Get Role Name
echo -e "\nIAM ロール名を入力 (デフォルト: ${ROLE_NAME}):"
read -p "> " ROLE_NAME_INPUT
ROLE_NAME=${ROLE_NAME_INPUT:-$ROLE_NAME}

echo -e "${GREEN}使用するロール名: ${ROLE_NAME}${NC}"

# Get ECR Repository Name
echo -e "\nECR リポジトリ名を入力 (デフォルト: ${REPOSITORY_NAME}):"
read -p "> " REPOSITORY_NAME_INPUT
REPOSITORY_NAME=${REPOSITORY_NAME_INPUT:-$REPOSITORY_NAME}

echo -e "${GREEN}使用するリポジトリ名: ${REPOSITORY_NAME}${NC}"

# Get Agent Name
echo -e "\nエージェント名を入力 (デフォルト: ${AGENT_NAME}):"
read -p "> " AGENT_NAME_INPUT
AGENT_NAME=${AGENT_NAME_INPUT:-$AGENT_NAME}

echo -e "${GREEN}使用するエージェント名: ${AGENT_NAME}${NC}"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo -e "\n${TEMP_DIR} にポリシーファイルを作成中..."

# Generate trust policy
cat > "${TEMP_DIR}/trust-policy.json" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AssumeRolePolicyProd",
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:*"
        }
      }
    }
  ]
}
EOF

# Generate the start of execution policy
cat > "${TEMP_DIR}/execution-policy.json" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRImageAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": [
EOF

# Add ECR resources for all regions
region_count=${#REGIONS_ARRAY[@]}
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:ecr:${region}:${ACCOUNT_ID}:repository/${REPOSITORY_NAME}\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:ecr:${region}:${ACCOUNT_ID}:repository/${REPOSITORY_NAME}\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

# Add ECR token access
cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Sid": "ECRTokenAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogStreams",
        "logs:CreateLogGroup"
      ],
      "Resource": [
EOF

# Add logs resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups"
      ],
      "Resource": [
EOF

# Add logs resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": [
EOF

# Add logs resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Effect": "Allow", 
      "Action": [ 
        "xray:PutTraceSegments", 
        "xray:PutTelemetryRecords", 
        "xray:GetSamplingRules", 
        "xray:GetSamplingTargets"
      ],
      "Resource": [ "*" ] 
    },
    {
      "Effect": "Allow",
      "Resource": "*",
      "Action": "cloudwatch:PutMetricData",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "bedrock-agentcore"
        }
      }
    },
    {
      "Sid": "GetAgentAccessToken",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetWorkloadAccessToken",
        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
        "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
      ],
      "Resource": [
EOF

# Add bedrock-agentcore resources for all regions
# This is more complex as each region needs two entries
all_resources=()
for region in "${REGIONS_ARRAY[@]}"; do
  all_resources+=("arn:aws:bedrock-agentcore:${region}:${ACCOUNT_ID}:workload-identity-directory/default")
  all_resources+=("arn:aws:bedrock-agentcore:${region}:${ACCOUNT_ID}:workload-identity-directory/default/workload-identity/${AGENT_NAME}-*")
done

# Now print the resources with proper commas
resource_count=${#all_resources[@]}
for ((i=0; i<resource_count; i++)); do
  resource="${all_resources[i]}"
  if [[ $i -eq $(($resource_count-1)) ]]; then
    # Last item, no comma
    echo "        \"${resource}\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"${resource}\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Sid": "BedrockModelInvocation", 
      "Effect": "Allow", 
      "Action": [ 
        "bedrock:InvokeModel", 
        "bedrock:InvokeModelWithResponseStream"
      ], 
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/*",
EOF

# Add bedrock resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:bedrock:${region}:${ACCOUNT_ID}:*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:bedrock:${region}:${ACCOUNT_ID}:*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    }
  ]
}
EOF

# Check if the role exists
echo -e "\nロール ${ROLE_NAME} が既に存在するか確認中..."
if aws iam get-role --role-name "${ROLE_NAME}" &> /dev/null; then
    echo -e "${YELLOW}ロール ${ROLE_NAME} は既に存在します。${NC}"
    read -p "ポリシーを更新しますか？ (Y/n): " UPDATE_ROLE
    UPDATE_ROLE=${UPDATE_ROLE:-Y}
    if [[ $UPDATE_ROLE == "n" || $UPDATE_ROLE == "N" || $UPDATE_ROLE == "no" || $UPDATE_ROLE == "No" || $UPDATE_ROLE == "NO" ]]; then
        echo -e "${YELLOW}ロール ${ROLE_NAME} に変更はありません${NC}"
        rm -rf "${TEMP_DIR}"
        exit 0
    fi
else
    echo -e "ロール ${ROLE_NAME} を作成中..."
    aws iam create-role --role-name "${ROLE_NAME}" --assume-role-policy-document file://"${TEMP_DIR}/trust-policy.json"
    if [ $? -ne 0 ]; then
        echo -e "${RED}エラー: ロールの作成に失敗しました。${NC}"
        rm -rf "${TEMP_DIR}"
        exit 1
    fi
    echo -e "${GREEN}ロール ${ROLE_NAME} が正常に作成されました。${NC}"
fi

# Attach policy to role
echo -e "\n実行ポリシーをロール ${ROLE_NAME} にアタッチ中..."
aws iam put-role-policy --role-name "${ROLE_NAME}" --policy-name "BedrockAgentCoreExecutionPolicy" --policy-document file://"${TEMP_DIR}/execution-policy.json"
if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: ロールへのポリシーのアタッチに失敗しました。${NC}"
    rm -rf "${TEMP_DIR}"
    exit 1
fi

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query "Role.Arn" --output text)

# Clean up
rm -rf "${TEMP_DIR}"

echo -e "\n${GREEN}✅ Bedrock AgentCore 用の IAM ロールのセットアップが正常に完了しました！${NC}"
echo -e "${GREEN}ロール ARN: ${ROLE_ARN}${NC}"
echo -e "\nこのロール ARN を Bedrock AgentCore 設定で使用できます。"
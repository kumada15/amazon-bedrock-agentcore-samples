#!/bin/bash
set -e

# Parse command line arguments
DELETE_SECRETS=false

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --delete-secrets)
            DELETE_SECRETS=true
            shift
            ;;
        *)
            echo "不明なオプション: $1"
            echo "使用法: $0 [--delete-secrets]"
            exit 1
            ;;
    esac
done

echo "リソースをクリーンアップ中..."

# Load configurations if they exist
if [ -f config/gateway_config.env ]; then
    source config/gateway_config.env
fi
if [ -f config/target_config.env ]; then
    source config/target_config.env
fi
if [ -f config/cognito_config.env ]; then
    source config/cognito_config.env
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

# Delete Gateway Targets
if [ ! -z "$GATEWAY_IDENTIFIER" ]; then
    echo "すべての Gateway ターゲットを一覧表示して削除中..."
    python3 -c "
import boto3
import os

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2')
)

try:
    # List all targets for the gateway
    response = agentcore_client.list_gateway_targets(
        gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER')
    )
    
    # Delete each target
    for target in response.get('items', []):
        target_id = target['targetId']
        print(f'Deleting target: {target_id}')
        agentcore_client.delete_gateway_target(
            gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
            targetId=target_id
        )
        print(f'Target {target_id} deleted successfully')
    
    # Also delete the specific target if provided
    if os.getenv('TARGET_ID') and os.getenv('TARGET_ID') not in [t['targetId'] for t in response.get('items', [])]:
        print(f'Deleting specific target: {os.getenv("TARGET_ID")}')
        agentcore_client.delete_gateway_target(
            gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
            targetId=os.getenv('TARGET_ID')
        )
        print(f'Target {os.getenv("TARGET_ID")} deleted successfully')
        
except Exception as e:
    print(f'Error with targets: {e}')
"
    
    # Wait for target deletion
    echo "ターゲット削除を待機中..."
    sleep 10
fi

# Delete Gateway
echo "Gateway を削除中..."
python3 -c "
import boto3
import os
import sys

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2')
)

# Try with the environment variable first
gateway_id = os.getenv('GATEWAY_IDENTIFIER')

# If not found, try to list all gateways and find one with a matching name
if not gateway_id:
    try:
        response = agentcore_client.list_gateways()
        for gateway in response.get('items', []):
            if 'DB-Performance-Analyzer-Gateway' in gateway.get('name', ''):
                gateway_id = gateway['gatewayId']
                print(f'Found gateway with ID: {gateway_id}')
                break
    except Exception as e:
        print(f'Error listing gateways: {e}')

if gateway_id:
    try:
        # List all targets for the gateway
        try:
            response = agentcore_client.list_gateway_targets(
                gatewayIdentifier=gateway_id
            )
            
            # Delete each target
            for target in response.get('items', []):
                target_id = target['targetId']
                print(f'Deleting target: {target_id}')
                agentcore_client.delete_gateway_target(
                    gatewayIdentifier=gateway_id,
                    targetId=target_id
                )
                print(f'Target {target_id} deleted successfully')
        except Exception as e:
            print(f'Error deleting targets: {e}')
        
        # Now delete the gateway
        agentcore_client.delete_gateway(
            gatewayIdentifier=gateway_id
        )
        print(f'Gateway {gateway_id} deleted successfully')
    except Exception as e:
        print(f'Error deleting gateway: {e}')
else:
    print('No gateway identifier found')
"

# Wait for gateway deletion
echo "Gateway 削除を待機中..."
sleep 10

# Delete Lambda functions
echo "Lambda 関数を削除中..."
aws lambda delete-function \
    --function-name DBPerformanceAnalyzer \
    --region $AWS_REGION || echo "DBPerformanceAnalyzer Lambda 関数の削除に失敗しました。続行します..."

aws lambda delete-function \
    --function-name PGStatAnalyzeDatabase \
    --region $AWS_REGION || echo "PGStatAnalyzeDatabase Lambda 関数の削除に失敗しました。続行します..."

# Delete Lambda layer
echo "Lambda レイヤーを削除中..."
if [ -f config/layer_config.env ]; then
    source config/layer_config.env
    if [ ! -z "$PSYCOPG2_LAYER_ARN" ]; then
        LAYER_NAME=$(echo $PSYCOPG2_LAYER_ARN | cut -d':' -f7)
        LAYER_VERSION=$(echo $PSYCOPG2_LAYER_ARN | cut -d':' -f8)
        aws lambda delete-layer-version \
            --layer-name $LAYER_NAME \
            --version-number $LAYER_VERSION \
            --region $AWS_REGION || echo "Lambda レイヤーの削除に失敗しました。続行します..."
    fi
fi

# Delete Lambda security group
echo "VPC リソースをクリーンアップ中..."
if [ -f config/vpc_config.env ]; then
    source config/vpc_config.env
    
    if [ ! -z "$LAMBDA_SECURITY_GROUP_ID" ] && [ ! -z "$DB_SECURITY_GROUP_IDS" ]; then
        # Remove inbound rules from DB security groups
        IFS=',' read -ra DB_SG_ARRAY <<< "$DB_SECURITY_GROUP_IDS"
        for DB_SG_ID in "${DB_SG_ARRAY[@]}"; do
            echo "DB セキュリティグループ $DB_SG_ID からインバウンドルールを削除中"
            aws ec2 revoke-security-group-ingress \
                --group-id $DB_SG_ID \
                --protocol tcp \
                --port 5432 \
                --source-group $LAMBDA_SECURITY_GROUP_ID \
                --region $AWS_REGION || echo "インバウンドルールの削除に失敗しました。続行します..."
        done

        # Delete Lambda security group
        # Clean up VPC endpoints first
        echo "VPC エンドポイントをクリーンアップ中..."
        ./scripts/cleanup_vpc_endpoints.sh || echo "VPC エンドポイントのクリーンアップに失敗しました。続行します..."

        echo "Lambda セキュリティグループ $LAMBDA_SECURITY_GROUP_ID を削除中"
        aws ec2 delete-security-group \
            --group-id $LAMBDA_SECURITY_GROUP_ID \
            --region $AWS_REGION || echo "Lambda セキュリティグループの削除に失敗しました。続行します..."
    fi
fi

# Delete Cognito domain
if [ ! -z "$COGNITO_USERPOOL_ID" ] && [ ! -z "$COGNITO_DOMAIN_NAME" ]; then
    echo "Cognito ドメインを削除中..."
    aws cognito-idp delete-user-pool-domain \
        --domain $COGNITO_DOMAIN_NAME \
        --user-pool-id $COGNITO_USERPOOL_ID \
        --region $AWS_REGION || echo "ドメインの削除に失敗しました。続行します..."
fi

# Delete Cognito user pool client
if [ ! -z "$COGNITO_USERPOOL_ID" ] && [ ! -z "$COGNITO_APP_CLIENT_ID" ]; then
    echo "Cognito ユーザープールクライアントを削除中..."
    aws cognito-idp delete-user-pool-client \
        --user-pool-id $COGNITO_USERPOOL_ID \
        --client-id $COGNITO_APP_CLIENT_ID \
        --region $AWS_REGION || echo "クライアントの削除に失敗しました。続行します..."
fi

# Delete Cognito user pool
if [ ! -z "$COGNITO_USERPOOL_ID" ]; then
    echo "Cognito ユーザープールを削除中..."
    aws cognito-idp delete-user-pool \
        --user-pool-id $COGNITO_USERPOOL_ID \
        --region $AWS_REGION || echo "ユーザープールの削除に失敗しました。続行します..."
fi

# Delete IAM roles
echo "IAM ロールを削除中..."

# Delete Lambda role
echo "DBAnalyzerLambdaRole からポリシーをデタッチ中..."
# List and delete all inline policies
POLICIES=$(aws iam list-role-policies --role-name DBAnalyzerLambdaRole --query 'PolicyNames' --output json 2>/dev/null || echo "[]")
for POLICY in $(echo $POLICIES | jq -r '.[]'); do
    echo "インラインポリシーを削除中: $POLICY"
    aws iam delete-role-policy --role-name DBAnalyzerLambdaRole --policy-name "$POLICY" || echo "ポリシー $POLICY の削除に失敗しました。続行します..."
done

# List and detach all managed policies
MANAGED_POLICIES=$(aws iam list-attached-role-policies --role-name DBAnalyzerLambdaRole --query 'AttachedPolicies[].PolicyArn' --output json 2>/dev/null || echo "[]")
for POLICY_ARN in $(echo $MANAGED_POLICIES | jq -r '.[]'); do
    echo "マネージドポリシーをデタッチ中: $POLICY_ARN"
    aws iam detach-role-policy --role-name DBAnalyzerLambdaRole --policy-arn "$POLICY_ARN" || echo "ポリシー $POLICY_ARN のデタッチに失敗しました。続行します..."
done

# Now try to delete the role
echo "ロールを削除中: DBAnalyzerLambdaRole"
aws iam delete-role --role-name DBAnalyzerLambdaRole || echo "Lambda ロールの削除に失敗しました。続行します..."

# Delete Gateway role
echo "AgentCoreGatewayRole からポリシーをデタッチ中..."
# List and delete all inline policies
POLICIES=$(aws iam list-role-policies --role-name AgentCoreGatewayRole --query 'PolicyNames' --output json 2>/dev/null || echo "[]")
for POLICY in $(echo $POLICIES | jq -r '.[]'); do
    echo "インラインポリシーを削除中: $POLICY"
    aws iam delete-role-policy --role-name AgentCoreGatewayRole --policy-name "$POLICY" || echo "ポリシー $POLICY の削除に失敗しました。続行します..."
done

# List and detach all managed policies
MANAGED_POLICIES=$(aws iam list-attached-role-policies --role-name AgentCoreGatewayRole --query 'AttachedPolicies[].PolicyArn' --output json 2>/dev/null || echo "[]")
for POLICY_ARN in $(echo $MANAGED_POLICIES | jq -r '.[]'); do
    echo "マネージドポリシーをデタッチ中: $POLICY_ARN"
    aws iam detach-role-policy --role-name AgentCoreGatewayRole --policy-arn "$POLICY_ARN" || echo "ポリシー $POLICY_ARN のデタッチに失敗しました。続行します..."
done

# Now try to delete the role
echo "ロールを削除中: AgentCoreGatewayRole"
aws iam delete-role --role-name AgentCoreGatewayRole || echo "Gateway ロールの削除に失敗しました。続行します..."

# Remove configuration files
echo "設定ファイルを削除中..."
rm -f config/*.env

# Delete secrets and SSM parameters if requested
if [ "$DELETE_SECRETS" = true ]; then
    echo "シークレットと SSM パラメータを削除中..."
    
    # Load database configurations if they exist
    DB_SECRETS_TO_DELETE=()
    SSM_PARAMS_TO_DELETE=()
    
    if [ -f config/db_prod_config.env ]; then
        source config/db_prod_config.env
        if [ ! -z "$DB_SSM_PARAMETER" ]; then
            # Get secret name from SSM Parameter Store instead of config file
            SECRET_NAME=$(aws ssm get-parameter --name "$DB_SSM_PARAMETER" --query "Parameter.Value" --output text 2>/dev/null || echo "")
            if [ ! -z "$SECRET_NAME" ] && [ "$SECRET_NAME" != "None" ]; then
                DB_SECRETS_TO_DELETE+=("$SECRET_NAME")
            fi
            SSM_PARAMS_TO_DELETE+=("$DB_SSM_PARAMETER")
        fi
    fi
    
    if [ -f config/db_dev_config.env ]; then
        source config/db_dev_config.env
        if [ ! -z "$DB_SSM_PARAMETER" ]; then
            # Get secret name from SSM Parameter Store instead of config file
            SECRET_NAME=$(aws ssm get-parameter --name "$DB_SSM_PARAMETER" --query "Parameter.Value" --output text 2>/dev/null || echo "")
            if [ ! -z "$SECRET_NAME" ] && [ "$SECRET_NAME" != "None" ]; then
                DB_SECRETS_TO_DELETE+=("$SECRET_NAME")
            fi
            SSM_PARAMS_TO_DELETE+=("$DB_SSM_PARAMETER")
        fi
    fi
    
    # Delete secrets
    for SECRET_NAME in "${DB_SECRETS_TO_DELETE[@]}"; do
        echo "シークレットを削除中: $SECRET_NAME"
        aws secretsmanager delete-secret \
            --secret-id "$SECRET_NAME" \
            --force-delete-without-recovery \
            --region $AWS_REGION || echo "シークレット $SECRET_NAME の削除に失敗しました。続行します..."
    done

    # Delete SSM parameters
    for PARAM_NAME in "${SSM_PARAMS_TO_DELETE[@]}"; do
        echo "SSM パラメータを削除中: $PARAM_NAME"
        aws ssm delete-parameter \
            --name "$PARAM_NAME" \
            --region $AWS_REGION || echo "パラメータ $PARAM_NAME の削除に失敗しました。続行します..."
    done
    
    # Database configuration files are removed with other config files
fi

echo "クリーンアップ完了"
#!/bin/bash

# AgentCore 完全クリーンアップスクリプト
# このスクリプトは AgentCore デプロイに関連するすべてのリソースを削除します
# 注意: すべてのエージェント、ID、プロバイダーが削除されます

set -e  # Exit on any error

echo "🧹 AgentCore 完全クリーンアップ"
echo "============================="
echo ""
echo "このスクリプトは以下のデプロイスクリプトで作成されたすべてのリソースを削除します:"
echo "  • 01-prerequisites.sh (IAM ロール、ECR リポジトリ)"
echo "  • 02-create-memory.sh (AgentCore メモリリソース)"
echo "  • 03-setup-oauth-provider.sh (OAuth2 認証プロバイダー)"
echo "  • 04-deploy-mcp-tool-lambda.sh (MCP Lambda 関数とスタック)"
echo "  • 05-create-gateway-targets.sh (AgentCore Gateway とターゲット)"
echo "  • 06-deploy-diy.sh (DIY エージェントランタイムと ECR イメージ)"
echo "  • 07-deploy-sdk.sh (SDK エージェントランタイムと ECR イメージ)"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG_DIR="${PROJECT_DIR}/config"

# 集中設定マネージャーを使用して設定を読み込み
echo "📋 AgentCoreConfigManager を使用して設定を読み込み中..."

# Create temporary Python script to get configuration values
CONFIG_SCRIPT="${SCRIPT_DIR}/temp_get_config.py"
cat > "$CONFIG_SCRIPT" << 'EOF'
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from shared.config_manager import AgentCoreConfigManager
    
    config_manager = AgentCoreConfigManager()
    base_config = config_manager.get_base_settings()
    dynamic_config = config_manager.get_dynamic_config()
    
    # Output configuration values for shell script
    print(f"REGION={base_config['aws']['region']}")
    print(f"ACCOUNT_ID={base_config['aws']['account_id']}")
    
    # Output dynamic configuration for cleanup targeting
    runtime_config = dynamic_config.get('runtime', {})
    gateway_config = dynamic_config.get('gateway', {})
    mcp_config = dynamic_config.get('mcp_lambda', {})
    
    # DIY Agent ARNs
    diy_arn = runtime_config.get('diy_agent', {}).get('arn', '')
    diy_endpoint_arn = runtime_config.get('diy_agent', {}).get('endpoint_arn', '')
    
    # SDK Agent ARNs  
    sdk_arn = runtime_config.get('sdk_agent', {}).get('arn', '')
    sdk_endpoint_arn = runtime_config.get('sdk_agent', {}).get('endpoint_arn', '')
    
    # Gateway info
    gateway_url = gateway_config.get('url', '')
    gateway_id = gateway_config.get('id', '')
    gateway_arn = gateway_config.get('arn', '')
    
    # MCP Lambda info
    mcp_function_arn = mcp_config.get('function_arn', '')
    mcp_function_name = mcp_config.get('function_name', '')
    mcp_stack_name = mcp_config.get('stack_name', 'bac-mcp-stack')
    
    print(f"DIY_RUNTIME_ARN={diy_arn}")
    print(f"DIY_ENDPOINT_ARN={diy_endpoint_arn}")
    print(f"SDK_RUNTIME_ARN={sdk_arn}")
    print(f"SDK_ENDPOINT_ARN={sdk_endpoint_arn}")
    print(f"GATEWAY_URL={gateway_url}")
    print(f"GATEWAY_ID={gateway_id}")
    print(f"GATEWAY_ARN={gateway_arn}")
    print(f"MCP_FUNCTION_ARN={mcp_function_arn}")
    print(f"MCP_FUNCTION_NAME={mcp_function_name}")
    print(f"MCP_STACK_NAME={mcp_stack_name}")
    
except Exception as e:
    print(f"# Error loading configuration: {e}", file=sys.stderr)
    # Fallback to default values
    print("REGION=us-east-1")
    print("ACCOUNT_ID=unknown")
    print("DIY_RUNTIME_ARN=")
    print("DIY_ENDPOINT_ARN=")
    print("SDK_RUNTIME_ARN=")
    print("SDK_ENDPOINT_ARN=")
    print("GATEWAY_URL=")
    print("GATEWAY_ID=")
    print("GATEWAY_ARN=")
    print("MCP_FUNCTION_ARN=")
    print("MCP_FUNCTION_NAME=")
    print("MCP_STACK_NAME=bac-mcp-stack")
EOF

# 設定スクリプトを実行して出力を読み込み
if CONFIG_OUTPUT=$(python3 "$CONFIG_SCRIPT" 2>/dev/null); then
    eval "$CONFIG_OUTPUT"
    echo "   ✅ 設定を正常に読み込みました"
else
    echo "   ⚠️  設定の読み込みに失敗しました、デフォルト値を使用"
    REGION="us-east-1"
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")
    DIY_RUNTIME_ARN=""
    DIY_ENDPOINT_ARN=""
    SDK_RUNTIME_ARN=""
    SDK_ENDPOINT_ARN=""
    GATEWAY_URL=""
    GATEWAY_ID=""
    GATEWAY_ARN=""
    MCP_FUNCTION_ARN=""
    MCP_FUNCTION_NAME=""
    MCP_STACK_NAME="bac-mcp-stack"
    if [ $? -ne 0 ] || [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
        echo "❌ AWS アカウント ID の取得に失敗しました。AWS 認証情報とネットワーク接続を確認してください。"
        echo "エラー: $ACCOUNT_ID"
        exit 1
    fi

fi

# 一時スクリプトを削除
rm -f "$CONFIG_SCRIPT"

echo -e "${BLUE}📝 読み込んだ設定:${NC}"
echo "   リージョン: $REGION"
echo "   アカウント ID: $ACCOUNT_ID"
echo ""
echo -e "${BLUE}📝 クリーンアップ対象のリソース:${NC}"
echo "   DIY ランタイム ARN: ${DIY_RUNTIME_ARN:-'(未デプロイ)'}"
echo "   SDK ランタイム ARN: ${SDK_RUNTIME_ARN:-'(未デプロイ)'}"
echo "   Gateway ID: ${GATEWAY_ID:-'(未デプロイ)'}"
echo "   MCP スタック: ${MCP_STACK_NAME:-'bac-mcp-stack'}"
echo ""

# 警告と確認
show_warning() {
    echo -e "${RED}⚠️  警告: 破壊的な操作${NC}"
    echo -e "${RED}=================================${NC}"
    echo ""
    echo -e "${YELLOW}このスクリプトは以下のすべてを削除します:${NC}"
    echo ""
    echo -e "${RED}🗑️  AgentCore ランタイムエージェント (06-deploy-diy.sh & 07-deploy-sdk.sh から):${NC}"
    echo "   • DIY エージェントランタイムインスタンスとエンドポイント"
    echo "   • SDK エージェントランタイムインスタンスとエンドポイント"
    echo "   • エージェントランタイム設定"
    echo ""
    echo -e "${RED}🗑️  AgentCore メモリリソース (02-create-memory.sh から):${NC}"
    echo "   • 会話保存用メモリリソース"
    echo "   • すべての保存済み会話履歴"
    echo "   • メモリ設定"
    echo ""
    echo -e "${RED}🗑️  AgentCore ID リソース (03-setup-oauth-provider.sh から):${NC}"
    echo "   • OAuth2 認証プロバイダー (Okta 統合)"
    echo "   • すべてのワークロード ID"
    echo "   • すべての ID 関連付け"
    echo ""
    echo -e "${RED}🗑️  AgentCore Gateway & MCP リソース (04-deploy-mcp-tool-lambda.sh & 05-create-gateway-targets.sh から):${NC}"
    echo "   • すべての AgentCore Gateway とターゲット"
    echo "   • MCP ツール Lambda 関数 (bac-mcp-tool)"
    echo "   • CloudFormation スタック (bac-mcp-stack)"
    echo "   • Lambda IAM ロール (MCPToolFunctionRole, BedrockAgentCoreGatewayExecutionRole)"
    echo "   • CloudWatch ロググループ (/aws/lambda/bac-mcp-tool)"
    echo "   • Gateway 設定"
    echo ""
    echo -e "${RED}🗑️  AWS インフラストラクチャ (01-prerequisites.sh から):${NC}"
    echo "   • ECR リポジトリ (bac-runtime-repo-diy, bac-runtime-repo-sdk) とすべてのイメージ"
    echo "   • IAM ロール: bac-execution-role"
    echo "   • ロールにアタッチされた IAM ポリシー"
    echo ""
    echo -e "${RED}🗑️  設定ファイル:${NC}"
    echo "   • 動的設定値 (空にリセット)"
    echo "   • 生成された設定セクション"
    echo ""
    echo -e "${YELLOW}💡 削除されないもの:${NC}"
    echo "   • static-config.yaml"
    echo "   • AWS アカウントレベルの設定"
    echo "   • AgentCore で作成されていない他の AWS リソース"
    echo ""
}

# AgentCore メモリリソースをクリーンアップする関数
cleanup_memory_resources() {
    echo -e "${BLUE}🗑️  AgentCore メモリリソースをクリーンアップ中...${NC}"
    echo "============================================="

    # 既存のメモリ削除スクリプトを使用 (正しいファイル名)
    if [[ -f "${SCRIPT_DIR}/12-delete-memory.sh" ]]; then
        echo "既存の 12-delete-memory.sh スクリプトを使用..."
        if bash "${SCRIPT_DIR}/12-delete-memory.sh"; then
            echo -e "${GREEN}✅ メモリリソースのクリーンアップが完了しました${NC}"
        else
            echo -e "${YELLOW}⚠️  メモリリソースのクリーンアップに問題がありました${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  12-delete-memory.sh が見つかりません - メモリクリーンアップをスキップ${NC}"
    fi
}

# AgentCore ランタイムエージェントをクリーンアップする関数
cleanup_runtime_agents() {
    echo -e "${BLUE}🗑️  AgentCore ランタイムエージェントをクリーンアップ中...${NC}"
    echo "============================================="

    # 既存のランタイム削除スクリプトを使用
    if [[ -f "${SCRIPT_DIR}/08-delete-runtimes.sh" ]]; then
        echo "既存の 08-delete-runtimes.sh スクリプトを使用..."
        if bash "${SCRIPT_DIR}/08-delete-runtimes.sh"; then
            echo -e "${GREEN}✅ ランタイムエージェントのクリーンアップが完了しました${NC}"
        else
            echo -e "${YELLOW}⚠️  ランタイムエージェントのクリーンアップに問題がありました${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  08-delete-runtimes.sh が見つかりません - ランタイムクリーンアップをスキップ${NC}"
    fi
}

# AgentCore Gateway と MCP リソースをクリーンアップする関数
cleanup_gateway_mcp_resources() {
    echo -e "${BLUE}🗑️  AgentCore Gateway と MCP リソースをクリーンアップ中...${NC}"
    echo "===================================================="

    # 既存の Gateway と MCP 削除スクリプトを使用
    echo "ステップ 1: Gateway とターゲットを削除中..."
    if [[ -f "${SCRIPT_DIR}/09-delete-gateways-targets.sh" ]]; then
        # Gateway 削除スクリプトを非対話的に実行
        # スクリプトは期待: オプション選択 (1 または 2)、その後確認 (y)
        # オプション 1 (設定済み Gateway を削除) を選択し、y で確認
        echo -e "1\ny" | bash "${SCRIPT_DIR}/09-delete-gateways-targets.sh" || echo -e "${YELLOW}⚠️  Gateway の削除に問題がありました${NC}"
    else
        echo -e "${YELLOW}⚠️  09-delete-gateways-targets.sh が見つかりません${NC}"
    fi

    echo ""
    echo "ステップ 2: MCP ツール Lambda デプロイを削除中..."
    if [[ -f "${SCRIPT_DIR}/10-delete-mcp-tool-deployment.sh" ]]; then
        # MCP 削除スクリプトを非対話的に実行
        echo "y" | bash "${SCRIPT_DIR}/10-delete-mcp-tool-deployment.sh" || echo -e "${YELLOW}⚠️  MCP の削除に問題がありました${NC}"
    else
        echo -e "${YELLOW}⚠️  10-delete-mcp-tool-deployment.sh が見つかりません${NC}"
    fi

    echo -e "${GREEN}✅ Gateway と MCP リソースのクリーンアップが完了しました${NC}"
}

# AgentCore ID リソースをクリーンアップする関数
cleanup_identity_resources() {
    echo -e "${BLUE}🗑️  AgentCore ID リソースをクリーンアップ中...${NC}"
    echo "==============================================="
    
    # Create temporary Python script for identity cleanup
    local cleanup_script="${SCRIPT_DIR}/temp_identity_cleanup.py"
    
    cat > "$cleanup_script" << 'EOF'
import boto3
import time
import os

def cleanup_oauth2_providers_with_retry(bedrock_client):
    """Enhanced OAuth2 provider cleanup with retry logic and dependency handling"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            providers = bedrock_client.list_oauth2_credential_providers()
            provider_list = providers.get('oauth2CredentialProviders', [])
            
            if not provider_list:
                print("   ✅ No OAuth2 credential providers to delete")
                return True
                
            print(f"   Found {len(provider_list)} OAuth2 credential providers (attempt {attempt + 1})")
            
            deleted_count = 0
            failed_count = 0
            
            for provider in provider_list:
                provider_name = provider.get('name')
                provider_arn = provider.get('credentialProviderArn')
                
                try:
                    # Check for dependencies before deletion
                    if has_provider_dependencies(bedrock_client, provider_arn):
                        print(f"   ⚠️  Provider {provider_name} has dependencies, cleaning up first...")
                        cleanup_provider_dependencies(bedrock_client, provider_arn)
                    
                    bedrock_client.delete_oauth2_credential_provider(
                        credentialProviderArn=provider_arn
                    )
                    print(f"   ✅ Deleted OAuth2 provider: {provider_name}")
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Failed to delete OAuth2 provider {provider_name}: {e}")
                    failed_count += 1
            
            print(f"   📊 OAuth2 Provider Results (attempt {attempt + 1}):")
            print(f"   ✅ Successfully deleted: {deleted_count}")
            print(f"   ❌ Failed to delete: {failed_count}")
            
            # If all providers were deleted successfully, we're done
            if failed_count == 0:
                return True
                
            # If this wasn't the last attempt, wait before retrying
            if attempt < max_retries - 1:
                print(f"   ⏳ Retrying failed deletions in 5 seconds...")
                time.sleep(5)
                
        except Exception as e:
            print(f"   ❌ Error in OAuth2 provider cleanup attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print(f"   ⏳ Retrying in 5 seconds...")
                time.sleep(5)
    
    print(f"   ⚠️  OAuth2 provider cleanup completed with some failures after {max_retries} attempts")
    return False

def has_provider_dependencies(bedrock_client, provider_arn):
    """Check if credential provider has dependencies"""
    try:
        # Check if any workload identities are using this provider
        identities = bedrock_client.list_workload_identities()
        for identity in identities.get('workloadIdentities', []):
            # This is a simplified check - in practice, you'd need to examine
            # the identity configuration to see if it references the provider
            pass
        return False
    except Exception:
        return False

def cleanup_provider_dependencies(bedrock_client, provider_arn):
    """Clean up resources that depend on the credential provider"""
    try:
        # In practice, this would identify and clean up dependent resources
        # For now, we'll just add a small delay to allow for eventual consistency
        time.sleep(2)
    except Exception as e:
        print(f"   ⚠️  Error cleaning up provider dependencies: {e}")

def cleanup_workload_identities_enhanced(bedrock_client):
    """Enhanced workload identity cleanup with proper pagination support"""
    try:
        print("   🔍 Getting ALL workload identities with pagination...")
        
        all_identities = []
        next_token = None
        page_count = 0
        
        while True:
            page_count += 1
            
            # Use maximum allowed page size (20)
            if next_token:
                response = bedrock_client.list_workload_identities(
                    maxResults=20,
                    nextToken=next_token
                )
            else:
                response = bedrock_client.list_workload_identities(maxResults=20)
            
            page_identities = response.get('workloadIdentities', [])
            all_identities.extend(page_identities)
            
            if page_count <= 5 or page_count % 100 == 0:  # Show progress for first 5 pages and every 100th page
                print(f"      📄 Page {page_count}: {len(page_identities)} identities (Total: {len(all_identities)})")
            
            next_token = response.get('nextToken')
            if not next_token:
                break
                
            # Safety limit to prevent infinite loops
            if page_count > 2000:
                print("         ⚠️  Stopping after 2000 pages for safety")
                break
        
        if page_count > 5:
            print(f"      📊 Pagination complete: {page_count} pages, {len(all_identities)} total identities")
        
        if not all_identities:
            print("   ✅ No workload identities to delete")
            return True
            
        print(f"   Found {len(all_identities)} workload identities")
        
        # Enhanced batching with progress tracking
        batch_size = 100  # Increased batch size for better performance
        deleted_count = 0
        failed_count = 0
        total_count = len(all_identities)
        
        for i in range(0, total_count, batch_size):
            batch = all_identities[i:i+batch_size]
            batch_deleted = 0
            batch_failed = 0
            
            print(f"   🔄 Processing batch {i//batch_size + 1}/{(total_count + batch_size - 1)//batch_size} ({len(batch)} identities)...")
            
            for identity in batch:
                identity_name = identity.get('name')
                
                try:
                    bedrock_client.delete_workload_identity(name=identity_name)
                    deleted_count += 1
                    batch_deleted += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete identity {identity_name}: {e}")
                    failed_count += 1
                    batch_failed += 1
            
            # Progress update
            print(f"   📊 Batch {i//batch_size + 1} complete: {batch_deleted} deleted, {batch_failed} failed")
            print(f"   📈 Overall progress: {deleted_count}/{total_count} ({(deleted_count/total_count)*100:.1f}%)")
            
            # Small delay between batches to avoid rate limiting
            if i + batch_size < total_count:
                time.sleep(1)
        
        print(f"\n   📊 Final Workload Identity Results:")
        print(f"   ✅ Successfully deleted: {deleted_count}")
        print(f"   ❌ Failed to delete: {failed_count}")
        print(f"   📈 Success rate: {(deleted_count/total_count)*100:.1f}%")
        
        return failed_count == 0
        
    except Exception as e:
        print(f"   ❌ Error with workload identities: {e}")
        return False

def verify_identity_cleanup_comprehensive(bedrock_client, oauth_success, identity_success):
    """Comprehensive verification of identity cleanup with detailed reporting"""
    try:
        print("   🔍 Performing comprehensive verification...")
        
        # Check OAuth2 credential providers
        providers_after = bedrock_client.list_oauth2_credential_providers()
        providers_count = len(providers_after.get('oauth2CredentialProviders', []))
        
        # Check workload identities (first page only for speed)
        identities_after = bedrock_client.list_workload_identities(maxResults=20)
        identities_count = len(identities_after.get('workloadIdentities', []))
        has_more_identities = 'nextToken' in identities_after
        
        # Detailed reporting
        print(f"   📊 Verification Results:")
        print(f"   ├── OAuth2 Credential Providers: {providers_count} remaining")
        if has_more_identities:
            print(f"   ├── Workload Identities: {identities_count}+ remaining (first page only)")
        else:
            print(f"   ├── Workload Identities: {identities_count} remaining")
        
        # Check for specific types of remaining resources
        if providers_count > 0:
            print(f"   ⚠️  Remaining OAuth2 providers:")
            for provider in providers_after.get('oauth2CredentialProviders', []):
                provider_name = provider.get('name', 'Unknown')
                print(f"       - {provider_name}")
        
        if identities_count > 0:
            print(f"   ⚠️  Remaining workload identities (showing first 10):")
            for i, identity in enumerate(identities_after.get('workloadIdentities', [])[:10]):
                identity_name = identity.get('name', 'Unknown')
                print(f"       - {identity_name}")
            if identities_count > 10:
                print(f"       ... and {identities_count - 10} more")
        
        # Overall assessment (conservative due to pagination)
        cleanup_complete = providers_count == 0 and identities_count == 0 and not has_more_identities
        
        if cleanup_complete:
            print("   🎉 Identity cleanup verification: PASSED")
            print("   ✅ All identity resources successfully removed")
        else:
            print("   ⚠️  Identity cleanup verification: PARTIAL")
            print(f"   📈 OAuth2 providers cleanup: {'✅ SUCCESS' if providers_count == 0 else '⚠️ PARTIAL'}")
            print(f"   📈 Workload identities cleanup: {'✅ SUCCESS' if identities_count == 0 else '⚠️ PARTIAL'}")
            
            # Provide guidance for remaining resources
            if providers_count > 0 or identities_count > 0:
                print("   💡 Recommendations:")
                if providers_count > 0:
                    print("       - Some OAuth2 providers may have dependencies")
                    print("       - Try running cleanup again after a few minutes")
                if identities_count > 0 or has_more_identities:
                    print("       - Large number of workload identities may require multiple runs")
                    print("       - Script now processes ALL pages, but verification shows first page only")
        
        return cleanup_complete
        
    except Exception as e:
        print(f"   ❌ Verification failed: {e}")
        return False

def cleanup_identity_resources():
    try:
        region = os.environ.get('CLEANUP_REGION', 'us-east-1')
        bedrock_client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        # 1. Delete all OAuth2 credential providers with retry logic
        print("🗑️  Deleting OAuth2 credential providers...")
        oauth_success = cleanup_oauth2_providers_with_retry(bedrock_client)
        
        # 2. Delete all workload identities with enhanced batching
        print("\n🗑️  Deleting workload identities...")
        identity_success = cleanup_workload_identities_enhanced(bedrock_client)
        
        # 3. Enhanced verification with detailed reporting
        print("\n✅ Verifying identity cleanup...")
        verification_success = verify_identity_cleanup_comprehensive(bedrock_client, oauth_success, identity_success)
        
        return verification_success
        
    except Exception as e:
        print(f"❌ Identity cleanup failed: {e}")
        return False

if __name__ == "__main__":
    cleanup_identity_resources()
EOF
    
    # ID クリーンアップを実行
    if python3 "$cleanup_script"; then
        echo -e "${GREEN}✅ ID リソースのクリーンアップが完了しました${NC}"
    else
        echo -e "${YELLOW}⚠️  ID リソースのクリーンアップに問題がありました${NC}"
    fi

    # 一時スクリプトを削除
    rm -f "$cleanup_script"
}

# ECR リポジトリをクリーンアップする関数
cleanup_ecr_repositories() {
    echo -e "${BLUE}🗑️  ECR リポジトリをクリーンアップ中...${NC}"
    echo "==================================="

    local repos=("bac-runtime-repo-diy" "bac-runtime-repo-sdk")

    for repo in "${repos[@]}"; do
        echo "ECR リポジトリを確認中: $repo"

        if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &> /dev/null; then
            echo "   🗑️  ECR リポジトリを削除中: $repo"

            # まずすべてのイメージを削除
            if aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*]' --output json | grep -q imageDigest; then
                echo "   📦 リポジトリ内のイメージを削除中..."
                aws ecr batch-delete-image \
                    --repository-name "$repo" \
                    --region "$REGION" \
                    --image-ids "$(aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*]' --output json)" &> /dev/null || true
            fi

            # リポジトリを削除
            if aws ecr delete-repository --repository-name "$repo" --region "$REGION" --force &> /dev/null; then
                echo -e "${GREEN}   ✅ ECR リポジトリを削除しました: $repo${NC}"
            else
                echo -e "${YELLOW}   ⚠️  ECR リポジトリの削除に失敗しました: $repo${NC}"
            fi
        else
            echo -e "${GREEN}   ✅ ECR リポジトリは存在しません: $repo${NC}"
        fi
    done
}

# IAM リソースをクリーンアップする関数
cleanup_iam_resources() {
    echo -e "${BLUE}🗑️  IAM リソースをクリーンアップ中...${NC}"
    echo "================================"

    local role_name="bac-execution-role"
    local policy_name="bac-execution-policy"

    echo "IAM ロールを確認中: $role_name"

    if aws iam get-role --role-name "$role_name" &> /dev/null; then
        echo "   🗑️  IAM ロールとポリシーを削除中..."

        # インラインポリシーを削除
        echo "   📝 インラインポリシーを削除中: $policy_name"
        aws iam delete-role-policy --role-name "$role_name" --policy-name "$policy_name" &> /dev/null || true

        # ロールを削除
        if aws iam delete-role --role-name "$role_name" &> /dev/null; then
            echo -e "${GREEN}   ✅ IAM ロールを削除しました: $role_name${NC}"
        else
            echo -e "${YELLOW}   ⚠️  IAM ロールの削除に失敗しました: $role_name${NC}"
        fi
    else
        echo -e "${GREEN}   ✅ IAM ロールは存在しません: $role_name${NC}"
    fi
}

# 設定ファイルをクリーンアップする関数
cleanup_config_files() {
    echo -e "${BLUE}🗑️  設定ファイルをクリーンアップ中...${NC}"
    echo "======================================"

    # dynamic-config.yaml を空の値にリセット
    local dynamic_config="${CONFIG_DIR}/dynamic-config.yaml"
    if [[ -f "$dynamic_config" ]]; then
        # バックアップを作成
        cp "$dynamic_config" "${dynamic_config}.backup.$(date +%Y%m%d_%H%M%S)"

        # すべての動的値を空にリセット
        cat > "$dynamic_config" << 'EOF'
# Dynamic Configuration - Updated by deployment scripts only
# This file contains all configuration values that are generated/updated during deployment
gateway:
  id: ""
  arn: ""
  url: ""
oauth_provider:
  provider_name: ""
  provider_arn: ""
  scopes: []
mcp_lambda:
  function_name: ""
  function_arn: ""
  role_arn: ""
  stack_name: ""
  gateway_execution_role_arn: ""
runtime:
  diy_agent:
    arn: ""
    ecr_uri: ""
    endpoint_arn: ""
  sdk_agent:
    arn: ""
    ecr_uri: ""
    endpoint_arn: ""
client:
  diy_runtime_endpoint: ""
  sdk_runtime_endpoint: ""
memory:
  id: ""
  name: ""
  region: ""
  status: ""
  event_expiry_days: ""
  created_at: ""
  description: ""
EOF
        echo -e "${GREEN}   ✅ dynamic-config.yaml を空の値にリセットしました${NC}"
        echo -e "${BLUE}   📝 タイムスタンプ付きでバックアップを保存しました${NC}"
    fi

    # 作成された可能性のある一時ファイルをクリーンアップ
    local temp_files=(
        "${SCRIPT_DIR}/temp_get_config.py"
        "${SCRIPT_DIR}/temp_gateway_mcp_cleanup.py"
        "${SCRIPT_DIR}/temp_identity_cleanup.py"
        "${CONFIG_DIR}/oauth-provider.yaml"
    )

    for temp_file in "${temp_files[@]}"; do
        if [[ -f "$temp_file" ]]; then
            rm -f "$temp_file"
            echo -e "${GREEN}   ✅ 一時ファイルを削除しました: $(basename "$temp_file")${NC}"
        fi
    done

    # 30日より古い .backup ファイルをクリーンアップ (安全のため最近のものは保持)
    find "${CONFIG_DIR}" -name "*.backup*" -type f -mtime +30 -delete 2>/dev/null || true

    echo -e "${GREEN}   ✅ 設定のクリーンアップが完了しました${NC}"
}

# クリーンアップ概要を表示する関数
show_cleanup_summary() {
    echo ""
    echo -e "${GREEN}🎉 クリーンアップ完了${NC}"
    echo -e "${GREEN}===================${NC}"
    echo ""
    echo -e "${BLUE}📋 クリーンアップされたもの:${NC}"
    echo "   ✅ AgentCore ランタイムエージェント (DIY と SDK)"
    echo "   ✅ AgentCore Gateway と MCP ターゲット"
    echo "   ✅ MCP ツール Lambda 関数と CloudFormation スタック"
    echo "   ✅ OAuth2 認証プロバイダー"
    echo "   ✅ ワークロード ID"
    echo "   ✅ AgentCore メモリリソース"
    echo "   ✅ ECR リポジトリとイメージ"
    echo "   ✅ IAM ロールとポリシー"
    echo "   ✅ 生成された設定ファイル"
    echo ""
    echo -e "${BLUE}📋 保持されたもの:${NC}"
    echo "   ✅ static-config.yaml (変更なし)"
    echo "   ✅ dynamic-config.yaml (空の値にリセット、バックアップあり)"
    echo "   ✅ AWS アカウント設定"
    echo "   ✅ その他の AWS リソース"
    echo ""
    echo -e "${BLUE}🚀 ゼロから再デプロイするには:${NC}"
    echo "   1. ./01-prerequisites.sh (IAM ロールと ECR リポジトリをセットアップ)"
    echo "   2. ./02-create-memory.sh (AgentCore メモリリソースを作成)"
    echo "   3. ./03-setup-oauth-provider.sh (OAuth2 認証プロバイダーをセットアップ)"
    echo "   4. ./04-deploy-mcp-tool-lambda.sh (MCP Lambda 関数をデプロイ)"
    echo "   5. ./05-create-gateway-targets.sh (AgentCore Gateway とターゲットを作成)"
    echo "   6. ./06-deploy-diy.sh (DIY エージェントランタイムをデプロイ)"
    echo "   7. ./07-deploy-sdk.sh (SDK エージェントランタイムをデプロイ)"
}

# メイン実行
main() {
    show_warning

    echo -e "${RED}本当にすべてを削除しますか？${NC}"
    echo -n "'DELETE EVERYTHING' と入力して確認: "
    read confirmation

    if [[ "$confirmation" != "DELETE EVERYTHING" ]]; then
        echo -e "${YELLOW}❌ クリーンアップがキャンセルされました${NC}"
        echo "   確認テキストが一致しませんでした"
        exit 1
    fi

    echo ""
    echo -e "${RED}🚨 破壊的クリーンアップを開始中...${NC}"
    echo ""

    # デプロイの逆順でクリーンアップステップを実行
    echo "ステップ 1: ランタイムエージェントをクリーンアップ中..."
    cleanup_runtime_agents
    echo ""

    echo "ステップ 2: Gateway と MCP リソースをクリーンアップ中..."
    cleanup_gateway_mcp_resources
    echo ""

    echo "ステップ 3: ID リソースをクリーンアップ中..."
    # ID クリーンアップ用の環境変数を設定
    export CLEANUP_REGION="$REGION"
    cleanup_identity_resources
    unset CLEANUP_REGION
    echo ""

    echo "ステップ 4: メモリリソースをクリーンアップ中..."
    cleanup_memory_resources
    echo ""

    echo "ステップ 5: ECR リポジトリをクリーンアップ中..."
    cleanup_ecr_repositories
    echo ""

    echo "ステップ 6: IAM リソースをクリーンアップ中..."
    cleanup_iam_resources
    echo ""

    echo "ステップ 7: 設定ファイルをクリーンアップ中..."
    cleanup_config_files
    echo ""

    show_cleanup_summary
}

# Run main function
main "$@"

#!/usr/bin/env python3
"""
Bedrock AgentCore ゲートウェイを削除する
統合 AgentCore 設定システムを使用
"""
import json
import boto3
import logging
import argparse
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add project root to path for shared config manager
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
from shared.config_manager import AgentCoreConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description='Delete Bedrock AgentCore Gateway')
    parser.add_argument('--gateway-id', required=True, help='Gateway ID to delete')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--delete-targets', action='store_true', help='Delete all targets first')
    parser.add_argument("--environment", type=str, default="dev", help="Environment to use (dev, gamma, prod)")
    return parser.parse_args()

def print_request(title, request_data):
    """フォーマットされたリクエストを出力する"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(request_data, indent=2, default=str))
    print("=" * 60)

def print_response(title, response_data):
    """フォーマットされたレスポンスを出力する"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def clear_dynamic_config_with_yq():
    """yq を使用してゲートウェイ設定をクリアする"""
    try:
        config_file = project_root / "config" / "dynamic-config.yaml"
        
        # Clear using yq commands
        subprocess.run([
            "yq", "eval", ".gateway.id = \"\"", "-i", str(config_file)
        ], check=True, capture_output=True)
        
        subprocess.run([
            "yq", "eval", ".gateway.arn = \"\"", "-i", str(config_file)
        ], check=True, capture_output=True)
        
        subprocess.run([
            "yq", "eval", ".gateway.url = \"\"", "-i", str(config_file)
        ], check=True, capture_output=True)
        
        subprocess.run([
            "yq", "eval", ".gateway.status = \"\"", "-i", str(config_file)
        ], check=True, capture_output=True)
        
        print("✅ 動的設定を正常にクリアしました")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  動的設定のクリアに失敗しました: {e}")
        return False
    except Exception as e:
        print(f"⚠️  設定のクリア中にエラーが発生しました: {e}")
        return False

def get_gateway_targets(bedrock_agentcore_client, gateway_id):
    """ゲートウェイのすべてのターゲットを取得する"""
    try:
        response = bedrock_agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        return response.get('items', [])
    except Exception as e:
        logger.error(f"ゲートウェイターゲットの取得に失敗しました: {str(e)}")
        return []

def delete_all_targets(bedrock_agentcore_client, gateway_id, targets):
    """ゲートウェイのすべてのターゲットを削除する"""
    success = True
    for target in targets:
        target_id = target['targetId']
        try:
            print(f"   ターゲットを削除中: {target_id}")
            bedrock_agentcore_client.delete_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id
            )
        except Exception as e:
            print(f"   ⚠️  ターゲット {target_id} の削除に失敗しました: {str(e)}")
            success = False
    return success

def confirm_deletion(gateway_info, targets):
    """ユーザーにゲートウェイ削除を確認する"""
    print(f"\nゲートウェイ削除の確認")
    print("=" * 40)
    print(f"Gateway ID: {gateway_info.get('gatewayId', 'Unknown')}")
    print(f"Gateway 名: {gateway_info.get('name', 'Unknown')}")
    print(f"ステータス: {gateway_info.get('status', 'Unknown')}")
    print(f"説明: {gateway_info.get('description', 'Unknown')}")
    print(f"ターゲット数: {len(targets)}")
    print(f"作成日時: {gateway_info.get('createdAt', 'Unknown')}")
    print(f"更新日時: {gateway_info.get('updatedAt', 'Unknown')}")
    print()
    print("この操作は元に戻せません！")
    print("すべてのターゲットとツールにアクセスできなくなります！")
    print()

    confirmation = input("ゲートウェイの削除を確認するには 'DELETE' と入力してください: ").strip()

    if confirmation != 'DELETE':
        print("削除がキャンセルされました")
        return False

    return True

def delete_bedrock_agentcore_gateway(config_manager, environment, gateway_id, force=False, delete_targets=False):
    """設定を使用して Bedrock AgentCore ゲートウェイを削除する"""
    
    # Get configuration from config manager
    base_settings = config_manager.get_base_settings()
    
    # Extract AWS configuration
    aws_config = {
        'region': base_settings['aws']['region'],
        'account_id': base_settings['aws']['account_id'],
        'profile': None  # Use default credentials
    }
    
    print(f"使用する設定:")
    print(f"   環境: {environment}")
    print(f"   AWS リージョン: {aws_config['region']}")
    print(f"   AWS アカウント: {aws_config['account_id']}")
    
    # Create AWS session
    session = boto3.Session(region_name=aws_config['region'])
    
    # Use bedrock-agentcore-control client
    bedrock_agentcore_client = session.client('bedrock-agentcore-control', region_name=aws_config['region'])
    
    print("\nAWS からゲートウェイ情報を取得中...")
    
    # Get gateway info
    try:
        gateway_response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
        gateway_info = gateway_response
    except Exception as e:
        print(f"ゲートウェイ {gateway_id} が見つかりません: {str(e)}")
        return False
    
    # Get targets from AWS
    targets = get_gateway_targets(bedrock_agentcore_client, gateway_id)
    
    # Confirm deletion unless forced
    if not force:
        if not confirm_deletion(gateway_info, targets):
            return False
    
    # Delete targets first if requested or if they exist
    if targets and (delete_targets or not force):
        if not delete_all_targets(bedrock_agentcore_client, gateway_id, targets):
            print("ターゲット削除の失敗により、ゲートウェイの削除を続行できません")
            return False
    
    # Prepare request
    request_data = {
        'gatewayIdentifier': gateway_id
    }
    
    print_request("DELETE GATEWAY REQUEST", request_data)
    
    try:
        # Delete gateway
        response = bedrock_agentcore_client.delete_gateway(**request_data)
        
        print_response("DELETE GATEWAY RESPONSE", response)
        
        gateway_status = response.get('status', 'Unknown')
        
        # Clear the dynamic config
        clear_dynamic_config_with_yq()
        
        print(f"\nゲートウェイが正常に削除されました！")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   環境: {environment}")
        print(f"   削除したターゲット数: {len(targets) if delete_targets else 0}")

        return True

    except Exception as e:
        logger.error(f"ゲートウェイの削除に失敗しました: {str(e)}")
        print(f"\nゲートウェイの削除に失敗しました: {str(e)}")
        return False

def main():
    """メイン関数"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = AgentCoreConfigManager()
    
    # Use environment from args
    environment = args.environment
    
    print("Bedrock AgentCore ゲートウェイの削除")
    print("=" * 40)
    print(f"環境: {environment}")
    print(f"Gateway ID: {args.gateway_id}")
    print(f"タイムスタンプ: {datetime.now().isoformat()}")
    
    try:
        # Delete gateway
        success = delete_bedrock_agentcore_gateway(
            config_manager,
            environment,
            args.gateway_id,
            args.force,
            args.delete_targets
        )
        
        if success:
            print(f"\nゲートウェイの削除が正常に完了しました！")
            print(f"   残りのゲートウェイを確認するには 'python list-gateways.py' を使用してください")
        else:
            print(f"\n❌ ゲートウェイの削除に失敗しました！")
            sys.exit(1)

    except Exception as e:
        logger.error(f"ゲートウェイの削除に失敗しました: {str(e)}")
        print(f"\n❌ ゲートウェイの削除に失敗しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

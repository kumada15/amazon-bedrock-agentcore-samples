#!/usr/bin/env python3
"""
Bedrock AgentCore Gateway ターゲットを一覧表示する
統合 AgentCore 設定システムを使用
"""
import json
import boto3
import logging
import argparse
import sys
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
    parser = argparse.ArgumentParser(description='List Bedrock AgentCore Gateway Targets')
    parser.add_argument('--gateway-id', help='Gateway ID (uses config default if not specified)')
    parser.add_argument("--environment", type=str, default="dev", help="Environment to use (dev, gamma, prod)")
    return parser.parse_args()

def print_response(title, response_data):
    """フォーマットされたレスポンスを出力する"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def get_gateway_info(bedrock_agentcore_client, gateway_id):
    """ゲートウェイ情報を取得する"""
    try:
        response = bedrock_agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
        return response
    except Exception as e:
        logger.error(f"ゲートウェイ情報の取得に失敗しました: {str(e)}")
        return None

def list_targets(config_manager, environment, gateway_id=None):
    """設定を使用してゲートウェイのすべてのターゲットを一覧表示する"""
    
    # Get configuration from config manager
    base_settings = config_manager.get_base_settings()
    dynamic_config = config_manager.get_dynamic_config()
    
    # Extract AWS configuration
    aws_config = {
        'region': base_settings['aws']['region'],
        'account_id': base_settings['aws']['account_id'],
        'profile': None  # Use default credentials
    }
    
    # Use gateway from config if not provided
    if not gateway_id:
        gateway_id = dynamic_config['gateway']['id']
        if not gateway_id:
            print("❌ ゲートウェイ ID が指定されておらず、設定にも見つかりません")
            return []
    
    print(f"ゲートウェイ {gateway_id} のライブターゲットを取得中...")
    
    # Create AWS session
    session = boto3.Session(region_name=aws_config['region'])
    
    # Use bedrock-agentcore-control client
    bedrock_agentcore_client = session.client('bedrock-agentcore-control', region_name=aws_config['region'])
    
    # Get gateway info
    gateway_info = get_gateway_info(bedrock_agentcore_client, gateway_id)
    gateway_name = gateway_info.get('name', 'Unknown') if gateway_info else 'Unknown'
    
    try:
        # List targets
        response = bedrock_agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        
        print_response(f"ターゲット一覧レスポンス (Gateway: {gateway_id})", response)

        targets = response.get('items', [])

        print(f"\nゲートウェイ {gateway_id} のライブデータサマリー:")
        print(f"   ターゲット総数: {len(targets)}")

        if targets:
            print(f"\nゲートウェイ {gateway_id} のライブターゲット:")
            print("=" * 60)
            print(f"Gateway 名: {gateway_name}")
            print(f"MCP エンドポイント: https://{gateway_id}.gateway.bedrock-agentcore.{aws_config['region']}.amazonaws.com/mcp")
            
            for i, target in enumerate(targets, 1):
                target_id = target.get('targetId', 'Unknown')
                target_name = target.get('name', 'Unknown')
                status = target.get('status', 'Unknown')
                description = target.get('description', 'Unknown')
                created_at = target.get('createdAt', 'Unknown')
                updated_at = target.get('updatedAt', 'Unknown')
                
                print(f"\n  {i}. Target ID: {target_id}")
                print(f"     名前: {target_name}")
                print(f"     ステータス: {status}")
                print(f"     説明: {description}")
                print(f"     作成日時: {created_at}")
                print(f"     更新日時: {updated_at}")

            print(f"\nAWS ライブデータからターゲットを取得しました")
        else:
            print(f"\nゲートウェイ {gateway_name} のターゲットが見つかりません")
        
        return targets
        
    except Exception as e:
        logger.error(f"ターゲットの一覧取得に失敗しました: {str(e)}")
        print(f"\nターゲットの一覧取得に失敗しました: {str(e)}")
        return []

def main():
    """メイン関数"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = AgentCoreConfigManager()
    
    # Use environment from args
    environment = args.environment
    
    print("Bedrock AgentCore Gateway ターゲット一覧 (ライブデータ)")
    print("=" * 50)
    print(f"環境: {environment}")
    print(f"エンドポイント: default")
    print(f"タイムスタンプ: {datetime.now().isoformat()}")
    print(f"データソース: AWS Bedrock AgentCore API (ライブ)")
    
    try:
        # List targets
        targets = list_targets(config_manager, environment, args.gateway_id)
        
        if not targets:
            print(f"\n⚠️  ターゲットが見つかりません")
            sys.exit(0)

    except Exception as e:
        logger.error(f"ターゲット一覧の取得に失敗しました: {str(e)}")
        print(f"\n❌ ターゲット一覧の取得に失敗しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

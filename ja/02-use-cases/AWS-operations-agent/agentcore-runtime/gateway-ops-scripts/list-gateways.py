#!/usr/bin/env python3
"""
Bedrock AgentCore ゲートウェイを一覧表示する
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
    parser = argparse.ArgumentParser(description='List Bedrock AgentCore Gateways')
    parser.add_argument("--environment", type=str, default="dev", help="Environment to use (dev, gamma, prod)")
    return parser.parse_args()

def print_response(title, response_data):
    """フォーマットされたレスポンスを出力する"""
    print(f"\n{title}")
    print("=" * 60)
    print(json.dumps(response_data, indent=2, default=str))
    print("=" * 60)

def list_gateways(config_manager, environment):
    """設定を使用してすべてのゲートウェイを一覧表示する"""
    
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
    print(f"   エンドポイントタイプ: default")
    
    # Create AWS session
    session = boto3.Session(region_name=aws_config['region'])
    
    # Use bedrock-agentcore-control client
    bedrock_agentcore_client = session.client('bedrock-agentcore-control', region_name=aws_config['region'])
    
    print("\nAWS Bedrock AgentCore API から稼働中のゲートウェイを取得中...")
    
    try:
        # List gateways
        response = bedrock_agentcore_client.list_gateways()
        
        print_response("ゲートウェイ一覧レスポンス (ライブデータ)", response)

        gateways = response.get('items', [])

        print(f"\nライブデータサマリー:")
        print(f"   ゲートウェイ総数: {len(gateways)}")

        if gateways:
            print(f"\nAWS からのライブゲートウェイ:")
            print("=" * 60)
            
            for i, gateway in enumerate(gateways, 1):
                gateway_id = gateway.get('gatewayId', 'Unknown')
                gateway_name = gateway.get('name', 'Unknown')
                status = gateway.get('status', 'Unknown')
                protocol = gateway.get('protocolType', 'Unknown')
                authorizer = gateway.get('authorizerType', 'Unknown')
                description = gateway.get('description', 'Unknown')
                created_at = gateway.get('createdAt', 'Unknown')
                updated_at = gateway.get('updatedAt', 'Unknown')
                
                # Try to construct MCP endpoint URL
                mcp_endpoint = f"https://{gateway_id}.gateway.bedrock-agentcore.{aws_config['region']}.amazonaws.com/mcp" if gateway_id != 'Unknown' else 'Unknown'
                
                print(f"\n{i}. Gateway ID: {gateway_id}")
                print(f"   名前: {gateway_name}")
                print(f"   ステータス: {status}")
                print(f"   プロトコル: {protocol}")
                print(f"   オーソライザー: {authorizer}")
                print(f"   Role ARN: 不明")  # Not returned in list response
                print(f"   MCP エンドポイント: {mcp_endpoint}")
                print(f"   説明: {description}")
                print(f"   作成日時: {created_at}")
                print(f"   更新日時: {updated_at}")

            print(f"\nAWS ライブデータから {len(gateways)} 個のゲートウェイを取得しました")
        else:
            print("\nゲートウェイが見つかりません")
        
        return gateways
        
    except Exception as e:
        logger.error(f"ゲートウェイの一覧取得に失敗しました: {str(e)}")
        print(f"\nゲートウェイの一覧取得に失敗しました: {str(e)}")
        return []

def main():
    """メイン関数"""
    args = parse_arguments()
    
    # Initialize configuration manager
    config_manager = AgentCoreConfigManager()
    
    # Use environment from args
    environment = args.environment
    
    print("Bedrock AgentCore ゲートウェイ一覧 (ライブデータ)")
    print("=" * 45)
    print(f"環境: {environment}")
    print(f"エンドポイント: default")
    print(f"タイムスタンプ: {datetime.now().isoformat()}")
    print(f"データソース: AWS Bedrock AgentCore API (ライブ)")
    
    try:
        # List gateways
        gateways = list_gateways(config_manager, environment)
        
        if not gateways:
            print(f"\n⚠️  ゲートウェイが見つかりません")
            sys.exit(0)

    except Exception as e:
        logger.error(f"ゲートウェイ一覧の取得に失敗しました: {str(e)}")
        print(f"\n❌ ゲートウェイ一覧の取得に失敗しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

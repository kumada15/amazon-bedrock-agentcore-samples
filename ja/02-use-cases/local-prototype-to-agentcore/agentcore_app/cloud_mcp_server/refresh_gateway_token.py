#!/usr/bin/env python3
"""
Bedrock AgentCore Gateway のアクセストークンを更新するスクリプト。
gateway_info.json ファイルに保存された Cognito クライアント情報を使用します。
"""

import json
import logging
import argparse
from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

def update_api_key(gateway_info, api_key):
    """指定された場合、Gateway 情報の API キーを更新"""
    if api_key:
        if "api" not in gateway_info:
            gateway_info["api"] = {}
            
        if "credentials" not in gateway_info["api"]:
            gateway_info["api"]["credentials"] = {}
            
        # Use the standard API key format
        gateway_info["api"]["credentials"] = {
            "apiKey": {
                "headers": {
                    "x-api-key": api_key
                }
            }
        }
        print("✓ gateway_info.json の API キーを更新しました")
    
    return gateway_info

def main():
    parser = argparse.ArgumentParser(description="Refresh access token for Bedrock AgentCore Gateway")
    parser.add_argument("--api-key", help="API key for the API Gateway (optional)")
    args = parser.parse_args()

    print("ゲートウェイ情報を読み込み中...")
    # Load gateway info from the previously saved file
    try:
        with open("gateway_info.json", "r") as f:
            gateway_info = json.load(f)
    except FileNotFoundError:
        print("エラー: gateway_info.json ファイルが見つかりません。先に 3_agentcore_gateway_setup.py を実行してください。")
        exit(1)

    # Initialize the gateway client with the correct region
    client = GatewayClient(region_name=gateway_info["gateway"]["region"])

    print("ゲートウェイ '{}' の新しいアクセストークンをリクエスト中...".format(gateway_info['gateway']['name']))
    # Create client_info structure expected by get_test_token_for_cognito
    client_info = {
        "client_id": gateway_info["auth"]["client_id"],
        "client_secret": gateway_info["auth"]["client_secret"],
        "token_endpoint": gateway_info["auth"]["token_endpoint"],
        "scope": gateway_info["auth"]["scope"]
    }
    
    # Get a new access token using the stored client credentials
    new_token = client.get_access_token_for_cognito(client_info)

    print("✓ 新しいアクセストークンを正常に生成しました")

    # Update the gateway_info file with the new token
    gateway_info["auth"]["access_token"] = new_token
    
    # Update API key if provided
    gateway_info = update_api_key(gateway_info, args.api_key)
    
    # Save the updated gateway info
    with open("gateway_info.json", "w") as f:
        json.dump(gateway_info, f, indent=2)

    print("\ngateway_info.json のアクセストークンを更新しました")
    print("\nこのトークンをアプリケーションで使用するには、クライアントコードでトークン値を更新してください。")
    print("新しいアクセストークンは gateway_info.json に保存されました。")
    
    # Output how to use in code (use placeholder, do not print sensitive value!)
    print("\nPython コードでトークンを使用する例:")
    print("""
from mcp.client.streamablehttp import streamablehttp_client
from strands.tools.mcp import MCPClient

# Create an MCP Client with your token
access_token = "YOUR_ACCESS_TOKEN"
mcp_url = "YOUR_MCP_URL"
mcp_client = MCPClient(lambda: streamablehttp_client(
    mcp_url, 
    headers={"Authorization": f"Bearer {access_token}"}
))
""")

if __name__ == "__main__":
    main()
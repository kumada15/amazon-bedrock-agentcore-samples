"""
DynamoDB ツール権限フィルタリング付き Lambda インターセプター

この Lambda 関数は Gateway MCP RESPONSES をインターセプトし、DynamoDB に保存された
クライアント権限に基づいてツールをフィルタリングします。tools/list レスポンスを
フィルタリングする RESPONSE インターセプターとして設定されます。
クライアントがアクセスを許可されているツールのみが返されます。

インターセプターは Authorization ヘッダーの JWT token から client_id を抽出します。
"""

import json
import boto3
import os
import base64
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError

# 環境変数（デプロイ時に設定）
TABLE_NAME = os.environ.get('PERMISSIONS_TABLE_NAME', 'ClientToolPermissions')
REGION = os.environ.get('DYNAMODB_REGION', os.environ.get('AWS_REGION', 'us-east-1'))

# DynamoDB リソースを初期化
dynamodb = boto3.resource('dynamodb', region_name=REGION)
permissions_table = dynamodb.Table(TABLE_NAME)


def extract_client_id_from_jwt(token: str) -> Optional[str]:
    """
    Extract client_id from JWT token payload.
    
    Args:
        token: JWT token string (with or without 'Bearer ' prefix)
    
    Returns:
        client_id from token payload, or None if extraction fails
    """
    try:
        # 'Bearer ' プレフィックスがあれば削除
        if token.startswith('Bearer '):
            token = token[7:]

        # token を部分に分割
        parts = token.split('.')
        if len(parts) != 3:
            print(f"無効な JWT 形式: 3つの部分が必要ですが、{len(parts)} つでした")
            return None

        # ペイロード（2番目の部分）をデコード
        payload = parts[1]

        # 必要に応じてパディングを追加
        payload += '=' * (4 - len(payload) % 4)

        # base64 をデコード
        decoded = base64.urlsafe_b64decode(payload)
        payload_data = json.loads(decoded)

        # client_id を抽出（機密データを含む可能性があるため完全なペイロードはログ出力しない）
        client_id = payload_data.get('client_id')
        
        if client_id:
            print(f"JWT から client_id を正常に抽出しました")
        else:
            print("警告: JWT ペイロードに client_id が見つかりません")

        return client_id

    except Exception as e:
        print(f"JWT から client_id の抽出中にエラー: {e}")
        return None


def get_client_permissions(client_id: str) -> List[str]:
    """
    Query DynamoDB to get all allowed tools for a specific client.

    Args:
        client_id: The client ID to look up

    Returns:
        List of tool names that the client is allowed to access
    """
    try:
        print(f"クライアントの権限をクエリ中: {client_id}")

        response = permissions_table.query(
            KeyConditionExpression='ClientID = :client_id',
            ExpressionAttributeValues={
                ':client_id': client_id
            }
        )

        # 許可されたツールのみをフィルタリング
        allowed_tools = [
            item['ToolName']
            for item in response.get('Items', [])
            if item.get('Allowed', False)
        ]

        print(f"クライアント {client_id} に許可された {len(allowed_tools)} 件のツールを発見: {allowed_tools}")
        return allowed_tools

    except ClientError as e:
        print(f"DynamoDB クエリ中にエラー: {e}")
        print(f"エラー詳細: {e.response}")
        # エラー時は空のリストを返す（すべてのツールを拒否）
        return []
    except Exception as e:
        print(f"権限取得中に予期しないエラー: {e}")
        return []


def extract_tool_name(gateway_tool_name: str) -> str:
    """
    Extract actual tool name from Gateway's naming format.
    Gateway returns: 'target-name___tool_name'
    We need: 'tool_name'

    Args:
        gateway_tool_name: Tool name in Gateway format

    Returns:
        Extracted tool name
    """
    if '___' in gateway_tool_name:
        return gateway_tool_name.split('___')[1]
    return gateway_tool_name


def filter_tools(tools: List[Dict[str, Any]], allowed_tools: List[str]) -> List[Dict[str, Any]]:
    """
    Filter tools list to only include tools the client is allowed to access.
    Handles Gateway's 'target-name___tool_name' naming format.

    Args:
        tools: List of tool dictionaries from Gateway
        allowed_tools: List of allowed tool names from DynamoDB

    Returns:
        Filtered list of tools
    """
    if not tools:
        return []

    # 高速検索のため allowed_tools を set に変換
    allowed_set = set(allowed_tools)

    filtered = []
    for tool in tools:
        gateway_name = tool.get('name', '')
        extracted_name = extract_tool_name(gateway_name)

        if extracted_name in allowed_set:
            filtered.append(tool)

    print(f"{len(tools)} 件のツールを {len(filtered)} 件の許可されたツールにフィルタリングしました")

    # フィルタされたツールをログ出力
    filtered_out = []
    for tool in tools:
        gateway_name = tool.get('name', '')
        extracted_name = extract_tool_name(gateway_name)
        if extracted_name not in allowed_set:
            filtered_out.append(gateway_name)

    if filtered_out:
        print(f"フィルタされたツール: {filtered_out}")

    return filtered


def lambda_handler(event, context):
    """
    Main Lambda handler for Gateway RESPONSE interceptor.

    Expected event structure (from Gateway RESPONSE):
    {
        "mcp": {
            "gatewayResponse": {
                "headers": {
                    "content-type": "application/json",
                    ...
                },
                "body": {
                    "jsonrpc": "2.0",
                    "result": {
                        "tools": [...]  # Tools list from Gateway targets
                    },
                    "id": 1
                }
            },
            "gatewayRequest": {
                "headers": {
                    "authorization": "Bearer <JWT_TOKEN>",
                    ...
                }
            }
        }
    }

    Returns transformed response with filtered tools.
    """
    print(f"Received event: {json.dumps(event, default=str)}")

    try:
        # リクエスト（Authorization ヘッダー用）とレスポンス（ツール用）の両方を抽出
        mcp_data = event.get('mcp', {})
        gateway_response = mcp_data.get('gatewayResponse', {})
        gateway_request = mcp_data.get('gatewayRequest', {})

        # Authorization 用のリクエストヘッダーを取得
        request_headers = gateway_request.get('headers', {})

        # レスポンスデータを取得
        response_headers = gateway_response.get('headers', {})
        response_body = gateway_response.get('body', {})

        # Authorization ヘッダーを抽出（大文字小文字を区別しない検索）
        auth_header = None
        for key, value in request_headers.items():
            if key.lower() == 'authorization':
                auth_header = value
                break

        print(f"Authorization ヘッダーの存在: {bool(auth_header)}")

        # JWT token から client_id を抽出
        client_id = None
        if auth_header:
            client_id = extract_client_id_from_jwt(auth_header)

        print(f"抽出された client_id: {client_id}")

        # client_id が抽出できない場合、すべてのツールを拒否（セキュリティ: フェイルクローズ）
        if not client_id:
            print("エラー: JWT token に client_id が見つかりません。すべてのツールを拒否します")
            # 元のレスポンス構造を維持しつつ、空のツールで返す
            denied_body = {
                "jsonrpc": "2.0",
                "result": {
                    "tools": []  # client_id がない場合はすべてのツールを拒否
                }
            }
            # 元のレスポンスに id フィールドがあれば保持
            if isinstance(response_body, dict) and 'id' in response_body:
                denied_body['id'] = response_body['id']
            
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": {
                            "Content-Type": "application/json",
                            "X-Auth-Error": "MissingClientId"
                        },
                        "body": denied_body
                    }
                }
            }

        # DynamoDB からこのクライアントに許可されたツールを取得
        allowed_tools = get_client_permissions(client_id)

        # これが tools/list レスポンス（MCP JSON-RPC 形式）かどうかを確認
        # レスポンスボディ形式: {"jsonrpc": "2.0", "result": {"tools": [...]}, "id": 1}
        if 'result' in response_body and 'tools' in response_body.get('result', {}):
            result = response_body['result']
            original_tools = result.get('tools', [])

            # 権限に基づいてツールをフィルタリング
            filtered_tools = filter_tools(original_tools, allowed_tools)

            # フィルタリングされたツールでレスポンスを更新
            filtered_body = response_body.copy()
            filtered_body['result'] = result.copy()
            filtered_body['result']['tools'] = filtered_tools

            # 権限適用のサマリーをログ出力
            print(f"権限適用サマリー:")
            print(f"  - クライアント ID: {client_id}")
            print(f"  - 元のツール数: {len(original_tools)}")
            print(f"  - フィルタ後のツール数: {len(filtered_tools)}")
            print(f"  - 削除されたツール数: {len(original_tools) - len(filtered_tools)}")

            # フィルタリングされたツールを含む変換済みレスポンスを返す
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": response_headers,
                        "body": filtered_body
                    }
                }
            }
        else:
            # Not a tools/list response, pass through unchanged
            print("tools/list レスポンスではないため、変更せずにパススルーします")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": response_headers,
                        "body": response_body
                    }
                }
            }

    except Exception as e:
        print(f"lambda_handler でエラー: {e}")
        print(f"例外タイプ: {type(e).__name__}")

        import traceback
        print(f"トレースバック: {traceback.format_exc()}")

        # エラー時は最小限の安全なレスポンスを返す（ツールなし）
        error_response = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Error": "InterceptorError"
                    },
                    "body": {
                        "jsonrpc": "2.0",
                        "result": {
                            "tools": []  # Safe default: no tools on error
                        },
                        "id": 1
                    }
                }
            }
        }

        return error_response

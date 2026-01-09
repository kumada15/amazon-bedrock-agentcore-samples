import json
import base64


def get_user_groups(jwt_token):
    """JWT トークンからユーザーグループを抽出。

    Args:
        jwt_token: JWT トークン文字列（'Bearer ' プレフィックスあり/なし両方対応）

    Returns:
        list: ユーザーグループ（例: ['sre'] または ['approvers']）
    """
    try:
        # 'Bearer ' プレフィックスがある場合は削除
        token = jwt_token.replace('Bearer ', '').strip()
        
        # JWT フォーマット: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return []
        
        # ペイロードをデコード（必要に応じてパディングを追加）
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        
        # cognito:groups クレームを抽出
        groups = claims.get('cognito:groups', [])
        return groups
    except Exception as e:
        print(f"JWT からグループの抽出中にエラー: {e}")
        return []


def lambda_handler(event, context):
    try:
        print("=" * 80)
        print("INTERCEPTOR LAMBDA - FULL REQUEST DUMP")
        print("=" * 80)
        print(json.dumps(event, indent=2))
        print("=" * 80)
        
        # 正しい構造から Gateway リクエストを抽出
        mcp_data = event.get('mcp', {})
        gateway_request = mcp_data.get('gatewayRequest', {})
        headers = gateway_request.get('headers', {})
        body = gateway_request.get('body', {})
        
        # エラーハンドリング付きで body を JSON としてパース
        try:
            body_json = json.loads(body) if isinstance(body, str) else body
        except json.JSONDecodeError as e:
            print(f"リクエストボディの JSON 解析エラー: {e}")
            return _deny_request(None, message="Invalid JSON in request body")
        
        # Authorization ヘッダーを抽出
        auth_header = headers.get('authorization', '') or headers.get('Authorization', '')
        print(f"Authorization ヘッダーを受信しました: {auth_header[:50]}..." if auth_header else "Authorization ヘッダーがありません")
        
        # JWT からユーザーグループを抽出
        user_groups = get_user_groups(auth_header)
        print(f"ユーザーグループ: {user_groups}")
        
        # JSON-RPC メソッドと id を抽出
        method = body_json.get("method")
        rpc_id = body_json.get("id")
        
        # 非ツール呼び出しは常にパススルー（例: initialize、ヘルスチェック）
        if method not in ("tools/call", "tools/list"):
            print(f"非ツールメソッド '{method}'、パススルー")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": {
                            "Authorization": headers.get("Authorization", ""),
                            "Content-Type": "application/json",
                            "AgentID": headers.get("AgentID", ""),
                        },
                        "body": body_json,
                    }
                },
            }
        
        # tools/list は通常 AgentID なしで許可
        if method == "tools/list":
            print(f"tools/list を許可")
            return {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayRequest": {
                        "headers": {
                            "Authorization": headers.get("Authorization", ""),
                            "Content-Type": "application/json",
                        },
                        "body": body_json,
                    }
                },
            }
        
        # tools/call の場合、ユーザーグループに基づいて認可をチェック
        if method == "tools/call":
            try:
                # params からツール名と引数を抽出
                tool_name = body_json.get("params", {}).get("name", "")
                tool_arguments = body_json.get("params", {}).get("arguments", {})
                print(f"ツール呼び出しがリクエストされました: {tool_name}")
                
                # 認可をチェック
                if "sre" in user_groups:
                    # SRE は action_type="only_plan" のみ使用可能
                    action_type = tool_arguments.get("action_type", "")
                    if action_type != "only_plan":
                        print(f"SRE user not authorized for action_type: {action_type}")
                        return _deny_request(
                            rpc_id,
                            message=f"SRE users can only use action_type='only_plan'"
                        )
                    print(f"SRE user authorized with action_type=only_plan")
                elif "approvers" in user_groups:
                    # Approvers はすべてのツールを呼び出し可能
                    print(f"Approver がツールを承認: {tool_name}")
                else:
                    print(f"ユーザーに認識されたグループがありません: {user_groups}")
                    return _deny_request(
                        rpc_id,
                        message="User does not belong to authorized groups (sre or approvers)"
                    )
                
                # 認可されている場合はパススルー
                return {
                    "interceptorOutputVersion": "1.0",
                    "mcp": {
                        "transformedGatewayRequest": {
                            "headers": {
                                "Authorization": headers.get("Authorization", ""),
                                "Content-Type": "application/json",
                            },
                            "body": body_json,
                        }
                    },
                }
            except Exception as e:
                print(f"tools/call の処理中にエラー: {e}")
                return _deny_request(rpc_id, message=f"Error processing tool call: {str(e)}")
        
        # その他のメソッドはパススルー
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayRequest": {
                    "headers": {
                        "Authorization": headers.get("Authorization", ""),
                        "Content-Type": "application/json",
                    },
                    "body": body_json,
                }
            },
        }
    
    except Exception as e:
        print(f"lambda_handler で予期しないエラー: {e}")
        # 安全なエラーレスポンスを返す
        return _deny_request(None, message=f"Internal error: {str(e)}")


def _deny_request(rpc_id, message: str):
    """有効な MCP/JSON-RPC エラーレスポンスを構築"""
    print(f"リクエストを拒否: {message}")
    error_rpc = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        },
    }
    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": error_rpc,
            }
        },
    }

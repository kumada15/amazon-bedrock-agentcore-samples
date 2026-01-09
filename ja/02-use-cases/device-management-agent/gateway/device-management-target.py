"""
デバイス管理 Gateway ターゲット設定スクリプト

このモジュールは、デバイス管理システム用の Amazon Bedrock AgentCore
Gateway ターゲットを作成および設定します。Gateway を通じて利用可能になる
MCP（Model Context Protocol）ツールを定義し、AWS Lambda 関数エンドポイントに
マッピングします。

スクリプトは7つのデバイス管理ツールを設定します:
1. list_devices: システム内の全デバイスを一覧表示
2. get_device_settings: 特定デバイスの詳細設定を取得
3. list_wifi_networks: デバイスに設定された WiFi ネットワークを一覧表示
4. list_users: システム内の全ユーザーを取得
5. query_user_activity: 時間範囲内のユーザーアクティビティをクエリ
6. update_wifi_ssid: WiFi ネットワークの SSID を更新
7. update_wifi_security: WiFi ネットワークのセキュリティタイプを更新

主な機能:
    - 入力検証付きの MCP ツールスキーマ定義
    - ARN による Lambda 関数統合
    - Gateway IAM ロール認証情報設定
    - AI エージェント理解のための包括的なツール説明
    - 各ツールの必須パラメータ検証

必須環境変数:
    AWS_REGION: Gateway 操作用の AWS リージョン
    GATEWAY_IDENTIFIER: ターゲットをアタッチする Gateway ID
    LAMBDA_ARN: ツール実行を処理する Lambda 関数の ARN
    TARGET_NAME: Gateway ターゲットの名前
    TARGET_DESCRIPTION: ターゲット機能の説明

ツールスキーマ構造:
    各ツールに含まれるもの:
    - name: ツールの一意識別子
    - description: AI エージェント用の自然言語説明
    - inputSchema: 必須およびオプションパラメータを定義する JSON スキーマ
    - required: 必須パラメータのリスト

使用例:
    .env ファイルで環境変数を設定してから実行:
    >>> python device-management-target.py

    出力:
    ターゲット ID: target-12345

注意事項:
    - 全てのツールは action_name パラメータを使用して Lambda ハンドラーにルーティング
    - 入力スキーマはパラメータ型と要件を強制
    - 認証情報プロバイダーは Lambda 呼び出しに Gateway IAM ロールを使用
    - ツール説明は各ツールの使用タイミングについて AI エージェントをガイド
"""
import boto3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables without fallback values
AWS_REGION = os.getenv('AWS_REGION')
#ENDPOINT_URL = os.getenv('ENDPOINT_URL')
GATEWAY_IDENTIFIER = os.getenv('GATEWAY_IDENTIFIER')
LAMBDA_ARN = os.getenv('LAMBDA_ARN')
TARGET_NAME = os.getenv('TARGET_NAME')
TARGET_DESCRIPTION = os.getenv('TARGET_DESCRIPTION')

bedrock_agent_core_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=AWS_REGION
    #endpoint_url=ENDPOINT_URL
)

lambda_target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": LAMBDA_ARN,
            "toolSchema": {
                "inlinePayload": [
                    {
                        "name": "list_devices",
                        "description": "To list the devices. use action_name default parameter value as 'list_devices'",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name"]
                            }
                        },
                        {
                        "name": "get_device_settings",
                        "description": "To list the devices. use action_name default parameter value as 'get_device_settings'. You need to get teh device_id from the user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "device_id": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id"]
                            }
                        },
                        {
                        "name": "list_wifi_networks",
                        "description": "To list the devices. use action_name default parameter value as 'list_wifi_networks'. You need to get teh device_id from the user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "device_id": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id"]
                            }
                        },
                        {
                        "name": "list_users",
                        "description": "To list the devices. use action_name default parameter value as 'list_users'",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name"]
                            }
                        },
                        {
                        "name": "query_user_activity",
                        "description": "To list the devices. use action_name default parameter value as 'query_user_activity'. Please get start_date, end_date, user_id and activity_type from the user",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "start_date": {
                                    "type": "string"
                                },
                                "end_date": {
                                    "type": "string"
                                },
                                "user_id": {
                                    "type": "string"
                                },
                                "activity_type": {
                                    "type": "string"
                                }               
                            },
                            "required": ["action_name","start_date","end_date"]
                            }
                        },
                        {
                        "name": "update_wifi_ssid",
                        "description": "To list the devices. use action_name default parameter value as 'update_wifi_ssid'. Get device_id, network_id and ssid from the user if not given in the context. ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                "device_id": {
                                    "type": "string"
                                },
                                "network_id": {
                                    "type": "string"
                                },
                                "ssid": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id","network_id","ssid"]
                            }
                        },
                        {
                        "name": "update_wifi_security",
                        "description": "To list the devices. use action_name default parameter value as 'update_wifi_security'. Get device_id, network_id and security_type from the user if not given in the context.  ",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "action_name": {
                                    "type": "string"
                                },
                                 "device_id": {
                                    "type": "string"
                                },
                                 "network_id": {
                                    "type": "string"
                                },
                                 "security_type": {
                                    "type": "string"
                                }
                            },
                            "required": ["action_name","device_id","network_id","security_type"]
                            }
                        }
                ]
            }
        }
    }
}

credential_config = [ 
    {
        "credentialProviderType" : "GATEWAY_IAM_ROLE"
    }
]

response = bedrock_agent_core_client.create_gateway_target(
    gatewayIdentifier=GATEWAY_IDENTIFIER,
    name=TARGET_NAME,
    description=TARGET_DESCRIPTION,
    credentialProviderConfigurations=credential_config, 
    targetConfiguration=lambda_target_config)

print(f"ターゲット ID: {response['targetId']}")

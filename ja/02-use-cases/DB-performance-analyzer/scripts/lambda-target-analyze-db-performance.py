import boto3
import os

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2'), 
    endpoint_url=os.getenv('ENDPOINT_URL')
)

lambda_target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": os.getenv('LAMBDA_ARN'),
            "toolSchema": {
                "inlinePayload": [
                    {
                        "name": "explain_query",
                        "description": "データベースパフォーマンスを最適化するために SQL クエリの実行計画を分析し説明します。データベース環境（dev/prod）と分析する SQL クエリを指定してください。action_type のデフォルト値は explain_query です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'explain_query' を使用します。"
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
                            }
                        },
                        {
                        "name": "extract_ddl",
                        "description": "データベースオブジェクトの DDL（データ定義言語）を抽出します。環境（dev/prod）、object_type（table、view、function など）、object_name、object_schema を指定して作成スクリプトを取得します。action_type のデフォルト値は extract_ddl です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'extract_ddl' を使用します。"
                                },
                                 "object_type": {
                                    "type": "string"
                                },
                                "object_name": {
                                    "type": "string"
                                },
                                "object_schema": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","object_type","object_name","object_schema"]
                            }
                        },
                        {
                        "name": "execute_query",
                        "description": "読み取り専用 SQL クエリを安全に実行し、パフォーマンスメトリクス付きで結果を返します。環境（dev/prod）と実行する SQL クエリを指定してください。action_type のデフォルト値は execute_query です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'execute_query' を使用します。"
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
                            }
                        },
                        {
                        "name": "enhanced_query_diagnostics",
                        "description": "実行計画分析、バッファ使用状況、データベース統計、パフォーマンスメトリクスを含む包括的なクエリ診断を提供します。runbooks.py の拡張診断に基づいています。環境（dev/prod）と分析する SQL クエリを指定してください。action_type のデフォルト値は enhanced_query_diagnostics です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'enhanced_query_diagnostics' を使用します。"
                                },
                                 "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["environment","action_type","query"]
                            }
                        },
                        {
                        "name": "performance_insights_analysis",
                        "description": "実行時間別トップクエリ、待機イベント分析、データベース負荷メトリクスを含む Performance Insights スタイルの分析を提供します。runbooks.py の包括的な診断に基づいています。分析する環境（dev/prod）を指定してください。action_type のデフォルト値は performance_insights_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'performance_insights_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
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

response = agentcore_client.create_gateway_target(
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name=os.getenv('TARGET_NAME', 'pg-analyze-db-performance'),
    description=os.getenv('TARGET_DESCRIPTION', '包括的なクエリ実行計画分析、DDL 抽出、安全な読み取り専用クエリ実行、バッファ使用分析付き拡張クエリ診断、Performance Insights スタイルのメトリクスを備えた拡張 PostgreSQL データベースパフォーマンス分析ツール。深い診断機能を持つ本番環境対応の runbooks に基づいています。'),
    credentialProviderConfigurations=credential_config,
    targetConfiguration=lambda_target_config)

target_id = response['targetId']
print(f"ターゲット ID: {target_id}")

# target_config.env ファイルを作成
with open('target_config.env', 'w') as f:
    f.write(f"TARGET_ID={target_id}\n")

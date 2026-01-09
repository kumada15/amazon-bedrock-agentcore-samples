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
                        "name": "slow_query",
                        "description": "pg_stat_statements を使用してデータベース内の最も遅いクエリを特定し分析します。スロークエリを分析する環境（dev/prod）を指定してください。action_type のデフォルト値は slow_query です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'slow_query' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "conn_issues",
                        "description": "アイドル接続、接続リーク、接続プールの問題などのデータベース接続の問題を検出し分析します。分析する環境（dev/prod）を指定してください。action_type のデフォルト値は connection_management_issues です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'connection_management_issues' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "index_analysis",
                        "description": "データベースのインデックス使用状況を評価し、欠落または未使用のインデックスを特定し、最適化の推奨事項を提供します。インデックスを分析する環境（dev/prod）を指定してください。action_type のデフォルト値は index_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'index_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "autovacuum_analysis",
                        "description": "PostgreSQL の autovacuum パフォーマンス、不要タプルの蓄積を調べ、設定の推奨事項を提供します。autovacuum 設定を分析する環境（dev/prod）を指定してください。action_type のデフォルト値は autovacuum_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'autovacuum_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "io_analysis",
                        "description": "データベースの I/O パターン、バッファ使用状況、チェックポイントアクティビティを分析してパフォーマンスボトルネックを特定します。I/O パフォーマンスを分析する環境（dev/prod）を指定してください。action_type のデフォルト値は io_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'io_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "replication_analysis",
                        "description": "高可用性を確保するために PostgreSQL のレプリケーション状態、遅延、ヘルスを監視します。レプリケーションパフォーマンスを分析する環境（dev/prod）を指定してください。action_type のデフォルト値は replication_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'replication_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "system_health",
                        "description": "キャッシュヒット率、デッドロック、長時間実行トランザクションを含む PostgreSQL データベースの包括的なヘルスチェックを提供します。システムヘルスを分析する環境（dev/prod）を指定してください。action_type のデフォルト値は system_health です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'system_health' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "vacuum_progress",
                        "description": "フェーズ、期間、完了率を含む現在の vacuum 操作の進捗を監視します。runbooks.py の包括的な診断に基づいています。vacuum の進捗を分析する環境（dev/prod）を指定してください。action_type のデフォルト値は vacuum_progress です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'vacuum_progress' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "xid_analysis",
                        "description": "トランザクション ID（XID）ラップアラウンド状態、データベース全体の最も古い XID、ラップアラウンドを防ぐために vacuum が必要なテーブルを分析します。runbooks.py の包括的な診断に基づいています。XID 状態を分析する環境（dev/prod）を指定してください。action_type のデフォルト値は xid_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'xid_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "bloat_analysis",
                        "description": "著しい肥大化があるテーブルを特定し、肥大化率と無駄なスペースを計算します。runbooks.py の包括的な診断に基づいています。テーブルの肥大化を分析する環境（dev/prod）を指定してください。action_type のデフォルト値は bloat_analysis です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'bloat_analysis' を使用します。"
                                }
                            },
                            "required": ["environment","action_type"]
                            }
                        },
                        {
                        "name": "long_running_transactions",
                        "description": "vacuum 操作をブロックしている可能性がある、またはパフォーマンスの問題を引き起こしている長時間実行トランザクションを特定します。runbooks.py の包括的な診断に基づいています。長時間実行トランザクションを分析する環境（dev/prod）を指定してください。action_type のデフォルト値は long_running_transactions です。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "environment": {
                                    "type": "string"
                                },
                                "action_type": {
                                    "type": "string",
                                    "description": "実行するアクションのタイプ。このツールでは 'long_running_transactions' を使用します。"
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
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),  # GatewayID に置き換えてください
    name=os.getenv('TARGET_NAME','pgstat-analyze-db'),
    description=os.getenv('TARGET_DESCRIPTION', 'スロークエリ、接続の問題、I/O ボトルネック、インデックス使用状況、autovacuum、レプリケーション、システムヘルス、vacuum 進捗監視、XID ラップアラウンド分析、テーブル肥大化検出、長時間実行トランザクション特定を含む包括的な診断機能を備えた拡張 PostgreSQL データベースパフォーマンス分析ツール。深い診断機能を持つ本番環境対応の runbooks に基づいています。'),
    credentialProviderConfigurations=credential_config,
    targetConfiguration=lambda_target_config)

print(f"ターゲット ID: {response['targetId']}")

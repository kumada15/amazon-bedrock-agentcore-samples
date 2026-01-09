import boto3
import os
import sys

# スクリプトディレクトリとプロジェクトディレクトリを取得
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

agentcore_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=os.getenv('AWS_REGION', 'us-west-2'), 
    endpoint_url=os.getenv('ENDPOINT_URL')
)

# Lambda ARN を読み込む
config_file = os.path.join(project_dir, "config", "lambda_config.env")
if not os.path.exists(config_file):
    print(f"エラー: Lambda 設定ファイルが見つかりません: {config_file}")
    sys.exit(1)

with open(config_file, 'r') as f:
    for line in f:
        if line.startswith('export '):
            key, value = line.replace('export ', '').strip().split('=', 1)
            os.environ[key] = value.strip('"\'')


lambda_target_config = {
    'mcp': {
        'lambda': {
            'lambdaArn': os.getenv('LAMBDA_ARN'),
            'toolSchema': {
                'inlinePayload': [
                    {
                        'name': 'explain_query',
                        'description': '指定された SQL クエリの実行計画を分析し説明します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'},
                                'query': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type', 'query']
                        }
                    },
                    {
                        'name': 'extract_ddl',
                        'description': '指定されたデータベースオブジェクトの DDL を抽出します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'},
                                'object_type': {'type': 'string'},
                                'object_name': {'type': 'string'},
                                'object_schema': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type', 'object_type', 'object_name', 'object_schema']
                        }
                    },
                    {
                        'name': 'execute_query',
                        'description': '読み取り専用クエリを安全に実行し、結果を返します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'},
                                'query': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type', 'query']
                        }
                    }
                ]
            }
        }
    }
}

credential_config = [
    {
        'credentialProviderType': 'GATEWAY_IAM_ROLE'
    }
]

# DB Performance Analyzer ターゲットを作成
response = agentcore_client.create_gateway_target(
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name=os.getenv('TARGET_NAME', 'db-performance-analyzer'),
    description=os.getenv('TARGET_DESCRIPTION', 'DB パフォーマンス分析ツール'),
    credentialProviderConfigurations=credential_config,
    targetConfiguration=lambda_target_config
)

print(f"DB Performance Analyzer ターゲットを作成しました。ID: {response['targetId']}")

# ターゲット設定をファイルに保存
target_config_file = os.path.join(project_dir, "config", "target_config.env")
with open(target_config_file, 'w') as f:
    f.write(f"export TARGET_ID={response['targetId']}\n")

# PGStat ターゲット設定を作成
pgstat_target_config = {
    'mcp': {
        'lambda': {
            'lambdaArn': os.getenv('PGSTAT_LAMBDA_ARN'),
            'toolSchema': {
                'inlinePayload': [
                    {
                        'name': 'slow_query',
                        'description': 'PostgreSQL データベースのスロークエリを分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'connection_management_issues',
                        'description': 'PostgreSQL データベースの接続管理の問題を分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'index_analysis',
                        'description': 'PostgreSQL データベースのインデックス使用状況と効率を分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'autovacuum_analysis',
                        'description': 'PostgreSQL データベースの autovacuum パフォーマンスを分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'io_analysis',
                        'description': 'PostgreSQL データベースの I/O パフォーマンスを分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'replication_analysis',
                        'description': 'PostgreSQL データベースのレプリケーション状態を分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    },
                    {
                        'name': 'system_health',
                        'description': 'PostgreSQL データベースの全体的なシステムヘルスを分析します。',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'environment': {'type': 'string'},
                                'action_type': {'type': 'string'}
                            },
                            'required': ['environment', 'action_type']
                        }
                    }
                ]
            }
        }
    }
}

# PGStat ターゲットを作成
pgstat_response = agentcore_client.create_gateway_target(
    gatewayIdentifier=os.getenv('GATEWAY_IDENTIFIER'),
    name='pgstat-analyzer',
    description='PostgreSQL 統計とパフォーマンス分析ツール',
    credentialProviderConfigurations=credential_config,
    targetConfiguration=pgstat_target_config
)

print(f"PGStat ターゲットを作成しました。ID: {pgstat_response['targetId']}")

# PGStat ターゲット設定をファイルに保存
pgstat_config_file = os.path.join(project_dir, "config", "pgstat_target_config.env")
with open(pgstat_config_file, 'w') as f:
    f.write(f"export PGSTAT_TARGET_ID={pgstat_response['targetId']}\n")
"""
デバイス管理 Strands Agent Runtime - デプロイスクリプト

このモジュールは、Device Management Strands Agent Runtime を
Amazon Bedrock AgentCore へデプロイする処理を自動化します。
Docker コンテナ化、環境設定、オブザーバビリティ設定、
およびデプロイ監視を処理します。

スクリプトは以下の操作を実行します:
1. .env および .env.runtime ファイルから環境変数を読み込み
2. 必須パラメータ（gateway_id、agent_name）を検証
3. デプロイ操作用の AgentCore クライアントを作成
4. コピーするファイルと環境変数を設定
5. gateway ID から gateway エンドポイント URL を取得
6. 除外設定付きの .dockerignore ファイルを生成
7. 実行ロールと要件でエージェントランタイムを設定
8. コンテナ化されたエージェントランタイムを AWS に起動
9. 完了までデプロイステータスを監視
10. デプロイ成功時にクイックテスト呼び出しを実行

主な機能:
    - ECR 統合による自動 Docker コンテナ化
    - 複数ソースからの環境変数管理
    - Gateway エンドポイントの解決と設定
    - 効率的なビルドのための動的 .dockerignore 生成
    - ポーリングによるデプロイステータス監視
    - OpenTelemetry インストルメンテーション設定
    - Cognito OAuth 認証セットアップ
    - デプロイステータス確認の自動リトライロジック

コマンドライン引数:
    --gateway_id（必須）: MCP サーバー接続用の Gateway ID
    --agent_name（オプション）: エージェント名（デフォルト: device_management_agent_29_jul_21）
    --execution_role（オプション）: IAM 実行ロール ARN（指定しない場合は .env の ROLE_ARN を使用）

環境変数（.env と .env.runtime）:
    AWS 設定:
    - AWS_REGION: デプロイ用の AWS リージョン（デフォルト: us-west-2）
    - AWS_DEFAULT_REGION: フォールバック AWS リージョン

    Cognito 設定:
    - COGNITO_DOMAIN: Cognito ドメイン URL
    - COGNITO_CLIENT_ID: OAuth クライアント ID
    - COGNITO_CLIENT_SECRET: OAuth クライアントシークレット
    - COGNITO_DISCOVERY_URL: OIDC ディスカバリーエンドポイント
    - COGNITO_AUTH_URL: 認可エンドポイント
    - COGNITO_TOKEN_URL: トークンエンドポイント
    - COGNITO_PROVIDER_NAME: 認証情報プロバイダー名

    MCP サーバー設定:
    - MCP_SERVER_URL: Gateway エンドポイント URL（gateway_id から自動設定）

    IAM 設定:
    - ROLE_ARN: IAM 実行ロール ARN

    エージェント設定:
    - ENDPOINT_URL: Bedrock AgentCore コントロールエンドポイント
    - AGENT_NAME: エージェント名（デフォルト: device-management-agent）
    - AGENT_DESCRIPTION: エージェントの説明
    - BEDROCK_MODEL_ID: モデル ID（デフォルト: claude-3-7-sonnet）

コンテナにコピーされるファイル:
    - strands_agent_runtime.py: メインエージェントランタイムコード
    - access_token.py: OAuth トークン管理
    - utils.py: ユーティリティ関数
    - requirements-runtime.txt: Python 依存関係

コンテナから除外されるもの:
    - .venv/: 仮想環境
    - .ipynb_checkpoints/: Jupyter チェックポイント
    - __pycache__/: Python キャッシュ
    - .git/: Git リポジトリ
    - images/: 画像ファイル
    - FilesToCopy リストにない全てのファイル

デプロイプロセス:
    1. 設定フェーズ:
       - 環境変数を読み込み
       - パラメータを検証
       - AgentCore クライアントを作成
       - Gateway エンドポイントを解決

    2. ビルドフェーズ:
       - .dockerignore を生成
       - 要件でランタイムを設定
       - 認証をセットアップ

    3. 起動フェーズ:
       - Docker イメージをビルド
       - ECR にプッシュ
       - AgentCore にデプロイ

    4. 監視フェーズ:
       - 10秒ごとにデプロイステータスをポーリング
       - READY、CREATE_FAILED、またはその他の終了状態を待機
       - 最終ステータスを表示

    5. 検証フェーズ:
       - クイックテスト呼び出しを実行
       - テスト結果を表示

デプロイステータスの状態:
    - READY: デプロイ成功、エージェントは準備完了
    - CREATE_FAILED: 作成中にデプロイ失敗
    - UPDATE_FAILED: 更新中にデプロイ失敗
    - DELETE_FAILED: 削除中にデプロイ失敗
    - その他の状態: 進行中または遷移中

使用例:
    必須の gateway ID でデプロイ:
    >>> python strands_agent_runtime_deploy.py --gateway_id gateway-12345

    カスタムエージェント名でデプロイ:
    >>> python strands_agent_runtime_deploy.py --gateway_id gateway-12345 --agent_name my-agent

    カスタム実行ロールでデプロイ:
    >>> python strands_agent_runtime_deploy.py --gateway_id gateway-12345 --execution_role arn:aws:iam::...

終了コード:
    0 - デプロイ成功（ステータス: READY）
    1 - 必須パラメータが不足
    1 - AgentCore クライアント作成失敗
    1 - 設定失敗
    1 - 起動失敗

出力:
    - エージェント ARN: 起動成功時に表示
    - デプロイステータス: 監視して表示
    - テストレスポンス: デプロイ成功時に表示
    - エラーメッセージ: 失敗時に表示

注意事項:
    - AgentCore 権限を持つ有効な AWS 認証情報が必要
    - エージェントランタイムをデプロイする前に Gateway を作成する必要あり
    - .env ファイルに Cognito 認証情報を設定する必要あり
    - Docker イメージは自動的にビルドされ ECR にプッシュされる
    - デプロイ監視には10秒のポーリング間隔を含む
    - テスト呼び出しにはシンプルな挨拶プロンプトを使用
    - macOS と Linux 環境の両方をサポート
    - 設定前に既存の Docker ファイルをクリーンアップ

オブザーバビリティ:
    - Dockerfile で OpenTelemetry インストルメンテーションを設定
    - CloudWatch Logs 統合
    - X-Ray トレーシング有効
    - CloudWatch へのメトリクスエクスポート

認証:
    - JWT トークン付き Cognito OAuth2
    - カスタム JWT オーソライザー設定
    - OAuth 認証情報プロバイダー統合
    - 自動トークンリフレッシュサポート
"""
from bedrock_agentcore_starter_toolkit import Runtime
import time
import utils
import os
import sys
from dotenv import load_dotenv
import argparse

# Reading environment variables from .env and .env.runtime files
# load_dotenv() automatically loads from .env file
# Variables from .env.runtime will also be available if loaded separately
load_dotenv()
load_dotenv('.env.runtime')  # Explicitly load .env.runtime file

script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Python ファイルディレクトリ: {script_dir}")

# Setting parameters
parser = argparse.ArgumentParser(
    prog='device_management_strands_agent_runtime',
    description='Device Management Strands Agent with MCP Gateway',
    epilog='Input Parameters'
)

parser.add_argument('--gateway_id', help="Gateway Id", required=True)
parser.add_argument('--agent_name', help="Name of the agent", default="device_management_agent_29_jul_21")
parser.add_argument('--execution_role', help="IAM execution role ARN")

args = parser.parse_args()

# Parameter Validations
if args.gateway_id is None:
    raise Exception("Gateway Id is required")

if args.agent_name is None:
    args.agent_name = os.getenv("AGENT_NAME", "device-management-agent")

print(f"エージェントをデプロイ中: {args.agent_name}")
print(f"ゲートウェイ ID: {args.gateway_id}")

# Create AgentCore client
try:
    (boto_session, agentcore_client) = utils.create_agentcore_client()
except Exception as e:
    print(f"AgentCore クライアント作成エラー: {e}")
    print("AWS 認証情報が設定されていること、および utils.py に create_agentcore_client 関数があることを確認してください")
    sys.exit(1)

# Launch configurations
FilesToCopy = [
    "strands_agent_runtime.py",
    "access_token.py",
    "utils.py", 
    "requirements-runtime.txt"
]

# Environment variables for the runtime
# Loading from both .env and .env.runtime files
EnvVariables = {
    # AWS configuration
    "AWS_DEFAULT_REGION": os.getenv("AWS_REGION", "us-west-2"),
    "AWS_REGION": os.getenv("AWS_REGION", "us-west-2"),
    
    # Cognito configuration
    "COGNITO_DOMAIN": os.getenv("COGNITO_DOMAIN"),
    "COGNITO_CLIENT_ID": os.getenv("COGNITO_CLIENT_ID"),
    "COGNITO_CLIENT_SECRET": os.getenv("COGNITO_CLIENT_SECRET"),
    "COGNITO_DISCOVERY_URL": os.getenv("COGNITO_DISCOVERY_URL"),
    "COGNITO_AUTH_URL": os.getenv("COGNITO_AUTH_URL"),
    "COGNITO_TOKEN_URL": os.getenv("COGNITO_TOKEN_URL"),
    "COGNITO_PROVIDER_NAME": os.getenv("COGNITO_PROVIDER_NAME"),
    
    # MCP Server configuration
    "MCP_SERVER_URL": os.getenv("MCP_SERVER_URL"),
    
    # IAM Role configuration
    "ROLE_ARN": os.getenv("ROLE_ARN"),
    
    # Bedrock AgentCore Runtime configuration
    "ENDPOINT_URL": os.getenv("ENDPOINT_URL"),
    "AGENT_NAME": os.getenv("AGENT_NAME", "device-management-agent"),
    "AGENT_DESCRIPTION": os.getenv("AGENT_DESCRIPTION", "Device Management Agent for IoT devices"),
    
    # Model configuration
    "BEDROCK_MODEL_ID": os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
}

# Get gateway endpoint
try:
    gatewayEndpoint = utils.get_gateway_endpoint(agentcore_client=agentcore_client, gateway_id=args.gateway_id)
    print(f"ゲートウェイエンドポイント: {gatewayEndpoint}")
    if gatewayEndpoint:
        # 実際のゲートウェイエンドポイントで MCP_SERVER_URL を上書き
        EnvVariables["MCP_SERVER_URL"] = gatewayEndpoint
        EnvVariables["gateway_endpoint"] = gatewayEndpoint  # 後方互換性のために保持
    else:
        print("ゲートウェイエンドポイントが空です。.env ファイルの値を使用します")
except Exception as e:
    print(f"警告: ゲートウェイエンドポイントを取得できませんでした: {e}")
    print(".env ファイルの値を使用します")

aws_region = boto_session.region_name
print(f"AWS リージョン: {aws_region}")

print(f"環境変数: {EnvVariables}")

# Exclusions for dockerignore file
excluded_prefixes = ('.venv', '.ipynb_checkpoints', '__pycache__', '.git', 'images')
dockerignoreappend = ['.venv/', '.ipynb_checkpoints/', '__pycache__/', '.git/', 'images/']

for root, dirs, files in os.walk(script_dir):
    # Modify dirs in-place to exclude unwanted directories
    dirs[:] = [d for d in dirs if not d.startswith(excluded_prefixes)]
    
    relativePathDir = os.path.split(root)[-1]
    
    if root != script_dir:
        if relativePathDir not in FilesToCopy:
            dockerignoreappend.append(f"{relativePathDir}/")
    else:
        for file in files:
            if file not in FilesToCopy: #and not file.startswith('.env'):
                dockerignoreappend.append(f"{file}")

print("設定前に既存の Docker ファイルをクリーンアップ中")
cleanup_files = [".dockerignore", "Dockerfile", ".bedrock_agentcore.yaml"]
for cleanup_file in cleanup_files:
    file_path = os.path.join(script_dir, cleanup_file)
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"{cleanup_file} を削除しました")

# Authentication configuration for Cognito
auth_config = {
    "customJWTAuthorizer": {
        "allowedClients": [
            os.getenv("COGNITO_CLIENT_ID")
        ],
        "discoveryUrl": f"https://{os.getenv('COGNITO_DOMAIN')}/.well-known/openid_configuration"
    }
}

# Credential configuration for OAuth
credential_config = {
    "credentialProviderType": "OAUTH",
    "credentialProvider": {
        "oauthCredentialProvider": {
            "providerArn": os.getenv("OAUTH_PROVIDER_ARN", ""),
            "scopes": ["openid"]
        }
    }
}

# Initialize AgentCore Runtime
agentcore_runtime = Runtime()

print("エージェントランタイムを設定中")
try:
    response = agentcore_runtime.configure(
        entrypoint="strands_agent_runtime.py",
        execution_role=args.execution_role or os.getenv("ROLE_ARN"),
        auto_create_ecr=True,
        requirements_file="requirements-runtime.txt",
        region=aws_region,
        agent_name=args.agent_name,
        # 認証情報設定を使用する場合はコメント解除
        # authorizer_configuration=credential_config
    )
    print("設定が成功しました")
except Exception as e:
    print(f"設定に失敗しました: {e}")
    sys.exit(1)

print(".dockerignore ファイルに追記中")
with open(os.path.join(script_dir, ".dockerignore"), "a", encoding='utf-8') as f:
    f.write("\n")
    f.write("# Auto-generated exclusions\n")
    for ignorefile in dockerignoreappend:
        f.write(ignorefile + "\n")

print("エージェントを起動中...")
try:
    launch_result = agentcore_runtime.launch(env_vars=EnvVariables)
    print(f"エージェントが作成されました。ARN: {launch_result.agent_arn}")
except Exception as e:
    print(f"起動に失敗しました: {e}")
    sys.exit(1)

# デプロイメントステータスを監視
print("デプロイメントステータスを監視中...")
status_response = agentcore_runtime.status()
print(f"初期ステータス: {status_response}")

status = status_response.endpoint['status']
end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']

while status not in end_status:
    print(f"現在のステータス: {status}")
    # 必須: Sleep はデプロイメントステータスポーリング中の API レート制限を防ぎます
    # これは任意ではなく、AgentCore デプロイメントの推奨ポーリング間隔です
    time.sleep(10)
    try:
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']
    except Exception as e:
        print(f"ステータス確認エラー: {e}")
        break

print(f"最終ステータス: {status}")

if status == 'READY':
    print("🎉 エージェントのデプロイが成功しました！")

    # クイックテスト
    print("クイックテストを実行中...")
    try:
        invoke_response = agentcore_runtime.invoke({
            "prompt": "こんにちは！デバイス管理を手伝っていただけますか？"
        })
        print(f"テストレスポンス: {invoke_response}")
    except Exception as e:
        print(f"テスト呼び出しに失敗しました: {e}")

elif status in ['CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']:
    print(f"❌ エージェントのデプロイに失敗しました。ステータス: {status}")
    print("詳細なエラーログは AWS コンソールで確認してください")
else:
    print(f"⚠️  エージェントのデプロイが予期しないステータスで終了しました: {status}")

print("デプロイスクリプトが完了しました。")
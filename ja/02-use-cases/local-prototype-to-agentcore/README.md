# プロトタイプから本番環境へ: AWS Bedrock AgentCore を使用したエージェントアプリケーション

> [!IMPORTANT]
> このサンプルは実験および教育目的のみです。コンセプトとテクニックを示していますが、本番環境での直接使用を意図したものではありません。

**重要:**
- このアプリケーションは本番環境での直接使用を**意図していません**。
- ここで提示されているコードとアーキテクチャは例であり、特定のユースケースのすべてのセキュリティ、スケーラビリティ、またはコンプライアンス要件を満たさない場合があります。
- 同様のシステムを本番環境にデプロイする前に、以下が重要です：
  - 徹底的なテストとセキュリティ監査を実施
  - すべての関連規制と業界標準への準拠を確保
  - 特定のパフォーマンスとスケーラビリティのニーズに合わせて最適化
  - 適切なエラーハンドリング、ロギング、モニタリングを実装
  - 本番デプロイのためのすべての AWS ベストプラクティスに従う

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/AWS-Bedrock_AgentCore-orange.svg" alt="AWS Bedrock AgentCore"/>
  <img src="https://img.shields.io/badge/Strands-Agents-green.svg" alt="Strands Agents"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100.0+-purple.svg" alt="FastAPI"/>
</div>

<!-- アーキテクチャ図は「本番環境への移行」セクションの ASCII アートです -->

## 概要

このリポジトリでは、エージェントアプリケーションのローカルプロトタイプを AWS Bedrock AgentCore を使用して本番環境対応システムに変換する方法を示します。顧客が見積もりを取得し、車両情報を取得し、保険契約を管理するのに役立つ自動車保険エージェントの完全な実装を提供します。

リポジトリには2つの並列実装が含まれています：

- **`local_prototype/`** - ローカルサーバーと直接接続を使用した開発重視の実装
- **`agentcore_app/`** - AWS Bedrock AgentCore サービスを活用した本番環境対応の実装

## クラウド移行の主なメリット

| ローカルプロトタイプ | AgentCore を使用した本番環境 | メリット |
|----------------|--------------------------|---------|
| 手動認証 | Cognito を使用した OAuth2 | セキュリティの強化 |
| ローカルロギング | CloudWatch 統合 | 集中モニタリング |
| 手動スケーリング | オートスケーリングランタイム | パフォーマンスの向上 |
| ローカルデプロイ | コンテナ化デプロイ | 運用の簡素化 |
| アドホックテスト | CI/CD 統合 | 信頼性の高い品質 |
| 直接 API アクセス | API Gateway + Lambda | コストの最適化 |

## アーキテクチャ

本番環境のアーキテクチャは3つの主要コンポーネントで構成されています：

1. **Cloud Insurance API** - AWS Lambda 関数としてデプロイされた FastAPI アプリケーション
2. **Cloud MCP Server** - 保険 API を MCP ツールとして公開する AgentCore Gateway 設定
3. **Cloud Strands Insurance Agent** - AgentCore Gateway を使用する Strands ベースのエージェント

### コンポーネント間のやり取りフロー：

1. ユーザーが Insurance Agent にクエリを送信
2. エージェントが OAuth 認証を使用して AgentCore Gateway MCP サーバーに接続
3. AgentCore Gateway が API 操作を MCP ツールとして公開
4. Insurance API がリクエストを処理してデータを返却
5. エージェントが LLM とツールの結果を使用して回答を作成

## 使用テクノロジー

- **AWS Bedrock AgentCore**: マネージドエージェントランタイム環境
- **AWS Lambda & API Gateway**: サーバーレス API ホスティング
- **Amazon Cognito**: 認証と認可
- **Strands Agents**: MCP 統合を備えたエージェントフレームワーク
- **FastAPI**: Python 向けモダン API フレームワーク
- **CloudWatch**: モニタリングと可観測性

## リポジトリ構造

```
insurance_final/
├── local_prototype/                  # 開発実装
│   ├── insurance_api/                # ローカル FastAPI サーバー
│   ├── native_mcp_server/            # ローカル MCP サーバー
│   └── strands_insurance_agent/      # ローカルエージェント実装
│
└── agentcore_app/       # 本番実装
    ├── cloud_insurance_api/          # Lambda デプロイ FastAPI
    ├── cloud_mcp_server/             # AgentCore Gateway 設定
    └── cloud_strands_insurance_agent/  # クラウドエージェント実装
```

## ローカルプロトタイプ

クラウドにデプロイする前に、アプリケーションスタック全体をローカルで実行およびテストして、その機能を理解し、開発の反復を高速化できます。

### アーキテクチャ

ローカルプロトタイプは、マシン上で実行される3つの主要コンポーネントで構成されています：

1. **Local Insurance API**（ポート 8001）: 保険データとビジネスロジックを持つ FastAPI バックエンド
2. **Local MCP Server**（ポート 8000）: API エンドポイントをツールとして公開する Model Context Protocol サーバー
3. **Local Strands Insurance Agent**: Claude を使用してユーザークエリを処理するインタラクティブなエージェント

<!-- ローカルアーキテクチャ図は上記のテキストで説明されています -->

### ローカルプロトタイプの実行

ローカルプロトタイプを開始するには、以下の手順に従ってください：

1. **Insurance API の起動**
   ```bash
   cd local_prototype/local_insurance_api
   python -m venv venv
   source venv/bin/activate  # Windows の場合: venv\Scripts\activate
   pip install -r requirements.txt
   python -m uvicorn server:app --port 8001
   ```

2. **MCP Server の起動**
   ```bash
   cd local_prototype/local_mcp_server
   python -m venv venv
   source venv/bin/activate  # Windows の場合: venv\Scripts\activate
   pip install -r requirements.txt
   python server.py --http
   ```

3. **Strands Agent の実行**
   ```bash
   cd local_prototype/local_strands_insurance_agent
   python -m venv venv
   source venv/bin/activate  # Windows の場合: venv\Scripts\activate
   pip install -r requirements.txt
   # Bedrock アクセス用に AWS 認証情報を設定
   # (https://strandsagents.com/latest/documentation/docs/user-guide/quickstart/#configuring-credentials) を使用して認証情報を設定
   # インタラクティブエージェントを起動
   python interactive_insurance_agent.py
   ```

### ローカルプロトタイプのテスト

ローカルプロトタイプと対話するには、いくつかの方法があります：

- **API テスト**: `http://localhost:8001/docs` にアクセスして API エンドポイントを直接テスト
- **MCP Inspector**: `npx @modelcontextprotocol/inspector` を実行して MCP ツールを検査およびテスト
- **チャットインターフェース**: ターミナルベースのチャットインターフェースを通じてエージェントと対話

### サンプルクエリ

```
You: What information do you have about customer cust-001?
Agent: I have information for John Smith. He is 35 years old and lives at 123 Main St, Springfield, IL.
       His email is john.smith@example.com and phone number is 555-123-4567.

You: What kind of car does he have?
Agent: John Smith owns a 2020 Toyota Camry.

You: Can you give me a quote for a 2023 Honda Civic?
Agent: Based on John Smith's profile, a 2023 Honda Civic would cost approximately $1,245 per year for comprehensive coverage.
```

より詳細な手順と例については、[ローカルプロトタイプ README](local_prototype/README.md) を参照してください。

## はじめに

### 前提条件

- Bedrock アクセスが有効な AWS アカウント
- 適切な権限で設定された AWS CLI
- Python 3.10 以上
- Docker Desktop または Finch がインストール済み
- AWS サービスの基本的な理解

## 本番環境への移行

このセクションでは、ローカルプロトタイプの各コンポーネントが Bedrock AgentCore を使用して本番環境対応の AWS ソリューションにどのように変換されるかを説明します。

```
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│                   │      │                   │      │                   │
│  Local Strands    │◄────►│  Local MCP Server │◄────►│  Local FastAPI    │
│  Agent            │      │                   │      │                   │
│                   │      │                   │      │                   │
└─────────┬─────────┘      └─────────┬─────────┘      └─────────┬─────────┘
          │                          │                          │
          ▼                          ▼                          ▼
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│                   │      │                   │      │                   │
│  AgentCore        │◄────►│  AgentCore        │◄────►│  AWS Lambda +     │
│  Runtime Agent    │      │  Gateway          │      │  API Gateway      │
│                   │      │                   │      │                   │
└───────────────────┘      └───────────────────┘      └───────────────────┘
```

### 1. FastAPI から Mangum を使用した AWS Lambda へ

ローカル FastAPI アプリケーションは Mangum アダプタを使用してサーバーレスデプロイに適応されます：

- **Mangum 統合**: AWS Lambda と ASGI アプリケーション間のブリッジとして機能
- **Lambda Handler**: FastAPI 処理用に API Gateway イベントを変換するラッパー関数
- **デプロイパッケージ**: Lambda 実行用に依存関係とバンドルされたアプリケーションコード
- **API Gateway**: Lambda 関数に HTTP エンドポイントと認証を提供
- **AWS SAM テンプレート**: 必要なすべてのリソースを定義するコードとしてのインフラストラクチャ

```python
# 例: lambda_function.py - FastAPI が Lambda に接続する方法
from local_insurance_api.app import app  # FastAPI アプリをインポート
from mangum import Mangum

# API Gateway が呼び出す Lambda ハンドラーを作成
handler = Mangum(app)
```

### 2. MCP Server から AgentCore Gateway へ

ローカル MCP サーバーは AWS Bedrock AgentCore Gateway に置き換えられます：

- **OpenAPI 統合**: Gateway が OpenAPI 仕様から API 操作をインポート
- **ツールスキーマ定義**: API エンドポイントが MCP ツールスキーマに変換
- **OAuth 認証**: Cognito 統合が安全なアクセス制御を提供
- **マネージドインフラストラクチャ**: AWS がスケーリング、可用性、可観測性を処理
- **Gateway 設定**: ツール定義がエージェントコードとの互換性を維持

```python
# 例: OpenAPI 仕様を使用した Gateway セットアップ
gateway = client.create_mcp_gateway(
    name="InsuranceAPIGateway",
    authorizer_config=cognito_response["authorizer_config"]
)

# OpenAPI 仕様を使用して API を MCP ツールとして登録
client.create_mcp_gateway_target(
    gateway=gateway,
    name="InsuranceAPITarget",
    target_type="openApiSchema",
    target_payload={"inlinePayload": json.dumps(openapi_spec)}
)
```

### 3. Strands Agent から AgentCore Runtime へ

ローカル Strands エージェントは AWS Bedrock AgentCore Runtime にデプロイされます：

- **BedrockAgentCoreApp**: Strands エージェントを AWS にデプロイするためのラッパー
- **エントリーポイントデコレーション**: クラウド実行用の標準化されたインターフェース
- **コンテナデプロイ**: 一貫した実行のために Docker イメージとしてパッケージ化
- **マネージドスケーリング**: AWS がエージェント実行リソースを処理
- **認証情報管理**: ゲートウェイとモデルへの安全なアクセス

```python
# 例: AgentCore 用に適応された Strands エージェント
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    user_input = payload.get("user_input")

    # 認証付きで Gateway MCP に接続
    gateway_client = MCPClient(lambda: streamablehttp_client(
        gateway_url,
        headers={"Authorization": f"Bearer {access_token}"}
    ))

    with gateway_client:
        # 標準的な Strands エージェントコードがここから続く
        tools = gateway_client.list_tools_sync()
        agent = Agent(model="claude-3", tools=tools, system_prompt="...")
        return agent(user_input)
```

### 本番デプロイ手順

完全な本番ソリューションをデプロイするには、以下の手順に従ってください：

1. **Insurance API のデプロイ**
   ```bash
   cd agentcore_app/cloud_insurance_api/deployment
   ./deploy.sh
   ```
   これにより、AWS SAM を使用して FastAPI アプリケーションが AWS Lambda にデプロイされ、API Gateway エンドポイントが作成されます。

2. **AgentCore Gateway での MCP Server のセットアップ**
   ```bash
   cd ../cloud_mcp_server
   # 環境変数を設定
   cp .env.example .env
   # 設定で .env を編集

   # セットアップスクリプトを実行
   python agentcore_gateway_setup_openapi.py
   ```
   これにより、OAuth 認証付きで API 操作を MCP ツールとして公開する AgentCore Gateway が作成されます。

3. **Strands Insurance Agent のデプロイ**
   ```bash
   cd ../cloud_strands_insurance_agent

   # 環境変数を設定
   cp .env.example .env
   # MCP URL とトークンで .env を更新

   # 設定とデプロイ
   agentcore configure -e "agentcore_strands_insurance_agent.py" \
     --name insurance_agent_strands \
     -er <execution-role-arn>

   # クラウドにデプロイ
   agentcore launch
   ```
   これにより、エージェントがコンテナ化され、安全に呼び出せる AgentCore Runtime にデプロイされます。

4. **デプロイのテスト**
   ```bash
   # 必要に応じてトークンを更新
   cd 1_pre_req_setup/cognito_auth
   ./refresh_token.sh

   # エージェントを呼び出し
   agentcore invoke --bearer-token $BEARER_TOKEN \
     '{"user_input": "I need a quote for a 2023 Toyota Camry"}'
   ```

   ![Bedrock AgentCore Insurance App Conversation](agentcore_app/cloud_strands_insurance_agent/agentcore_strands_conversation.gif)

## コンポーネントの詳細
![Bedrock AgentCore Insurance App Architecture](agentcore-insurance-app-architecture.png)

### Cloud Insurance API

Insurance API は FastAPI で構築され、AWS Lambda と API Gateway を使用してサーバーレスアプリケーションとしてデプロイされます。保険関連情報のクエリ用のエンドポイントを提供します。

[Cloud Insurance API の詳細](agentcore_app/cloud_insurance_api/README.md)

### Cloud MCP Server

MCP Server コンポーネントは、保険 API 操作を LLM 駆動のエージェントが使用できる MCP ツールとして公開するように AWS Bedrock AgentCore Gateway を設定します。

[Cloud MCP Server の詳細](agentcore_app/cloud_mcp_server/README.md)

### Cloud Strands Insurance Agent

Insurance Agent は Strands Agents フレームワークを使用して構築され、AgentCore Gateway に接続して自然言語のやり取りを通じて保険支援を提供します。

[Cloud Strands Insurance Agent の詳細](agentcore_app/cloud_strands_insurance_agent/README.md)

## セキュリティに関する考慮事項

- すべての機密設定は環境変数に保存
- 認証は Cognito を使用した OAuth 2.0 を使用
- API アクセスは API キーとベアラートークンで保護
- IAM ロールは最小権限の原則に従う

## モニタリングと可観測性

本番実装には以下が含まれます：
- すべてのコンポーネントの CloudWatch ログ
- リクエストフロー用の X-Ray トレーシング
- エージェントパフォーマンス用のカスタムメトリクス
- エラーレポートとアラート

## クリーンアップ

AgentCore アプリの使用が終了したら、以下の手順に従ってリソースをクリーンアップします：

1. **Gateway と Target の削除**:
   ```bash
   # Gateway ID を取得
   aws bedrock-agentcore-control list-gateways

   # Gateway の Target をリスト
   aws bedrock-agentcore-control list-gateway-targets --gateway-identifier your-gateway-id

   # 最初に Target を削除（Gateway 全体を削除しない場合）
   aws bedrock-agentcore-control delete-gateway-target --gateway-identifier your-gateway-id --target-id your-target-id

   # Gateway を削除（これにより関連するすべての Target も削除されます）
   aws bedrock-agentcore-control delete-gateway --gateway-identifier your-gateway-id
   ```

2. **AgentCore Runtime リソースの削除**:
   ```bash
   # エージェントランタイムをリスト
   aws bedrock-agentcore-control list-agent-runtimes

   # エージェントランタイムエンドポイントをリスト
   aws bedrock-agentcore-control list-agent-runtime-endpoints --agent-runtime-identifier your-agent-runtime-id

   # エージェントランタイムエンドポイントを削除
   aws bedrock-agentcore-control delete-agent-runtime-endpoint --agent-runtime-identifier your-agent-runtime-id --agent-runtime-endpoint-identifier your-endpoint-id

   # エージェントランタイムを削除
   aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-identifier your-agent-runtime-id
   ```

3. **OAuth2 認証情報プロバイダーの削除**:
   ```bash
   # OAuth2 認証情報プロバイダーをリスト
   aws bedrock-agentcore-control list-oauth2-credential-providers

   # OAuth2 認証情報プロバイダーを削除
   aws bedrock-agentcore-control delete-oauth2-credential-provider --credential-provider-identifier your-provider-id
   ```

4. **Cognito リソース**:
   ```bash
   aws cognito-idp delete-user-pool-client --user-pool-id your-user-pool-id --client-id your-app-client-id
   aws cognito-idp delete-user-pool --user-pool-id your-user-pool-id
   ```

## ライセンス

このプロジェクトは Apache License 2.0 の下でライセンスされています - 詳細は [LICENSE](../../LICENSE) ファイルを参照してください。

---

<p align="center">
  AWS Bedrock AgentCore と Strands Agents を使用して構築
</p>

# Cloud MCP Server

このコンポーネントは、OpenAPI 仕様を使用して保険 API 操作を MCP ツールとして公開する AWS Bedrock AgentCore Gateway をセットアップします。

## 概要

Cloud MCP Server は、LLM を活用したエージェントと保険 API の橋渡しをします。AWS Bedrock AgentCore Gateway を活用して、エージェントが保険操作にアクセスするために使用できる安全で管理された MCP（Model Control Protocol）エンドポイントを作成します。

## 機能

- **OpenAPI 統合**: API の OpenAPI 仕様を MCP ツールに自動変換
- **OAuth 認証**: Amazon Cognito による安全なアクセスを設定
- **環境ベースの設定**: 柔軟なデプロイのための環境変数を使用
- **Gateway 管理**: AWS Bedrock AgentCore Gateway を作成・設定

## 前提条件

- Bedrock アクセスのある AWS アカウント
- Python 3.10 以上
- 保険 API の OpenAPI 仕様
- デプロイ済みでアクセス可能な API エンドポイント

## インストール

1. このリポジトリをクローン
2. 依存関係をインストール：

```bash
pip install -r requirements.txt
```

## 設定

`cloud_mcp_server` ディレクトリに以下の変数を含む `.env` ファイルを作成：

```
# AWS 設定
AWS_REGION=us-west-2
ENDPOINT_URL=https://bedrock-agentcore-control.us-west-2.amazonaws.com

# Gateway 設定
GATEWAY_NAME=InsuranceAPIGatewayCreds3
GATEWAY_DESCRIPTION=Insurance API Gateway with OpenAPI Specification

# API 設定
API_GATEWAY_URL=https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/dev
OPENAPI_FILE_PATH=../cloud_insurance_api/openapi.json

# API 認証情報
API_KEY=your-api-key
CREDENTIAL_LOCATION=HEADER
CREDENTIAL_PARAMETER_NAME=X-Subscription-Token

# 出力設定
GATEWAY_INFO_FILE=./gateway_info.json
```

プレースホルダー値を実際の設定に置き換えてください。

## 使用方法

Gateway セットアップスクリプトを実行：

```bash
python agentcore_gateway_setup_openapi.py
```

これにより：

1. 新しい AWS Bedrock AgentCore Gateway を作成
2. Amazon Cognito で OAuth 認証を設定
3. OpenAPI 仕様を MCP ツールとして登録
4. 今後の使用のために Gateway 情報を保存

スクリプト実行後、以下が取得されます：
- Gateway ID と MCP URL
- 認証情報
- テスト用のアクセストークン

## Gateway 情報

スクリプトはすべての Gateway 情報を JSON ファイル（デフォルトは `gateway_info.json`）に以下の構造で保存します：

```json
{
  "gateway": {
    "name": "InsuranceAPIGatewayCreds3",
    "id": "gateway-id",
    "mcp_url": "https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp",
    "region": "us-west-2",
    "description": "Insurance API Gateway with OpenAPI Specification"
  },
  "api": {
    "gateway_url": "https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/dev",
    "openapi_file_path": "/path/to/openapi.json",
    "target_id": "target-id"
  },
  "auth": {
    "access_token": "temporary-access-token",
    "client_id": "cognito-client-id",
    "client_secret": "cognito-client-secret",
    "token_endpoint": "https://auth-endpoint.amazonaws.com/oauth2/token",
    "scope": "gateway-name/invoke",
    "user_pool_id": "us-west-2_poolid",
    "discovery_url": "https://cognito-idp.region.amazonaws.com/user-pool-id/.well-known/openid-configuration"
  }
}
```

## エージェントの接続

エージェントは MCP URL と認証トークンを使用してこの MCP サーバーに接続できます。例えば、strands-agents ライブラリを使用する場合：

```python
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# gateway_info.json から MCP URL とアクセストークンを取得
MCP_SERVER_URL = "https://gateway-id.gateway.bedrock-agentcore.region.amazonaws.com/mcp"
access_token = "your-access-token"

# MCP クライアントを作成
mcp_client = MCPClient(lambda: streamablehttp_client(
    MCP_SERVER_URL,
    headers={"Authorization": f"Bearer {access_token}"}
))

# エージェントでクライアントを使用
with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(
        model="your-model",
        tools=tools,
        system_prompt="Your system prompt"
    )
    response = agent(user_input)
```

## トラブルシューティング

- **認証エラー**: アクセストークンが有効で期限切れでないことを確認
- **OpenAPI エラー**: スクリプト実行前に OpenAPI 仕様を検証
- **Gateway 作成失敗**: AWS 権限と Bedrock サービス制限を確認
- **無効なエンドポイント**: API Gateway URL がアクセス可能か確認

## 次のステップ

MCP サーバーをセットアップした後：

1. MCP URL と認証を使用するようにエージェントを設定
2. 本番使用のためのトークン更新をセットアップ
3. Gateway 操作のモニタリングとログを追加

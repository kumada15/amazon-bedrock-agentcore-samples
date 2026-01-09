# AWS Bedrock AgentCore を使用した Cloud Strands Insurance Agent

このガイドでは、自動車保険見積もりと車両情報クエリを処理するために AWS AgentCore Gateway MCP サービスに接続する Strands ベースの Insurance Agent をデプロイして実行する方法を示します。

![Bedrock AgentCore 保険アプリ会話](agentcore_strands_conversation.gif)

## 前提条件

- 適切な権限を持つ AWS アカウント
- Docker Desktop または Finch がインストール済みで実行中
- Python 3.10 以上
- AWS CLI がインストール済みで設定済み
- jq コマンドライン JSON プロセッサ

## プロジェクト構造

```
cloud_strands_insurance_agent/
├── agentcore_strands_insurance_agent.py  # メインエージェントコード
├── requirements.txt                      # 依存関係
├── 1_pre_req_setup/                      # セットアップスクリプト
│   ├── cognito_auth/                     # 認証セットアップ
│   │   ├── setup_cognito.sh              # インタラクティブセットアップスクリプト
│   │   ├── refresh_token.sh              # トークン更新ユーティリティ
│   │   ├── cognito_config.json           # 設定ストレージ
│   │   └── README.md                     # セットアップドキュメント
│   └── iam_roles_setup/                  # IAM ロール設定
│       ├── setup_role.sh                 # インタラクティブ IAM ロールセットアップ
│       ├── policy_templates.py           # IAM ポリシー定義
│       ├── config.py                     # 設定ユーティリティ
│       ├── collect_info.py               # インタラクティブ入力収集
│       └── README.md                     # セットアップドキュメント
└── .env_example                          # 環境変数テンプレート
```

## ステップ 1: 前提条件のセットアップ

必要な IAM ロールと Cognito 認証をセットアップします：

### IAM 実行ロール

```bash
cd 1_pre_req_setup/iam_roles_setup
./setup_role.sh
```

このインタラクティブスクリプトは以下を行います：
- AWS 認証情報を確認
- 必要な情報（リージョン、リポジトリ名、エージェント名）を収集
- Bedrock AgentCore 用の最小権限で IAM ロールを作成
- 後で使用するためにロール ARN を保存

### Cognito 認証

```bash
cd ../cognito_auth
./setup_cognito.sh
```

このインタラクティブスクリプトは以下を行います：
- Cognito User Pool と App Client を作成
- 認証情報でテストユーザーをセットアップ
- 初期認証トークンを生成
- 簡単にアクセスできるようにすべての設定を保存

## ステップ 2: 環境変数の設定

エージェントは設定に環境変数を使用します。サンプルに基づいて `.env` ファイルを作成：

```bash
# サンプルファイルをコピーして値を編集
cp .env_example .env
nano .env
```

必要な環境変数：
```
# MCP Server 設定
MCP_SERVER_URL="your-gateway-mcp-url"
MCP_ACCESS_TOKEN="your-access-token"

# モデル設定
MODEL_NAME="global.anthropic.claude-haiku-4-5-20251001-v1:0"

# オプション: Gateway 情報ファイルパス（トークン更新用）
GATEWAY_INFO_FILE="../cloud_mcp_server/gateway_info.json"
```

Gateway セットアップ中に生成された gateway_info.json ファイルからアクセストークンと MCP URL を取得できます：

```bash
# gateway_info.json から値を抽出（利用可能な場合）
MCP_URL=$(jq -r '.gateway.mcp_url' ../cloud_mcp_server/gateway_info.json)
ACCESS_TOKEN=$(jq -r '.auth.access_token' ../cloud_mcp_server/gateway_info.json)

# 抽出した値で .env ファイルを更新
sed -i "s|MCP_SERVER_URL=.*|MCP_SERVER_URL=\"$MCP_URL\"|g" .env
sed -i "s|MCP_ACCESS_TOKEN=.*|MCP_ACCESS_TOKEN=\"$ACCESS_TOKEN\"|g" .env
```

## ステップ 3: エージェントの設定

実行ロール（ステップ 1 の ARN を使用）でエージェントを設定：

```bash
# セットアップ出力または AWS コンソールからロール ARN を取得
ROLE_ARN=$(aws iam get-role --role-name BedrockAgentCoreExecutionRole --query 'Role.Arn' --output text)

# エージェントを設定
agentcore configure -e "agentcore_strands_insurance_agent.py" \
  --name insurance_agent_strands \
  -er $ROLE_ARN
```

これにより以下が作成されます：
- `.bedrock_agentcore.yaml` - 設定ファイル
- `Dockerfile` - コンテナビルド手順（まだ存在しない場合）
- `.dockerignore` - ビルドから除外するファイル

## ステップ 4: ローカルテスト

クラウドデプロイ前にエージェントをローカルでテスト：

```bash
# .env ファイルから環境変数を読み込み
source .env

# 環境変数付きでローカル起動
agentcore launch -l \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN
```

これにより：
- Docker イメージをビルド
- ポート 8080 でコンテナをローカル実行
- エージェントサーバーを起動

ローカルでテスト：
```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"user_input": "I need a quote for auto insurance"}'
```

## ステップ 5: クラウドへのデプロイ

エージェントを AWS にデプロイ：

```bash
# .env ファイルから環境変数を読み込み
source .env

# AWS Bedrock AgentCore にデプロイ
agentcore launch \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN
```

これにより：
- Docker イメージをビルドして ECR にプッシュ
- Bedrock AgentCore Runtime を作成
- エージェントをクラウドにデプロイ
- 呼び出し用のエージェント ARN を返す

## ステップ 6: エージェントの呼び出し

Bearer トークンを設定してデプロイされたエージェントを呼び出し：

```bash
# Cognito Bearer トークンを取得
cd 1_pre_req_setup/cognito_auth

# 必要に応じてトークンを更新
./refresh_token.sh

# トークンをエクスポート
export BEARER_TOKEN=$(jq -r '.bearer_token' cognito_config.json)

# プロジェクトルートに戻る
cd ../../

# エージェントを呼び出し
agentcore invoke --bearer-token $BEARER_TOKEN '{"user_input": "Can you help me get a quote for auto insurance?"}'
```

## エージェントコード構造

`agentcore_strands_insurance_agent.py` は以下のパターンに従います：

```python
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    user_input = payload.get("user_input", "I need a quote for auto insurance")

    # 認証付きで Gateway MCP に接続
    gateway_client = MCPClient(lambda: streamablehttp_client(
        gateway_url,
        headers={"Authorization": f"Bearer {access_token}"}
    ))

    with gateway_client:
        tools = gateway_client.list_tools_sync()
        agent = Agent(
            model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
            tools=tools,
            system_prompt="You are an insurance agent assistant..."
        )
        response = agent(user_input)
        return {"result": str(response)}
```

## 依存関係

`requirements.txt` の主な依存関係：
```
mcp>=0.1.0
strands-agents>=0.1.8
bedrock_agentcore
boto3
botocore
typing-extensions
python-dateutil
python-dotenv>=1.0.0
```

## トラブルシューティング

- **424 Failed Dependency**: CloudWatch でエージェントログを確認
- **Token expired**: `./1_pre_req_setup/cognito_auth/refresh_token.sh` を実行して `.env` ファイルを更新
- **Permission denied**: 実行ロールに Bedrock モデルアクセスがあることを確認
- **Local testing fails**: Docker が実行中であることを確認
- **Authentication errors**: `.env` ファイルの MCP_ACCESS_TOKEN が有効で期限切れでないことを確認
- **IAM role errors**: `iam_roles_setup/README.md` で指定されたすべての必要な権限が IAM ロールにあることを確認
- **Cognito authentication issues**: トラブルシューティングについては `cognito_auth/README.md` のドキュメントを確認

## モニタリングとオブザーバビリティ

- CloudWatch でエージェントパフォーマンスを監視
- AWS X-Ray でトレースを表示
- 詳細なエラー情報についてエージェントログを確認

## 次のステップ

- トークン更新の自動化をセットアップ
- セッション管理を設定
- 追加の保険 API と統合
- エラーハンドリングとログを強化

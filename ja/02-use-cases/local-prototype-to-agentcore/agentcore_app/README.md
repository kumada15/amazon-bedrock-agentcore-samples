# プロトタイプから本番へ: AWS Bedrock AgentCore を使用したエージェントアプリケーション

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/AWS-Bedrock_AgentCore-orange.svg" alt="AWS Bedrock AgentCore"/>
  <img src="https://img.shields.io/badge/Strands-Agents-green.svg" alt="Strands Agents"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100.0+-purple.svg" alt="FastAPI"/>
</div>

このプロジェクトは、API ツールを持つローカルのエージェントベース MCP アプリケーションを本番環境のメリットを得るために AWS クラウドに移行する方法を示します。この実装では、認証、オブザーバビリティ、マネージドランタイム環境などの機能でエージェントアプリケーションの本番化を支援する AWS Bedrock AgentCore を活用しています。



## 概要

`production_using_agentcore` フォルダには、`local_prototype` フォルダにある保険アプリケーションコンポーネントのクラウドベースの実装が含まれており、AWS Bedrock AgentCore サービスを活用するように変更されています。

## アーキテクチャ
![Bedrock AgentCore 保険アプリアーキテクチャ](../agentcore-insurance-app-architecture.png)


ソリューションは3つの主要コンポーネントで構成されています：

1. **Cloud Insurance API** (`cloud_insurance_api/`): API Gateway 統合を持つ AWS Lambda 関数としてデプロイされた FastAPI アプリケーション
2. **Cloud MCP Server** (`cloud_mcp_server/`): AWS Bedrock AgentCore Gateway を通じて保険 API を MCP ツールとして公開するゲートウェイ設定
3. **Cloud Strands Insurance Agent** (`cloud_strands_insurance_agent/`): AgentCore Gateway に接続して保険 API ツールにアクセスする Strands ベースのエージェント実装

## 前提条件

- 適切な権限を持つ AWS アカウント
- 管理者アクセスで設定された AWS CLI
- Python 3.10 以上
- Docker Desktop または Finch がインストール済み（ローカルテストとデプロイ用）
- AWS アカウントで Bedrock モデルアクセスが有効
- jq コマンドライン JSON プロセッサ

## セットアッププロセス

セットアップは3つの主要ステップで構成されています：

### 1. Cloud Insurance API のデプロイ

最初のステップは、AWS Lambda と API Gateway を使用して保険 API をサーバーレスアプリケーションとしてデプロイすることです：

```bash
cd cloud_insurance_api/deployment
chmod +x ./deploy.sh
./deploy.sh
```

これにより、AWS SAM を使用して FastAPI アプリケーションがデプロイされ、Lambda 関数、API Gateway、権限を含む必要なすべてのリソースが作成されます。

### 2. AgentCore Gateway を使用した MCP Server のセットアップ

次に、保険 API を MCP ツールとして公開するように AWS Bedrock AgentCore Gateway を設定します：

```bash
cd ../cloud_mcp_server

# OpenAPI 統合で AgentCore Gateway をセットアップ
python agentcore_gateway_setup_openapi.py
```

これにより、保険 API ツールにアクセスするための MCP エンドポイントを提供する OAuth 認証付きの AgentCore Gateway が作成されます。

### 3. Strands Insurance Agent のデプロイ

最後に、MCP Gateway と対話するエージェントをデプロイします：

```bash
cd ../cloud_strands_insurance_agent

# IAM 実行ロールのセットアップ
cd 1_pre_req_setup/iam_roles_setup
./setup_role.sh

# Cognito 認証のセットアップ
cd ../cognito_auth
./setup_cognito.sh

# プロジェクトルートに戻る
cd ../../

# サンプル環境ファイルをコピーして値を編集
cp .env_example .env
nano .env

# セットアップ出力または AWS コンソールからロール ARN を取得
ROLE_ARN=$(aws iam get-role --role-name BedrockAgentCoreExecutionRole --query 'Role.Arn' --output text)

# エージェントを設定
agentcore configure -e "agentcore_strands_insurance_agent.py" \
  --name insurance_agent_strands \
  -er $ROLE_ARN

# .env ファイルから環境変数を読み込み
source .env

# クラウドにデプロイ
agentcore launch \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN
```

## コンポーネント詳細

### Cloud Insurance API

AWS Lambda 関数としてデプロイされた FastAPI アプリケーションで、以下のエンドポイントを提供します：
- 顧客情報の取得
- 車両情報の検索
- 保険見積もりの生成
- ポリシー管理

詳細は [Cloud Insurance API README](cloud_insurance_api/README.md) を参照してください。

### Cloud MCP Server

AWS Bedrock AgentCore のゲートウェイ設定を提供し、以下を行います：
- 保険 API エンドポイントを MCP ツールとして公開
- Amazon Cognito を使用した認証を設定
- ツールの実行環境をセットアップ
- CloudWatch を通じたオブザーバビリティを有効化

### Cloud Strands Insurance Agent

以下を行う Strands ベースのエージェント実装：
- AgentCore Gateway MCP サーバーに接続
- 利用可能なツールを使用して保険関連のクエリを処理
- 会話インターフェースを通じてユーザーインタラクションを処理

詳細は [Cloud Strands Insurance Agent README](cloud_strands_insurance_agent/README.md) を参照してください。

![Bedrock AgentCore 保険アプリ会話](cloud_strands_insurance_agent/agentcore_strands_conversation.gif)

## AgentCore のメリット

- **認証**: Cognito を使用した OAuth2 による安全なアクセス
- **オブザーバビリティ**: CloudWatch を通じたモニタリングとログ
- **スケーラビリティ**: 自動スケールするマネージドランタイム環境
- **コンプライアンス**: 組み込みセキュリティコントロールを備えたマネージドサービス
- **コスト最適化**: 従量課金モデル

## 使用例

```bash
# cognito_auth ディレクトリに移動
cd cloud_strands_insurance_agent/1_pre_req_setup/cognito_auth

# 必要に応じてトークンを更新
./refresh_token.sh

# トークンをエクスポート
export BEARER_TOKEN=$(jq -r '.bearer_token' cognito_config.json)

# プロジェクトルートに戻る
cd ../../

# エージェントを呼び出し
agentcore invoke --bearer-token $BEARER_TOKEN '{"user_input": "Can you help me get a quote for auto insurance?"}'
```

## トラブルシューティング

- **424 Failed Dependency**: CloudWatch でエージェントログを確認
- **Token expired**: `./1_pre_req_setup/cognito_auth/refresh_token.sh` を実行して `.env` ファイルを更新
- **Permission denied**: 実行ロールに Bedrock モデルアクセスがあることを確認
- **Local testing fails**: Docker が実行中であることを確認
- **Authentication errors**: `.env` ファイルの MCP_ACCESS_TOKEN が有効で期限切れでないことを確認
- **IAM role errors**: `iam_roles_setup/README.md` で指定されたすべての必要な権限が IAM ロールにあることを確認
- **Cognito authentication issues**: トラブルシューティングについては `cognito_auth/README.md` のドキュメントを確認

## クリーンアップ

agentcore アプリの使用が終わったら、以下の手順でリソースをクリーンアップしてください：

1. **Gateway と Target の削除**:
   ```bash
   # Gateway ID を取得
   aws bedrock-agentcore-control list-gateways

   # Gateway の Target をリスト
   aws bedrock-agentcore-control list-gateway-targets --gateway-identifier your-gateway-id

   # まず Target を削除（Gateway 全体を削除しない場合）
   aws bedrock-agentcore-control delete-gateway-target --gateway-identifier your-gateway-id --target-id your-target-id

   # Gateway を削除（これにより関連するすべての Target も削除されます）
   aws bedrock-agentcore-control delete-gateway --gateway-identifier your-gateway-id
   ```

2. **AgentCore Runtime リソースの削除**:
   ```bash
   # Agent Runtime をリスト
   aws bedrock-agentcore-control list-agent-runtimes

   # Agent Runtime エンドポイントをリスト
   aws bedrock-agentcore-control list-agent-runtime-endpoints --agent-runtime-identifier your-agent-runtime-id

   # Agent Runtime エンドポイントを削除
   aws bedrock-agentcore-control delete-agent-runtime-endpoint --agent-runtime-identifier your-agent-runtime-id --agent-runtime-endpoint-identifier your-endpoint-id

   # Agent Runtime を削除
   aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-identifier your-agent-runtime-id
   ```

3. **OAuth2 Credential Provider の削除**:
   ```bash
   # OAuth2 Credential Provider をリスト
   aws bedrock-agentcore-control list-oauth2-credential-providers

   # OAuth2 Credential Provider を削除
   aws bedrock-agentcore-control delete-oauth2-credential-provider --credential-provider-identifier your-provider-id
   ```

4. **Cognito リソース**:
   ```bash
   aws cognito-idp delete-user-pool-client --user-pool-id your-user-pool-id --client-id your-app-client-id
   aws cognito-idp delete-user-pool --user-pool-id your-user-pool-id
   ```

## 次のステップ

- 保険商品とサービスの追加
- 会話メモリの実装
- エージェントインタラクション用の Web UI の追加
- 保険オファリング強化のための追加データソースとの統合

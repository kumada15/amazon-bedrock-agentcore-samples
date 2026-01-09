# Agent Runtime モジュール

## アーキテクチャと概要

### Agent Runtime とは？

Agent Runtime モジュールは、デバイス管理システムのコア会話型 AI コンポーネントです。Amazon Bedrock AgentCore と Strands Agents SDK を使用して、自然言語処理、会話管理、ツール実行を処理します。

### 主な責務
- **自然言語処理**: ユーザークエリを理解し、人間らしい応答を生成
- **会話管理**: 複数ターンの会話でコンテキストを維持
- **ツールオーケストレーション**: MCP ツールを通じてデバイス管理操作を実行
- **認証**: 安全なアクセスのための Amazon Cognito 認証を管理
- **オブザーバビリティ**: 包括的なログ、トレース、メトリクスを提供

### アーキテクチャコンポーネント
- **Strands Agent**: Amazon Bedrock モデルを使用するコア会話型 AI エージェント
- **MCP クライアント**: デバイス管理ツールにアクセスするため Gateway と通信
- **認証プロバイダー**: Amazon Cognito OAuth トークン管理を処理
- **オブザーバビリティスタック**: Amazon CloudWatch Logs、AWS X-Ray トレース、カスタムメトリクス

## 前提条件

### 必要なソフトウェア
- **Python 3.10 以上**
- **Docker**（コンテナ化デプロイ用）
- **AWS CLI**（適切な権限で設定済み）

### AWS サービスアクセス
- **Amazon Bedrock AgentCore**
- **Amazon Cognito**（認証用）
- **Amazon CloudWatch**（オブザーバビリティ用）
- **AWS X-Ray**（トレース用）

### 環境依存関係
- **Gateway モジュール**: MCP サーバーエンドポイントを提供するため先にデプロイが必要
- **Device Management モジュール**: AWS Lambda 関数がデプロイされ、Gateway 経由でアクセス可能であること

## デプロイ手順

### オプション 1: 自動デプロイ（推奨）

```bash
# agent-runtime ディレクトリから
chmod +x setup.sh
./setup.sh
```

### オプション 2: 手動デプロイ

#### ステップ 1: 環境設定
```bash
# .env ファイルを作成
cp .env.example .env
# .env を編集して値を設定:
# - AWS_REGION
# - MCP_SERVER_URL（Gateway モジュールから）
# - COGNITO_* 変数
```

#### ステップ 2: 依存関係のインストール
```bash
pip install -r requirements-runtime.txt
```

#### ステップ 3: Agent Runtime のデプロイ
```bash
python strands_agent_runtime_deploy.py
```

#### ステップ 4: Docker デプロイ（オプション）
```bash
# コンテナをビルド
docker build -t device-management-agent-runtime .

# コンテナを実行
docker run -p 8080:8080 --env-file .env device-management-agent-runtime
```

### デプロイの検証

```bash
# ローカルランタイムをテスト
python strands-agent-runtime.py

# コンテナのヘルスを確認（Docker 使用時）
curl http://localhost:8080/health

# Amazon CloudWatch ログを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/bedrock-agentcore"
```

## サンプルクエリ

Agent Runtime がデプロイされると、これらのタイプの自然言語クエリを処理できます：

### デバイス管理
```
"システム内のすべてのデバイスを一覧表示して"
"オフラインのデバイスを表示して"
"デバイス DG-10016 のステータスは？"
```

### 設定管理
```
"デバイス DG-10005 の設定を取得して"
"すべてのデバイスの WiFi 設定を表示して"
"デバイス DG-10016 の SSID を 'NewNetwork' に更新して"
```

### ユーザーとアクティビティクエリ
```
"システム内のすべてのユーザーを一覧表示して"
"昨日のログインアクティビティを表示して"
"最近デバイス DG-10016 にアクセスしたのは誰？"
```

### 期待されるレスポンス形式
Agent Runtime はフォーマットされた会話形式のレスポンスを返します：

```
システムには 25 台のデバイスがあります。現在オフラインのデバイスは以下のとおりです：

• Factory Sensor A3（DG-10016）- 最終確認: 2 時間前
• Warehouse Camera（DG-10022）- 最終確認: 1 日前

これらのデバイスの詳細を表示しますか？
```

## クリーンアップ手順

### 実行中のサービスを停止

```bash
# ローカルランタイムを停止
# フォアグラウンドで実行中の場合は Ctrl+C を押す

# Docker コンテナを停止
docker stop device-management-agent-runtime
docker rm device-management-agent-runtime
```

### Docker イメージの削除

```bash
# ビルド済みイメージを削除
docker rmi device-management-agent-runtime

# ベースイメージを削除（オプション）
docker image prune
```

### Amazon CloudWatch リソースのクリーンアップ

```bash
# ロググループを削除
aws logs delete-log-group --log-group-name "/aws/bedrock-agentcore/device-management-agent"

# カスタムメトリクスのクリーンアップ（自動的に期限切れになります）
```

### 設定ファイルの削除

```bash
# 環境ファイルを削除（機密データを含む）
rm .env

# デプロイ成果物を削除
rm -rf __pycache__/
rm -rf .pytest_cache/
```

## 設定

### 環境変数

```bash
# AWS 設定
AWS_REGION=us-west-2
AWS_DEFAULT_REGION=us-west-2

# MCP サーバー設定
MCP_SERVER_URL=https://gateway-id.gateway.bedrock-agentcore.us-west-2.amazonaws.com
BEARER_TOKEN=your-cognito-access-token

# Amazon Cognito 設定
COGNITO_DOMAIN=your-domain.auth.us-west-2.amazoncognito.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret

# Docker 設定
DOCKER_CONTAINER=1  # コンテナ内で実行時に設定
```

### オブザーバビリティ設定

Agent Runtime には包括的なオブザーバビリティが含まれます：

#### Amazon CloudWatch Logs
- **ロググループ**: `/aws/bedrock-agentcore/device-management-agent`
- **ログレベル**: INFO（設定可能）
- **含まれる内容**: リクエスト/レスポンスデータ、エラー、パフォーマンスメトリクス

#### AWS X-Ray トレース
- **サービス名**: device-management-agent-runtime
- **トレースデータ**: リクエストフロー、ツール実行、レスポンス時間
- **コンソール**: https://console.aws.amazon.com/xray/home

#### カスタムメトリクス
- **名前空間**: DeviceManagement/AgentRuntime
- **メトリクス**: リクエスト数、エラー率、レスポンス時間
- **コンソール**: https://console.aws.amazon.com/cloudwatch/home

## トラブルシューティング

### よくある問題

**Agent Runtime の起動失敗**:
- MCP_SERVER_URL がアクセス可能か確認
- Amazon Cognito 認証情報が有効か確認
- Gateway モジュールがデプロイされ実行中か確認

**認証エラー**:
- Amazon Cognito アクセストークンを再生成
- COGNITO_* 環境変数を確認
- Amazon Cognito ユーザープール設定を確認

**ツール実行の失敗**:
- Gateway Target が正しく設定されているか確認
- AWS Lambda 関数がデプロイされアクセス可能か確認
- 詳細なエラーについて Amazon CloudWatch ログを確認

### デバッグコマンド

```bash
# MCP サーバー接続をテスト
curl -H "Authorization: Bearer $BEARER_TOKEN" $MCP_SERVER_URL/mcp

# Agent Runtime ログを確認
aws logs tail /aws/bedrock-agentcore/device-management-agent --follow

# ローカル Agent Runtime をテスト
python -c "from strands_agent_runtime import test_connection; test_connection()"
```

## 他のモジュールとの統合

- **Gateway モジュール**: MCP サーバーエンドポイントと認証を提供
- **Device Management モジュール**: AWS Lambda 経由で実際のデバイス操作を実行
- **Frontend モジュール**: ユーザー表示用に処理済みレスポンスを受信

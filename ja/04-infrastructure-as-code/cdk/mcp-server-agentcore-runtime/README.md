# MCP Server を AgentCore Runtime でホスティング - CDK

## 概要

この CDK スタックは、Amazon Bedrock AgentCore Runtime 上に MCP (Model Context Protocol) サーバーをデプロイします。Infrastructure as Code を使用して AgentCore Runtime 上に MCP ツールをホストする方法を示し、効率的なエクスペリエンスのための自動化されたデプロイスクリプトを提供します。

このスタックは、Amazon Bedrock AgentCore Python SDK を使用してエージェント関数を Amazon Bedrock AgentCore と互換性のある MCP サーバーとしてラップします。MCP サーバーの詳細を処理するため、エージェントのコア機能に集中できます。

ツールをホスティングする際、Amazon Bedrock AgentCore Python SDK は、セッション分離のための `MCP-Session-Id` ヘッダーを使用した [Stateless Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) トランスポートプロトコルを実装します。MCP サーバーはポート `8000` でホストされ、1 つの呼び出しパス (`mcp-POST` エンドポイント) を提供します。

### チュートリアル詳細

| 情報              | 詳細                                                      |
|:------------------|:----------------------------------------------------------|
| チュートリアルタイプ | ツールのホスティング                                      |
| ツールタイプ       | MCP サーバー                                              |
| チュートリアル構成 | CDK、AgentCore Runtime、MCP サーバー                     |
| チュートリアル分野 | クロスバーティカル                                        |
| 例の複雑さ         | 簡単                                                      |
| 使用 SDK          | Amazon BedrockAgentCore Python SDK と MCP Client          |

### アーキテクチャ

![MCP Server AgentCore Runtime Architecture](architecture.png)

この CDK スタックは、3 つのツール (`add_numbers`、`multiply_numbers`、`greet_user`) を持つシンプルな MCP サーバーをデプロイします。

アーキテクチャは以下で構成されます：

- **ユーザー/MCP クライアント**: JWT 認証を使用して MCP サーバーにリクエストを送信
- **Amazon Cognito**: JWT ベースの認証を提供
  - 事前作成されたテストユーザー (testuser/MyPassword123!) を持つユーザープール
  - アプリケーションアクセス用のユーザープールクライアント
- **AWS CodeBuild**: MCP サーバーを含む ARM64 Docker コンテナイメージをビルド
- **Amazon ECR リポジトリ**: コンテナイメージを保存
- **AgentCore Runtime**: MCP Server をホスト
  - **MCP Server**: HTTP トランスポート経由で 3 つのツールを公開
    - `add_numbers`: 2 つの数を加算
    - `multiply_numbers`: 2 つの数を乗算
    - `greet_user`: ユーザーに名前で挨拶
  - Cognito からの JWT トークンを検証
  - MCP ツール呼び出しを処理
- **IAM ロール**:
  - CodeBuild 用 IAM ロール (イメージのビルドとプッシュ)
  - AgentCore Runtime 用 IAM ロール (ランタイム権限)

### 主な機能

* **完全な Infrastructure as Code** - 完全な CDK 実装
* **デフォルトでセキュア** - Cognito による JWT 認証
* **自動ビルド** - CodeBuild が ARM64 Docker イメージを作成
* **簡単なテスト** - 自動テストスクリプト付属
* **シンプルなクリーンアップ** - 1 コマンドですべてのリソースを削除

## デプロイされる内容

CDK スタックは以下を作成します：

- **Amazon ECR リポジトリ** - MCP サーバー Docker イメージを保存
- **AWS CodeBuild プロジェクト** - ARM64 Docker イメージを自動的にビルド
- **Amazon Cognito ユーザープール** - JWT 認証
- **Cognito ユーザープールクライアント** - アプリケーションクライアント設定
- **Cognito ユーザー** - 事前作成されたテストユーザー (testuser/MyPassword123!)
- **IAM ロール** - すべてのサービスに対する最小権限
- **Lambda 関数** - カスタムリソースの自動化
- **Amazon Bedrock AgentCore Runtime** - MCP サーバーをホスト

**MCP サーバーツール**:
- `add_numbers` - 2 つの数を加算
- `multiply_numbers` - 2 つの数を乗算
- `greet_user` - ユーザーに名前で挨拶

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [前提条件](#前提条件)
- [デプロイ](#デプロイ)
- [テスト](#テスト)
- [クリーンアップ](#クリーンアップ)
- [トラブルシューティング](#トラブルシューティング)

## 概要

この CDK スタックは、Amazon Cognito を使用した JWT 認証付きの MCP サーバーを作成します。MCP サーバーは 3 つのツール (`add_numbers`、`multiply_numbers`、`greet_user`) を提供します。

### 主な機能

* **完全な Infrastructure as Code** - 完全な CDK 実装
* **デフォルトでセキュア** - Cognito による JWT 認証
* **自動ビルド** - CodeBuild が ARM64 Docker イメージを作成
* **簡単なテスト** - 自動テストスクリプト付属
* **シンプルなクリーンアップ** - 1 コマンドですべてのリソースを削除

## アーキテクチャ

アーキテクチャは以下で構成されます：

- **ユーザー/MCP クライアント**: JWT 認証を使用して MCP サーバーにリクエストを送信
- **Amazon Cognito**: JWT ベースの認証を提供
  - 事前作成されたテストユーザー (testuser/MyPassword123!) を持つユーザープール
  - アプリケーションアクセス用のユーザープールクライアント
- **AWS CodeBuild**: MCP サーバーを含む ARM64 Docker コンテナイメージをビルド
- **Amazon ECR リポジトリ**: コンテナイメージを保存
- **AgentCore Runtime**: MCP Server をホスト
  - **MCP Server**: HTTP トランスポート経由で 3 つのツールを公開
    - `add_numbers`: 2 つの数を加算
    - `multiply_numbers`: 2 つの数を乗算
    - `greet_user`: ユーザーに名前で挨拶
  - Cognito からの JWT トークンを検証
  - MCP ツール呼び出しを処理
- **IAM ロール**:
  - CodeBuild 用 IAM ロール (イメージのビルドとプッシュ)
  - AgentCore Runtime 用 IAM ロール (ランタイム権限)

## デプロイされる内容

CDK スタックは以下を作成します：

- **Amazon ECR リポジトリ** - MCP サーバー Docker イメージを保存
- **AWS CodeBuild プロジェクト** - ARM64 Docker イメージを自動的にビルド
- **Amazon Cognito ユーザープール** - JWT 認証
- **Cognito ユーザープールクライアント** - アプリケーションクライアント設定
- **Cognito ユーザー** - 事前作成されたテストユーザー (testuser/MyPassword123!)
- **IAM ロール** - すべてのサービスに対する最小権限
- **Lambda 関数** - カスタムリソースの自動化
- **Amazon Bedrock AgentCore Runtime** - MCP サーバーをホスト

**MCP サーバーツール**:
- `add_numbers` - 2 つの数を加算
- `multiply_numbers` - 2 つの数を乗算
- `greet_user` - ユーザーに名前で挨拶

## 前提条件

- 適切な認証情報で設定された AWS CLI
- 以下を作成する権限を持つ AWS アカウント：
  - CloudFormation スタック
  - ECR リポジトリ
  - CodeBuild プロジェクト
  - Cognito ユーザープール
  - IAM ロールとポリシー
  - Lambda 関数
  - Bedrock AgentCore Runtime
- Python 3.10+ と AWS CDK v2 のインストール済み
- CDK バージョン 2.220.0 以降 (BedrockAgentCore サポート用)

## デプロイ

### CDK と CloudFormation の比較

これは MCP サーバー AgentCore ランタイムの **CDK バージョン** です。CloudFormation を好む場合は、[CloudFormation バージョン](../../cloudformation/mcp-server-agentcore-runtime/) をご覧ください。

### オプション 1: クイックデプロイ (推奨)

```bash
# 依存関係のインストール
pip install -r requirements.txt

# CDK のブートストラップ (初回のみ)
cdk bootstrap

# デプロイ
cdk deploy
```

### オプション 2: ステップバイステップ

```bash
# 1. Python 仮想環境を作成して有効化
python3 -m venv .venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate

# 2. Python 依存関係のインストール
pip install -r requirements.txt

# 3. アカウント/リージョンで CDK をブートストラップ (初回のみ)
cdk bootstrap

# 4. CloudFormation テンプレートを合成 (オプション)
cdk synth

# 5. スタックをデプロイ
cdk deploy --require-approval never

# 6. 出力を取得
cdk list
```

### デプロイ時間

デプロイには約 **10-15 分** かかり、以下が含まれます：
- すべての AWS リソースの作成
- Docker イメージのビルド
- ECR へのプッシュ
- AgentCore Runtime の起動

## テスト

### 1. 認証トークンの取得

まず、Cognito から JWT トークンを取得します：

```bash
# CDK 出力から Cognito ユーザープールクライアント ID を取得
CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name MCPServerDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolClientId`].OutputValue' \
  --output text)

# 認証トークンを取得
python get_token.py $CLIENT_ID testuser MyPassword123! us-east-1
```

これにより JWT トークンが出力されます。次のステップのためにトークンをコピーしてください。

### 2. MCP サーバーのテスト

```bash
# MCP サーバー Runtime ARN を取得
RUNTIME_ARN=$(aws cloudformation describe-stacks \
  --stack-name MCPServerDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerRuntimeArn`].OutputValue' \
  --output text)

# MCP サーバーをテスト (YOUR_JWT_TOKEN をステップ 1 のトークンに置き換え)
python test_mcp_server.py $RUNTIME_ARN YOUR_JWT_TOKEN us-east-1
```

これにより以下が実行されます：
- MCP サーバーに接続
- 利用可能なツールを一覧表示
- 3 つすべての MCP ツールをテスト
- 結果を表示

### 期待される出力

```
🔄 Initializing MCP session...
✓ MCP session initialized

🔄 Listing available tools...

📋 Available MCP Tools:
==================================================
🔧 add_numbers: Add two numbers together
🔧 multiply_numbers: Multiply two numbers together
🔧 greet_user: Greet a user by name

🧪 Testing MCP Tools:
==================================================

➕ Testing add_numbers(5, 3)...
   Result: 8

✖️  Testing multiply_numbers(4, 7)...
   Result: 28

👋 Testing greet_user('Alice')...
   Result: Hello, Alice! Nice to meet you.

✅ MCP tool testing completed!
```

## クリーンアップ

### CDK を使用 (推奨)

```bash
cdk destroy
```

### AWS CLI を使用

```bash
aws cloudformation delete-stack \
  --stack-name MCPServerDemo \
  --region us-east-1

# 削除完了を待機
aws cloudformation wait stack-delete-complete \
  --stack-name MCPServerDemo \
  --region us-east-1
```

## トラブルシューティング

### CDK ブートストラップが必要

ブートストラップエラーが表示された場合：
```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### 権限の問題

IAM ユーザー/ロールに以下があることを確認：
- `CDKToolkit` 権限または同等のもの
- スタック内のすべてのリソースを作成する権限
- サービスロール用の `iam:PassRole`

### Python 依存関係

プロジェクトディレクトリで依存関係をインストール：
```bash
pip install -r requirements.txt
```

テストには追加のパッケージが必要な場合があります：
```bash
pip install boto3 mcp
```

### 認証の問題

認証が失敗した場合：
- Cognito ユーザープールクライアント ID が正しいことを確認
- 正しいリージョンを使用していることを確認
- ユーザーが存在し、パスワードが正しいことを確認
- クライアントで USER_PASSWORD_AUTH が有効になっていることを確認

### ビルドの失敗

AWS コンソールで CodeBuild ログを確認：
1. CodeBuild コンソールに移動
2. ビルドプロジェクトを見つける (名前に "mcp-server-build" を含む)
3. ビルド履歴とログを確認

## コスト見積もり

### 月額コスト内訳 (us-east-1)

| サービス | 使用量 | 月額コスト |
|---------|--------|-----------|
| **AgentCore Runtime** | 1 ランタイム、最小使用量 | 約 $5-10 |
| **ECR リポジトリ** | 1 リポジトリ、<1GB ストレージ | 約 $0.10 |
| **CodeBuild** | 時折のビルド | 約 $1-2 |
| **Lambda** | カスタムリソースの実行 | 約 $0.01 |
| **Cognito ユーザープール** | 1 ユーザープール、最小使用量 | 約 $0.01 |
| **CloudWatch Logs** | エージェントログ | 約 $0.50 |

**推定合計: 約 $7-13/月**

### コスト最適化のヒント

- **使用しないときは削除**: `cdk destroy` を使用してすべてのリソースを削除
- **使用量を監視**: CloudWatch 請求アラームを設定
- **ビルドを最適化**: コード変更時のみ再ビルド

## コントリビューション

コントリビューションを歓迎します！詳細は [Contributing Guide](../../CONTRIBUTING.md) をご覧ください。

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](../../LICENSE) ファイルをご覧ください。

# MCP Server を AgentCore Runtime でホスティング - Terraform

このパターンは、Terraform を使用して Amazon Bedrock AgentCore Runtime 上に MCP (Model Context Protocol) サーバーをデプロイする方法を示しています。JWT 認証と 3 つのカスタムツールを持つ MCP サーバーを作成します。

## 目次

- [概要](#概要)
- [アーキテクチャ](#アーキテクチャ)
- [前提条件](#前提条件)
- [クイックスタート](#クイックスタート)
- [MCP サーバーのテスト](#mcp-サーバーのテスト)
- [サンプルツール呼び出し](#サンプルツール呼び出し)
- [カスタマイズ](#カスタマイズ)
- [ファイル構成](#ファイル構成)
- [トラブルシューティング](#トラブルシューティング)
- [クリーンアップ](#クリーンアップ)
- [料金](#料金)
- [次のステップ](#次のステップ)
- [リソース](#リソース)
- [コントリビューション](#コントリビューション)
- [ライセンス](#ライセンス)

## 概要

この Terraform 設定は、以下を含む MCP サーバーデプロイを作成します：

- **MCP Server**: 3 つのカスタムツール (add_numbers、multiply_numbers、greet_user) をホスト
- **JWT 認証**: セキュアなアクセスのための Cognito ユーザープール
- **AgentCore Runtime**: MCP プロトコルサポート付きのサーバーレスホスティング
- **ECR リポジトリ**: Docker コンテナイメージを保存
- **CodeBuild プロジェクト**: ARM64 Docker イメージを自動的にビルド

このスタックは、Amazon Bedrock AgentCore Python SDK を使用してエージェント関数を Amazon Bedrock AgentCore と互換性のある MCP サーバーとしてラップします。ツールをホスティングする際、SDK はセッション分離のための `MCP-Session-Id` ヘッダーを使用した [Stateless Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) トランスポートプロトコルを実装します。

これにより、以下に最適です：
- AgentCore Runtime で MCP プロトコルを学ぶ
- JWT 認証付きのセキュアな MCP サーバーを構築
- MCP ツール開発パターンを理解
- AI エージェント用のカスタムツールを作成

### チュートリアル詳細

| 情報              | 詳細                                                      |
|:------------------|:----------------------------------------------------------|
| チュートリアルタイプ | ツールのホスティング                                      |
| ツールタイプ       | MCP サーバー                                              |
| チュートリアル構成 | Terraform、AgentCore Runtime、MCP サーバー、Cognito       |
| チュートリアル分野 | クロスバーティカル                                        |
| 例の複雑さ         | 中級                                                      |
| 使用 SDK          | Amazon BedrockAgentCore Python SDK と MCP Client          |

## アーキテクチャ

![Architecture Diagram](architecture.png)

アーキテクチャは以下で構成されます：

- **ユーザー/MCP クライアント**: JWT 認証を使用して MCP サーバーにリクエストを送信
- **Amazon Cognito**: JWT ベースの認証を提供
  - 事前作成されたテストユーザー (testuser/MyPassword123!) を持つユーザープール
  - アプリケーションアクセス用のユーザープールクライアント
- **AWS CodeBuild**: MCP サーバーを含む ARM64 Docker コンテナイメージをビルド
- **Amazon ECR リポジトリ**: コンテナイメージを保存
- **AgentCore Runtime**: MCP Server をホスト
  - **MCP Server**: ポート 8000 で HTTP トランスポート経由で 3 つのツールを公開
    - `add_numbers`: 2 つの数を加算
    - `multiply_numbers`: 2 つの数を乗算
    - `greet_user`: ユーザーに名前で挨拶
  - Cognito からの JWT トークンを検証
  - MCP ツール呼び出しを処理
- **IAM ロール**:
  - CodeBuild 用 IAM ロール (イメージのビルドとプッシュ)
  - AgentCore Runtime 用 IAM ロール (ランタイム権限)

## 含まれる内容

この Terraform 設定は以下を作成します：

- **S3 バケット**: バージョン管理されたビルド用の MCP サーバーソースコードを保存
- **ECR リポジトリ**: MCP サーバー Docker イメージ用のコンテナレジストリ
- **CodeBuild プロジェクト**: 自動化された Docker イメージのビルドとプッシュ
- **Cognito ユーザープール**: 事前設定されたテストユーザーによる JWT 認証
- **Cognito ユーザープールクライアント**: 認証用のアプリケーションクライアント
- **IAM ロール**: AgentCore、CodeBuild、Cognito 操作用の実行ロール
- **AgentCore Runtime**: JWT 検証付きのサーバーレス MCP サーバーランタイム

### MCP サーバーコード管理

`mcp-server-code/` ディレクトリには MCP サーバーのソースファイルが含まれています：
- `mcp_server.py` - 3 つのツールを持つ MCP サーバー実装
- `Dockerfile` - コンテナ設定
- `requirements.txt` - Python 依存関係 (mcp>=1.10.0、boto3、bedrock-agentcore)

**自動変更検出**:
- Terraform は `mcp-server-code/` ディレクトリをアーカイブ
- MD5 ベースのバージョニングで S3 にアップロード
- CodeBuild が S3 からプルして Docker イメージをビルド
- ファイルへの変更は自動的に再ビルドをトリガー (新規ファイル、変更、削除)

## 前提条件

### 必要なツール

1. **Terraform** (>= 1.6)
   - **推奨**: バージョン管理用の [tfenv](https://github.com/tfutils/tfenv)
   - **または直接ダウンロード**: [terraform.io/downloads](https://www.terraform.io/downloads)

   **注意**: `brew install terraform` は v1.5.7 (非推奨) を提供します。>= 1.6 には tfenv または直接ダウンロードを使用してください。

2. **AWS CLI** (認証情報設定済み)
   ```bash
   aws configure
   ```

3. **Python 3.11+** (テストスクリプト用)
   ```bash
   python --version  # Python 3.11 以降を確認
   pip install boto3 mcp
   ```

4. **Docker** (ローカルテスト用、オプション)

### AWS アカウント要件

- 適切な権限を持つ AWS アカウント
- Amazon Bedrock AgentCore サービスへのアクセス
- 以下を作成する権限：
  - ECR リポジトリ
  - CodeBuild プロジェクト
  - Cognito ユーザープール
  - IAM ロールとポリシー
  - AgentCore Runtime リソース

## クイックスタート

### 1. 変数の設定

サンプル変数ファイルをコピーしてカスタマイズ：

```bash
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を好みの値で編集します。

### 2. Terraform の初期化

ローカルとリモートのステートに関する詳細なガイダンスは、メイン README の [ステート管理オプション](../README.md#state-management-options) を参照してください。

**ローカルステートでのクイックスタート:**
```bash
terraform init
```

**チームコラボレーションにはリモートステートを使用** - セットアップ手順は [メイン README](../README.md#state-management-options) を参照してください。

### 3. プランのレビュー

```bash
terraform plan
```

### 4. デプロイ

**方法 1: デプロイスクリプトを使用 (推奨)**

スクリプトを実行可能にする (初回のみ):
```bash
chmod +x deploy.sh
```

その後デプロイ:
```bash
./deploy.sh
```

デプロイスクリプトは以下を実行:
- Terraform 設定の検証
- デプロイプランの表示
- 確認のプロンプト
- 変更の適用

**方法 2: Terraform コマンドを直接使用**

```bash
terraform apply
```

プロンプトが表示されたら、`yes` と入力してデプロイを確認します。

**注意**: デプロイプロセスには以下が含まれます：
1. ECR リポジトリの作成
2. CodeBuild による Docker イメージのビルド
3. Cognito ユーザープールとテストユーザーの作成
4. MCP プロトコル付き AgentCore Runtime の作成

合計デプロイ時間: **約 5-10 分**

### 5. 出力の取得

デプロイ完了後：

```bash
terraform output
```

出力例：
```
agent_runtime_id = "AGENT1234567890"
agent_runtime_arn = "arn:aws:bedrock-agentcore:us-west-2:123456789012:agent-runtime/AGENT1234567890"
cognito_user_pool_id = "us-west-2_AbCdEfGhI"
cognito_user_pool_client_id = "1234567890abcdefghijklmno"
cognito_discovery_url = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_AbCdEfGhI/.well-known/openid-configuration"
test_username = "testuser"
get_token_command = "python get_token.py 1234567890abcdefghijklmno testuser MyPassword123! us-west-2"
```

## 認証モデル

このパターンは **Cognito JWT ベースの認証** を使用します：

- **JWT トークン**: Cognito ユーザープールが認証用の JWT トークンを発行
- **カスタム JWT 認可**: ランタイムが Cognito discovery URL に対して JWT トークンを検証
- **テストユーザー**: テスト用に事前設定されたユーザー (testuser/MyPassword123!)
- **トークン有効期限**: JWT トークンは 1 時間後に期限切れ
- **Discovery URL**: トークン検証用の OpenID Connect discovery エンドポイント

**認証フロー:**
1. ユーザーが Cognito ユーザープールで認証
2. Cognito が JWT アクセストークンを発行
3. クライアントが MCP リクエストヘッダーに JWT トークンを含める
4. ランタイムが Cognito の OIDC discovery エンドポイントを使用してトークンを検証
5. 認可されたリクエストが MCP サーバーで処理される

**注意**: これは MCP ツールアクセス用のバックエンド認証パターンです。ユーザー向けアプリケーションの場合は、ID プロバイダーと統合するか、エンドユーザー認証に Cognito ホスト UI を使用してください。

## MCP サーバーのテスト

### テストの前提条件

テスト前に、必要なパッケージがインストールされていることを確認：

**オプション A: uv を使用 (推奨)**
```bash
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
uv pip install boto3 mcp  # MCP サーバーテストに両方必要
```

**オプション B: システム全体へのインストール**
```bash
pip install boto3 mcp  # MCP サーバーテストに両方必要
```

**注意**: `boto3` (AWS API 呼び出し用) と `mcp` (MCP プロトコル用) の両方が MCP サーバーのテストに必要です。

### ステップ 1: 認証トークンの取得

まず、Cognito から JWT トークンを取得します：

```bash
# terraform 出力からコマンドを使用
terraform output -raw get_token_command | bash
```

または手動で：

```bash
# クライアント ID を取得
CLIENT_ID=$(terraform output -raw cognito_user_pool_client_id)
REGION=$(terraform output -raw aws_region)

# 認証トークンを取得
python get_token.py $CLIENT_ID testuser MyPassword123! $REGION
```

これにより JWT トークンが出力されます。次のステップのためにトークンをコピーしてください。

### ステップ 2: MCP サーバーのテスト

```bash
# Runtime ARN を取得
RUNTIME_ARN=$(terraform output -raw agent_runtime_arn)
REGION=$(terraform output -raw aws_region)

# MCP サーバーをテスト (YOUR_JWT_TOKEN をステップ 1 のトークンに置き換え)
python test_mcp_server.py $RUNTIME_ARN YOUR_JWT_TOKEN $REGION
```

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

## サンプルツール呼び出し

以下の MCP ツール呼び出しを試してください：

1. **数の加算**:
   ```python
   # ツール: add_numbers
   # パラメータ: {"a": 10, "b": 25}
   # 期待される結果: 35
   ```

2. **数の乗算**:
   ```python
   # ツール: multiply_numbers
   # パラメータ: {"a": 6, "b": 7}
   # 期待される結果: 42
   ```

3. **ユーザーへの挨拶**:
   ```python
   # ツール: greet_user
   # パラメータ: {"name": "John"}
   # 期待される結果: "Hello, John! Nice to meet you."
   ```

## カスタマイズ

### MCP サーバーコードの変更

`mcp-server-code/` 内のファイルを編集してデプロイ：

**新しいツールの追加**:

`mcp-server-code/mcp_server.py` を編集：
```python
@mcp.tool()
def subtract_numbers(a: int, b: int) -> int:
    """Subtract two numbers"""
    return a - b
```

**依存関係の更新**:

`mcp-server-code/requirements.txt` を編集：
```
mcp>=1.10.0
boto3
bedrock-agentcore
your-new-package>=1.0.0
```

変更は自動的に検出され、再ビルドがトリガーされます。デプロイするには `terraform apply` を実行します。

### 認証の変更

Cognito パスワードポリシーを変更するには、`cognito.tf` を編集：
```hcl
password_policy {
  minimum_length    = 12
  require_uppercase = true
  require_lowercase = true
  require_numbers   = true
  require_symbols   = true
}
```

### 環境変数

`terraform.tfvars` に追加：
```hcl
environment_variables = {
  LOG_LEVEL = "DEBUG"
  CUSTOM_VAR = "value"
}
```

### ネットワークモード

VPC デプロイには `network_mode = "PRIVATE"` を設定 (追加の VPC 設定が必要)。

## ファイル構成

```
mcp-server-agentcore-runtime/
├── main.tf                      # MCP プロトコル付き AgentCore ランタイム
├── variables.tf                 # 入力変数
├── outputs.tf                   # 出力値 (Cognito を含む)
├── versions.tf                  # プロバイダー設定
├── iam.tf                       # IAM ロールとポリシー
├── s3.tf                        # MCP サーバーソース用 S3 バケット
├── ecr.tf                       # ECR リポジトリ
├── codebuild.tf                 # Docker ビルド自動化
├── cognito.tf                   # Cognito ユーザープールとクライアント
├── buildspec.yml                # CodeBuild ビルド仕様
├── terraform.tfvars.example     # 設定例
├── backend.tf.example           # リモートステート例
├── mcp-server-code/             # MCP サーバーソースコード
│   ├── mcp_server.py           # 3 つのツールを持つ MCP サーバー
│   ├── Dockerfile              # コンテナ設定
│   └── requirements.txt        # Python 依存関係
├── scripts/                     # ビルド自動化スクリプト
│   └── build-image.sh          # CodeBuild トリガーと検証
├── get_token.py                 # Cognito JWT トークン取得
├── test_mcp_server.py           # MCP サーバーテストスクリプト
├── deploy.sh                    # デプロイヘルパースクリプト
├── destroy.sh                   # クリーンアップヘルパースクリプト
├── architecture.png             # アーキテクチャ図
├── .gitignore                   # Git 無視パターン
└── README.md                    # このファイル
```

## トラブルシューティング

### CodeBuild の失敗

Docker ビルドが失敗した場合：

1. CodeBuild ログを確認：
   ```bash
   PROJECT_NAME=$(terraform output -raw codebuild_project_name)
   aws codebuild batch-get-builds \
     --ids $PROJECT_NAME
   ```

2. よくある問題：
   - ネットワーク接続の問題
   - ECR 認証の問題
   - requirements.txt の Python 依存関係の競合

### ランタイム作成の失敗

ランタイム作成が失敗した場合：

1. Docker イメージが存在することを確認：
   ```bash
   REPO_NAME=$(terraform output -raw ecr_repository_url | cut -d'/' -f2)
   aws ecr describe-images --repository-name $REPO_NAME
   ```

2. IAM ロールの権限を確認
3. Bedrock AgentCore サービスクォータを確認
4. MCP プロトコルが正しく設定されていることを確認

### 認証の問題

JWT 認証が失敗した場合：

1. Cognito ユーザーが存在することを確認：
   ```bash
   USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)
   aws cognito-idp admin-get-user \
     --user-pool-id $USER_POOL_ID \
     --username testuser
   ```

2. トークンの有効期限を確認 (トークンは 1 時間後に期限切れ)
3. discovery URL がアクセス可能であることを確認
4. allowed_clients がクライアント ID と一致していることを確認

### MCP サーバー接続の失敗

MCP ツール呼び出しが失敗した場合：

1. AWS コンソールでランタイムステータスを確認
2. ランタイムの CloudWatch Logs を確認
3. JWT トークンが有効で期限切れでないことを確認
4. MCP プロトコルが正しく設定されていることを確認
5. ランタイムが ACTIVE 状態であることを確認

## クリーンアップ

### すべてのリソースを削除

スクリプトを実行可能にする (初回のみ):
```bash
chmod +x destroy.sh
```

その後クリーンアップ:
```bash
./destroy.sh
```

または Terraform を直接使用：

```bash
terraform destroy
```

**注意**: 以下が削除されます：
- AgentCore Runtime
- ECR リポジトリ (およびすべてのイメージ)
- Cognito ユーザープール (およびすべてのユーザー)
- S3 バケット (およびすべてのソースコードアーカイブ)
- すべての IAM ロールとポリシー

### クリーンアップの確認

すべてのリソースが削除されたことを確認：

```bash
# AgentCore ランタイムを確認
aws bedrock-agentcore list-agent-runtimes

# ECR リポジトリを確認
aws ecr describe-repositories | grep mcp-server

# Cognito ユーザープールを確認
aws cognito-idp list-user-pools --max-results 10
```

## 料金

最新の料金情報については、以下を参照してください：
- [Amazon Bedrock 料金](https://aws.amazon.com/bedrock/pricing/)
- [Amazon ECR 料金](https://aws.amazon.com/ecr/pricing/)
- [AWS CodeBuild 料金](https://aws.amazon.com/codebuild/pricing/)
- [Amazon Cognito 料金](https://aws.amazon.com/cognito/pricing/)
- [Amazon S3 料金](https://aws.amazon.com/s3/pricing/)
- [Amazon CloudWatch 料金](https://aws.amazon.com/cloudwatch/pricing/)
- [AWS Lambda 料金](https://aws.amazon.com/lambda/pricing/)

**注意**: 実際のコストは、使用パターン、AWS リージョン、および消費した特定のサービスによって異なります。

## 次のステップ

### 他のパターンを探索

- [Basic Runtime](../basic-runtime/) - MCP プロトコルなしのよりシンプルなデプロイ
- [Multi-Agent Runtime](../multi-agent-runtime/) - 複数の連携するエージェントをデプロイ
- [End-to-End Weather Agent](../end-to-end-weather-agent/) - ツールを備えたフル機能エージェント

### このパターンを拡張

- `mcp-server-code/mcp_server.py` に MCP ツールを追加
- 外部 API と統合
- 永続ストレージを追加 (DynamoDB、S3)
- カスタム認証ロジックを実装
- モニタリングとアラートを追加
- プライベートネットワーク用に VPC にデプロイ

### MCP についてさらに学ぶ

- [Model Context Protocol 仕様](https://modelcontextprotocol.io/specification/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP サーバーの構築](https://modelcontextprotocol.io/docs/building-mcp-servers)

## リソース

- [Terraform AWS プロバイダードキュメント](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Amazon Cognito ドキュメント](https://docs.aws.amazon.com/cognito/)
- [AgentCore サンプルリポジトリ](https://github.com/aws-samples/amazon-bedrock-agentcore-samples)

## コントリビューション

コントリビューションを歓迎します！詳細は [Contributing Guide](../../../CONTRIBUTING.md) をご覧ください。

## ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](../../../LICENSE) ファイルをご覧ください。

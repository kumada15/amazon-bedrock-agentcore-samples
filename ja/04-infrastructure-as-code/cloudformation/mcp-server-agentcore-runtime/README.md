# MCP Server を AgentCore Runtime でホスティング - CloudFormation

## 概要

この CloudFormation テンプレートは、Amazon Bedrock AgentCore Runtime 上に MCP (Model Context Protocol) サーバーをデプロイします。Infrastructure as Code を使用して AgentCore Runtime 上に MCP ツールをホストする方法を示し、効率的なエクスペリエンスのための自動化されたデプロイスクリプトを提供します。

このテンプレートは、Amazon Bedrock AgentCore Python SDK を使用してエージェント関数を Amazon Bedrock AgentCore と互換性のある MCP サーバーとしてラップします。MCP サーバーの詳細を処理するため、エージェントのコア機能に集中できます。

ツールをホスティングする際、Amazon Bedrock AgentCore Python SDK は、セッション分離のための `MCP-Session-Id` ヘッダーを使用した [Stateless Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) トランスポートプロトコルを実装します。MCP サーバーはポート `8000` でホストされ、1 つの呼び出しパス (`mcp-POST` エンドポイント) を提供します。

### チュートリアル詳細

| 情報              | 詳細                                                      |
|:------------------|:----------------------------------------------------------|
| チュートリアルタイプ | ツールのホスティング                                      |
| ツールタイプ       | MCP サーバー                                              |
| チュートリアル構成 | CloudFormation、AgentCore Runtime、MCP サーバー           |
| チュートリアル分野 | クロスバーティカル                                        |
| 例の複雑さ         | 簡単                                                      |
| 使用 SDK          | Amazon BedrockAgentCore Python SDK と MCP Client          |

### アーキテクチャ

![MCP Server AgentCore Runtime Architecture](architecture.png)

この CloudFormation テンプレートは、3 つのツール (`add_numbers`、`multiply_numbers`、`greet_user`) を持つシンプルな MCP サーバーをデプロイします。

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

* **ワンコマンドデプロイ** - 自動化スクリプトがすべてを処理
* **完全なインフラストラクチャ** - 完全な Infrastructure as Code
* **デフォルトでセキュア** - Cognito による JWT 認証
* **自動ビルド** - CodeBuild が ARM64 Docker イメージを作成
* **簡単なテスト** - 自動テストスクリプト付属
* **シンプルなクリーンアップ** - 1 コマンドですべてのリソースを削除

## デプロイされる内容

CloudFormation スタックは以下を作成します：

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
- Python 3.8+ (テスト用)
- `boto3` と `mcp` Python パッケージ (テストスクリプトにより自動インストール)

## クイックスタート

### 1. スタックのデプロイ

```bash
cd 04-infrastructure-as-code/cloudformation/mcp-server-agentcore-runtime
./deploy.sh
```

デプロイには約 **10-15 分** かかり、以下が含まれます：
- すべての AWS リソースの作成
- Docker イメージのビルド
- ECR へのプッシュ
- AgentCore Runtime の起動

### 2. MCP サーバーのテスト

デプロイ完了後：

```bash
./test.sh
```

これにより以下が実行されます：
- Cognito での認証
- 3 つすべての MCP ツールのテスト
- 結果の表示

### 3. クリーンアップ

完了したら：

```bash
./cleanup.sh
```

これにより作成されたすべてのリソースが削除されます。

## コンポーネントの理解

#### 認証フロー

1. ユーザーがユーザー名/パスワードで Cognito 認証
2. Cognito がアクセストークン (JWT) を返却
3. アクセストークンが Bearer トークンとして AgentCore Runtime に渡される
4. AgentCore Runtime が Cognito でトークンを検証
5. 有効な場合、MCP サーバーがリクエストを処理

#### MCP サーバーの実装

MCP サーバーは CodeBuild の buildspec に埋め込まれており、以下を含みます：

```python
from bedrock_agentcore.mcp import MCPServer

server = MCPServer()

@server.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

@server.tool()
def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers together."""
    return a * b

@server.tool()
def greet_user(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}!"
```

#### Docker イメージビルド

CodeBuild は自動的に以下を実行：
1. Python 3.12 ARM64 環境を作成
2. 依存関係をインストール
3. MCP サーバーコードを作成
4. Docker イメージをビルド
5. ECR にプッシュ
6. AgentCore Runtime の更新をトリガー





## 追加リソース

- [Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Model Context Protocol 仕様](https://modelcontextprotocol.io/)
- [CloudFormation テンプレートリファレンス](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/AWS_BedrockAgentCore.html)
- [オリジナルチュートリアル](../../01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/)
- [詳細技術ガイド](DETAILED_GUIDE.md)

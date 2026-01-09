# Customer Support Assistant - Private VPC

> [!IMPORTANT]
> このリポジトリで提供される例は、実験および教育目的のみです。概念と技術を示していますが、本番環境での直接使用を意図したものではありません。

これは完全なプライベート VPC 環境にデプロイされた Amazon Bedrock AgentCore を使用したカスタマーサポートエージェントの実装です。保証確認、顧客プロファイル管理、Aurora PostgreSQL、DynamoDB テーブル、Lambda ベース API を含む複数のデータソースへのクロスシステムデータアクセス機能を備えた AI 駆動のカスタマーサポートインターフェースを提供します。このアーキテクチャは、インターネット接続なしで AWS サービスアクセスに VPC エンドポイントを使用した安全で分離されたデプロイメントを示しています。

## アーキテクチャ概要

![arch](./images/architecture.png)

## デモ

![demo](./images/demo.gif)

## 前提条件

1. **AWS アカウント**: 適切な権限を持つ有効な AWS アカウントが必要です
   - [AWS アカウント作成](https://aws.amazon.com/account/)
   - [AWS コンソールアクセス](https://aws.amazon.com/console/)

2. **AWS CLI**: AWS CLI をインストールし、認証情報を設定します
   - [AWS CLI のインストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [AWS CLI の設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

   ```bash
   aws configure
   ```

3. **Bedrock モデルアクセス**: AWS リージョンで Amazon Bedrock Anthropic Claude 4.0 モデルへのアクセスを有効にします
   - [Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock/)に移動
   - 「モデルアクセス」に移動し、以下へのアクセスをリクエスト：
     - Anthropic Claude 4.0 Sonnet モデル
     - Anthropic Claude 3.5 Haiku モデル
   - [Amazon Bedrock モデルアクセスガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. [ガイド](https://docs.astral.sh/uv/getting-started/installation/)に従って uv をインストールしてください。

5. **サポートされるリージョン**: このソリューションは現在、以下の AWS リージョンでテストおよびサポートされています：

   | リージョンコード | リージョン名 | ステータス |
   |------------------|--------------|------------|
   | `us-west-2`      | 米国西部（オレゴン） | ✅ サポート対象 |

   > **注意**: 他のリージョンにデプロイするには、`cloudformation/vpc-stack.yaml` の DynamoDB プレフィックスリストマッピングを更新する必要があります。詳細は [VPC スタックドキュメント](cloudformation/vpc-stack.yaml)を参照してください。

## デプロイ手順

> [!NOTE]
> このスクリプトは AWS アカウントへのリソースのデプロイを自動化します。作成されるリソースについては[デプロイされるリソース](#デプロイされるリソース)を参照してください。

```bash
# 実行可能にする
chmod +x deploy.sh

./deploy.sh --help
# またはモデルをカスタマイズ
./deploy.sh --model global.anthropic.claude-haiku-4-5-20251001-v1:0 --region us-west-2 --env dev --email <EmailAddress> --password <Password>


```

### デプロイされるリソース

デプロイにより、以下の CloudFormation スタックと AWS リソースが作成されます：

<details>
<summary><b>0. S3 バケット</b>（<code>deploy.sh</code> によって作成）</summary>

- 自動生成された名前を持つ **1 つの S3 バケット**（`customersupportvpc-*` プレフィックス）
- CloudFormation テンプレートのバージョン管理用に**バージョニング有効**
- **目的**: すべての CloudFormation ネストスタックテンプレートをホスト
- **ライフサイクル**: デプロイが成功し、テンプレートを更新しない場合は削除可能

</details>

<details>
<summary><b>1. VPC スタック</b>（<code>vpc-stack.yaml</code>）</summary>

- DNS サポートが有効な **1 つの VPC**
- 3 つのアベイラビリティゾーンにまたがる **4 つのプライベートサブネット**
- プライベートサブネット用の **1 つのルートテーブル**
- **13 の VPC エンドポイント**（インターフェースおよびゲートウェイ）：
  - Bedrock Runtime & AgentCore
  - ECR（API & Docker）
  - CloudWatch Logs & Monitoring
  - DynamoDB ゲートウェイエンドポイント
  - S3 ゲートウェイエンドポイント
  - Secrets Manager
  - RDS Data API
  - KMS
  - SSM Parameter Store
  - X-Ray
- **3 つのセキュリティグループ**（VPC エンドポイント、エージェントランタイム、MCP ランタイム）
- VPC フローログ暗号化用の **1 つの KMS キー**
- VPC フローログ用の **1 つの CloudWatch ロググループ**

</details>

<details>
<summary><b>2. Cognito スタック</b>（<code>cognito-m2m-stack.yaml</code>）</summary>

- M2M 認証用の **1 つの Cognito ユーザープール**
- OAuth エンドポイント用の **1 つのユーザープールドメイン**
- カスタムスコープ（read、write、gateway、agent）を持つ **1 つのリソースサーバー**
- クライアント認証情報フローを持つ **3 つのアプリクライアント**（Gateway、Agent、MCP）
- クライアント設定用の **3 つの Secrets Manager シークレット**
- Secrets Manager 暗号化用の **1 つの KMS キー**
- クライアントシークレットの取得と保存用の **1 つの Lambda 関数**
- クライアントシークレット更新用の **3 つのカスタムリソース**

</details>

<details>
<summary><b>3. Aurora PostgreSQL スタック</b>（<code>aurora-postgres-stack.yaml</code>）</summary>

- RDS Data API が有効な **1 つの Aurora PostgreSQL クラスター**
- **1 つの Aurora インスタンス**（db.r5.large）
- 2 つのサブネットにまたがる **1 つの DB サブネットグループ**
- データベース暗号化用の **1 つの KMS キー**
- **2 つのセキュリティグループ**（Aurora、Lambda）
- Lambda レイヤーアーティファクト用の **1 つの S3 バケット**
- psycopg2 レイヤービルド用の **1 つの CodeBuild プロジェクト**
- **1 つの Lambda レイヤー**（psycopg2）
- **2 つの Lambda 関数**（レイヤービルダー、モックデータローダー）
- **サンプルデータ**: モックレコードを含む Users、Products、Orders テーブル

</details>

<details>
<summary><b>4. DynamoDB スタック</b>（<code>dynamodb-stack.yaml</code>）</summary>

- **2 つの DynamoDB テーブル**：
  - Reviews テーブル（3 つの GSI：product、customer、rating）
  - Products テーブル（4 つの GSI：category、name、price、stock）
- DynamoDB 暗号化用の **1 つの KMS キー**
- データ投入用の **1 つの Lambda 関数**
- テーブル名用の **2 つの SSM パラメータ**
- **サンプルデータ**: 5 つのレビューと 5 つの製品

</details>

<details>
<summary><b>5. MCP Server スタック</b>（<code>mcp-server-stack.yaml</code>）</summary>

- MCP Docker イメージ用の **1 つの ECR リポジトリ**
- **1 つの Bedrock AgentCore MCP ランタイム**
- Docker イメージビルド用の **1 つの CodeBuild プロジェクト**
- ビルドオーケストレーション用の **1 つの Lambda 関数**
- ECR イメージ通知用の **1 つの Lambda 関数**
- 自動更新用の **1 つの EventBridge ルール**
- MCP 認証用の **1 つの OAuth2 認証情報プロバイダー**
- **3 つの IAM ロール**（ランタイム実行、CodeBuild、Lambda）

</details>

<details>
<summary><b>6. Gateway スタック</b>（<code>gateway-stack.yaml</code>）</summary>

- MCP プロトコルを備えた **1 つの Bedrock AgentCore Gateway**
- **1 つの Gateway ターゲット**（Lambda 統合）
- カスタマーサポートツール用の **1 つの Lambda 関数**（保証確認、プロファイル検索）
- Gateway 管理用の **1 つの Lambda 関数**
- データ投入用の **1 つの Lambda 関数**
- **2 つの DynamoDB テーブル**：
  - Warranty テーブル（KMS で暗号化）
  - Customer Profile テーブル（2 つの GSI：email、phone）
- DynamoDB 暗号化用の **1 つの KMS キー**
- Gateway 認証用の **1 つの OAuth2 認証情報プロバイダー**
- **3 つの SSM パラメータ**（Gateway ID、ARN、URL）
- **3 つの IAM ロール**（Gateway、Lambda、管理）
- **サンプルデータ**: 5 つの保証と 5 つの顧客プロファイル

</details>

<details>
<summary><b>7. Agent Server スタック</b>（<code>agent-server-stack.yaml</code>）</summary>

- Agent Docker イメージ用の **1 つの ECR リポジトリ**
- HTTP プロトコルを備えた **1 つの Bedrock AgentCore Agent ランタイム**
- Agent Docker ビルド用の **1 つの CodeBuild プロジェクト**
- **2 つの Lambda 関数**（ビルドオーケストレーション、ECR 通知）
- 自動更新用の **1 つの EventBridge ルール**
- Agent 認証用の **1 つの OAuth2 認証情報プロバイダー**
- **4 つの IAM ロール**（ランタイム実行、CodeBuild、Lambda）
- **環境変数**: モデル ID、MCP ARN、Gateway プロバイダー、Aurora 認証情報

</details>

## テスト

デプロイ後、提供されているテストスクリプトを使用してシステムをテストできます：

### Agent Runtime のテスト

Agent Runtime とのインタラクティブなチャットセッションを開始：

![runtime-aurora](./images/agent.png)

```bash
# 依存関係をインストール
uv sync

# インタラクティブセッションを開始
uv run python test/connect_agent.py
```

これにより、エージェントと会話できるインタラクティブなチャットインターフェースが起動します。質問を入力して Enter を押して送信します。`q` または `quit` と入力して終了します。

**パラメータ：**

- `--verbose` / `-v`（オプション）: 詳細ログを有効化
- `--debug`（オプション）: デバッグログを有効化

### MCP Server のテスト

MCP DynamoDB サーバーをテストし、利用可能なツールを一覧表示：

![runtime-mcp](./images/mcp.png)

```bash
# 依存関係をインストール
uv sync

uv run python test/connect_mcp.py
```

**パラメータ：**

- `--verbose` / `-v`（オプション）: 詳細ログを有効化
- `--debug`（オプション）: デバッグログを有効化

このスクリプトは以下を実行します：

1. MCP サーバーに接続
2. 利用可能なすべてのツールを一覧表示（get_reviews、get_products など）
3. DynamoDB テーブルに対してテストクエリを実行

### AgentCore Gateway のテスト

![runtime-mcp](./images/gateway.png)

```bash
  # 依存関係をインストール
  uv sync

  # Gateway をテスト
  uv run python test/connect_gateway.py --prompt "Check warranty status for serial number LAPTOP001A1B2C"

  # 詳細ログ付き
  uv run python test/connect_gateway.py --prompt "Get customer profile for CUST001"

  # カスタムスタック名を使用
```

- `--verbose` / `-v`（オプション）: 詳細ログを有効化
- `--debug`（オプション）: デバッグログを有効化

## React フロントエンド

以下のコマンドで[フロントエンド](./frontend/README.md)を実行します。

```bash
cd frontend
npm install

chmod +x ./setup-env.sh
./setup-env.sh

npm run dev

```

## サンプルクエリ

1. CUST001 の顧客について、購入履歴やサポートの詳細を含む完全なプロファイルを教えてください。
2. Laptop Pro 製品（シリアル番号：LAPTOP001A1B2C、レビュー ID 1 および 2）について、カスタマーレビュー、在庫状況、保証情報を含めて教えてください。
3. Bob Johnson のアカウント（CUST003）と、最近の購入で発生した可能性のある問題について教えてください。
4. ノートパソコンを購入した顧客とその感想は？また、現在の在庫レベルも確認してください。
5. Electronics カテゴリのすべての製品、そのレビュー、および購入パターンに基づいてこのカテゴリを好む顧客を表示してください。
6. Jane Smith の登録から最新のインタラクションまでの完全なカスタマージャーニーを追跡してください。
7. CUST004 のシステム間のデータ整合性を確認し、不整合があれば強調表示してください。
8. 最も価値のある顧客は誰で、どの製品を好みますか？サポートエンゲージメントレベルも含めてください。

## クリーンアップ

デプロイされたリソースを削除するには、提供されているクリーンアップスクリプトを使用します：

```bash
# 実行可能にする
chmod +x cleanup.sh

./cleanup.sh --help

# VPC 以外のすべてのスタックを削除
./cleanup.sh --delete-s3  --region us-west-2

```

> [!WARNING]
> Amazon Bedrock AgentCore Runtime は VPC に [ENI](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html) を作成します。これらの ENI はサービスによって自動的に削除されるまで約 8 時間かかります。ENI が削除された後、VPC スタックを手動で削除してください。

```bash
./cleanup.sh --delete-vpc  --region us-west-2
```

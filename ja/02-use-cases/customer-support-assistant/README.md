# カスタマーサポートエージェント

> [!IMPORTANT]
> このリポジトリで提供される例は、実験および教育目的のみです。概念と技術を示すものであり、本番環境での直接使用を意図したものではありません。

これは Amazon Bedrock AgentCore フレームワークを使用したカスタマーサポートエージェントの実装です。このシステムは、保証確認、顧客プロファイル管理、Google カレンダー統合、Amazon Bedrock Knowledge Base 取得機能を備えた AI 駆動のカスタマーサポートインターフェースを提供します。

![architecture](./images/architecture.png)

## 目次

- [カスタマーサポートエージェント](#カスタマーサポートエージェント)
  - [目次](#目次)
  - [前提条件](#前提条件)
    - [AWS アカウントセットアップ](#aws-アカウントセットアップ)
  - [デプロイ](#デプロイ)
  - [サンプルクエリ](#サンプルクエリ)
  - [スクリプト](#スクリプト)
    - [Amazon Bedrock AgentCore Gateway](#amazon-bedrock-agentcore-gateway)
      - [Amazon Bedrock AgentCore Gateway の作成](#amazon-bedrock-agentcore-gateway-の作成)
      - [Amazon Bedrock AgentCore Gateway の削除](#amazon-bedrock-agentcore-gateway-の削除)
    - [Amazon Bedrock AgentCore Memory](#amazon-bedrock-agentcore-memory)
      - [Amazon Bedrock AgentCore Memory の作成](#amazon-bedrock-agentcore-memory-の作成)
      - [Amazon Bedrock AgentCore Memory の削除](#amazon-bedrock-agentcore-memory-の削除)
    - [Cognito 認証情報プロバイダー](#cognito-認証情報プロバイダー)
      - [Cognito 認証情報プロバイダーの作成](#cognito-認証情報プロバイダーの作成)
      - [Cognito 認証情報プロバイダーの削除](#cognito-認証情報プロバイダーの削除)
    - [Google 認証情報プロバイダー](#google-認証情報プロバイダー)
      - [認証情報プロバイダーの作成](#認証情報プロバイダーの作成)
      - [認証情報プロバイダーの削除](#認証情報プロバイダーの削除)
    - [Agent Runtime](#agent-runtime)
      - [Agent Runtime の削除](#agent-runtime-の削除)
  - [クリーンアップ](#クリーンアップ)
  - [🤝 貢献](#-貢献)
  - [📄 ライセンス](#-ライセンス)
  - [🆘 サポート](#-サポート)
  - [🔄 更新](#-更新)

## 前提条件

### AWS アカウントセットアップ

1. **AWS アカウント**：適切な権限を持つ有効な AWS アカウントが必要です
   - [AWS アカウント作成](https://aws.amazon.com/account/)
   - [AWS コンソールアクセス](https://aws.amazon.com/console/)

2. **AWS CLI**：AWS CLI をインストールし、認証情報を設定します
   - [AWS CLI のインストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [AWS CLI の設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

   ```bash
   aws configure
   ```

3. **IAM 権限**：デプロイと運用に必要な IAM 権限

   このサンプルを正常にデプロイおよび実行するには、AWS ユーザーまたはロールに以下の権限が必要です：

   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Sid": "AllowS3VectorOperations",
               "Effect": "Allow",
               "Action": [
                   "s3vectors:*"
               ],
               "Resource": "*"
           },
           {
               "Sid": "AllowSSMParameterOperations",
               "Effect": "Allow",
               "Action": [
                   "ssm:PutParameter",
                   "ssm:GetParameter",
                   "ssm:GetParameters",
                   "ssm:GetParametersByPath",
                   "ssm:DeleteParameter",
                   "ssm:DeleteParameters",
                   "ssm:DescribeParameters",
                   "ssm:AddTagsToResource"
               ],
               "Resource": "*"
           },
           {
               "Sid": "AllowDynamoDBOperations",
               "Effect": "Allow",
               "Action": [
                   "dynamodb:DescribeTable",
                   "dynamodb:CreateTable",
                   "dynamodb:DeleteTable",
                   "dynamodb:UpdateTable",
                   "dynamodb:PutItem",
                   "dynamodb:GetItem",
                   "dynamodb:UpdateItem",
                   "dynamodb:DeleteItem",
                   "dynamodb:Query",
                   "dynamodb:Scan",
                   "dynamodb:BatchGetItem",
                   "dynamodb:BatchWriteItem",
                   "dynamodb:DescribeTimeToLive",
                   "dynamodb:UpdateTimeToLive",
                   "dynamodb:TagResource",
                   "dynamodb:UntagResource",
                   "dynamodb:ListTagsOfResource",
                   "dynamodb:UpdateContinuousBackups",
                   "dynamodb:DescribeContinuousBackups"
               ],
               "Resource": "*"
           },
           {
               "Sid": "AllowCognitoOperations",
               "Effect": "Allow",
               "Action": [
                   "cognito-idp:CreateUserPool",
                   "cognito-idp:DeleteUserPool",
                   "cognito-idp:DescribeUserPool",
                   "cognito-idp:UpdateUserPool",
                   "cognito-idp:CreateUserPoolClient",
                   "cognito-idp:DeleteUserPoolClient",
                   "cognito-idp:DescribeUserPoolClient",
                   "cognito-idp:UpdateUserPoolClient",
                   "cognito-idp:CreateGroup",
                   "cognito-idp:DeleteGroup",
                   "cognito-idp:GetGroup",
                   "cognito-idp:UpdateGroup",
                   "cognito-idp:ListGroups",
                   "cognito-idp:CreateResourceServer",
                   "cognito-idp:DeleteResourceServer",
                   "cognito-idp:DescribeResourceServer",
                   "cognito-idp:UpdateResourceServer",
                   "cognito-idp:SetUserPoolMfaConfig",
                   "cognito-idp:TagResource",
                   "cognito-idp:UntagResource",
                   "cognito-idp:ListTagsForResource"
               ],
               "Resource": "*"
           }
       ]
   }
   ```

   **追加権限**：完全な Amazon Bedrock アクセスのために `AmazonBedrockFullAccess` マネージドポリシーの追加を検討してください。

   **注意**：上記の権限は簡略化のために `"Resource": "*"` を使用しています。本番環境では、最小権限の原則に従って特定のリソースに範囲を限定する必要があります。

4. **Bedrock モデルアクセス**：AWS リージョンで Amazon Bedrock Anthropic Claude 4.0 モデルへのアクセスを有効にします
   - [Amazon Bedrock コンソール](https://console.aws.amazon.com/bedrock/)に移動
   - 「モデルアクセス」に移動し、以下へのアクセスをリクエスト：
     - Anthropic Claude 4.0 Sonnet モデル
     - Anthropic Claude 3.5 Haiku モデル
   - [Bedrock モデルアクセスガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

5. **Python 3.10+**：アプリケーション実行に必要
   - [Python ダウンロード](https://www.python.org/downloads/)

6. **uv**：モダンな Python パッケージインストーラーおよびリゾルバー
   - [uv のインストール](https://github.com/astral-sh/uv)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

7. **カレンダーアクセス用の OAuth 2.0 認証情報の作成**：Google カレンダー統合用
   - [Google OAuth セットアップ](./prerequisite/google_oauth_setup.md)に従ってください

## デプロイ

1. **インフラストラクチャの作成**

    ```bash
    # AWS リージョンを設定（デフォルトは us-east-1）
    export AWS_DEFAULT_REGION=us-east-1

    # uv を使用して依存関係をインストール
    uv sync
    source .venv/bin/activate
    chmod +x scripts/prereq.sh
    ./scripts/prereq.sh

    chmod +x scripts/list_ssm_parameters.sh
    ./scripts/list_ssm_parameters.sh
    ```

    > [!NOTE]
    > デプロイはデフォルトで `us-east-1` リージョンになります。別のリージョンにデプロイするには、スクリプト実行前に `AWS_DEFAULT_REGION` 環境変数を設定してください。例えば、`us-west-2` にデプロイする場合：
    > ```bash
    > export AWS_DEFAULT_REGION=us-west-2
    > ```

    > [!CAUTION]
    > すべてのリソース名には `customersupport` プレフィックスを付けてください。

2. **Agentcore Gateway の作成**

    ```bash
    uv run python scripts/agentcore_gateway.py create --name customersupport-gw
    ```

3. **Agentcore Identity のセットアップ**

    - **Cognito 認証情報プロバイダーのセットアップ**

    ```bash
    uv run python scripts/cognito_credentials_provider.py create --name customersupport-gateways

    uv run python test/test_gateway.py --prompt "Check warranty with serial number MNO33333333"
    ```

    - **Google 認証情報プロバイダーのセットアップ**

    [Google 認証情報](./prerequisite/google_oauth_setup.md)のセットアップ手順に従ってください。

    ```bash
    uv run python scripts/google_credentials_provider.py create --name customersupport-google-calendar

    uv run python test/test_google_tool.py
    ```

4. **Memory の作成**

    ```bash
    uv run python scripts/agentcore_memory.py create --name customersupport

    uv run python test/test_memory.py load-conversation
    uv run python test/test_memory.py load-prompt "My preference of gaming console is V5 Pro"
    uv run python test/test_memory.py list-memory
    ```

5. **Agent Runtime のセットアップ**

> [!CAUTION]
> エージェント名は `customersupport` で始まるようにしてください。

  ```bash
  agentcore configure --entrypoint main.py -er arn:aws:iam::<Account-Id>:role/<Role> --name customersupport<AgentName>
  ```

  `./scripts/list_ssm_parameters.sh` を使用して以下を入力：
  - `Role = ValueOf(/app/customersupport/agentcore/runtime_iam_role)`
  - `OAuth Discovery URL = ValueOf(/app/customersupport/agentcore/cognito_discovery_url)`
  - `OAuth client id = ValueOf(/app/customersupport/agentcore/web_client_id)`

  ![configure](./images/runtime_configure.png)

  > [!CAUTION]
  > agentcore launch を実行する前に `.agentcore.yaml` を削除してください。

  ```bash

  rm .agentcore.yaml

  agentcore launch

  uv run python test/test_agent.py customersupport<AgentName> -p "Hi"
  ```

  ![code](./images/code.png)

6. **Streamlit UI のローカルホスト**

> [!CAUTION]
> Streamlit アプリはポート `8501` でのみ実行してください。

```bash
uv run streamlit run app.py --server.port 8501 -- --agent=customersupport<AgentName>
```

## サンプルクエリ

1. Gaming Console Pro デバイスを持っています。保証ステータスを確認したいです。保証シリアル番号は MNO33333333 です。

2. 保証サポートガイドラインは何ですか？

3. 今日の予定は何ですか？

4. 保証更新の電話を設定するイベントを作成できますか？

5. デバイスの過熱問題があります。デバッグを手伝ってください。

## スクリプト

### Amazon Bedrock AgentCore Gateway

#### Amazon Bedrock AgentCore Gateway の作成

```bash
uv run python scripts/agentcore_gateway.py create --name my-gateway
uv run python scripts/agentcore_gateway.py create --name my-gateway --api-spec-file custom/path.json
```

#### Amazon Bedrock AgentCore Gateway の削除

```bash
# Gateway を削除（gateway.config から自動的に読み取り）
uv run python scripts/agentcore_gateway.py delete

# 確認をスキップして削除
uv run python scripts/agentcore_gateway.py delete --confirm
```

### Amazon Bedrock AgentCore Memory

#### Amazon Bedrock AgentCore Memory の作成

```bash
uv run python scripts/agentcore_memory.py create --name MyMemory
uv run python scripts/agentcore_memory.py create --name MyMemory --event-expiry-days 60
```

#### Amazon Bedrock AgentCore Memory の削除

```bash
# Memory を削除（SSM から自動的に読み取り）
uv run python scripts/agentcore_memory.py delete

# 確認をスキップして削除
uv run python scripts/agentcore_memory.py delete --confirm
```

### Cognito 認証情報プロバイダー

#### Cognito 認証情報プロバイダーの作成

```bash
uv run python scripts/cognito_credentials_provider.py create --name customersupport-gateways
```

#### Cognito 認証情報プロバイダーの削除

```bash
# プロバイダーを削除（SSM から名前を自動的に読み取り）
uv run python scripts/cognito_credentials_provider.py delete

# 名前で特定のプロバイダーを削除
uv run python scripts/cognito_credentials_provider.py delete --name customersupport-gateways

# 確認をスキップして削除
uv run python scripts/cognito_credentials_provider.py delete --confirm
```

### Google 認証情報プロバイダー

#### 認証情報プロバイダーの作成

```bash
uv run python scripts/google_credentials_provider.py create --name customersupport-google-calendar
uv run python scripts/google_credentials_provider.py create --name my-provider --credentials-file /path/to/credentials.json
```

#### 認証情報プロバイダーの削除

```bash
# プロバイダーを削除（SSM から名前を自動的に読み取り）
uv run python scripts/google_credentials_provider.py delete

# 名前で特定のプロバイダーを削除
uv run python scripts/google_credentials_provider.py delete --name customersupport-google-calendar

# 確認をスキップして削除
uv run python scripts/google_credentials_provider.py delete --confirm
```

### Agent Runtime

#### Agent Runtime の削除

```bash
# 名前で特定の Agent Runtime を削除
uv run python scripts/agentcore_agent_runtime.py customersupport

# 実際に削除せずに削除対象をプレビュー
uv run python scripts/agentcore_agent_runtime.py --dry-run customersupport

# 名前で任意の Agent Runtime を削除
uv run python scripts/agentcore_agent_runtime.py <agent-name>
```

## クリーンアップ

```bash
chmod +x scripts/cleanup.sh
./scripts/cleanup.sh

uv run python scripts/google_credentials_provider.py delete
uv run python scripts/cognito_credentials_provider.py delete
uv run python scripts/agentcore_memory.py delete
uv run python scripts/agentcore_gateway.py delete
uv run python scripts/agentcore_agent_runtime.py customersupport<AgentName>

rm .agentcore.yaml
rm .bedrock_agentcore.yaml
```

## 🤝 貢献

貢献を歓迎します！以下の詳細については[貢献ガイドライン](../../CONTRIBUTING.md)をご覧ください：

- 新しいサンプルの追加
- 既存の例の改善
- 問題の報告
- 機能強化の提案

## 📄 ライセンス

このプロジェクトは MIT ライセンスの下でライセンスされています - 詳細は [LICENSE](../../LICENSE) ファイルを参照してください。

## 🆘 サポート

- **Issues**：バグ報告や機能リクエストは [GitHub Issues](https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues) 経由で
- **ドキュメント**：特定のガイダンスについては個別フォルダの README を確認

## 🔄 更新

このリポジトリは積極的にメンテナンスされ、新しい機能と例で更新されています。最新の追加を把握するためにリポジトリをウォッチしてください。

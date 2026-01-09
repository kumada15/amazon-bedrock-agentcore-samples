# デバイス管理システム

## アーキテクチャと概要

### デバイス管理システムとは？

このユースケースは、Amazon Bedrock AgentCore を使用した包括的なデバイス管理システムを実装しています。IoT デバイス、WiFi ネットワーク、ユーザー、アクティビティを自然言語インタラクションを通じて管理するための統一インターフェースを提供し、複数のデバイス固有のアプリケーションを操作する必要をなくします。

| 情報 | 詳細 |
|------|------|
| ユースケースタイプ | 会話型 AI |
| エージェントタイプ | シングルエージェント |
| ユースケースコンポーネント | Tools、Gateway、Runtime、Frontend |
| ユースケースの業種 | IoT/スマートホーム |
| サンプルの複雑さ | 中級 |
| 使用する SDK | Amazon Bedrock AgentCore SDK、boto3 |

### システムアーキテクチャ

![Device Management Architecture](./images/device-management-architecture.png)

デバイス管理システムは、モジュール式でクラウドネイティブなアーキテクチャに従います：

#### コアコンポーネント：
1. **ユーザーインターフェース**: 自然言語インタラクション用のチャットインターフェースを備えた Web アプリケーション
2. **Amazon Bedrock AgentCore Runtime**: 自然言語リクエストを処理し、会話コンテキストを管理
3. **Amazon Bedrock Gateway**: リクエストを認証し、適切なターゲットにルーティング
4. **AWS Lambda 関数**: デバイス管理操作とビジネスロジックを実行
5. **Amazon DynamoDB**: デバイスデータ、ユーザー情報、アクティビティログを保存
6. **Amazon Cognito**: ユーザー認証と認可を処理

#### データフロー：
1. ユーザーが Web インターフェースを通じて自然言語クエリを送信
2. リクエストは Amazon Cognito で認証され、AgentCore Runtime で処理
3. Runtime は適切なツールを決定し、Gateway を通じてリクエストを送信
4. Gateway は Amazon DynamoDB をクエリ/更新する AWS Lambda 関数にルーティング
5. 結果は同じパスを通じて自然言語レスポンスとして返される

#### オブザーバビリティ：
- **Amazon CloudWatch Logs**: すべてのコンポーネントの集中ログ
- **AWS X-Ray**: リクエストフローの分散トレース
- **Amazon CloudWatch Metrics**: パフォーマンスと使用状況のメトリクス

### 主な機能

- **デバイス管理**: デバイスの一覧表示、設定の取得、ステータスの監視
- **WiFi ネットワーク管理**: ネットワーク設定（SSID、セキュリティ）の表示と更新
- **ユーザー管理**: ユーザーアカウントと権限の管理
- **アクティビティ追跡**: ユーザーインタラクションとシステムアクティビティのクエリ
- **自然言語インターフェース**: 複雑な UI の代わりに会話型インタラクション

## 前提条件

### 必要なソフトウェア
- **Python 3.10+**
- **AWS CLI**（適切な権限で設定済み）
- **Git**（リポジトリのクローン用）

### AWS アカウント要件
- 管理者権限を持つ **AWS アカウント**
- **AWS リージョン**: us-west-2 を推奨（設定可能）

### 必要な AWS サービス
- **Amazon Bedrock AgentCore** へのアクセス
- **AWS Lambda** サービスへのアクセス
- **Amazon DynamoDB** サービスへのアクセス
- **Amazon Cognito** サービスへのアクセス
- **Amazon CloudWatch** サービスへのアクセス

### IAM 権限
AWS ユーザー/ロールには以下の権限が必要です：
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "iam:PassRole"
            ],
            "Resource": "arn:aws:iam::*:role/DeviceManagement*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:*",
                "lambda:*",
                "dynamodb:*",
                "cognito-idp:*",
                "logs:*"
            ],
            "Resource": [
                "arn:aws:bedrock-agentcore:*:*:*",
                "arn:aws:lambda:*:*:function:device-management-*",
                "arn:aws:dynamodb:*:*:table/Devices*",
                "arn:aws:cognito-idp:*:*:userpool/*",
                "arn:aws:logs:*:*:log-group:/aws/lambda/device-management-*"
            ]
        }
    ]
}
```

### 環境セットアップ
1. **リポジトリをクローン**：
   ```bash
   git clone <repository-url>
   cd device-management-system
   ```

2. **Python 依存関係をインストール**：
   ```bash
   # オプション 1: すべての依存関係をインストール（完全セットアップに推奨）
   pip install -r requirements.txt

   # オプション 2: コンポーネント固有の依存関係のみインストール
   pip install -r device-management/requirements.txt  # コア AWS Lambda 機能
   pip install -r gateway/requirements.txt           # Gateway 作成のみ
   pip install -r agent-runtime/requirements.txt     # エージェントランタイムのみ
   pip install -r frontend/requirements.txt          # Web インターフェースのみ
   ```

3. **環境変数を設定**：
   ```bash
   cp .env.example .env
   # .env を特定の値で編集
   ```

## デプロイ手順

### オプション 1: 自動デプロイ（推奨）

単一のスクリプトですべてのコンポーネントをデプロイ：

```bash
chmod +x deploy_all.sh
./deploy_all.sh
```

このスクリプトは以下を実行します：
1. 依存関係付きで AWS Lambda 関数をデプロイ
2. Amazon Bedrock Gateway を作成および設定
3. Gateway ターゲットとオブザーバビリティをセットアップ
4. エージェントランタイムを設定
5. フロントエンドアプリケーションをセットアップ

### オプション 2: 手動ステップバイステップデプロイ

#### ステップ 1: AWS Lambda 関数をデプロイ
```bash
cd device-management
chmod +x deploy.sh
./deploy.sh
cd ..
```

#### ステップ 2: Amazon Bedrock Gateway を作成
```bash
cd gateway
python create_gateway.py
python device-management-target.py
python gateway_observability.py
cd ..
```

#### ステップ 3: エージェントランタイムをセットアップ
```bash
cd agent-runtime
chmod +x setup.sh
./setup.sh
cd ..
```

#### ステップ 4: フロントエンドをセットアップ（オプション）
```bash
cd frontend
python main.py
# http://localhost:8000 でアクセス
```

#### ステップ 5: テストデータを生成
```bash
cd device-management
python synthetic_data.py
cd ..
```

### デプロイの確認

1. **AWS Lambda 関数をテスト**：
   ```bash
   cd device-management
   python test_lambda.py
   ```

2. **Gateway 接続を確認**：
   ```bash
   curl -H "Authorization: Bearer <token>" \
        https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
   ```

3. **Amazon DynamoDB テーブルを確認**：
   ```bash
   aws dynamodb list-tables --region <your-region>
   ```

## サンプルクエリ

デプロイ後、自然言語を使用してシステムと対話できます。クエリの例：

### デバイス管理クエリ
```
"システム内のすべてのデバイスを一覧表示してください"
"すべての休止中のデバイスを表示してください"
"現在オンラインのデバイスは何ですか？"
"過去 24 時間接続していないデバイスを一覧表示してください"
```

### デバイス設定クエリ
```
"デバイス ID DG-10016 のデバイス設定を表示してください"
"デバイス DG-10005 の現在のファームウェアバージョンは何ですか？"
"すべての WR64 モデルデバイスの設定を表示してください"
```

### WiFi ネットワーク管理
```
"デバイス ID DB-10005 の WiFi 設定を表示してください"
"デバイス DG-10016 のすべての WiFi ネットワークを一覧表示してください"
"デバイス DG-10016 の SSID を 'HomeNetwork-5G' に更新してください"
"デバイス DB-10005 ネットワーク WN-1005-1 のセキュリティタイプを WPA3 に変更してください"
```

### ユーザーとアクティビティクエリ
```
"システム内のすべてのユーザーを一覧表示してください"
"過去 24 時間のログインアクティビティを表示してください"
"昨日デバイス DG-10016 にアクセスしたのは誰ですか？"
"2023-06-20 から 2023-06-25 までの john.smith のユーザーアクティビティをクエリしてください"
```

### システム情報クエリ
```
"利用可能なツールは何ですか？"
"ゲストネットワークに接続されているデバイスは何台ですか？"
"今週のすべてのメンテナンスアクティビティを表示してください"
```

### 期待されるレスポンス形式
システムはフォーマットされた人間が読みやすいレスポンスを返します：

```
Device Remote Management System のデバイス

Name                  | Device ID  | Model     | Status     | IP Address      | Last Connected
----------------------|------------|-----------|------------|-----------------|---------------
Factory Sensor A3     | DG-10016   | Sensor-X  | Connected  | 192.168.1.16    | 2023-06-26 18:26
Warehouse Camera      | DG-10022   | Cam-Pro   | Dormant    | 192.168.1.22    | 2023-06-10 14:45
```

## 設定

### 環境変数

システムは設定に環境変数を使用します。主な変数：

```bash
# AWS 設定
AWS_REGION=us-west-2
ENDPOINT_URL=https://bedrock-agentcore-control.us-west-2.amazonaws.com

# AWS Lambda 設定
LAMBDA_ARN=arn:aws:lambda:us-west-2:account:function:DeviceManagementLambda

# Gateway 設定
GATEWAY_IDENTIFIER=your-gateway-identifier
MCP_SERVER_URL=https://gateway-id.gateway.bedrock-agentcore.us-west-2.amazonaws.com

# Amazon Cognito 設定
COGNITO_USERPOOL_ID=your-cognito-userpool-id
COGNITO_APP_CLIENT_ID=your-cognito-app-client-id
COGNITO_DOMAIN=your-domain.auth.us-west-2.amazoncognito.com
```

### MCP クライアント設定

Amazon Q CLI 統合用：

```json
{
  "mcpServers": {
    "device-management": {
      "command": "npx",
      "timeout": 60000,
      "args": [
        "mcp-remote@latest",
        "https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp",
        "--header",
        "Authorization: Bearer <bearer-token>"
      ]
    }
  }
}
```

## トラブルシューティング

### 一般的な問題

**AWS Lambda デプロイの失敗**：
- AWS IAM 権限と AWS Lambda サービスクォータを確認
- requirements.txt の Python 依存関係を確認

**Gateway 作成の失敗**：
- Amazon Cognito User Pool ID と App Client ID を確認
- IAM ロール ARN の権限を確認

**Amazon DynamoDB アクセスの問題**：
- AWS Lambda 実行ロールに必要な権限があることを確認
- テーブル名とリージョンが設定と一致することを確認

**認証の問題**：
- Amazon Cognito 設定とトークンの有効性を確認
- ベアラートークン生成プロセスを確認

### デバッグコマンド

```bash
# AWS Lambda 関数をローカルでテスト
cd device-management && python test_lambda.py

# Amazon DynamoDB テーブルを確認
aws dynamodb list-tables --region us-west-2

# Gateway ステータスを確認
aws bedrock-agentcore get-gateway --gateway-identifier <gateway-id>

# ログを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/bedrock-agentcore"
```

## クリーンアップ手順

### 自動クリーンアップ

```bash
chmod +x cleanup_all.sh
./cleanup_all.sh
```

### 手動クリーンアップ

#### 1. AWS Lambda 関数を削除
```bash
aws lambda delete-function --function-name DeviceManagementLambda
```

#### 2. Gateway コンポーネントを削除
```bash
# Gateway ターゲットを削除
aws bedrock-agentcore delete-gateway-target \
  --gateway-identifier <gateway-identifier> \
  --target-name device-management-target

# Gateway を削除
aws bedrock-agentcore delete-gateway \
  --gateway-identifier <gateway-identifier>
```

#### 3. Amazon DynamoDB テーブルを削除
```bash
aws dynamodb delete-table --table-name Devices
aws dynamodb delete-table --table-name DeviceSettings
aws dynamodb delete-table --table-name WifiNetworks
aws dynamodb delete-table --table-name Users
aws dynamodb delete-table --table-name UserActivities
```

#### 4. Amazon CloudWatch ロググループを削除
```bash
aws logs delete-log-group --log-group-name /aws/bedrock-agentcore/device-management-agent
aws logs delete-log-group --log-group-name /aws/lambda/DeviceManagementLambda
```

#### 5. IAM ロールを削除（デプロイで作成された場合）
```bash
aws iam delete-role --role-name DeviceManagementLambdaRole
aws iam delete-role --role-name AgentGatewayAccessRole
```

## プロジェクト構造

```
device-management-system/
├── agent-runtime/          # エージェントランタイムコンポーネント
│   ├── requirements.txt    # エージェントランタイム依存関係
│   └── requirements-runtime.txt # ランタイム固有の依存関係
├── device-management/      # AWS Lambda 関数と Amazon DynamoDB セットアップ
│   └── requirements.txt    # Lambda 関数依存関係
├── frontend/              # Web インターフェースアプリケーション
│   └── requirements.txt    # フロントエンド Web アプリ依存関係
├── gateway/               # Gateway 作成と設定
│   └── requirements.txt    # Gateway セットアップ依存関係
├── images/                # アーキテクチャ図
├── .env.example          # 環境変数テンプレート
├── requirements.txt      # 統合依存関係（すべてのコンポーネント）
├── deploy_all.sh         # 自動デプロイスクリプト
├── cleanup_all.sh        # 自動クリーンアップスクリプト
└── README.md             # このファイル
```

## 追加リソース

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Amazon DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- [Amazon Cognito Documentation](https://docs.aws.amazon.com/cognito/)

## 免責事項

このリポジトリで提供されるサンプルは、実験および教育目的のみです。概念と技術を示していますが、本番環境での直接使用を意図していません。プロンプトインジェクションから保護するために、Amazon Bedrock Guardrails を適切に配置してください。

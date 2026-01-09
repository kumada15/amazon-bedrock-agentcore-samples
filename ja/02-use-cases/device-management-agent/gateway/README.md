# Gateway モジュール

## アーキテクチャと概要

### Gateway モジュールとは？

Gateway モジュールは、すべてのデバイス管理操作の安全なエントリポイントとして機能する Amazon Bedrock AgentCore Gateway を作成・設定します。Amazon Cognito による認証を処理し、リクエストを適切な AWS Lambda 関数ターゲットにルーティングします。

### 主な責務
- **Gateway 作成**: 適切な認証を備えた Amazon Bedrock AgentCore Gateway のセットアップ
- **ターゲット設定**: Gateway Target を介して Gateway を AWS Lambda 関数に接続
- **認証管理**: 安全なアクセスのための Amazon Cognito OAuth の設定
- **オブザーバビリティ設定**: Amazon CloudWatch ログとモニタリングの有効化
- **セキュリティ強制**: JWT トークン検証とアクセス制御の実装

### アーキテクチャコンポーネント
- **Amazon Bedrock Gateway**: MCP プロトコルリクエストのメインエントリポイント
- **Gateway Target**: Gateway と AWS Lambda 関数間の接続
- **Amazon Cognito 統合**: OAuth 認証と認可
- **Amazon CloudWatch Logs**: Gateway 操作の集中ログ

## 前提条件

### 必要なソフトウェア
- **Python 3.10 以上**
- **AWS CLI**（適切な権限で設定済み）
- **Boto3**（AWS SDK for Python）

### AWS サービスアクセス
- **Amazon Bedrock AgentCore** サービス権限
- **Amazon Cognito** ユーザープール管理
- **IAM** ロール作成と管理
- **Amazon CloudWatch Logs**（オブザーバビリティ用）

### 必要な AWS リソース
- **Amazon Cognito ユーザープール**: Gateway セットアップ前に作成が必要
- **Amazon Cognito アプリクライアント**: 適切な OAuth スコープ付き
- **IAM ロール**: bedrock-agentcore 権限を持つ Gateway 実行用
- **AWS Lambda 関数**: device-management モジュールからデプロイ済み

### 必要な IAM 権限
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "iam:PassRole",
                "bedrock-agentcore:*",
                "cognito-idp:*",
                "logs:*"
            ],
            "Resource": "*"
        }
    ]
}
```

## デプロイ手順

### オプション 1: 自動セットアップ（推奨）

```bash
# gateway ディレクトリから
python cognito_oauth_setup.py    # Amazon Cognito OAuth をセットアップ
python create_gateway.py         # Gateway を作成
python device-management-target.py  # Gateway Target を作成
python gateway_observability.py  # ログを有効化
```

### オプション 2: 手動ステップバイステップデプロイ

#### ステップ 1: 環境設定
```bash
# .env ファイルを作成
cp .env.example .env
# 値を編集:
# - AWS_REGION
# - COGNITO_USERPOOL_ID
# - COGNITO_APP_CLIENT_ID
# - LAMBDA_ARN（device-management モジュールから）
```

#### ステップ 2: 依存関係のインストール
```bash
pip install -r requirements.txt
```

#### ステップ 3: Amazon Cognito OAuth のセットアップ
```bash
python cognito_oauth_setup.py
# これにより .env ファイルが自動的に更新されます:
# - COGNITO_CLIENT_SECRET
# - COGNITO_DOMAIN
```

#### ステップ 4: Amazon Bedrock Gateway の作成
```bash
python create_gateway.py
# 出力から Gateway ID を確認し、.env を更新:
# GATEWAY_IDENTIFIER=your-gateway-id
```

#### ステップ 5: Gateway Target の作成
```bash
python device-management-target.py
# これにより Gateway が AWS Lambda 関数に接続されます
```

#### ステップ 6: オブザーバビリティの有効化
```bash
python gateway_observability.py
# これにより Amazon CloudWatch ログがセットアップされます
```

### デプロイの検証

```bash
# Gateway 接続をテスト
curl -H "Authorization: Bearer <token>" \
     https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp

# Gateway が存在することを確認
aws bedrock-agentcore get-gateway --gateway-identifier <gateway-id>

# Gateway Target を確認
aws bedrock-agentcore list-gateway-targets --gateway-identifier <gateway-id>

# Amazon CloudWatch ロググループを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/bedrock-agentcore"
```

## サンプルクエリ

Gateway がデプロイされたら、これらの操作でテストできます：

### 認証トークンの生成
```bash
# Amazon Cognito から OAuth トークンを取得
curl --http1.1 -X POST https://<cognito-domain>.auth.<region>.amazoncognito.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=<client-id>&client_secret=<client-secret>"
```

### MCP プロトコルリクエスト
```bash
# 利用可能なツールを一覧表示
curl -X POST https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/list",
    "params": {}
  }'

# デバイス一覧ツールを実行
curl -X POST https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tools/call",
    "params": {
      "name": "list_devices",
      "arguments": {}
    }
  }'
```

### 期待されるレスポンス形式
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "tools": [
      {
        "name": "list_devices",
        "description": "List all devices in the system"
      },
      {
        "name": "get_device_settings",
        "description": "Get settings for a specific device"
      }
    ]
  }
}
```

## クリーンアップ手順

### Gateway コンポーネントの削除

```bash
# Gateway Target を削除
aws bedrock-agentcore delete-gateway-target \
  --gateway-identifier <gateway-identifier> \
  --target-name device-management-target

# Gateway を削除
aws bedrock-agentcore delete-gateway \
  --gateway-identifier <gateway-identifier>
```

### Amazon CloudWatch リソースの削除

```bash
# ロググループを削除
aws logs delete-log-group --log-group-name "/aws/bedrock-agentcore/gateway"
aws logs delete-log-group --log-group-name "/aws/bedrock-agentcore/device-management"
```

### ローカルファイルのクリーンアップ

```bash
# 環境ファイルを削除（機密データを含む）
rm .env

# 一時ファイルを削除
rm -rf __pycache__/
```

### オプション: Amazon Cognito リソースのクリーンアップ

```bash
# このプロジェクト用に特別に作成した場合のみ
# aws cognito-idp delete-user-pool-client --user-pool-id <pool-id> --client-id <client-id>
# aws cognito-idp delete-user-pool --user-pool-id <pool-id>
```

## 設定

### 環境変数

```bash
# AWS 設定
AWS_REGION=us-west-2
ENDPOINT_URL=https://bedrock-agentcore-control.us-west-2.amazonaws.com

# AWS Lambda 設定（device-management モジュールから）
LAMBDA_ARN=arn:aws:lambda:us-west-2:account:function:DeviceManagementLambda

# Gateway 設定
GATEWAY_IDENTIFIER=your-gateway-identifier
GATEWAY_NAME=Device-Management-Gateway
GATEWAY_DESCRIPTION=Device Management Gateway
ROLE_ARN=arn:aws:iam::account:role/YourGatewayRole

# ターゲット設定
TARGET_NAME=device-management-target
TARGET_DESCRIPTION=List, Update device management activities

# Amazon Cognito 設定
COGNITO_USERPOOL_ID=your-cognito-userpool-id
COGNITO_APP_CLIENT_ID=your-cognito-app-client-id
COGNITO_CLIENT_SECRET=your-cognito-client-secret
COGNITO_DOMAIN=your-domain.auth.us-west-2.amazoncognito.com

# スクリプトで自動入力
GATEWAY_ARN=arn:aws:bedrock-agentcore:us-west-2:account:gateway/gateway-id
GATEWAY_ID=your-gateway-id
```

### Amazon Cognito OAuth 設定

Gateway は以下の設定で Amazon Cognito を認証に使用します：
- **Grant Type**: `client_credentials`
- **Scopes**: `cognito-device-gateway/invoke`
- **Token Endpoint**: `https://<domain>.auth.<region>.amazoncognito.com/oauth2/token`
- **Discovery URL**: `https://cognito-idp.<region>.amazonaws.com/<pool-id>/.well-known/openid-configuration`

## トラブルシューティング

### よくある問題

**Gateway 作成の失敗**:
- Amazon Cognito ユーザープール ID とアプリクライアント ID が正しいか確認
- IAM ロール ARN に適切な権限があるか確認
- AWS リージョンがすべてのリソースで一貫しているか確認

**認証エラー**:
- Amazon Cognito クライアントシークレットを再生成
- OAuth スコープが正しく設定されているか確認
- トークンの有効期限を確認し、必要に応じて更新

**Gateway Target 接続エラー**:
- AWS Lambda 関数が存在しアクセス可能か確認
- Gateway 識別子が作成した Gateway と一致するか確認
- AWS Lambda 関数に適切な権限があるか確認

### デバッグコマンド

```bash
# Amazon Cognito トークン生成をテスト
python -c "
import requests
response = requests.post('https://<domain>.auth.<region>.amazoncognito.com/oauth2/token',
  headers={'Content-Type': 'application/x-www-form-urlencoded'},
  data='grant_type=client_credentials&client_id=<id>&client_secret=<secret>')
print(response.json())
"

# Gateway ステータスを確認
aws bedrock-agentcore get-gateway --gateway-identifier <gateway-id>

# Gateway Target を一覧表示
aws bedrock-agentcore list-gateway-targets --gateway-identifier <gateway-id>

# Amazon CloudWatch ログを確認
aws logs describe-log-groups --log-group-name-prefix "/aws/bedrock-agentcore"
```

## 他のモジュールとの統合

- **Device Management モジュール**: Gateway Target がこのモジュールの AWS Lambda 関数に接続
- **Agent Runtime モジュール**: Gateway エンドポイントを使用して MCP ツールにアクセス
- **Frontend モジュール**: デバイス操作のため Agent Runtime を通じて間接的に Gateway を使用

# デバイス管理モジュール

## アーキテクチャと概要

### デバイス管理モジュールとは？

デバイス管理モジュールは、すべてのデバイス管理操作を実装するコアバックエンドコンポーネントです。MCP（Model Context Protocol）ツールの実行エンジンとして機能する AWS Lambda 関数と、データ永続化のための Amazon DynamoDB で構成されています。

### 主な責務
- **デバイス操作**: IoT デバイスインベントリの一覧表示、クエリ、管理
- **設定管理**: デバイス設定と WiFi ネットワーク設定の処理
- **ユーザー管理**: ユーザーアカウントとアクセス権限の管理
- **アクティビティ追跡**: デバイスとのユーザーインタラクションのログ記録とクエリ
- **データ永続化**: Amazon DynamoDB テーブルへのデータの保存と取得

### アーキテクチャコンポーネント
- **AWS Lambda 関数**: デバイス管理ロジックを実行するサーバーレスコンピューティング
- **Amazon DynamoDB テーブル**: デバイス、ユーザー、アクティビティデータを保存する NoSQL データベース
- **MCP ツール**: デバイス管理操作の標準化されたインターフェース
- **IAM ロール**: AWS サービスアクセスのセキュリティポリシー

## 前提条件

### 必要なソフトウェア
- **Python 3.10 以上**
- **AWS CLI**（適切な権限で設定済み）
- **Boto3**（AWS SDK for Python）

### AWS サービスアクセス
- **AWS Lambda** サービス権限
- **Amazon DynamoDB** 読み取り/書き込みアクセス
- **IAM** ロール作成と管理権限
- **Amazon CloudWatch Logs**（関数ログ用）

### 必要な IAM 権限
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "dynamodb:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## デプロイ手順

### オプション 1: 自動デプロイ（推奨）

```bash
# device-management ディレクトリから
chmod +x deploy.sh
./deploy.sh
```

### オプション 2: 手動デプロイ

#### ステップ 1: 環境設定
```bash
# .env ファイルを作成
cp .env.example .env
# 値を編集:
# - AWS_REGION
# - LAMBDA_FUNCTION_NAME
# - LAMBDA_ROLE_NAME
```

#### ステップ 2: 依存関係のインストール
```bash
pip install -r requirements.txt
```

#### ステップ 3: Amazon DynamoDB テーブルの作成
```bash
python dynamodb_models.py
```

#### ステップ 4: AWS Lambda 関数のデプロイ
```bash
# パッケージ化とデプロイ
zip -r function.zip . -x "*.env" "__pycache__/*" "*.pyc"
aws lambda create-function \
  --function-name DeviceManagementLambda \
  --runtime python3.10 \
  --role arn:aws:iam::ACCOUNT:role/DeviceManagementLambdaRole \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip
```

#### ステップ 5: テストデータの生成（オプション）
```bash
python synthetic_data.py
```

### デプロイの検証

```bash
# AWS Lambda 関数をローカルでテスト
python test_lambda.py

# デプロイ済み関数をテスト
aws lambda invoke \
  --function-name DeviceManagementLambda \
  --payload '{"tool_name": "list_devices"}' \
  response.json

# Amazon DynamoDB テーブルを確認
aws dynamodb list-tables --region us-west-2
```

## サンプルクエリ

AWS Lambda 関数は以下の MCP ツール操作をサポートします：

### デバイス管理操作
```python
# 全デバイスを一覧表示
{
  "tool_name": "list_devices"
}

# 特定のデバイス設定を取得
{
  "tool_name": "get_device_settings",
  "device_id": "DG-10016"
}
```

### WiFi ネットワーク操作
```python
# デバイスの WiFi ネットワークを一覧表示
{
  "tool_name": "list_wifi_networks",
  "device_id": "DG-10005"
}

# WiFi SSID を更新
{
  "tool_name": "update_wifi_ssid",
  "device_id": "DG-10016",
  "network_id": "WN-1016-1",
  "ssid": "NewNetworkName"
}

# WiFi セキュリティを更新
{
  "tool_name": "update_wifi_security",
  "device_id": "DG-10005",
  "network_id": "WN-1005-1",
  "security_type": "WPA3"
}
```

### ユーザーとアクティビティ操作
```python
# 全ユーザーを一覧表示
{
  "tool_name": "list_users"
}

# ユーザーアクティビティをクエリ
{
  "tool_name": "query_user_activity",
  "start_date": "2023-06-20",
  "end_date": "2023-06-25",
  "user_id": "user123"  # オプション
}
```

### 期待されるレスポンス形式
```json
{
  "statusCode": 200,
  "body": [
    {
      "device_id": "DG-10016",
      "name": "Factory Sensor A3",
      "model": "Sensor-X",
      "connection_status": "Connected",
      "ip_address": "192.168.1.16",
      "last_connected": "2023-06-26T18:26:46"
    }
  ]
}
```

## クリーンアップ手順

### AWS Lambda 関数の削除

```bash
# 関数を削除
aws lambda delete-function --function-name DeviceManagementLambda

# 関数ログを削除
aws logs delete-log-group --log-group-name "/aws/lambda/DeviceManagementLambda"
```

### Amazon DynamoDB テーブルの削除

```bash
# 全テーブルを削除
aws dynamodb delete-table --table-name Devices
aws dynamodb delete-table --table-name DeviceSettings
aws dynamodb delete-table --table-name WifiNetworks
aws dynamodb delete-table --table-name Users
aws dynamodb delete-table --table-name UserActivities
```

### IAM ロールの削除（デプロイで作成した場合）

```bash
# ポリシーをデタッチしてロールを削除
aws iam detach-role-policy \
  --role-name DeviceManagementLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam delete-role --role-name DeviceManagementLambdaRole
```

### ローカルファイルのクリーンアップ

```bash
# デプロイ成果物を削除
rm -f function.zip
rm -f response.json
rm -rf __pycache__/
rm -f .env  # 機密データを含む
```

## 設定

### Amazon DynamoDB テーブルスキーマ

#### Devices テーブル
- **プライマリキー**: `device_id`（String）
- **属性**: `name`、`model`、`connection_status`、`ip_address`、`mac_address`、`firmware_version`、`last_connected`

#### DeviceSettings テーブル
- **プライマリキー**: `device_id`（String）
- **属性**: `settings`（Map）、`last_updated`

#### WifiNetworks テーブル
- **プライマリキー**: `device_id`（String）、`network_id`（String）
- **属性**: `ssid`、`security_type`、`enabled`、`channel`、`signal_strength`

#### Users テーブル
- **プライマリキー**: `user_id`（String）
- **属性**: `username`、`email`、`role`、`created_at`、`last_login`

#### UserActivities テーブル
- **プライマリキー**: `user_id`（String）、`timestamp`（String）
- **グローバルセカンダリインデックス**: `activity_type` の `ActivityTypeIndex`
- **属性**: `activity_type`、`description`、`ip_address`、`device_id`

### 環境変数

```bash
# AWS 設定
AWS_REGION=us-west-2

# AWS Lambda 設定
LAMBDA_FUNCTION_NAME=DeviceManagementLambda
LAMBDA_ROLE_NAME=DeviceManagementLambdaRole

# IAM 設定
AGENT_GATEWAY_POLICY_NAME=AgentGatewayAccess
AGENT_GATEWAY_ROLE_NAME=AgentGatewayAccessRole
```

## トラブルシューティング

### よくある問題

**AWS Lambda デプロイの失敗**:
- Lambda サービスの IAM 権限を確認
- Python 依存関係の互換性を確認
- デプロイパッケージサイズが AWS の制限内であることを確認

**Amazon DynamoDB アクセスエラー**:
- IAM ロールに DynamoDB 権限があることを確認
- テーブル名が設定と一致することを確認
- テーブルが正しいリージョンに存在することを確認

**関数タイムアウトエラー**:
- AWS Lambda タイムアウト設定を増加
- インデックスで DynamoDB クエリを最適化
- コードに無限ループがないか確認

### デバッグコマンド

```bash
# 関数をローカルでテスト
python test_lambda.py

# 関数ログを確認
aws logs tail /aws/lambda/DeviceManagementLambda --follow

# DynamoDB 接続をテスト
aws dynamodb scan --table-name Devices --max-items 5

# 関数設定を検証
aws lambda get-function --function-name DeviceManagementLambda
```

## 他のモジュールとの統合

- **Gateway モジュール**: この AWS Lambda 関数を Gateway Target を通じて MCP ツールとして公開
- **Agent Runtime モジュール**: Gateway を通じてこれらのツールを呼び出してデバイス操作を実行
- **Frontend モジュール**: ユーザーインタラクション用に Agent Runtime を通じて間接的にこれらの操作を使用

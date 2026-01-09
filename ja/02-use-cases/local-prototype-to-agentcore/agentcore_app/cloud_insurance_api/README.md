# Mangum を使用した FastAPI の AWS Lambda へのデプロイ

このプロジェクトは、Mangum アダプターを使用して FastAPI アプリケーションを API Gateway 統合で AWS Lambda にデプロイする方法を示します。

## プロジェクト構造

```
cloud_insurance_api/
├── local_insurance_api/      # FastAPI アプリケーションソースコード
│   ├── app.py                # FastAPI アプリケーション定義
│   ├── data_loader.py        # データ読み込みユーティリティ
│   ├── routes/               # API ルートモジュール
│   └── services/             # ビジネスロジックサービス
├── lambda_function.py        # Mangum 統合付き AWS Lambda ハンドラー
├── deployment/
│   ├── template.yaml         # インフラストラクチャ用 AWS SAM テンプレート
│   └── deploy.sh             # AWS SAM を使用したデプロイスクリプト
├── openapi.json              # 生成された OpenAPI 仕様
└── README.md                 # プロジェクトドキュメント
```

## 仕組み

### 1. FastAPI アプリケーション

`local_insurance_api` ディレクトリには、保険関連のエンドポイントを提供する FastAPI アプリケーションが含まれています。これはローカルで実行することも、AWS Lambda にデプロイすることもできる標準的な FastAPI アプリケーションです。

### 2. Mangum 統合

[Mangum](https://github.com/jordaneremieff/mangum) は、FastAPI のような ASGI アプリケーションを AWS Lambda および API Gateway で使用するためのアダプターです。API Gateway リクエストを FastAPI が処理できる形式に変換し、FastAPI レスポンスを API Gateway が理解できる形式に戻します。

統合は `lambda_function.py` で行われます：

```python
import os
import sys

# 現在のディレクトリを Python パスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# FastAPI アプリをインポート
from local_insurance_api.app import app

# AWS Lambda 統合用に Mangum をインポート
from mangum import Mangum

# ハンドラーを作成
handler = Mangum(app)
```

`handler` 関数は Lambda 関数のエントリーポイントです。API Gateway が Lambda 関数を呼び出すと、Mangum がイベントとコンテキストを処理し、リクエストを FastAPI アプリに渡し、API Gateway が理解できる形式でレスポンスを返します。

### 3. AWS SAM テンプレート

`deployment/template.yaml` ファイルは、AWS Serverless Application Model（SAM）を使用して作成される AWS リソースを定義します。これらには以下が含まれます：

- Lambda 関数: FastAPI アプリケーションコードを実行
- API Gateway: Lambda 関数を呼び出すための HTTP エンドポイントを提供
- IAM ロール: Lambda 実行の権限
- CloudWatch Log Group: Lambda 実行ログ用

### 4. デプロイプロセス

デプロイは `deployment/deploy.sh` スクリプトによって処理され、AWS SAM CLI を使用して以下を行います：

1. デプロイアーティファクト用の S3 バケットを作成
2. アプリケーションコードと依存関係を含むデプロイパッケージをビルド
3. パッケージを S3 にアップロード
4. 定義されたリソースで CloudFormation スタックをデプロイ

## 前提条件

デプロイ前に、以下を確認してください：

- 適切な権限で設定された AWS CLI がインストール済み
- AWS SAM CLI がインストール済み
- Python 3.10 以上がインストール済み
- Lambda、API Gateway、CloudFormation、S3、IAM へのアクセスを持つ AWS アカウント

## デプロイ手順

1. **依存関係のインストール**

   ローカル環境に必要な依存関係がすべてあることを確認：

   ```bash
   pip install -r local_insurance_api/requirements.txt
   pip install aws-sam-cli
   ```

2. **OpenAPI 仕様のエクスポート（オプション）**

   API には `openapi.json` に事前生成された OpenAPI 仕様があります。

3. **AWS へのデプロイ**

   デプロイスクリプトを実行：

   ```bash
   # dev 環境にデプロイ（デフォルト）
   ./deployment/deploy.sh

   # 特定の環境（dev、test、prod）にデプロイ
   ./deployment/deploy.sh prod
   ```

4. **API のテスト**

   デプロイ後、curl または任意の HTTP クライアントを使用して API をテスト：

   ```bash
   # 実際の API Gateway URL に置き換え
   ENDPOINT="https://i0zzy6t0x9.execute-api.us-west-2.amazonaws.com/dev"

   # ヘルスエンドポイントをテスト
   curl $ENDPOINT/health

   # ポリシーエンドポイントをテスト
   curl $ENDPOINT/policies

   # 顧客情報エンドポイントをテスト（POST リクエスト）
   curl -X POST $ENDPOINT/customer_info \
     -H "Content-Type: application/json" \
     -d '{"customer_id": "cust-001"}'
   ```

## ローカルテスト

デプロイ前にローカルでテストするには：

```bash
# FastAPI アプリケーションを直接実行
cd local_insurance_api
uvicorn app:app --reload --port 8001

# AWS SAM を使用してローカルでテスト
cd ..
sam local start-api
```

## トラブルシューティング

よくある問題と解決策：

### 1. 循環インポート

FastAPI アプリケーションは、モジュラー構造を使用する際に循環インポートが発生する可能性があります。Lambda では、これらがデプロイ失敗の原因となることがあります。解決策：

- モジュールレベルではなく関数内で関数ベースのインポートを使用
- 必要な時だけモジュールをインポートするラッパー関数を作成
- 依存性注入パターンを使用

例えば、API では：
```python
# 循環インポートを避けるために関数を使用してルーターをインポート
def get_routers():
    from local_insurance_api.routes.general import router as general_router
    # その他のインポート...
    return general_router, ...
```

### 2. インポートパスの問題

ローカル環境と Lambda 間でコードを移動する際、インポートパスが壊れる可能性があります。Lambda では常に完全修飾インポートを使用：

```python
# Lambda 環境ではこれを使用
from local_insurance_api.services import data_service

# これは使用しない（ローカルでは動作するが Lambda で壊れる可能性がある）
from services import data_service
```

### 3. API Gateway エラー

- **403 Forbidden**: IAM 権限を確認
- **500 Internal Server Error**: CloudWatch で Lambda 実行ログを確認
- **"Missing Authentication Token"**: 通常 URL パスが正しくないことを意味する

### 4. コールドスタートレイテンシー

Lambda 関数は「コールドスタート」遅延が発生する可能性があります。最小化するには：

- `template.yaml` で Lambda メモリ割り当てを増加
- 重要なエンドポイントにプロビジョンドコンカレンシーを使用
- 依存関係サイズを最適化

## API ドキュメント

API は保険関連の操作のためにいくつかのエンドポイントを提供：
- `/openapi.json`: 生の OpenAPI 仕様
- `/health`: ヘルスチェックエンドポイント
- `/policies`: すべての保険ポリシーを取得
- `/customer_info`: 顧客情報を取得
- `/vehicle_info`: 車両情報を取得
- `/insurance_products`: 利用可能な保険商品を取得

## その他のリソース

- [FastAPI ドキュメント](https://fastapi.tiangolo.com/)
- [Mangum ドキュメント](https://mangum.io/)
- [AWS Lambda ドキュメント](https://docs.aws.amazon.com/lambda/)
- [AWS SAM ドキュメント](https://docs.aws.amazon.com/serverless-application-model/)

## クリーンアップ

Insurance API アプリケーションの使用が終わったら、以下の手順ですべての AWS リソースをクリーンアップ：

1. **CloudFormation スタックの削除**:
   ```bash
   # スタック名を取得（覚えていない場合）
   aws cloudformation list-stacks --query "StackSummaries[?contains(StackName,'insurance-api')].StackName" --output text

   # スタックを削除
   aws cloudformation delete-stack --stack-name insurance-api-stack-dev
   ```

2. **S3 デプロイバケットの削除**（不要になった場合）:
   ```bash
   # デプロイバケットを見つけるために S3 バケットをリスト
   aws s3 ls | grep insurance-api

   # まずバケットからすべてのファイルを削除
   aws s3 rm s3://insurance-api-deployment-bucket-1234 --recursive

   # 空のバケットを削除
   aws s3api delete-bucket --bucket insurance-api-deployment-bucket-1234
   ```

3. **リソース削除の確認**:
   ```bash
   # Lambda 関数がまだ存在するか確認
   aws lambda list-functions --query "Functions[?contains(FunctionName,'insurance-api')].FunctionName" --output text

   # API Gateway がまだ存在するか確認
   aws apigateway get-rest-apis --query "items[?contains(name,'insurance-api')].id" --output text
   ```

4. **CloudWatch ログのクリーンアップ**（オプション）:
   ```bash
   # ロググループを見つける
   aws logs describe-log-groups --query "logGroups[?contains(logGroupName,'/aws/lambda/insurance-api')].logGroupName" --output text

   # ロググループを削除
   aws logs delete-log-group --log-group-name /aws/lambda/insurance-api-function-dev
   ```

注意: `insurance-api-stack-dev`、`insurance-api-deployment-bucket-1234`、`/aws/lambda/insurance-api-function-dev` などのプレースホルダー値を実際のリソース名に置き換えてください。

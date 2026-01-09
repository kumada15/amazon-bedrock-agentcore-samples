# バックエンドデプロイメント - CDK でのデータソースと設定管理デプロイメント

**[AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/)** を使用して、ビデオゲーム売上データアナリストアシスタントのバックエンドインフラストラクチャをデプロイします。

> [!NOTE]
> **作業ディレクトリ**: このチュートリアルを開始する前に、`cdk-agentcore-strands-data-analyst-assistant/` フォルダにいることを確認してください。このガイドのすべてのコマンドはこのディレクトリから実行する必要があります。

## 概要

このチュートリアルでは、以下の主要コンポーネントを含むビデオゲーム売上データアナリストエージェントに必要な基盤 AWS サービスをデプロイします：

- **IAM AgentCore 実行ロール**: Bedrock モデル、RDS Data API、DynamoDB、Secrets Manager へのアクセスを含む、Amazon Bedrock AgentCore 実行のための包括的な権限
- **パブリックおよびプライベートサブネットを持つ VPC**: アウトバウンド接続用の NAT Gateway を備えた、データベースリソースのネットワーク分離とセキュリティ
- **Amazon Aurora Serverless v2 PostgreSQL**: RDS Data API 統合と暗号化を備えた、ビデオゲーム売上データを保存するスケーラブルなデータベースクラスター
- **Amazon DynamoDB**: 従量課金制での SQL クエリ結果追跡用の単一テーブル
- **AWS Secrets Manager**: データベース認証情報の安全なストレージ
- **Amazon S3**: ライフサイクルポリシーを備えた、Aurora PostgreSQL へのデータロード用のインポートバケット
- **VPC ゲートウェイエンドポイント**: S3 および DynamoDB サービスへのコスト効率の良いアクセス
- **SSM Parameter Store**: AgentCore ランタイムパラメータの設定管理

> [!IMPORTANT]
> テスト後は、提供されているクリーンアップ手順に従ってリソースをクリーンアップし、不要なコストを避けることを忘れずに。

## 前提条件

開始前に、以下を確認してください：

* サービスデプロイのための適切な IAM 権限を持つ AWS アカウント
* **開発環境**：
  * Python 3.10 以降がインストール済み
  * **[AWS CDK がインストール済み](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)**

* RDS 用のサービスリンクロールを作成するために以下のコマンドを実行：

```bash
aws iam create-service-linked-role --aws-service-name rds.amazonaws.com
```

## AWS デプロイメント

CDK プロジェクトフォルダに移動し、依存関係をインストール：

```bash
npm install
```

インフラストラクチャをデプロイ：

```bash
cdk deploy
```

デフォルトパラメータ：
- **ProjectId**: "agentcore-data-analyst-assistant" - リソースの命名に使用されるプロジェクト識別子
- **DatabaseName**: "video_games_sales" - データベースの名前

デプロイされるリソース：

- **VPC**: パブリック/プライベートサブネット、NAT Gateway、セキュリティグループ、VPC エンドポイント
- **Aurora PostgreSQL Serverless v2**: RDS Data API を備えたデータベースクラスター
- **DynamoDB**: SQL クエリ結果用のテーブル
- **S3**: ライフサイクルポリシーを備えたデータインポート用バケット
- **Secrets Manager**: データベース認証情報ストレージ
- **IAM**: Bedrock、RDS、DynamoDB 権限を持つ AgentCore 実行ロール
- **SSM Parameter Store**: 設定パラメータ
  - `/<projectId>/SECRET_ARN`: データベースシークレット ARN
  - `/<projectId>/AURORA_RESOURCE_ARN`: Aurora クラスター ARN
  - `/<projectId>/DATABASE_NAME`: データベース名
  - `/<projectId>/QUESTION_ANSWERS_TABLE`: DynamoDB 質問応答テーブル名
  - `/<projectId>/MAX_RESPONSE_SIZE_BYTES`: 最大レスポンスサイズ（バイト単位、1MB）
  - `/<projectId>/MEMORY_ID`: エージェント用の AgentCore メモリ ID

  これらのパラメータは、データベース接続を確立しエージェントの動作を設定するために Strands Agent によって自動的に取得されます。

> [!IMPORTANT]
> **[Strands Agents SDK](https://strandsagents.com/latest/user-guide/safety-security/guardrails/)** が提供するシームレスな統合により、AI アプリケーションに **[Amazon Bedrock Guardrails](https://aws.amazon.com/bedrock/guardrails/)** を実装して AI の安全性とコンプライアンスを強化してください。

## PostgreSQL データベースへのサンプルデータのロード

1. 必要な Python 依存関係をインストール：

``` bash
pip install boto3
```

2. 必要な環境変数をセットアップ：

``` bash
# スタック名の環境変数を設定
export STACK_NAME=CdkAgentcoreStrandsDataAnalystAssistantStack

# 出力値を取得して環境変数に保存
export SECRET_ARN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='SecretARN'].OutputValue" --output text)
export DATA_SOURCE_BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='DataSourceBucketName'].OutputValue" --output text)
export AURORA_SERVERLESS_DB_CLUSTER_ARN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='AuroraServerlessDBClusterARN'].OutputValue" --output text)
export AGENT_CORE_ROLE_EXECUTION=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='AgentCoreMyRoleARN'].OutputValue" --output text)
export MEMORY_ID_SSM_PARAMETER=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='MemoryIdSSMParameter'].OutputValue" --output text)
cat << EOF
STACK_NAME: ${STACK_NAME}
SECRET_ARN: ${SECRET_ARN}
DATA_SOURCE_BUCKET_NAME: ${DATA_SOURCE_BUCKET_NAME}
AURORA_SERVERLESS_DB_CLUSTER_ARN: ${AURORA_SERVERLESS_DB_CLUSTER_ARN}
AGENT_CORE_ROLE_EXECUTION: ${AGENT_CORE_ROLE_EXECUTION}
MEMORY_ID_SSM_PARAMETER: ${MEMORY_ID_SSM_PARAMETER}
EOF

```

3. PostgreSQL にサンプルデータをロード：

``` bash
python3 resources/create-sales-database.py
```

スクリプトは **[video_games_sales_no_headers.csv](./resources/database/video_games_sales_no_headers.csv)** をデータソースとして使用します。

> [!NOTE]
> 提供されているデータソースには [Video Game Sales](https://www.kaggle.com/datasets/asaniczka/video-game-sales-2024) からの情報が含まれており、[ODC Attribution License](https://opendatacommons.org/licenses/odbl/1-0/) の下で利用可能です。

## 次のステップ

**[エージェントデプロイメント - AgentCore での Strands Agent インフラストラクチャデプロイメント](../agentcore-strands-data-analyst-assistant/)** に進むことができます。

## リソースのクリーンアップ（オプション）

不要な課金を避けるため、CDK スタックを削除：

``` bash
cdk destroy
```

## ありがとうございます

## ライセンス

このプロジェクトは Apache-2.0 ライセンスの下でライセンスされています。
# エージェント型セールスアナリスト

販売データベースのデータとリアルタイムのウェブリサーチを組み合わせて、ビジネス意思決定のための完全な市場コンテキストを提供するエージェント型セールスアナリストです。このエージェントは Strands Agent SDK で構築され、ECS にデプロイされ（EKS サポートは近日公開予定）、会話コンテキストには AgentCore Memory を、エージェントパフォーマンスの洞察には AgentCore Observability を使用します。推論機能には Claude Sonnet v3 モデルを使用しています。

## 機能

- 🤖 **エージェント型 AI** - Claude 3 Sonnet を使用した Strands SDK
- 🗄️ **データベース統合** - サンプル販売データを含む PostgreSQL
- 🌐 **ウェブ検索** - 市場インテリジェンス用の Brave Search API
- 💾 **会話メモリ** - Amazon Bedrock AgentCore Memory
- 📊 **可観測性** - Amazon Bedrock AgentCore Observability
- 🎨 **モダン UI** - ストリーミングレスポンス対応の React フロントエンド

## アーキテクチャ

### ローカル開発
```
Docker Compose (3 コンテナ):
├─ PostgreSQL (port 5432) - サンプル販売データ
├─ Backend (port 8080) - Python Flask + Strands SDK
└─ Frontend (port 3000) - React アプリ
```

### AWS デプロイメント

**ECS**
![ECS Architecture](agentic-sales-analyst-solution-overview.jpg)

**EKS（作業中）**
<!-- TODO: Add EKS architecture diagram -->

## クイックスタート

### ローカル開発

```bash
# 1. リポジトリをクローン
git clone <repo-url>
cd agentic-sales-analyst

# 2. IAM 権限を追加（Bedrock と AgentCore Memory に必要）
aws iam put-user-policy \
  --user-name YOUR_AWS_USERNAME \
  --policy-name BedrockLocalDev \
  --policy-document file://local-dev-policy.json

# 3. 環境変数を設定
export BRAVE_SEARCH_API_KEY=your-api-key
export AWS_REGION=ap-southeast-2

# 4. すべてのサービスを開始（~/.aws 認証情報を使用）
docker-compose -f docker-compose.local.yml up

# 5. アプリケーションにアクセス
open http://localhost:3000
```

### AWS デプロイメント

> **⚠️ 警告:** このプロジェクトは VPC、ECS Fargate タスク、Application Load Balancer、EFS、ECR、Bedrock サービスを含む AWS リソースを作成します。このプロジェクトをデプロイすると、使用した AWS リソースに対して課金されます。不要になったらクリーンアップスクリプトを使用してリソースを削除してください。

#### AWS インフラストラクチャ
```bash
cd deployment
./deploy-infrastructure.sh
```

#### ECS
```bash
cd deployment/ecs
./deploy-ecs.sh
```

#### EKS（作業中）
```bash
# 注意: EKS デプロイメントはまだ開発中です
cd deployment/eks
./deploy-k8s.sh
```

### クリーンアップ

**ECS/EKS デプロイメントの削除（共有インフラストラクチャは保持）**
```bash
# ECS
cd deployment/ecs
./cleanup-ecs.sh

# EKS（作業中）
cd deployment/eks
./cleanup-k8s.sh
```

**すべてのインフラストラクチャの削除（VPC、IAM、ECR を含む）**
```bash
cd deployment
./cleanup-infrastructure.sh
```

**注意:** 依存関係の問題を避けるため、デプロイメント固有のクリーンアップを先に実行し、その後インフラストラクチャのクリーンアップを実行してください。

## プロジェクト構造

```
.
├── client/                      # React フロントエンド
│   ├── src/
│   │   ├── App.tsx             # メインチャットインターフェース
│   │   └── index.css           # スタイル
│   ├── Dockerfile              # フロントエンドコンテナ
│   └── package.json
├── deployment/                  # AWS デプロイメントファイル
│   ├── deploy-infrastructure.sh # 共有インフラストラクチャデプロイメント
│   ├── cleanup-infrastructure.sh # 共有インフラストラクチャクリーンアップ
│   ├── common/                 # 共有 CloudFormation テンプレート
│   │   ├── 01-network.yaml    # VPC、サブネット、IGW
│   │   ├── 02-iam.yaml        # IAM ロールとポリシー
│   │   └── 03-ecr.yaml        # ECR リポジトリ
│   ├── ecs/                    # ECS 固有ファイル
│   │   ├── cluster.yaml       # ECS クラスターと ALB
│   │   ├── service.yaml       # ECS サービス（3 コンテナ）
│   │   ├── deploy-ecs.sh      # ECS デプロイメントスクリプト
│   │   ├── cleanup-ecs.sh     # ECS クリーンアップスクリプト
│   │   └── README.md          # ECS ドキュメント
│   └── eks/                    # EKS 固有ファイル（作業中）
│       ├── cluster.yaml       # EKS クラスター
│       ├── k8s-deployment.yaml # Kubernetes マニフェスト
│       ├── deploy-k8s.sh      # EKS デプロイメントスクリプト
│       ├── cleanup-k8s.sh     # EKS クリーンアップスクリプト
│       └── README.md          # EKS ドキュメント
├── strands_agentcore_runtime.py # メイン Python ランタイム
├── Dockerfile                   # バックエンドコンテナ
├── Dockerfile.postgres          # データ付き PostgreSQL
├── docker-compose.local.yml     # ローカル開発

├── create_and_load_sales_data.sql # データベーススキーマ
├── sales_data_sample_utf8.csv   # サンプルデータ
└── requirements.txt             # Python 依存関係
```

## テクノロジースタック

### バックエンド
- **Python 3.11** - ランタイム
- **Flask** - Web フレームワーク
- **Strands SDK** - エージェント型 AI フレームワーク
- **psycopg2** - PostgreSQL ドライバー
- **boto3** - AWS SDK
- **ADOT** - 可観測性

### フロントエンド
- **React 18** - UI フレームワーク
- **TypeScript** - 型安全性
- **Node 18** - ビルドツール

### インフラストラクチャ
- **AWS Fargate** - サーバーレスコンテナ（ECS）
- **Amazon EFS** - ファイルストレージ（ECS）
- **Application Load Balancer** - トラフィックルーティング
- **Amazon ECR** - コンテナレジストリ
- **CloudWatch** - ロギングとメトリクス
- **AgentCore** - 可観測性

### AI/ML
- **Amazon Bedrock** - Claude 3 Sonnet
- **Bedrock AgentCore Memory** - 会話履歴
- **Brave Search API** - ウェブ検索

## 設定

### 必須環境変数

```bash
# AWS 設定
AWS_REGION=ap-southeast-2
AWS_ACCOUNT_ID=123456789012

# API キー
BRAVE_SEARCH_API_KEY=your-brave-api-key

# データベース（コンテナ内で自動設定）
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sales_db
```

## 開発

### 前提条件

**必須:**
- Docker および Docker Compose
- 認証情報が設定された AWS CLI
- Brave Search API キー（https://brave.com/search/api/ で取得）
- Node.js 18+（ローカルフロントエンド開発用）
- Python 3.11+（ローカルバックエンド開発用）

**IAM 権限:**

ローカル開発には、AWS ユーザーに Bedrock と AgentCore Memory の権限が必要です：
```bash
aws iam put-user-policy \
  --user-name YOUR_AWS_USERNAME \
  --policy-name BedrockLocalDev \
  --policy-document file://local-dev-policy.json
```

### 既知の脆弱性

フロントエンドにはビルド時の依存関係（react-scripts 5.0.1）に既知の脆弱性があります：
- `nth-check`、`postcss`、`webpack-dev-server` - 開発およびビルド時に使用
- これらは Create React App から継承されており、現在はアクティブにメンテナンスされていません
- 脆弱性はビルドプロセスにのみ影響し、本番バンドルには影響しません
- 本番バンドルはスキャンされ、脆弱なコードパスを削除するためにミニファイされます
- 対策: `npm start` と `npm build` は信頼できる環境でのみ実行してください

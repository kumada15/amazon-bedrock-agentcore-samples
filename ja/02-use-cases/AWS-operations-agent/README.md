# Amazon Bedrock AgentCore を使用した AWS サポートエージェント

OAuth2 認証、MCP（Model Control Protocol）統合、および包括的な AWS サービス操作を備えた、Amazon Bedrock AgentCore 上に構築された AWS サポート会話型 AI システムです。

## デモ

![AWS Support Agent Demo](images/demo-agentcore.gif)

*Amazon Bedrock AgentCore を使用した AWS サポートエージェントのインタラクティブデモ*

## アーキテクチャ概要

### ハイレベルアーキテクチャ

![AWS Support Agent High-Level Architecture](images/architecture-2.jpg)

*オブザーバビリティ統合を含む完全な AgentCore エコシステムを示すハイレベルシステムアーキテクチャ*

### 詳細な認証フロー

![AWS Support Agent Authentication Flow](images/flow.jpg)

*AgentCore コンポーネント間の OAuth2 認証フローとトークン管理を示す詳細なシーケンス図*

![AWS Support Agent Architecture](images/architecture.jpg)

*コンポーネントの相互作用とデータフローを示すコアシステムアーキテクチャ*

システムはセキュアで分散されたアーキテクチャに従います：

1. **Chat Client** は Okta OAuth2 経由でユーザーを認証し、JWT トークン付きで質問を送信します
2. **AgentCore Runtime** はトークンを検証し、会話を処理し、セッションメモリを維持します
3. **AgentCore Gateway** は MCP プロトコルを通じてセキュアなツールアクセスを提供します
4. **AWS Lambda Target** は適切な認証で AWS サービス操作を実行します
5. **AgentCore Identity** はワークロード認証とトークン交換を管理します
6. **AgentCore Observability** は包括的な監視、メトリクス、ログ機能を提供します

## 主な機能

- 🔐 **エンタープライズ認証**: JWT トークン検証を備えた Okta OAuth2
- 🤖 **デュアルエージェントアーキテクチャ**: FastAPI（DIY）と BedrockAgentCoreApp（SDK）の両方の実装
- 🧠 **会話メモリ**: AgentCore Memory による永続的なセッションストレージ
- 🔗 **MCP 統合**: 標準化されたツール通信プロトコル
- 🛠️ **20 以上の AWS ツール**: AWS サービス全体にわたる包括的な読み取り専用操作
- 📊 **本番環境対応**: 完全なデプロイ自動化とインフラストラクチャ管理

## プロジェクト構造

```
AgentCore/
├── README.md                           # このドキュメント
├── requirements.txt                    # Python 依存関係
├── config/                             # 🔧 設定管理
│   ├── static-config.yaml              # 手動設定
│   └── dynamic-config.yaml             # ランタイム生成設定
│
├── shared/                             # 🔗 共有設定ユーティリティ
│   ├── config_manager.py               # 中央設定管理
│   └── config_validator.py             # 設定検証
│
├── chatbot-client/                     # 🤖 クライアントアプリケーション
│   ├── src/client.py                   # インタラクティブチャットクライアント
│   └── README.md                       # クライアント固有のドキュメント
│
├── agentcore-runtime/                  # 🚀 メインランタイム実装
│   ├── src/
│   │   ├── agents/                     # エージェント実装
│   │   │   ├── diy_agent.py            # FastAPI 実装
│   │   │   └── sdk_agent.py            # BedrockAgentCoreApp 実装
│   │   ├── agent_shared/               # 共有エージェントユーティリティ
│   │   │   ├── auth.py                 # JWT 検証
│   │   │   ├── config.py               # エージェント設定
│   │   │   ├── mcp.py                  # MCP クライアント
│   │   │   ├── memory.py               # 会話メモリ
│   │   │   └── responses.py            # レスポンスフォーマット
│   │   └── utils/
│   │       └── memory_manager.py       # メモリ管理ユーティリティ
│   ├── deployment/                     # 🚀 デプロイスクリプト
│   │   ├── 01-prerequisites.sh         # IAM ロールと前提条件
│   │   ├── 02-create-memory.sh         # AgentCore Memory セットアップ
│   │   ├── 03-setup-oauth-provider.sh  # OAuth2 プロバイダー設定
│   │   ├── 04-deploy-mcp-tool-lambda.sh # MCP Lambda デプロイ
│   │   ├── 05-create-gateway-targets.sh # ゲートウェイとターゲットセットアップ
│   │   ├── 06-deploy-diy.sh            # DIY エージェントデプロイ
│   │   ├── 07-deploy-sdk.sh            # SDK エージェントデプロイ
│   │   ├── 08-delete-runtimes.sh       # ランタイムクリーンアップ
│   │   ├── 09-delete-gateways-targets.sh # ゲートウェイクリーンアップ
│   │   ├── 10-delete-mcp-tool-deployment.sh # MCP クリーンアップ
│   │   ├── 11-delete-oauth-provider.sh # OAuth プロバイダークリーンアップ
│   │   ├── 12-delete-memory.sh         # メモリクリーンアップ
│   │   ├── 13-cleanup-everything.sh    # 完全クリーンアップスクリプト
│   │   ├── bac-permissions-policy.json # IAM 権限ポリシー
│   │   ├── bac-trust-policy.json       # IAM 信頼ポリシー
│   │   ├── Dockerfile.diy              # DIY エージェントコンテナ
│   │   ├── Dockerfile.sdk              # SDK エージェントコンテナ
│   │   ├── deploy-diy-runtime.py       # DIY デプロイ自動化
│   │   └── deploy-sdk-runtime.py       # SDK デプロイ自動化
│   ├── gateway-ops-scripts/            # 🌉 ゲートウェイ管理
│   │   └── [ゲートウェイ CRUD 操作]
│   ├── runtime-ops-scripts/            # ⚙️ ランタイム管理
│   │   └── [ランタイムとアイデンティティ管理]
│   └── tests/local/                    # 🧪 ローカルテストスクリプト
│
├── mcp-tool-lambda/                    # 🔧 AWS ツール Lambda
│   ├── lambda/mcp-tool-handler.py      # MCP ツール実装
│   ├── mcp-tool-template.yaml          # CloudFormation テンプレート
│   └── deploy-mcp-tool.sh              # Lambda デプロイスクリプト
│
├── okta-auth/                          # 🔐 認証セットアップ
│   ├── OKTA-OPENID-PKCE-SETUP.md      # Okta 設定ガイド
│   ├── iframe-oauth-flow.html          # OAuth フローテスト
│   └── setup-local-nginx.sh           # ローカル開発セットアップ
│
└── docs/                               # 📚 ドキュメント
    └── images/
        └── agentcore-implementation.jpg # アーキテクチャ図
```

## クイックスタート

### 前提条件

- **AWS CLI** が適切な権限で設定されていること
- **Docker** と Docker Compose がインストールされていること
- **Python 3.11+** がインストールされていること
- **Okta 開発者アカウント** とアプリケーションが設定されていること
- **yq** ツール（YAML 処理用、オプション、フォールバックあり）

### 1. 設定の構成

特定の設定で構成ファイルを編集します：

```bash
# AWS と Okta の設定を構成 - 静的設定を必ず更新してください
# 以下のファイルでプレースホルダー <your-aws-account-id>、<YOUR_OKTA_DOMAIN>、<YOUR_OKTA_CLIENT_ID>、
# <YOUR_OKTA_AUTHORIZATION_SERVER_AUDIENCE> を置き換えて更新してください
vim config/static-config.yaml

# 更新する主要な設定：
# - aws.account_id: あなたの AWS アカウント ID
# - aws.region: 希望する AWS リージョン（このプロジェクトは us-east-1 でテスト済み）
# - okta.domain: あなたの Okta ドメイン
# - okta.client_credentials.client_id: あなたの Okta クライアント ID

# 重要：IAM ポリシーファイルをあなたの AWS アカウント ID で更新してください
# これらのファイルの YOUR_AWS_ACCOUNT_ID プレースホルダーを置き換えます：
sed -i "s/YOUR_AWS_ACCOUNT_ID/$(aws sts get-caller-identity --query Account --output text)/g" \
  agentcore-runtime/deployment/bac-permissions-policy.json \
  agentcore-runtime/deployment/bac-trust-policy.json

# アカウント ID が正しく更新されたことを確認
grep -n "$(aws sts get-caller-identity --query Account --output text)" \
  agentcore-runtime/deployment/bac-permissions-policy.json \
  agentcore-runtime/deployment/bac-trust-policy.json
```

### 2. インフラストラクチャのデプロイ

デプロイスクリプトを順番に実行します：

#### 注意: `以下のスクリプトを実行する前に、Okta のセットアップが正常に完了し、http://localhost:8080/okta-auth/iframe-oauth-flow.html を使用してアクセストークンを生成できることを確認してください - 詳細は OKTA-OPENID-PKCE-SETUP.md を参照。[/AWS-operations-agent/okta-auth/OKTA-OPENID-PKCE-SETUP.md]`

```bash
cd agentcore-runtime/deployment

# ./01-prerequisites.sh を実行する前に、プレースホルダー <your-aws-account-id>、<YOUR_OKTA_DOMAIN>、
# <YOUR_OKTA_CLIENT_ID>、<YOUR_OKTA_AUTHORIZATION_SERVER_AUDIENCE> を置き換えて以下のファイルを更新してください
# bac-permissions-policy.json
# bac-trust-policy.json
# 最新の AWS CLI がインストールされ、AWS CLI 認証情報ファイルにデフォルトプロファイルが設定されているか、
# ターミナルで AWS 認証情報をエクスポートしていることを確認してください
# 使用している AWS アカウントで、Bedrock > Model Access ページ（us-east-1、バージニア北部リージョン）で
# Anthropic モデルが有効になっていることを確認してください
./01-prerequisites.sh

# 'aws bedrock-agentcore-control is not available' エラーが発生した場合
# 以下を使用して AWS CLI を最新バージョンに更新してください
# curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
# sudo installer -pkg AWSCLIV2.pkg -target /

# 会話ストレージ用の AgentCore Memory を作成
./02-create-memory.sh

# Okta OAuth2 プロバイダーをセットアップ - これは AgentCore Runtime から AgentCore Gateway エンドポイントへの
# アウトバウンド認証用のセットアップです。
# クライアント側のインバウンド認証（ランタイムとの）用に SPA アプリをセットアップするには、
# OKTA-OPENID-PKCE-SETUP.md ファイルを確認してください
# また、AgentCore Runtime と AgentCore Gateway エンドポイント間のアウトバウンド認証用に
# 新しい API サービスアプリもセットアップしてください。
# 以下のスクリプトを実行する際に、Okta アプリ 'App name: aws-support-agent-m2m' の
# クライアント ID/クライアントシークレットを追加する必要があります。
# これにより、これらのシークレットが保存される認証情報プロバイダーが作成されます。
# Okta Console > Applications > Applications > aws-support-agent-m2m に移動して、
# クライアント ID とクライアントシークレットをコピーしてください。
# OKTA-OPENID-PKCE-SETUP.md に従って Okta で新しいスコープ 'api' を作成済みと想定しているため、
# 以下のスクリプト実行時に 'api' の値を変更する必要はありません
./03-setup-oauth-provider.sh

# MCP ツール Lambda 関数をデプロイ
./04-deploy-mcp-tool-lambda.sh

# AgentCore Gateway とターゲットを作成
./05-create-gateway-targets.sh

# エージェントをデプロイ（一方または両方を選択）
./06-deploy-diy.sh    # FastAPI 実装
./07-deploy-sdk.sh    # BedrockAgentCoreApp 実装
```

#### 注意: `上記のスクリプトは dynamic-config.yaml ファイルを動的に更新します。yaml ファイルが正しく更新されていることを確認してください。`

### 3. システムのテスト

#### インタラクティブチャットクライアントを使用

**デプロイされたエージェント用：**
```bash
cd chatbot-client
python src/client.py
```

#### 注意: `http://localhost:8080/okta-auth/iframe-oauth-flow.html を使用してアクセストークンを取得してください。クライアントがトークンを要求します`

クライアントは利用可能なデプロイされたエージェントを表示します：
```
🤖 AgentCore Chatbot Client
==============================

📦 Available AgentCore Runtimes:
========================================
1. DIY Agent
   Name: bac_runtime_diy
   ARN: arn:aws:bedrock-agentcore:us-east-1:xxxxxxx:runtime/bac_runtime_diy-xxxxx
   Status: ✅ Available
2. SDK Agent
   Name: bac_runtime_sdk
   ARN: arn:aws:bedrock-agentcore:us-east-1:xxxxx:runtime/bac_runtime_sdk-xxxx
   Status: ✅ Available

🎯 Select Runtime:
Enter choice (1 for DIY, 2 for SDK):
```

#### ローカルコンテナを使用したインタラクティブチャットクライアント（オプション - 上級ユースケース）

#### `以下のスクリプトを実行してエージェントをローカルにデプロイしてください。エージェントは AWS の AgentCore サービスに接続します。`

```bash
# ローカルエージェントコンテナを起動
cd agentcore-runtime/tests/local
./run-diy-local-container.sh    # DIY エージェント用
# または
./run-sdk-local-container.sh    # SDK エージェント用

# 別のターミナルで、チャットクライアントに接続
cd chatbot-client
python src/client.py --local
```

#### 注意: `クライアントは利用可能なローカルエージェントを表示し、一度に 1 つのエージェントにのみ接続できます。両方のエージェントは 8080 にデプロイされるためです。nginx を停止しないと、ローカルデプロイと競合します。または、nginx ポートをサーバーブロック設定を更新して変更し、それに応じて Okta 設定も変更してください。`

```
🤖 Local Testing Mode
==============================

📦 Local Testing Mode:
========================================
1. DIY Agent
   Name: Local DIY Agent
   URL: http://localhost:8080
   Status: ✅ Available (if Docker container is running)
2. SDK Agent
   Name: Local SDK Agent
   URL: http://localhost:8080
   Status: ✅ Available (if Docker container is running)

🎯 Select Runtime:
Enter choice (1 for DIY, 2 for SDK):
```

**コンテナを使用したローカルテスト用：**
```bash
cd chatbot-client
python src/client.py --local
```

`--local` フラグは、localhost:8080 で実行されているコンテナ化されたエージェントに接続できるローカルテストモードを有効にします。


## コンポーネントの詳細

### エージェント実装

#### DIY エージェント（FastAPI）
- **フレームワーク**: Uvicorn を使用した FastAPI
- **エンドポイント**: `/invoke`
- **機能**: リクエスト/レスポンス処理を完全に制御できるカスタム実装
- **コンテナ**: `agentcore-runtime/deployment/Dockerfile.diy`

#### SDK エージェント（BedrockAgentCoreApp）
- **フレームワーク**: BedrockAgentCoreApp SDK
- **機能**: 組み込み最適化を備えたネイティブ AgentCore 統合
- **コンテナ**: `agentcore-runtime/deployment/Dockerfile.sdk`

### 認証フロー

1. **ユーザー認証**: ユーザーは Okta OAuth2 PKCE フロー経由で認証
2. **トークン検証**: AgentCore Runtime は Okta のディスカバリエンドポイントを使用して JWT トークンを検証
3. **ワークロードアイデンティティ**: ランタイムはユーザートークンをワークロードアクセストークンに交換
4. **サービス認証**: ワークロードトークンで AgentCore Gateway とツールに認証

### メモリ管理

- **ストレージ**: AgentCore Memory サービスが永続的な会話ストレージを提供
- **セッション管理**: 各会話はインタラクション間でセッションコンテキストを維持
- **保持**: 会話データの保持期間を設定可能
- **プライバシー**: ユーザーセッションごとのメモリ分離

### ツール統合

システムは MCP Lambda を通じて 20 以上の AWS サービスツールを提供：

- **EC2**: インスタンス管理と監視
- **S3**: バケット操作とポリシー分析
- **Lambda**: 関数管理と監視
- **CloudFormation**: スタック操作とリソース追跡
- **IAM**: ユーザー、ロール、ポリシー管理
- **RDS**: データベースインスタンス監視
- **CloudWatch**: メトリクス、アラーム、ログ分析
- **Cost Explorer**: コスト分析と最適化
- **その他多数...**

## 設定管理

### 静的設定（`config/static-config.yaml`）
手動で設定される設定を含みます：
- AWS アカウントとリージョン設定
- Okta OAuth2 設定
- エージェントモデル設定
- ツールスキーマと定義

### 動的設定（`config/dynamic-config.yaml`）
デプロイ中に自動生成：
- ランタイム ARN とエンドポイント
- ゲートウェイ URL と識別子
- OAuth プロバイダー設定
- メモリサービスの詳細

### 設定マネージャー
`shared/config_manager.py` は以下を提供：
- 統一された設定アクセス
- 環境固有の設定
- 検証とエラー処理
- 後方互換性


### コンテナ開発

両方のエージェントは標準化されたコンテナ構造に従います：

```
/app/
├── shared/                     # プロジェクト全体のユーティリティ
├── agent_shared/              # エージェント固有のヘルパー
├── config/                    # 設定ファイル
│   ├── static-config.yaml
│   └── dynamic-config.yaml
├── [agent].py                 # エージェント実装
└── requirements.txt
```

### ローカルコンテナスクリプト

以下のスクリプトは、完全なコンテナ化によるローカルテストを簡単に行えます：

- **`agentcore-runtime/tests/local/run-diy-local-container.sh`** - ポート 8080 で Docker コンテナ内の DIY エージェントを実行
- **`agentcore-runtime/tests/local/run-sdk-local-container.sh`** - ポート 8080 で Docker コンテナ内の SDK エージェントを実行

これらのコンテナには以下が含まれます：
- 完全な MCP ツール統合
- MCP ゲートウェイが利用できない場合のローカルツールフォールバック
- AWS デプロイなしの完全なエージェント機能
- 分離されたテスト環境

### 新しいツールの追加

1. **ツールスキーマを定義**: `config/static-config.yaml` 内
2. **ツールロジックを実装**: `mcp-tool-lambda/lambda/mcp-tool-handler.py` 内
3. **ゲートウェイターゲットを更新**: gateway-ops-scripts を使用
4. **統合をテスト**: ローカルテストスクリプトを使用

## 監視と運用

### ランタイム管理
```bash
cd agentcore-runtime/runtime-ops-scripts

# デプロイされたすべてのランタイムを一覧表示
python runtime_manager.py list

# ランタイムの詳細を確認
python runtime_manager.py get <runtime_id>

# OAuth フローをテスト
python oauth_test.py test-config
```

### ゲートウェイ管理
```bash
cd agentcore-runtime/gateway-ops-scripts

# すべてのゲートウェイを一覧表示
python list-gateways.py

# ゲートウェイターゲットを確認
python list-targets.py

# ゲートウェイ設定を更新
python update-gateway.py --gateway-id <id> --name "New Name"
```

### ログ分析
- **CloudWatch Logs**: エージェントランタイムログ
- **リクエストトレース**: 完全なリクエスト/レスポンスログ
- **エラー監視**: 集中型エラー追跡
- **パフォーマンスメトリクス**: レスポンス時間とリソース使用量

## クリーンアップ

デプロイされたすべてのリソースを削除するには：

### 注意: `ランタイムの削除には時間がかかります。`

```bash
cd agentcore-runtime/deployment

# ランタイムを削除
./08-delete-runtimes.sh

# ゲートウェイとターゲットを削除
./09-delete-gateways-targets.sh

# MCP Lambda を削除
./10-delete-mcp-tool-deployment.sh

# Identity - Credentials Provider を削除
./11-delete-oauth-provider.sh

# メモリを削除
./12-delete-memory.sh

# 完全クリーンアップ（オプション）
./13-cleanup-everything.sh
```

## セキュリティベストプラクティス

- **トークン検証**: すべてのリクエストを Okta JWT に対して検証
- **最小権限**: IAM ロールは最小権限の原則に従う
- **暗号化**: 転送中および保管中のすべてのデータを暗号化
- **ネットワークセキュリティ**: 制御されたアクセスを持つプライベートネットワーキング
- **監査ログ**: すべての操作の包括的な監査証跡

## トラブルシューティング

### 一般的な問題

1. **トークン検証の失敗**
   - `static-config.yaml` の Okta 設定を確認
   - JWT オーディエンスと発行者の設定を確認
   - `oauth_test.py` でテスト

2. **メモリアクセスの問題**
   - AgentCore Memory がデプロイされ利用可能であることを確認
   - `dynamic-config.yaml` のメモリ設定を確認
   - ローカルスクリプトでメモリ操作をテスト

3. **ツール実行の失敗**
   - MCP Lambda のデプロイステータスを確認
   - ゲートウェイターゲット設定を確認
   - MCP クライアントで個々のツールをテスト

4. **コンテナ起動の問題**
   - Docker ビルドログを確認
   - requirements.txt の互換性を確認
   - コンテナヘルスエンドポイントを確認

### ヘルプの取得

1. **デプロイログを確認**: CloudWatch で
2. **診断スクリプトを実行**: runtime-ops-scripts 内
3. **設定を確認**: config_manager 検証を使用
4. **コンポーネントを個別にテスト**: ローカルテストスクリプトを使用

## ライセンス

このプロジェクトは教育および実験目的です。組織のポリシーと AWS サービス規約への準拠を確認してください。

# 植物健康 AI アシスタント

Amazon Bedrock AgentCore を使用して構築された包括的な植物健康分析システムです。マルチエージェントオーケストレーション、AgentCore Runtime、永続メモリ、MCP（Model Context Protocol）ゲートウェイ統合を特徴としています。

## 概要

このプロジェクトでは、AWS Bedrock AgentCore の機能を使用してインテリジェントな植物健康分析システムを構築する方法を示します。このシステムは、植物検出、専門家コンサルテーション、Web 検索、永続メモリを組み合わせて、包括的な植物ケアの推奨を提供します。

## アーキテクチャ
![Farm Management Architecture](./Image/solution_architecture_diagram.png)

システムは2つの主要コンポーネントで構成されています：

### パート 1: ゲートウェイセットアップ (`01_plant_advisor_gateway.ipynb`)
- MCP ツールとして5つの Lambda 関数を作成
- Cognito 認証を使用して Bedrock AgentCore Gateway をセットアップ
- 植物検出、ケアアドバイス、天気予報、Web 検索ツールを設定

### パート 2: メモリ付きランタイム (`02_plant_advisor_runtime_mem.ipynb`)
- LangGraph ベースのマルチエージェントワークフローを実装
- 植物分析履歴用の永続メモリを統合
- Docker コンテナ化で AgentCore Runtime にデプロイ

## 主要コンポーネント

### 1. マルチエージェント LangGraph ワークフロー
![LangGraph Architecture](./Image/enhanced_plant_workflow.png)
- **エントリールーター**: クエリが分析用か履歴取得用かを判定
- **植物検出エージェント**: 画像から植物の種類と健康問題を識別
- **ケアエージェント**: 専門家による治療アドバイスを提供
- **Web 検索エージェント**: 最新の研究と推奨を検索
- **メモリエージェント**: 植物分析履歴を保存および取得

### 2. Amazon Bedrock AgentCore Runtime
- **サーバーレス実行**: AI エージェントのデプロイとスケーリングのための安全でサーバーレスなランタイム
- **オートスケーリング**: 需要に基づく自動スケーリング
- **フレームワーク非依存**: LangGraph およびその他のエージェントフレームワークで動作
- **本番環境対応**: エンタープライズグレードのセキュリティと信頼性

### 3. AWS Bedrock AgentCore Memory
- 植物分析セッション用の永続ストレージ
- アクターベースのメモリ分離（農家別）
- 植物健康追跡用の30日間保持
- 会話形式のメモリフォーマット

### 4. MCP Gateway ツール
- **Plant Detection**: 植物画像を分析して種と健康問題を特定
- **Plant Care**: 専門家によるケア推奨を提供
- **Plant Web Search**: 特定の植物ケア情報を検索
- **Weather Forecast**: 植物ケア計画用の天気データを取得
- **Web Search**: 一般的な Web 検索機能

## 前提条件

- Python 3.10 以上
- Bedrock AgentCore アクセス権を持つ AWS アカウント
- Docker または Finch がインストールされ実行中であること
- Jupyter Notebook 環境
- Web 検索機能用の Tavily API キー

## セットアップ手順

### 1. 環境セットアップ

```bash
# パッケージ管理用に uv をインストール
pip install uv

# 仮想環境を作成
uv python install 3.10
uv venv --python 3.10
source .venv/bin/activate

# 依存関係をインストール
uv add -r requirements.txt --active
```
### 2. ゲートウェイ設定（Notebook 01）

1. ノートブック内の `TAVILY_API_KEY` を更新
2. すべてのセルを実行して以下を行う：
   - 植物分析ツール用の Lambda 関数を作成
   - Cognito 認証をセットアップ
   - MCP Gateway を作成
   - Lambda 関数を MCP ツールとして登録
   - ゲートウェイ機能をテスト

### 3. ランタイムデプロイ（Notebook 02）

すべてのセルを実行して以下を行う：
- ノートブック 1 から設定を読み込み
- AgentCore Memory ストアを作成
- LangGraph ワークフローを AgentCore Runtime にデプロイ
- 植物画像とメモリクエリでテスト

## 機能

- **画像ベースの植物検出**: 植物の写真をアップロードして自動種識別
- **健康評価**: 植物の健康問題と症状の詳細な分析
- **専門家による推奨**: 植物の種類と状態に基づく包括的なケアアドバイス
- **メモリ統合**: 経時的な植物の健康追跡のための分析履歴の永続ストレージ
- **マルチモーダル検索**: 最新の植物ケア研究のための Web 検索統合
- **天気統合**: 天気を考慮した植物ケアの推奨
- **スケーラブルなアーキテクチャ**: 自動スケーリング付きのサーバーレスデプロイ

## ファイル構造

```
├── 01_plant_advisor_gateway.ipynb     # ゲートウェイセットアップと MCP ツール
├── 02_plant_advisor_runtime_mem.ipynb # メモリ付きランタイムデプロイ
├── requirements.txt                    # Python 依存関係
├── Lambda/                             # Lambda 関数コード
│   ├── plant_care.py
│   ├── plant_detection.py
│   ├── plant_websearch.py
│   ├── weather_forecast.py
│   └── websearch.py
├── utils/
│   └── utils.py                        # ユーティリティ関数
├── Image/                              # アーキテクチャ図とサンプル画像
│   ├── solution_architecture_diagram.png
│   ├── enhanced_plant_workflow.png
│   └── sweet_potato_leaf.png
└── README.md
```


## トラブルシューティング

### よくある問題

- **ランタイムデプロイ**: 適切な IAM ロールと ARM64 プラットフォームの互換性を確認
- **メモリ作成エラー**: IAM ロールに AgentCore Memory の適切な権限があることを確認
- **ゲートウェイ認証**: Cognito 設定とトークン生成を確認
- **Lambda タイムアウト**: 画像処理関数のタイムアウト設定を増加
- **画像サイズ制限**: ペイロード制限内に収まるように画像をリサイズ（推奨 < 1MB）

### デバッグ情報

システムには包括的なデバッグ情報が含まれています：
- AgentCore Runtime 実行ログ
- メモリ操作ステータス
- ゲートウェイツールの可用性
- Lambda 関数実行ログ

## クリーンアップ

この例で作成されたすべてのリソースを削除するには：

### 1. AgentCore リソースの削除
```python
# デプロイされたエージェントを削除
runtime.delete_agent()

# メモリストアを削除
memory_client.delete_memory(memory_id=MEMORY_ID)
```
### 2. ゲートウェイリソースの削除
#### Lambda 関数の削除
```python
aws lambda delete-function --function-name plant-detection-target
aws lambda delete-function --function-name plant-care-target
aws lambda delete-function --function-name plant-web-search-target
aws lambda delete-function --function-name weather-forecast-target
aws lambda delete-function --function-name websearch-target

### ゲートウェイの削除
aws bedrock-agentcore delete-gateway --gateway-id YOUR_GATEWAY_ID
```
### 3. IAM ロールの削除
```python
aws iam delete-role --role-name agentcore-plant-advisor-agent-langgraph-role
aws iam delete-role --role-name agentcore-mem-plant-advisor-mem-langgraph-role
```
### 4. ECR リポジトリの削除
```python
aws ecr delete-repository --repository-name bedrock-agentcore-plant_advisor_agent --force
```
## コントリビューション

このプロジェクトは Amazon Bedrock AgentCore の実験的な機能を示しています。本番環境での使用には：

- 適切なエラーハンドリングとリトライロジックを実装
- 入力検証とサニタイズを追加
- 適切な IAM 権限を設定
- モニタリングとアラートをセットアップ
- ユーザー認証と認可を実装

## ライセンス

このプロジェクトは教育および実験目的で提供されています。詳細はメインリポジトリのライセンスを参照してください。

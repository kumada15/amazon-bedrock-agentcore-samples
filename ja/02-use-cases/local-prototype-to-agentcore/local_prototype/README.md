# 自動車保険プラットフォーム - ローカルプロトタイプ

このディレクトリには、3つの主要コンポーネントで構成される自動車保険プラットフォームの完全なローカルプロトタイプが含まれています：

1. **Insurance API**: 保険関連のデータと機能を提供する FastAPI ベースのバックエンドサービス
2. **Local MCP Server**: 保険ツールを LLM に公開する Model Context Protocol サーバー
3. **Strands Insurance Agent**: Claude 3.7 を使用して保険ツールと対話するインタラクティブエージェント

## システム概要

ローカルプロトタイプは、保険アプリケーション向けの完全なエージェントベースアーキテクチャを示しています：

- **Insurance API** (Port 8001): 顧客、車両、ポリシーデータを持つコアバックエンドサービス
- **MCP Server** (Port 8000): Insurance API エンドポイントを MCP ツールとして公開するミドルウェア
- **Strands Agent**: Claude 3.7 Sonnet を使用して自然言語インターフェースを提供するフロントエンド

このアーキテクチャは、開発者が標準化されたプロトコルを通じて構造化データサービスと対話する LLM 搭載アプリケーションを構築する方法を示しています。

## コンポーネント

### 1. Insurance API

リアルなサンプルデータを使用して自動車保険バックエンドをシミュレートする FastAPI アプリケーション。

**主な機能:**
- 顧客情報エンドポイント
- 車両データと安全評価
- リスク評価計算
- 保険商品カタログと価格設定
- ポリシー管理（表示、フィルター、検索）

**サンプルデータ:**
- 顧客プロファイル
- 車両仕様
- 信用レポート
- 保険商品
- 保険ポリシー

### 2. Local MCP Server

標準化されたツールを通じて Insurance API へのアクセスを提供する Model Context Protocol（MCP）サーバー。

**主なツール:**
- `get_customer_info`: 顧客詳細を取得
- `get_vehicle_info`: 車両仕様を取得
- `get_insurance_quote`: 保険見積もりを生成
- `get_vehicle_safety`: 安全評価にアクセス
- `get_all_policies`: すべてのポリシーを表示
- `get_policy_by_id`: 特定のポリシー詳細を取得
- `get_customer_policies`: 顧客 ID でポリシーを検索

### 3. Strands Insurance Agent

MCP サーバーに接続する Anthropic の Strands フレームワークで構築されたインタラクティブエージェント。

**主な機能:**
- 保険ツールとの自然言語インタラクション
- 会話履歴とコンテキスト保持
- Claude 3.7 Sonnet 用の AWS Bedrock 統合
- 包括的なエラーハンドリングとレスポンスフォーマット

### 4. Streamlit ダッシュボード

保険プラットフォームシステム全体の可視化とテストインターフェース。

**主な機能:**
- システムステータスモニタリング
- API エンドポイントテスト
- MCP ツール実行
- エージェントチャットシミュレーション
- システムアーキテクチャ可視化
- インタラクティブデータ探索

## セットアップ手順

### 前提条件

- Python 3.10 以上
- Claude 3.7 Sonnet への Bedrock アクセスを持つ AWS アカウント
- Node.js と npm（MCP Inspector 用）
- uv パッケージマネージャー（推奨）

### 1. Insurance API セットアップ

```bash
# Insurance API ディレクトリに移動
cd local_insurance_api

# 仮想環境を作成して有効化
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# API サーバーを起動
python -m uvicorn server:app --port 8001
```

Insurance API は `http://localhost:8001` で利用可能になります。

### 2. MCP Server セットアップ

```bash
# MCP Server ディレクトリに移動
cd local_mcp_server

# 仮想環境を作成して有効化
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# HTTP トランスポートで MCP サーバーを起動
python server.py --http
```

MCP サーバーは `http://localhost:8000/mcp` で利用可能になります。

### 3. Strands Agent セットアップ

```bash
# Strands Agent ディレクトリに移動
cd local_strands_insurance_agent

# 仮想環境を作成して有効化
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# AWS 認証情報を設定
[リンク](https://strandsagents.com/latest/documentation/docs/user-guide/quickstart/#configuring-credentials)を使用して認証情報を設定

# インタラクティブエージェントを起動
python interactive_insurance_agent.py
```


## MCP Inspector でのテスト

MCP Inspector ツールを使用して MCP サーバーを直接テストできます：

```bash
# MCP Inspector をインストールして起動
npx @modelcontextprotocol/inspector
```

これによりブラウザで MCP Inspector が開きます。`http://localhost:8000/mcp` に接続して、利用可能なツールを探索してテストできます。

## 使用例

### Insurance API エンドポイント

```bash
# すべてのポリシーを取得
curl http://localhost:8001/policies

# 特定のポリシーを取得
curl http://localhost:8001/policies/policy-001

# 顧客のポリシーを取得
curl http://localhost:8001/customer/cust-001/policies

# 保険商品を取得
curl -X POST http://localhost:8001/insurance_products \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Strands Agent クエリ

```
あなた: 顧客 cust-001 についてどんな情報がありますか？
エージェント: [John Smith に関する詳細情報を返す]

あなた: 彼はどんな車を持っていますか？
エージェント: [コンテキストを使用して車両情報を提供]

あなた: 2023 年の Toyota RAV4 の見積もりをもらえますか？
エージェント: [顧客プロファイルに基づいて見積もりを生成]
```

## 有効なテストデータ

テストにはこれらの値を使用してください：

- 顧客 ID: `cust-001`、`cust-002`、`cust-003`
- 車両メーカー: `Toyota`、`Honda`、`Ford`
- 車両モデル: `Camry`、`Civic`、`F-150`
- 車両年式: 2010〜2023 年の任意の年
- ポリシー ID: `policy-001`、`policy-002`、`policy-003`

## ディレクトリ構造

```
local_prototype/
├── local_insurance_api/            # コアバックエンドサービス
│   ├── data/                 # サンプルデータファイル
│   ├── routes/               # API エンドポイント
│   ├── services/             # ビジネスロジック
│   ├── app.py                # アプリケーション初期化
│   └── server.py             # エントリーポイント
├── local_mcp_server/        # MCP サーバー実装
│   ├── tools/                # MCP ツール定義
│   ├── config.py             # サーバー設定
│   └── server.py             # エントリーポイント
└── local_strands_insurance_agent/  # インタラクティブエージェント
    └── interactive_insurance_agent.py  # エージェント実装
```

## アーキテクチャ図

```
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│                   │      │                   │      │                   │
│  Strands Agent    │◄────►│  MCP Server       │◄────►│  Insurance API    │
│  (Claude 3.7)     │      │  (Model Context   │      │  (FastAPI)        │
│                   │      │   Protocol)       │      │                   │
└───────────────────┘      └───────────────────┘      └───────────────────┘
       ▲                                                      ▲
       │                                                      │
       │                                                      │
       ▼                                                      ▼
┌───────────────────┐                               ┌───────────────────┐
│                   │                               │                   │
│  ユーザー          │                               │  サンプルデータ     │
│  (コンソール)      │                               │  (JSON ファイル)   │
│                   │                               │                   │
└───────────────────┘                               └───────────────────┘
```

## トラブルシューティング

### よくある問題

1. **ポートが使用中**
   - エラー: "Address already in use"
   - 解決策: ポートを使用しているプロセスを終了するか、別のポートを指定

2. **接続拒否**
   - エラー: サービスへの接続時に "Connection refused"
   - 解決策: 3つのコンポーネントすべてが実行中であることを確認

3. **AWS 認証の問題**
   - エラー: "Could not connect to the endpoint URL"
   - 解決策: AWS 認証情報とリージョンを確認

## 次のステップ

本番デプロイについては、AgentCore を使用してこのアーキテクチャを AWS にデプロイする方法を示す `agentcore_app` ディレクトリを参照してください。

## ライセンス

このプロジェクトは Apache License 2.0 の下でライセンスされています - 詳細は [LICENSE](../../../LICENSE) ファイルを参照してください。


## 注意

このローカルプロトタイプは、開発者が以下を使用してエージェントアプリケーションを構築する方法を示しています：
- FastAPI バックエンドサービス
- Model Context Protocol（MCP）サーバー
- Anthropic の Strands エージェントフレームワーク
- Claude 3.7 Sonnet LLM

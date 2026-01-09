# 自動車保険 API MCP サーバー

このディレクトリには、自動車保険 API へのアクセスを提供する Model Context Protocol（MCP）サーバーが含まれています。LLM やその他のアプリケーションが標準化されたプロトコルを通じて顧客情報、車両詳細、保険見積もりを取得できるようにします。

## 概要

MCP サーバーは、LLM（Claude など）と自動車保険 API の橋渡しをします。以下のために使用できる複数のツールを公開しています：

1. 顧客情報の取得
2. 車両情報の取得
3. 保険見積もりの取得
4. 車両安全情報の取得
5. ポリシー情報の取得（全ポリシー、特定のポリシー、顧客のポリシー）

## 前提条件

- Python 3.10 以上
- Node.js と npm（MCP Inspector 用）
- uv パッケージマネージャー（推奨）

## セットアップ手順

### 1. 依存関係のインストール

```bash
# リポジトリをクローン（まだの場合）
cd local_prototype/native_mcp_server

# オプション 1: セットアップスクリプトを使用
chmod +x setup.sh
./setup.sh

# オプション 2: 手動セットアップ
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 保険 API の起動

MCP サーバーは保険 API に接続します。ポート 8001 で実行されている必要があります：

```bash
cd ../insurance_api
python -m uvicorn server:app --port 8001
```

### 3. MCP サーバーの起動

新しいターミナルウィンドウで：

```bash
cd local_prototype/native_mcp_server
source venv/bin/activate

# uv で実行（推奨）
uv run server.py

# または通常の Python で実行
python server.py
```

以下のような出力が表示されます：
```
🚀 LocalMCP v1.0.0 MCP サーバーを起動中...
📂 プロジェクトディレクトリ: /Users/username/local_mcp_projects
🔌 保険 API URL: http://localhost:8001
✅ サーバーが稼働中です。停止するには CTRL+C を押してください。
streamable-http トランスポートで起動中...
INFO: Uvicorn が http://127.0.0.1:8000 で稼働中（停止するには CTRL+C を押してください）
```

### 4. MCP Inspector で接続

MCP Inspector でサーバーをテストするには：

1. MCP Inspector をインストールして起動：
```bash
npx @modelcontextprotocol/inspector
```

2. ブラウザで MCP Inspector が自動的に開きます

3. MCP サーバー URL を追加：
   - 「Add MCP URL」をクリック
   - 入力: `http://localhost:8000/mcp`
   - 「Connect」をクリック

4. 利用可能なツールが表示され、操作できるようになります：
   - `get_customer_info`
   - `get_vehicle_info`
   - `get_insurance_quote`
   - `get_vehicle_safety`
   - `get_all_policies`
   - `get_policy_by_id`
   - `get_customer_policies`

## ツールの使用

### 例: 顧客情報の取得

顧客に関する情報を取得するには：

1. MCP Inspector で `get_customer_info` ツールを選択
2. パラメータに有効な顧客 ID（例: `cust-001`）を入力
3. 「Run」をクリック

### 例: ポリシーデータの操作

MCP サーバーは保険ポリシーを扱うための 3 つのツールを提供しています：

#### 全ポリシーの取得

利用可能なすべてのポリシーを取得するには：

1. MCP Inspector で `get_all_policies` ツールを選択
2. パラメータは不要
3. 「Run」をクリック

#### ID によるポリシーの取得

特定のポリシーの詳細を取得するには：

1. MCP Inspector で `get_policy_by_id` ツールを選択
2. パラメータに有効なポリシー ID（例: `policy-001`）を入力
3. 「Run」をクリック

#### 顧客のポリシーを取得

特定の顧客のすべてのポリシーを取得するには：

1. MCP Inspector で `get_customer_policies` ツールを選択
2. パラメータに有効な顧客 ID（例: `cust-001`）を入力
3. 「Run」をクリック

![get_customer_info ツール呼び出しの例](local_mcp_call.png)

### 有効なテストデータ

テストにはこれらの値を使用してください：

- 顧客 ID: `cust-001`、`cust-002`、`cust-003`
- 車両メーカー: `Toyota`、`Honda`、`Ford`
- 車両モデル: `Camry`、`Civic`、`F-150`
- 車両年式: 2010〜2023 年の任意の年
- ポリシー ID: `policy-001`、`policy-002`、`policy-003`

## トラブルシューティング

- **接続拒否エラー**: 保険 API と MCP サーバーの両方が実行中であることを確認
- **顧客が見つからないエラー**: 有効な顧客 ID を使用していることを確認
- **ポートが使用中**: ポートを使用しているプロセスを終了するか、別のポートを指定

## アーキテクチャ

MCP サーバーは以下で構成されています：

1. `server.py` - MCP サーバーを初期化するメインエントリーポイント
2. `tools/insurance_tools.py` - 保険 API と対話するツール
3. `config.py` - API URL とサーバー設定を含む設定

## 開発者向け

ツールを追加するには：

1. `tools/insurance_tools.py` に関数を追加
2. `register_insurance_tools` 関数で登録
3. サーバーを再起動して利用可能にする

エラーハンドリングを変更するには：

- ツール実装の try/except ブロックを編集してエラーメッセージをカスタマイズ

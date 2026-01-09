# フロントエンドモジュール

## アーキテクチャと概要

### フロントエンドモジュールとは？

フロントエンドモジュールは、デバイス管理システムの Web ベースのユーザーインターフェースを提供します。FastAPI と WebSocket で構築されており、ユーザーが自然言語クエリを使用して IoT デバイスと対話できるチャットライクなインターフェースを提供します。

### 主な責務
- **Web インターフェース**: デバイス管理用のレスポンシブ HTML インターフェースを提供
- **リアルタイム通信**: ライブチャット体験のための WebSocket 接続を処理
- **ユーザー認証**: 安全なユーザーログインのため Amazon Cognito と統合
- **レスポンスフォーマット**: デバイスデータをユーザーフレンドリーな形式で表示
- **セッション管理**: ユーザーセッションと会話コンテキストを維持

### アーキテクチャコンポーネント
- **FastAPI アプリケーション**: インターフェースと API エンドポイントを提供する Web フレームワーク
- **WebSocket ハンドラー**: Agent Runtime とのリアルタイム通信
- **認証システム**: ユーザー管理のための Amazon Cognito 統合
- **テンプレートエンジン**: 動的 HTML レンダリング用の Jinja2
- **静的アセット**: ユーザーインターフェース用の CSS、JavaScript、画像

## 前提条件

### 必要なソフトウェア
- **Python 3.10 以上**
- **Web ブラウザ**（Chrome、Firefox、Safari、Edge）
- **Node.js**（オプション、高度なフロントエンド開発用）

### AWS サービスアクセス
- 認証用の **Amazon Cognito** ユーザープール
- デバイス操作用の **Agent Runtime** エンドポイント

### 必要な依存関係
- **FastAPI**: Web フレームワーク
- **Uvicorn**: ASGI サーバー
- **WebSockets**: リアルタイム通信
- **Jinja2**: テンプレートエンジン
- **Python-Jose**: JWT トークン処理

## デプロイ手順

### オプション 1: 自動セットアップ（推奨）

```bash
# frontend ディレクトリから
chmod +x setup_and_run.sh
./setup_and_run.sh
```

### オプション 2: 手動デプロイ

#### ステップ 1: 環境設定
```bash
# .env ファイルを作成
cp .env.example .env
# 値を編集:
# - MCP_SERVER_URL（Gateway モジュールから）
# - 認証用の COGNITO_* 変数
# - HOST と PORT 設定
```

#### ステップ 2: 依存関係のインストール
```bash
pip install -r requirements.txt
```

#### ステップ 3: 開発サーバーの実行
```bash
# ローカル開発
python main.py

# または uvicorn を直接使用
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

#### ステップ 4: Docker デプロイ（オプション）
```bash
# コンテナをビルド
docker build -t device-management-frontend .

# コンテナを実行
docker run -p 5001:5001 --env-file .env device-management-frontend
```

### デプロイの検証

```bash
# ローカルサーバーをテスト
curl http://localhost:8000/

# ヘルスエンドポイントをテスト
curl http://localhost:8000/health

# WebSocket 接続をテスト（ブラウザまたは WebSocket クライアントが必要）
# ブラウザで http://localhost:8000 を開いてチャットインターフェースを試す
```

## サンプルクエリ

フロントエンドが実行されると、ユーザーは Web インターフェースを通じてこれらのタイプのクエリで対話できます：

### デバイス管理クエリ
```
"すべてのデバイスを表示して"
"オフラインのデバイスを一覧表示して"
"デバイス DG-10016 のステータスは？"
"デバイスは何台ありますか？"
```

### デバイス設定クエリ
```
"デバイス DG-10005 の設定を取得して"
"デバイス DG-10016 の WiFi ネットワークを表示して"
"デバイス DG-10022 のファームウェアバージョンは？"
```

### WiFi 管理クエリ
```
"デバイス DG-10016 の WiFi SSID を 'HomeNetwork-5G' に更新して"
"デバイス DG-10005 のセキュリティタイプを WPA3 に変更して"
"すべての WiFi ネットワークを表示して"
```

### ユーザーとアクティビティクエリ
```
"今日ログインしたのは誰？"
"最近のアクティビティを表示して"
"システム内のすべてのユーザーを一覧表示して"
```

### 期待されるユーザー体験
- **リアルタイムレスポンス**: エージェントが処理する間、メッセージがリアルタイムでストリーミング
- **フォーマットされた出力**: デバイス情報が読みやすいテーブルとリストで表示
- **エラーハンドリング**: 失敗した操作に対するユーザーフレンドリーなエラーメッセージ
- **セッション永続化**: ブラウザセッション間でログイン状態を維持

## クリーンアップ手順

### 実行中のサービスを停止

```bash
# 開発サーバーを停止
# フォアグラウンドで実行中の場合は Ctrl+C を押す

# Docker コンテナを停止
docker stop device-management-frontend
docker rm device-management-frontend
```

### Docker リソースの削除

```bash
# ビルド済みイメージを削除
docker rmi device-management-frontend

# 未使用イメージをクリーンアップ
docker image prune
```

### ローカルファイルのクリーンアップ

```bash
# 環境ファイルを削除（機密データを含む）
rm .env

# セッションデータとキャッシュを削除
rm -rf __pycache__/
rm -rf .pytest_cache/

# ログファイルを削除（存在する場合）
rm -f *.log
```

## 設定

### 環境変数

```bash
# サーバー設定
HOST=127.0.0.1  # Docker の場合は 0.0.0.0 を使用
PORT=8000

# Agent Runtime 接続
MCP_SERVER_URL=https://gateway-id.gateway.bedrock-agentcore.us-west-2.amazonaws.com
AGENT_RUNTIME_URL=http://localhost:8080  # ローカル Agent Runtime を使用する場合

# Amazon Cognito 設定（ユーザー認証用）
COGNITO_USERPOOL_ID=your-frontend-userpool-id
COGNITO_APP_CLIENT_ID=your-frontend-client-id
COGNITO_DOMAIN=your-frontend-domain.auth.us-west-2.amazoncognito.com
COGNITO_CLIENT_SECRET=your-frontend-client-secret

# CORS 設定
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# セッション設定
SESSION_SECRET_KEY=your-secret-key-for-sessions
SESSION_MAX_AGE=3600  # 1 時間
```

### Web インターフェース機能

#### 認証オプション
- **Amazon Cognito ログイン**: ホスト UI を使用した完全な OAuth フロー
- **シンプルログイン**: 開発/デモ用の基本的なユーザー名/パスワード
- **セッション管理**: CSRF 保護を備えた安全なセッション Cookie

#### チャットインターフェース
- **WebSocket 通信**: リアルタイム双方向通信
- **メッセージ履歴**: セッション中の会話履歴を維持
- **タイピングインジケーター**: エージェント処理中の視覚的フィードバック
- **エラー回復**: 接続断時の自動再接続

#### レスポンスフォーマット
- **デバイステーブル**: ステータスインジケーター付きのフォーマットされたデバイス一覧
- **設定表示**: 構造化された設定とネットワーク情報
- **アクティビティログ**: タイムスタンプ付きの時系列ユーザーアクティビティ
- **エラーメッセージ**: ユーザーフレンドリーなエラー説明と提案

## トラブルシューティング

### よくある問題

**フロントエンドが起動しない**:
- ポート 8000 が既に使用されていないか確認
- Python 依存関係がインストールされているか確認
- .env ファイルに正しい設定があるか確認

**認証エラー**:
- Amazon Cognito 設定を確認
- ユーザープールとアプリクライアントが存在するか確認
- CORS オリジンにドメインが含まれているか確認

**WebSocket 接続エラー**:
- Agent Runtime が実行中でアクセス可能か確認
- MCP_SERVER_URL が正しいか確認
- バックエンドサービスへのネットワーク接続をテスト

**チャットインターフェースが応答しない**:
- ブラウザコンソールで JavaScript エラーを確認
- WebSocket 接続が確立されているか確認
- バックエンドサービスを独立してテスト

### デバッグコマンド

```bash
# FastAPI サーバーをテスト
curl -v http://localhost:8000/

# WebSocket エンドポイントを確認
curl -v -H "Connection: Upgrade" -H "Upgrade: websocket" \
     http://localhost:8000/ws/test-client

# 認証エンドポイントをテスト
curl -v http://localhost:8000/simple-login

# 静的ファイル配信を確認
curl -v http://localhost:8000/static/style.css
```

### ブラウザ開発者ツール

1. **Console タブ**: JavaScript エラーを確認
2. **Network タブ**: WebSocket 接続と HTTP リクエストを監視
3. **Application タブ**: セッションストレージと Cookie を検査
4. **Elements タブ**: HTML/CSS レンダリングの問題をデバッグ

## 他のモジュールとの統合

- **Agent Runtime モジュール**: リアルタイムチャット機能のため WebSocket 経由で通信
- **Gateway モジュール**: デバイス操作のため Agent Runtime を通じて間接的にアクセス
- **Device Management モジュール**: フルスタック（Frontend → Agent Runtime → Gateway → Lambda）を通じて操作を実行

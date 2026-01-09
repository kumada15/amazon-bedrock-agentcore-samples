# Amazon Bedrock AgentCore - 双方向 WebSocket サンプル

このリポジトリには、Amazon Bedrock AgentCore との双方向 WebSocket 通信を示すサンプル実装が含まれています：

- **Sonic** - AgentCore に直接デプロイされたネイティブ Amazon Nova Sonic Python WebSocket 実装。直接イベント処理による Nova Sonic プロトコルの完全な制御を提供します。音声選択と割り込みサポートを備えたリアルタイム音声会話をテストするための Web クライアントを含みます。

- **Strands** - 簡素化されたリアルタイム音声会話のための Strands BidiAgent を使用した高レベルフレームワーク実装。自動セッション管理、ツール統合、合理化された API を備えた Nova Sonic の上に構築されています。フレームワーク抽象化の恩恵を受けるラピッドプロトタイピングと本番アプリケーションに最適です。

- **Echo** - AI 機能なしで WebSocket 接続と認証をテストするためのシンプルなエコーサーバー。

すべてのサンプルは、ルートの `setup.sh` と `cleanup.sh` スクリプトを通じて統一されたセットアップとクリーンアッププロセスを使用します。

## 前提条件

- 適切な権限で設定された AWS CLI
- Python 3.12+
- Docker（カスタムエージェントイメージのビルド用）
- AWS アカウント ID

---

## Sonic サンプル - ネイティブ Nova Sonic 2 実装

このサンプルは、**ネイティブ Amazon Nova Sonic 2 Python WebSocket サーバー** を AgentCore に直接デプロイします。直接イベント処理による Nova Sonic プロトコルの完全な制御を提供し、セッション管理、オーディオストリーミング、レスポンス生成の完全な可視性を実現します。

**アーキテクチャ：**

![AgentCore Sonic Architecture](./images/agentcore-sonic-architecture.png)

**最適な用途：** セッション管理とイベント処理のきめ細かな制御が必要なリアルタイム音声会話を必要とする本番アプリケーション。

### セットアップ

```bash
# 必須
export ACCOUNT_ID=your_aws_account_id

# オプション - これらをカスタマイズするか、デフォルトを使用
export AWS_REGION=us-east-1
export IAM_ROLE_NAME=WebSocketSonicAgentRole
export ECR_REPO_NAME=agentcore_sonic_images
export AGENT_NAME=websocket_sonic_agent

# AWS 認証（いずれかの方法を選択）：

# 方法 1：AWS プロファイルを使用（推奨）
# AWS_PROFILE 環境変数を設定するか、デフォルトプロファイルが適切なアクセス権を持っていることを確認
export AWS_PROFILE=your_profile_name

# 方法 2：AWS 認証情報を直接使用
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # オプション、一時認証情報用

# セットアップを実行
./setup.sh sonic
```

### クライアントの実行

**オプション 1：起動スクリプトを使用（推奨）**
```bash
./start_client.sh sonic
```

**オプション 2：手動起動**
```bash
# 環境変数をエクスポート（セットアップ出力から）
export AWS_REGION="us-east-1"

# AWS 認証（いずれかの方法を選択）：
# AWS_PROFILE 環境変数を設定するか、デフォルトプロファイルが適切なアクセス権を持っていることを確認
export AWS_PROFILE=your_profile_name
# または
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # オプション

# Web クライアントを起動
python sonic/client/client.py --runtime-arn "<agent-arn-from-setup>"
```

Web クライアントは以下を行います：
1. ブラウザで自動的に開く
2. マイクへのアクセスを要求
3. AI とのリアルタイム音声会話を有効にする

### 機能

- **リアルタイム音声ストリーミング** - 自然に話し、即座にレスポンスを得る
- **音声選択** - 複数の言語（英語、フランス語、イタリア語、ドイツ語、スペイン語）の複数の音声から選択
- **動的音声切り替え** - アクティブな会話中に音声を変更
- **割り込みサポート** - アシスタントのレスポンス中に割り込むバージイン機能
- **ツール統合** - 「今何時？」や「今日は何日？」などの質問に応答するサンプル `getDateTool` を含む
- **Web ベース UI** - インストール不要、任意の最新ブラウザで動作
- **セッション管理** - 自動セッション処理とオーディオバッファリング
- **イベントログ** - フィルタリング機能付きで、すべての WebSocket イベントをリアルタイムで確認

### サンプルツール：getDateTool

Sonic 実装には、ツール統合の動作例が含まれています。`getDateTool` は以下の方法を示します：
- クライアント設定でツールを定義（[`sonic/client/sonic-client.html`](sonic/client/sonic-client.html#L617-L628)）
- セッションセットアップ中にツール設定を送信（[`sonic/client/sonic-client.html`](sonic/client/sonic-client.html#L773-L784)）
- サーバーでツール呼び出しを処理（[`sonic/websocket/s2s_session_manager.py`](sonic/websocket/s2s_session_manager.py#L339-L342)）
- 結果を会話フローに返す

**試してみる：** 「今何時？」や「今日の日付は？」などの質問をすると、アシスタントがツールを呼び出して現在の UTC 日時を取得します。

### クリーンアップ

```bash
./cleanup.sh sonic
```

---

## Strands サンプル - フレームワークベース実装

このサンプルは、Amazon Nova Sonic とのリアルタイム音声会話のための **Strands BidiAgent フレームワーク** の使用を示します。Strands は、双方向ストリーミング、自動セッション管理、ツール統合を簡素化する高レベル抽象化を提供します。

**アーキテクチャ：**

Strands 実装は、BidiAgent フレームワークを使用して、WebSocket 通信、オーディオストリーミング、ツールオーケストレーションの複雑さを自動的に処理します。

**最適な用途：** 完全な Nova Sonic 機能を維持しながら、フレームワーク抽象化の恩恵を受けるラピッドプロトタイピングと本番アプリケーション。

### セットアップ

```bash
# 必須
export ACCOUNT_ID=your_aws_account_id

# オプション - これらをカスタマイズするか、デフォルトを使用
export AWS_REGION=us-east-1
export IAM_ROLE_NAME=WebSocketStrandsAgentRole
export ECR_REPO_NAME=agentcore_strands_images
export AGENT_NAME=websocket_strands_agent

# AWS 認証（いずれかの方法を選択）：

# 方法 1：AWS プロファイルを使用（推奨）
# AWS_PROFILE 環境変数を設定するか、デフォルトプロファイルが適切なアクセス権を持っていることを確認
export AWS_PROFILE=your_profile_name

# 方法 2：AWS 認証情報を直接使用
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # オプション、一時認証情報用

# セットアップを実行
./setup.sh strands
```

### クライアントの実行

**オプション 1：起動スクリプトを使用（推奨）**
```bash
./start_client.sh strands
```

**オプション 2：手動起動**
```bash
# 環境変数をエクスポート（セットアップ出力から）
export AWS_REGION="us-east-1"

# AWS 認証（いずれかの方法を選択）：
# AWS_PROFILE 環境変数を設定するか、デフォルトプロファイルが適切なアクセス権を持っていることを確認
export AWS_PROFILE=your_profile_name
# または
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # オプション

# Web クライアントを起動
python strands/client/client.py --runtime-arn "<agent-arn-from-setup>"
```

Web クライアントは以下を行います：
1. ブラウザで自動的に開く
2. マイクへのアクセスを要求
3. AI とのリアルタイム音声会話を有効にする

### サンプルツール：電卓

Strands 実装には、フレームワークベースのツール統合を示す電卓ツールが含まれています。このツールは基本的な算術演算を実行できます。

**試してみる：** 「25掛ける4は？」や「100割る5を計算して」などの質問をすると、アシスタントが電卓ツールを使用します。

### Sonic サンプルとの主な違い

- **抽象化レベル：** Strands は高レベル API を提供 vs. Sonic の直接プロトコル制御
- **コードの複雑さ：** Strands はセッション管理のボイラープレートが少ない
- **ツール統合：** フレームワークがツールオーケストレーションを自動処理
- **柔軟性：** Sonic はイベントとレスポンスのよりきめ細かな制御を提供

### クリーンアップ

```bash
./cleanup.sh strands
```

---

## Echo サンプル - WebSocket テスト

WebSocket 接続と認証をテストするためのシンプルなエコーサーバー。

### セットアップ

```bash
# 必須
export ACCOUNT_ID=your_aws_account_id

# オプション - これらをカスタマイズするか、デフォルトを使用
export AWS_REGION=us-east-1
export IAM_ROLE_NAME=WebSocketEchoAgentRole
export DOCKER_REPO_NAME=agentcore_echo_images
export AGENT_NAME=websocket_echo_agent

# AWS 認証（いずれかの方法を選択）：

# 方法 1：AWS プロファイルを使用（推奨）
# AWS_PROFILE 環境変数を設定するか、デフォルトプロファイルが適切なアクセス権を持っていることを確認
export AWS_PROFILE=your_profile_name

# 方法 2：AWS 認証情報を直接使用
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # オプション、一時認証情報用

# セットアップを実行
./setup.sh echo
```

### クライアントの実行

**オプション 1：起動スクリプトを使用（推奨）**
```bash
./start_client.sh echo
```

**オプション 2：手動起動**
```bash
# 環境変数をエクスポート（セットアップ出力から）
export AWS_REGION="us-east-1"

# AWS 認証（いずれかの方法を選択）：
# AWS_PROFILE 環境変数を設定するか、デフォルトプロファイルが適切なアクセス権を持っていることを確認
export AWS_PROFILE=your_profile_name
# または
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # オプション

# SigV4 ヘッダー認証でテスト
python echo/client/client.py --runtime-arn "<agent-arn-from-setup>" --auth-type headers

# SigV4 クエリパラメータでテスト
python echo/client/client.py --runtime-arn "<agent-arn-from-setup>" --auth-type query
```
### 機能

- **シンプルエコー** - メッセージを送信し、エコーレスポンスを確認
- **複数の認証方法** - SigV4 ヘッダーまたはクエリパラメータをテスト
- **接続テスト** - WebSocket 接続を確認
- **最小限の依存関係** - デバッグに最適

### 期待される出力

```
WebSocket connected
Sent: {"msg": "Hello, World! Echo Test"}
Received: {"msg": "Hello, World! Echo Test"}
Echo test PASSED
```

### クリーンアップ

```bash
./cleanup.sh echo
```

---

## デプロイメントの仕組み

`setup.sh` スクリプトは完全なデプロイメントを自動化します：

1. **前提条件チェック** - jq、Python 3、Docker、AWS CLI がインストールされていることを確認
2. **Python 環境** - 仮想環境を作成し、依存関係をインストール
3. **Docker ビルド＆プッシュ** - ARM64 コンテナイメージをビルドし、Amazon ECR にプッシュ
4. **IAM ロール** - ECR、CloudWatch、Bedrock、X-Ray の権限を持つロールを作成
5. **エージェントランタイム** - WebSocket サーバーを Bedrock AgentCore にデプロイ
6. **設定** - クリーンアップ用にデプロイ詳細を `setup_config.json` に保存

デプロイ後、ECR リポジトリ、IAM ロール、実行中のエージェントランタイム、簡単なクリーンアップのための設定ファイルが利用可能になります。

---

## ファイル構造

```
.
├── setup.sh                       # 統一セットアップスクリプト（フォルダパラメータを取る）
├── start_client.sh                # 統一クライアント起動スクリプト（フォルダパラメータを取る）
├── cleanup.sh                     # 統一クリーンアップスクリプト（フォルダパラメータを取る）
├── requirements.txt               # Python 依存関係
├── websocket_helpers.py           # 共有 WebSocket ユーティリティ（SigV4 認証、事前署名 URL）
├── agent_role.json               # IAM ロールポリシーテンプレート
├── trust_policy.json             # IAM 信頼ポリシー
│
├── sonic/                        # Sonic サンプル（ネイティブ実装）
│   ├── client/                   # Web ベースクライアント
│   │   ├── sonic-client.html     # 音声選択付き HTML UI
│   │   ├── client.py             # Web サーバー
│   │   └── requirements.txt      # クライアント依存関係
│   ├── websocket/                # サーバー実装
│   │   ├── server.py             # Sonic WebSocket サーバー
│   │   ├── s2s_session_manager.py # セッション管理
│   │   ├── s2s_events.py         # イベント処理
│   │   ├── Dockerfile            # コンテナ定義
│   │   └── requirements.txt      # サーバー依存関係
│   └── setup_config.json         # setup.sh で生成
│
├── strands/                      # Strands サンプル（フレームワークベース）
│   ├── client/                   # Web ベースクライアント
│   │   ├── strands-client.html   # HTML UI
│   │   ├── client.py             # Web サーバー
│   │   └── requirements.txt      # クライアント依存関係
│   ├── websocket/                # サーバー実装
│   │   ├── server.py             # Strands BidiAgent サーバー
│   │   ├── Dockerfile            # コンテナ定義
│   │   └── requirements.txt      # サーバー依存関係
│   └── setup_config.json         # setup.sh で生成
│
└── echo/                         # Echo サンプル（テスト）
    ├── client/                   # CLI クライアント
    │   └── client.py             # Echo テストクライアント
    ├── websocket/                # サーバー実装
    │   ├── server.py             # Echo WebSocket サーバー
    │   ├── Dockerfile            # コンテナ定義
    │   └── requirements.txt      # サーバー依存関係
    └── setup_config.json         # setup.sh で生成
```

---

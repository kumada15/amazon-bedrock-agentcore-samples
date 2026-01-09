# Bedrock AgentCoreチャットインターフェース

Amazon Bedrock AgentCore Runtimeにデプロイされたエージェントと対話するためのStreamlit Webアプリケーションです。このアプリケーションは、デプロイされたエージェントとリアルタイムで通信するための直感的なチャットインターフェースを提供します。

## Amazon Bedrock AgentCoreについて

Amazon Bedrock AgentCoreは、任意のフレームワークとモデルを使用して、高効率なAIエージェントをセキュアかつ大規模にデプロイおよび運用できる包括的なサービスです。AgentCore Runtimeは、LangGraph、CrewAI、Strands Agentsなどの人気のあるオープンソースフレームワークを使用して、動的なAIエージェントとツールをデプロイおよびスケーリングするために構築されたセキュアでサーバーレスなランタイムです。

## 機能

- **リアルタイムチャットインターフェース**: デプロイされたAgentCoreエージェントとのインタラクティブなチャット
- **エージェント検出**: AWSアカウント内の利用可能なエージェントを自動的に検出して選択
- **バージョン管理**: デプロイされたエージェントの特定バージョンを選択
- **マルチリージョンサポート**: 異なるAWSリージョンにデプロイされたエージェントに接続
- **ストリーミングレスポンス**: エージェントレスポンスのリアルタイムストリーミング
- **レスポンスフォーマット**: 生出力を表示するオプション付きのレスポンス自動フォーマット
- **セッション管理**: 一意のセッションIDで会話コンテキストを維持
- **ツール表示**: 実行中にエージェントが使用したツールのオプション表示
- **思考プロセス**: エージェントの推論プロセスのオプション表示（利用可能な場合）

## アーキテクチャ

![Architecture diagram](static/arch.png)

## 前提条件

- Python 3.11以上
- [uvパッケージマネージャー](https://docs.astral.sh/uv/getting-started/installation/)
- 適切な認証情報で設定されたAWS CLI
- Amazon Bedrock AgentCoreサービスへのアクセス
- Bedrock AgentCore Runtimeにデプロイされたエージェント

### 必要なAWS権限

AWS認証情報には以下の権限が必要です：

- `bedrock-agentcore-control:ListAgentRuntimes`
- `bedrock-agentcore-control:ListAgentRuntimeVersions`
- `bedrock-agentcore:InvokeAgentRuntime`

## インストール

1. **リポジトリをクローン**:

   ```bash
   git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
   cd amazon-bedrock-agentcore-samples/03-integrations/ux-examples/streamlit-chat
   ```

2. **uvを使用して依存関係をインストール**:

   ```bash
   uv sync
   ```

## （オプション）サンプルエージェントのデプロイ

1. **uvを使用して開発依存関係をインストール**（推奨）:

```bash
uv sync --dev
```

2. **エージェントを設定**:

```bash
cd example
uv run agentcore configure -e agent.py
```

3. **AgentCore Runtimeにデプロイ**:

```bash
uv run agentcore launch
cd ..
```

## アプリケーションの実行

### uvを使用（推奨）

```bash
uv run streamlit run app.py
```

アプリケーションが起動し、`http://localhost:8501`で利用可能になります。

## 使用方法

1. **AWSリージョンを設定**: サイドバーから希望のAWSリージョンを選択
2. **エージェントを選択**: アカウント内で自動検出されたエージェントから選択
3. **バージョンを選択**: 使用するエージェントの特定バージョンを選択
4. **チャットを開始**: チャット入力にメッセージを入力してEnterを押す

### 設定オプション

- **レスポンスの自動フォーマット**: 可読性向上のためにエージェントレスポンスをクリーンアップしてフォーマット
- **生レスポンスを表示**: エージェントからの未処理レスポンスを表示
- **ツールを表示**: 実行中にエージェントがツールを使用した時を表示
- **思考を表示**: エージェントの推論プロセスを表示（利用可能な場合）
- **セッション管理**: 新しい会話を開始するために新しいセッションIDを生成

## プロジェクト構造

```
streamlit-chat/
├── app.py                    # メインStreamlitアプリケーション
├── example.py                # サンプルエージェント
├── static/                   # UIアセット（フォント、アイコン、ロゴ）
├── pyproject.toml            # プロジェクト依存関係
└── README.md                 # このファイル
```

## 設定ファイル

- **`pyproject.toml`**: プロジェクトの依存関係とメタデータを定義
- **`.streamlit/config.toml`**: Streamlit固有の設定

## トラブルシューティング

### よくある問題

1. **エージェントが見つからない**: 選択したリージョンにエージェントがデプロイされていること、適切なAWS権限があることを確認してください
2. **接続エラー**: AWS認証情報とネットワーク接続を確認してください
3. **権限拒否**: IAMユーザー/ロールに必要なBedrock AgentCore権限があることを確認してください

### デバッグモード

アプリケーションでStreamlitロガーレベルを設定してデバッグログを有効にするか、ブラウザコンソールで追加のエラー情報を確認してください。

## 開発

### 新機能の追加

このアプリケーションはモジュール性を念頭に構築されています。拡張のための主要な領域：

- **レスポンス処理**: カスタムフォーマットのために`clean_response_text()`を修正
- **エージェント選択**: カスタムフィルタリングのために`fetch_agent_runtimes()`を拡張
- **UIコンポーネント**: サイドバーまたはメインエリアに新しいStreamlitコンポーネントを追加

### 依存関係

- **boto3**: AWS SDK for Python
- **streamlit**: Webアプリケーションフレームワーク
- **uv**: 高速Pythonパッケージインストーラーおよびリゾルバー

## コントリビュート

1. リポジトリをフォーク
2. フィーチャーブランチを作成
3. 変更を加える
4. 十分にテスト
5. プルリクエストを提出

## ライセンス

このプロジェクトは、リポジトリのライセンスファイルに記載されている条件の下でライセンスされています。

## リソース

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Bedrock AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Strands Agents Framework](https://github.com/awslabs/strands-agents)

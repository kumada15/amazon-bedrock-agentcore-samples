# エージェントデプロイメント - AgentCore での Strands Agent インフラストラクチャデプロイメント

**Runtime** と **Memory** 機能を備えたスケーラブルなエージェントアプリケーション向けのフルマネージドサービスである **[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** を使用して、ビデオゲーム売上データアナリストアシスタント Strands Agent をデプロイします。

> [!NOTE]
> **作業ディレクトリ**: このチュートリアルを開始する前に、`agentcore-strands-data-analyst-assistant/` フォルダにいることを確認してください。このガイドのすべてのコマンドはこのディレクトリから実行する必要があります。

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore のマネージドインフラストラクチャを使用してビデオゲーム売上データアナリストエージェントをデプロイする方法を案内します。以下のモジュラーサービスが含まれます：

- **[Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)**: エージェントインスタンス用の呼び出しエンドポイント（`/invocations`）とヘルスモニタリング（`/ping`）を備えたマネージド実行環境を提供
- **[Amazon Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)**: AI エージェントがイベントをキャプチャし、メモリに変換し、必要に応じて関連するコンテキストを取得することで、対話を通じて記憶、学習、進化する能力を与えるフルマネージドサービス

**[Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)** を確認することを忘れずに。

> [!IMPORTANT]
> このサンプルアプリケーションはデモ目的であり、本番環境には対応していません。組織のセキュリティベストプラクティスでコードを検証してください。
>
> テスト後は、提供されているクリーンアップ手順に従ってリソースをクリーンアップし、不要なコストを避けることを忘れずに。

## 環境セットアップと要件

開始前に、以下を確認してください：

* **[バックエンドデプロイメント - CDK でのデータソースと設定管理デプロイメント](../cdk-agentcore-strands-data-analyst-assistant)**
* **[Docker](https://www.docker.com)**
* **必要なパッケージ**：
  * Amazon Bedrock AgentCore CLI をインストール：
    ```bash
    pip install bedrock-agentcore
    ```
  * すべてのプロジェクト依存関係をインストール：
    ```bash
    pip install -r requirements.txt
    ```

## 短期 AgentCore メモリの作成

エージェントをデプロイする前に、エージェントが会話コンテキストを維持するのに役立つ **[短期メモリ](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-memory.html)** ストアを作成する必要があります：

1. 7日間のデフォルト有効期限でメモリストアを作成：

```bash
python3 resources/memory_manager.py create DataAnalystAssistantMemory ${MEMORY_ID_SSM_PARAMETER}
```

2. メモリストアが正常に作成されたことを確認するために、利用可能なすべてのメモリストアを一覧表示：

```bash
python3 resources/memory_manager.py list
```

このメモリストアにより、エージェントは同じセッション内で以前のインタラクションを記憶でき、より一貫性のあるコンテキストに沿った会話体験を提供します。


## ローカルテスト

AWS にデプロイする前に、機能を確認するためにデータアナリストエージェントをローカルでテストできます：

1. 必要な環境変数を設定し、ローカルエージェントサーバーを起動：

```bash
export PROJECT_ID="agentcore-data-analyst-assistant"
python3 app.py
```

これにより、AgentCore ランタイム環境をシミュレートするローカルサーバーがポート 8080 で起動します。

2. 別のターミナルで、会話追跡用のセッション ID を作成：

```bash
export SESSION_ID=$(uuidgen)
```

3. curl を使用してサンプルクエリでエージェントをテスト：

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "Hello world!", "session_id": "'$SESSION_ID'", "last_k_turns": 20}'
```

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "what is the structure of your data available?!", "session_id": "'$SESSION_ID'", "last_k_turns": 20}'
```

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "Which developers tend to get the best reviews?", "session_id": "'$SESSION_ID'", "last_k_turns": 20}'
```

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "Give me a summary of our conversation", "session_id": "'$SESSION_ID'", "last_k_turns": 20}'
```


## Amazon Bedrock AgentCore で Strands Agent をデプロイ

以下の簡単なステップでエージェントを AWS にデプロイ：

1. プロンプトでデフォルト値を受け入れてエージェントデプロイメントを設定：

```bash
agentcore configure \
  --entrypoint app.py \
  --name agentcoredataanalystassistant \
  -er $AGENT_CORE_ROLE_EXECUTION \
  --disable-memory \
  --deployment-type container
```

2. エージェントインフラストラクチャを起動：

```bash
agentcore launch --env PROJECT_ID="agentcore-data-analyst-assistant"
```

## デプロイされたエージェントのテスト

会話追跡用のセッション ID を作成し、デプロイされたエージェントをテスト：

```bash
export SESSION_ID=$(uuidgen)
```

以下のサンプルクエリでテスト：

```bash
agentcore invoke '{
  "prompt": "Hello world!",
  "session_id": "'$SESSION_ID'",
  "last_k_turns": 20
}'
```

```bash
agentcore invoke '{
  "prompt": "what is the structure of your data available?!",
  "session_id": "'$SESSION_ID'",
  "last_k_turns": 20
}'
```

```bash
agentcore invoke '{
  "prompt": "Which developers tend to get the best reviews?",
  "session_id": "'$SESSION_ID'",
  "last_k_turns": 20
}'
```

```bash
agentcore invoke '{
  "prompt": "Give me a summary of our conversation",
  "session_id": "'$SESSION_ID'",
  "last_k_turns": 20
}'
```

**期待される動作**: エージェントは "Gus" として応答し、video_games_sales_units データベース（1971-2024 年の 64,016 のゲームタイトル）に関する情報を提供し、開発者のレビュースコアを分析し、インタラクション間で会話コンテキストを維持するビデオゲーム売上データアナリストアシスタントです。

## 次のステップ

**[フロントエンド実装 - すぐに使えるデータアナリストアシスタントアプリケーションとの AgentCore 統合](../amplify-video-games-sales-assistant-agentcore-strands/)** に進むことができます。

## リソースのクリーンアップ（オプション）

不要な課金を避けるため、AWS コンソールから AgentCore 実行環境を削除してください。

## ありがとうございます

## ライセンス

このプロジェクトは Apache-2.0 ライセンスの下でライセンスされています。
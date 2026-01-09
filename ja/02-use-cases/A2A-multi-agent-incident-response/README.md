# インシデント対応ログのための Amazon Bedrock AgentCore 上の Agent-to-Agent (A2A) マルチエージェントシステム

[Amazon Bedrock `AgentCore` ランタイム](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html)上で動作する特化型エージェントを使用した [Agent-to-Agent (A2A)](https://a2a-protocol.org/latest/) プロトコルの包括的な実装であり、AWS インフラストラクチャの監視と運用管理のためのインテリジェントな連携を実現します。このリポジトリでは、AWS アカウント内のインシデントとメトリクスに関する質問に回答し、最適な修復戦略を検索するための 3 つのコアエージェントのセットアップ方法を説明します。監視エージェント（[`Strands` Agents SDK](https://strandsagents.com/latest/) を使用して構築）は、AWS 内およびクロス AWS アカウントのメトリクスとログに関するすべての質問を処理します。修復エージェント（[`OpenAI` の Agents SDK](https://openai.github.io/openai-agents-python/) を使用して構築）は、ユーザーが要求できる最適な修復戦略と最適化技術の効率的な Web 検索を実行します。両方のエージェントは別々のランタイムで `A2A` サーバーとして動作し、すべての `AgentCore` プリミティブを活用します - コンテキスト管理のためのメモリ、両方のエージェントの詳細な分析のためのオブザーバビリティ、ツール（`Cloudwatch`、`JIRA`、`TAVILY` API）へのアクセスのためのゲートウェイ、そして OAuth 2.0 と API を使用してエージェントへのインバウンドおよびアウトバウンドアクセスを可能にし、エージェントがアクセスできるリソースへのアクセスを可能にする `AgentCore` アイデンティティを使用します。これら 2 つのエージェントは、クライアントとして機能し、ランタイム上の A2A を使用して各エージェントにタスクを委任するホスト [`Google ADK` エージェント](https://google.github.io/adk-docs/)によって管理されます。Google ADK ホストエージェントは独自の `AgentCore` ランタイム上で動作します。

## デモ

![demo](./images/demo.gif)

## アーキテクチャ概要

![arch](./images/architecture.png)

> [!NOTE]
> **デフォルトモデル**
>
> このソリューションはデフォルトで以下の AI モデルを使用します：
> - **ホストエージェント（Google ADK）**: `gemini-2.5-flash`
> - **監視エージェント（Strands）**: `global.anthropic.claude-sonnet-4-5-20250929-v1:0`（Amazon Bedrock）
> - **Web 検索エージェント（OpenAI）**: `gpt-4o-2024-08-06`
>
> これらのモデルはデプロイ時にカスタマイズ可能です。デプロイスクリプトは、必要に応じて異なるモデル ID を指定するよう求めます。

## A2A とは？

<details>
  <summary>Agent-to-Agent (A2A)</summary>
   **Agent-to-Agent (A2A)** は、異なるプラットフォームや実装間で AI エージェント間のシームレスな通信と連携を可能にするオープン標準プロトコルです。A2A プロトコルは以下を定義します：

   - **エージェント探索**: 機能、スキル、通信エンドポイントを記述する標準化されたエージェントカード
   - **通信形式**: 信頼性の高いエージェント間通信のための JSON-RPC 2.0 ベースのメッセージ形式
   - **認証**: 安全なエージェント間通信のための OAuth 2.0 ベースのセキュリティモデル
   - **相互運用性**: 異なるフレームワークのエージェントが連携できるプラットフォームに依存しない設計

   A2A プロトコルの詳細: [A2A Specification](https://a2a-protocol.org/)

   ## Amazon Bedrock AgentCore での A2A サポート

   Amazon Bedrock AgentCore は A2A プロトコルのネイティブサポートを提供し、以下を可能にします：

   - **A2A 準拠エージェントのデプロイ**: 自動エンドポイント管理を備えたランタイムサービスとして
   - **安全な認証**: AWS Cognito OAuth 2.0 統合による
   - **エージェント探索**: 標準化されたエージェントカードエンドポイントを通じて
   - **スケーラブルなデプロイ**: 本番ワークロード向けの AWS インフラストラクチャを活用
   - **組み込みオブザーバビリティ**: CloudWatch 統合と OpenTelemetry サポート

   AgentCore は、インフラストラクチャ、認証、スケーリング、監視を自動的に処理することで A2A エージェントのデプロイを簡素化します。
</details>

## 前提条件

1. **AWS アカウント**: 適切な権限を持つアクティブな AWS アカウントが必要です
   - [AWS アカウント作成](https://aws.amazon.com/account/)
   - [AWS コンソールアクセス](https://aws.amazon.com/console/)

2. **AWS CLI**: AWS CLI をインストールして認証情報を設定してください
   - [AWS CLI のインストール](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [AWS CLI の設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
   - **重要**: リージョンを `us-west-2` に設定してください

   ```bash
   aws configure set region us-west-2
   ```

3. **Python 3.8+**: デプロイスクリプトの実行に必要です

4. **uv**: [ガイド](https://docs.astral.sh/uv/getting-started/installation/)に従って uv パッケージマネージャーをインストールしてください

5. **API キー**: 以下の API キーが必要です（デプロイスクリプトがこれらを求めます）：
   - **OpenAI API キー**: [OpenAI Platform](https://platform.openai.com/api-keys) から取得
   - **Tavily API キー**: [Tavily](https://tavily.com/) から取得
   - **Google API キー**: [Google AI Studio](https://aistudio.google.com/app/apikey) から取得

   > **注意**: 有料モデルを使用する場合は、OpenAI と Google アカウントにクレジットがあることを確認してください。

6. **サポートされるリージョン**: このソリューションは現在、以下の AWS リージョンでテストおよびサポートされています：

   | リージョンコード | リージョン名 | ステータス |
   |------------------|--------------|------------|
   | `us-west-2`      | 米国西部（オレゴン） | ✅ サポート対象 |

## クイックスタートデプロイ

このソリューションをデプロイする最も簡単な方法は、自動デプロイスクリプトを使用することです：

```bash
# リポジトリをクローン
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd 02-use-cases/A2A-multi-agent-incident-response

# インタラクティブデプロイスクリプトを実行
uv run deploy.py
```

デプロイスクリプトは以下を実行します：

1. ✅ AWS CLI がインストールおよび設定されていることを確認
2. ✅ AWS 認証情報が有効であることを確認
3. ✅ リージョンが `us-west-2` に設定されていることを確認
4. ✅ 必要なすべてのパラメータをインタラクティブに収集
5. ✅ 一意の S3 バケット名を生成
6. ✅ 設定を `.a2a.config` に保存
7. ✅ すべてのスタックを正しい順序で自動デプロイ
8. ✅ 各スタックが完了するのを待ってから次に進む

**合計デプロイ時間**: 約 10〜15 分

## React フロントエンド

以下のコマンドでフロントエンドを実行します。

```bash
cd frontend
npm install

chmod +x ./setup-env.sh
./setup-env.sh

npm run dev
```

## Google ADK Web アプリ

[Agent Development Kit Web](https://github.com/google/adk-web) は、エージェント開発とデバッグを容易にするために Google Agent Development Kit と統合された組み込み開発者 UI です。

![adk](./images/adk.gif)

1. [セットアップ手順](https://github.com/google/adk-web?tab=readme-ov-file#-prerequisite)に従ってください。
2. この[プロジェクト](./)のルートから `adk web` を実行します。

## A2A プロトコルインスペクター

[A2A Inspector](https://github.com/a2aproject/a2a-inspector) は、A2A（Agent2Agent）プロトコルを実装するサーバーの検査、デバッグ、検証を支援するための Web ベースのツールです。A2A エージェントとやり取りし、通信を表示し、仕様への準拠を確認するためのユーザーフレンドリーなインターフェースを提供します。

![inspector](./images/inspector.gif)

1. [セットアップとアプリケーション実行の手順](https://github.com/a2aproject/a2a-inspector?tab=readme-ov-file#setup-and-running-the-application)に従ってください。
2. 以下から URL とベアラートークンを取得します：

   ```bash

   uv run monitoring_strands_agent/scripts/get_m2m_token.py
   # または
   uv run web_search_openai_agents/scripts/get_m2m_token.py
   ```

3. A2A Inspector に URL とベアラートークン（`Bearer <ここに追加>`）を貼り付け、3 つのヘッダー `Authorization`、`X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`、`X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actorid` を追加します。`X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` の値は少なくとも 32 文字である必要があります（`550e8400-e29b-41d4-a716-446655440000
`）。

### ベアラートークン

各エージェントのベアラートークンを取得して、A2A Inspector などのツールや直接 API テストに使用できます。
監視エージェント用の M2M トークンを取得：

```bash
uv run monitoring_strands_agent/scripts/get_m2m_token.py

uv run web_search_openai_agents/scripts/get_m2m_token.py

uv run host_adk_agent/scripts/get_m2m_token.py
```

## テストスクリプト

インタラクティブスクリプトを使用して個々のエージェントをテスト：

```bash
# 監視エージェントをテスト
uv run test/connect_agent.py --agent monitor

# Web 検索エージェントをテスト
uv run test/connect_agent.py --agent websearch

# ホストエージェントをテスト
uv run test/connect_agent.py --agent host
```

## クリーンアップ

### 自動クリーンアップ（推奨）

すべてのリソースをクリーンアップする最も簡単な方法は、自動クリーンアップスクリプトを使用することです：

```bash
# クリーンアップスクリプトを実行
uv run cleanup.py
```

クリーンアップスクリプトは以下を実行します：

1. 🔍 `.a2a.config` からデプロイ設定を読み込み
2. 📋 削除されるすべてのリソースを表示
3. 🔒 二重確認が必要（'DELETE' の入力を含む）
4. 🗑️ 正しい逆順ですべてのリソースを削除：
   - ホストエージェントスタック
   - Web 検索エージェントスタック
   - 監視エージェントスタック
   - Cognito スタック
   - S3 バケットとコンテンツ
5. ⏱️ 各削除が完了するのを待ってから次に進む

**合計クリーンアップ時間**: 約 10〜15 分

> [!WARNING]
> これにより、デプロイされたすべてのリソースが完全に削除されます。この操作は取り消すことができません！

### クリーンアップのトラブルシューティング

クリーンアップが失敗した場合やエラーが発生した場合：

1. **スタックステータスを確認**: AWS CloudFormation コンソールで確認
2. **手動リソース削除**: 依存関係がある場合、一部のリソースは手動で削除する必要があるかもしれません
3. **S3 バケットが空でない**: 削除前にバケットが完全に空であることを確認
4. **CloudWatch ログを確認**: スタック削除イベントのエラーを確認

# AgentCore Runtime での AI エージェントのホスティング

## 概要

このチュートリアルでは、Amazon Bedrock AgentCore Python SDK を使用して **Amazon Bedrock AgentCore Runtime** で AI エージェントをホストする方法を示します。エージェントコードを Amazon Bedrock のインフラストラクチャとシームレスに統合する標準化された HTTP サービスに変換する方法を学びます。

AgentCore Runtime は、任意のエージェントフレームワーク（Strands Agents、LangGraph、CrewAI）と任意の LLM モデル（Amazon Bedrock、OpenAI など）で構築されたエージェントをホストできる **フレームワークおよびモデル非依存** のプラットフォームです。

Amazon Bedrock AgentCore Python SDK は以下の機能を持つラッパーとして機能します：

- エージェントコードを AgentCore の標準化されたプロトコルに **変換**
- HTTP および MCP サーバーインフラストラクチャを自動的に **処理**
- エージェントのコア機能に **集中** できる環境を提供
- 2つのプロトコルタイプを **サポート**：
  - **HTTP プロトコル**：従来のリクエスト/レスポンス REST API エンドポイント
  - **MCP プロトコル**：ツールおよびエージェントサーバー用の Model Context Protocol

### サービスアーキテクチャ

エージェントをホストする際、SDK は自動的に以下を行います：

- ポート `8080` でエージェントをホスト
- 2つの主要エンドポイントを提供：
  - **`/invocations`**：プライマリエージェントインタラクション（JSON 入力 → JSON/SSE 出力）
  - **`/ping`**：モニタリング用のヘルスチェック

![Hosting agent](images/hosting_agent_python_sdk.png)

エージェントが AgentCore Runtime へのデプロイ準備ができたら、Amazon Bedrock AgentCore StarterKit を使用して AgentCore Runtime にデプロイできます。

StarterKit を使用すると、エージェントのデプロイを設定し、エージェントの設定と AgentCore Runtime エンドポイントを含む Amazon ECR リポジトリを作成し、作成されたエンドポイントを呼び出して検証できます。

![StarterKit](../images/runtime_overview.png)

デプロイ後、AWS での AgentCore Runtime アーキテクチャは以下のようになります：

![RuntimeArchitecture](../images/runtime_architecture.png)

## チュートリアル例

このチュートリアルには、開始するための3つのハンズオン例が含まれています：

| 例                                                                     | フレームワーク | モデル         | 説明                                       |
| ---------------------------------------------------------------------- | -------------- | -------------- | ------------------------------------------ |
| **[01-strands-with-bedrock-model](01-strands-with-bedrock-model)**     | Strands Agents | Amazon Bedrock | AWS ネイティブモデルでの基本的なエージェントホスティング |
| **[02-langgraph-with-bedrock-model](02-langgraph-with-bedrock-model)** | LangGraph      | Amazon Bedrock | LangGraph エージェントワークフロー         |
| **[03-strands-with-openai-model](03-strands-with-openai-model)**       | Strands Agents | OpenAI         | 外部 LLM プロバイダーとの統合              |

## 主なメリット

- **フレームワーク非依存**：任意の Python ベースのエージェントフレームワークで動作
- **モデル柔軟性**：Amazon Bedrock、OpenAI、その他の LLM プロバイダーの LLM をサポート
- **本番環境対応**：組み込みのヘルスチェックとモニタリング
- **簡単な統合**：最小限のコード変更で対応可能
- **スケーラブル**：エンタープライズワークロード向けに設計

## はじめに

上記のチュートリアル例から、お好みのフレームワークとモデルの組み合わせに基づいて選択してください。各例には以下が含まれます：

- ステップバイステップのセットアップ手順
- 完全なコードサンプル
- テストガイドライン
- ベストプラクティス

## 次のステップ

チュートリアル完了後、以下のことができます：

- これらのパターンを他のフレームワークやモデルに拡張
- 本番環境へのデプロイ
- 既存のアプリケーションとの統合
- エージェントインフラストラクチャのスケーリング

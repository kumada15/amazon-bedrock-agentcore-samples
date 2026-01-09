# 🔌 Amazon Bedrock AgentCore 統合

Amazon Bedrock AgentCore サンプルリポジトリの統合セクションへようこそ！

このフォルダには、Amazon Bedrock AgentCore を人気のエージェントフレームワーク、IDプロバイダー、可観測性ツール、AWSサービスと接続する方法を示すフレームワークおよびプロトコル統合が含まれています。

## 🤖 エージェントフレームワーク

* **[ADK](./agentic-frameworks/adk/)**：Google検索との Agent Development Kit 統合
* **[AutoGen](./agentic-frameworks/autogen/)**：マルチエージェント会話フレームワーク
* **[CrewAI](./agentic-frameworks/crewai/)**：コラボレーティブAIエージェントオーケストレーション
* **[LangChain](./agentic-frameworks/langchain/)**：チェーンベースのエージェントワークフローとツール統合
* **[LangGraph](./agentic-frameworks/langgraph/)**：Web検索機能を備えたマルチエージェントワークフロー
* **[LlamaIndex](./agentic-frameworks/llamaindex/)**：ドキュメント処理と検索拡張生成
* **[OpenAI Agents](./agentic-frameworks/openai-agents/)**：ハンドオフパターンを備えた OpenAI Assistant API 統合
* **[PydanticAI](./agentic-frameworks/pydanticai-agents/)**：Bedrock モデルを使用した型安全なエージェント開発
* **[Strands Agents](./agentic-frameworks/strands-agents/)**：ストリーミング、ファイルシステム、OpenAI ID を備えたネイティブ統合サンプル

## ☁️ AWS サービス

* **[SageMaker AI](./amazon-sagemakerai/)**：AgentCore Runtime との MLflow 統合
* **[Bedrock Agent](./bedrock-agent/)**：Bedrock エージェントと AgentCore Gateway 間の統合

## 🔐 ID プロバイダー

* **[EntraID](./IDP-examples/EntraID/)**：3LO アウトバウンド認証を備えた Microsoft Entra ID 統合
* **[Okta](./IDP-examples/Okta/)**：インバウンド認証のためのステップバイステップ Okta 統合

## ☁️ Nova

* **[Nova Sonic](./nova/nova-sonic/)**：Amazon Nova モデル統合サンプル

## 📊 可観測性

* **[Dynatrace](./observability/dynatrace/)**：旅行エージェントサンプルを使用したアプリケーションパフォーマンスモニタリング統合
* **[Simple Dual Observability](./observability/simple-dual-observability/)**：AgentCore Runtime の自動 OpenTelemetry 計装を備えた Amazon CloudWatch と Braintrust 統合

## 🎨 UX サンプル

* **[Streamlit Chat](./ux-examples/streamlit-chat/)**：AgentCore バックエンド統合を備えたインタラクティブチャットインターフェース

## 🚀 統合パターン

これらの統合は以下を示しています：

- **フレームワーク適応**：既存のエージェントフレームワークを AgentCore で動作するように適応
- **認証フロー**：さまざまな ID プロバイダー統合の実装
- **モニタリングセットアップ**：エージェントパフォーマンス追跡のための可観測性ツールの接続
- **UI 統合**：AgentCore サービスに接続するユーザーインターフェースの構築
- **サービス構成**：複数の AWS サービスと AgentCore の組み合わせ

## 🎯 対象者

これらの統合は以下のような方に最適です：

- 既存のエージェントアプリケーションを AgentCore に移行する
- エンタープライズ認証パターンを実装する
- 本番環境のモニタリングと可観測性をセットアップする
- エージェントインタラクション用のカスタムユーザーインターフェースを構築する
- AgentCore を既存の AWS インフラストラクチャと接続する

## 🔗 関連リソース

- [チュートリアル](../01-tutorials/) - AgentCore の基礎を学ぶ
- [ユースケース](../02-use-cases/) - エンドツーエンドのアプリケーションサンプル
- [AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)

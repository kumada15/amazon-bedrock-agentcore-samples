# 💡 Amazon Bedrock AgentCore ユースケース

Amazon Bedrock AgentCore サンプルリポジトリのユースケースセクションへようこそ！

このフォルダには、Amazon Bedrock AgentCore の機能を実際のビジネス問題解決に適用する方法を示すエンドツーエンドのアプリケーションが含まれています。各ユースケースは、詳細な説明とデプロイメント手順を備えた完全な実装を提供します。

## 🎯 注目のユースケース

* **[AWS Operations Agent](./AWS-operations-agent/)**：Okta 認証と包括的なモニタリング機能を備えたインテリジェントな AWS 運用アシスタント
* **[Customer Support Assistant](./customer-support-assistant/)**：メモリ、ナレッジベース統合、Google OAuth を備えた本番対応のカスタマーサービスエージェント
* **[DB Performance Analyzer](./DB-performance-analyzer/)**：PostgreSQL 統合を備えたデータベースパフォーマンスモニタリングおよび分析エージェント
* **[Device Management Agent](./device-management-agent/)**：Cognito 認証とリアルタイムモニタリングを備えた IoT デバイス管理システム
* **[Enterprise Web Intelligence Agent](./enterprise-web-intelligence-agent/)**：競合インテリジェンスのためのブラウザツールを使用した Web リサーチおよび分析エージェント
* **[Farm Management Advisor](./farm-management-advisor/)**：植物検出、天気予報、ケア推奨を備えた農業アドバイザリーシステム
* **[Finance Personal Assistant](./finance-personal-assistant/)**：マルチエージェントワークフローとガードレールを備えたパーソナル予算管理
* **[Healthcare Appointment Agent](./healthcare-appointment-agent/)**：患者データ統合を備えた FHIR 準拠のヘルスケア予約スケジューリング
* **[Local Prototype to AgentCore](./local-prototype-to-agentcore/)**：ローカル開発から本番 AgentCore デプロイメントへの移行ガイド
* **[Market Trends Agent](./market-trends-agent/)**：ブラウザツールとメモリ統合を備えた金融市場分析
* **[SRE Agent](./SRE-agent/)**：マルチエージェント LangGraph ワークフローを備えたサイト信頼性エンジニアリングアシスタント
* **[Text to Python IDE](./text-to-python-ide/)**：AgentCore Code Interpreter を使用したコード生成および実行環境
* **[Video Games Sales Assistant](./video-games-sales-assistant/)**：Amplify フロントエンドと CDK デプロイメントを備えたデータ分析アシスタント

## 🏗️ アーキテクチャパターン

これらのユースケースは、さまざまなアーキテクチャパターンを示しています：

- **シングルエージェント**：特定のタスクに焦点を当てたソリューション
- **マルチエージェント**：異なるフレームワークを使用したコラボレーティブエージェントワークフロー
- **フルスタック**：フロントエンド、バックエンド、デプロイメントを備えた完全なアプリケーション
- **統合**：外部システムおよび API との接続
- **認証**：さまざまな ID プロバイダー（Cognito、Okta、Google、EntraID）

## 🚀 はじめに

各ユースケースには以下が含まれます：
- 完全なソースコードと設定
- ステップバイステップのデプロイメント手順
- アーキテクチャ図と説明
- テストおよび検証スクリプト
- クリーンアップ手順

要件に合ったユースケースを選択し、個別の README に従ってセットアップ手順を実行してください。

## 🔗 関連リソース

- [チュートリアル](../01-tutorials/) - AgentCore の基礎を学ぶ
- [統合](../03-integrations/) - フレームワークおよびプロトコル統合
- [AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/)

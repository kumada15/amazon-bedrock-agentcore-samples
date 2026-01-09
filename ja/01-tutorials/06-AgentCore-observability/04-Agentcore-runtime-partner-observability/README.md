# サードパーティオブザーバビリティ統合

このセクションでは、Amazon Bedrock AgentCore Runtime でホストされたエージェントをサードパーティのオブザーバビリティプラットフォームと統合する方法を示します。AgentCore Runtime のメリットを維持しながら、専門的なモニタリングツールを活用する方法を学びます。

## 利用可能な統合

publish フォルダには以下が含まれています：
- 様々なオブザーバビリティソリューションを使用した AgentCore Runtime を示す Jupyter ノートブック
- 必要な依存関係をリストした requirements.txt ファイル

## はじめに

1. オブザーバビリティプラットフォームを選択
2. 各プラットフォームでアカウントを作成
3. API キーと設定詳細を取得
4. 要件をインストール：`pip install -r requirements.txt`
5. ノートブックで環境変数を設定
6. エージェントを AgentCore Runtime にデプロイ
7. ノートブックを実行して統合オブザーバビリティを確認

## フレームワークサポート

Amazon Bedrock AgentCore は任意のエージェントフレームワークとモデルをサポートします：
- CrewAI
- LangGraph
- LlamaIndex
- Strands Agents

### Strands Agents
[Strands](https://strandsagents.com/latest/) はビルトインのテレメトリサポートを提供し、サードパーティ統合のデモンストレーションに最適です。

## 設定要件

各プラットフォームには特定の設定が必要です：

### Arize
- Arize ダッシュボードからの API キーと Space ID
- プロジェクト設定

### Braintrust
- Braintrust ダッシュボードからの API キー
- プロジェクト設定

### Instana
- Instana キー
- プロジェクト設定

### Langfuse
- パブリックキーとシークレットキー
- プロジェクト設定

## クリーンアップ

サンプル完了後：
1. AgentCore Runtime デプロイメントを削除
2. ECR リポジトリを削除
3. プラットフォーム固有のリソースをクリーンアップ
4. 不要になった場合は API キーを取り消し

## 追加リソース

- [Arize ドキュメント](https://arize.com/docs/ax)
- [Braintrust ドキュメント](https://www.braintrust.dev/docs)
- [Instana ドキュメント](https://www.ibm.com/docs/en/instana-observability/1.0.308?topic=overview)
- [Langfuse ドキュメント](https://langfuse.com/docs)
- [AgentCore Runtime ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/userguide/runtime.html)

# Amazon Bedrock AgentCore エージェント向けサードパーティオブザーバビリティ

このリポジトリには、Arize、Braintrust、Instana、Langfuse などのサードパーティオブザーバビリティツールを使用した Amazon Bedrock AgentCore Runtime でホストされたエージェントの使用例が含まれています。これらのサンプルでは、エージェントパフォーマンスのモニタリング、LLM インタラクションのトレース、ワークフローのデバッグのための OpenTelemetry 統合を示しています。

# Bedrock AgentCore Runtime エージェント向け Amazon CloudWatch での AgentCore オブザーバビリティ

このリポジトリには、Amazon OpenTelemetry Python Instrumentation と Amazon CloudWatch を使用した、Amazon Bedrock AgentCore Runtime でホストされた Strands Agent の AgentCore オブザーバビリティを紹介するサンプルが含まれています。オブザーバビリティは、統合された運用ダッシュボードを通じて、開発者が本番環境でエージェントのパフォーマンスをトレース、デバッグ、モニタリングするのを支援します。OpenTelemetry 互換のテレメトリとエージェントワークフローの各ステップの詳細な可視化をサポートし、Amazon CloudWatch GenAI Observability により、開発者がエージェントの動作を容易に把握し、大規模に品質標準を維持できるようにします。


## はじめに

プロジェクトフォルダには以下が含まれています：
- AgentCore Runtime と CloudWatch でのオブザーバビリティを示す Jupyter ノートブック
- 必要な依存関係をリストした requirements.txt ファイル
- 必要な環境変数を示す .env.example ファイル


## 使用方法

1. 探索したいフレームワークのディレクトリに移動
2. 要件をインストール: `!pip install -r requirements.txt`
3. AWS 認証情報を設定
4. .env.example ファイルを .env にコピーして変数を更新
5. Jupyter ノートブックを開いて実行


### Strands Agents
[Strands](https://strandsagents.com/latest/) は、モデル駆動のエージェント開発に焦点を当て、複雑なワークフローを持つ LLM アプリケーションを構築するためのフレームワークを提供します。

## クリーンアップ

サンプル完了後：

1. AgentCore Runtime デプロイメントを削除
2. 作成された ECR リポジトリをクリーンアップ

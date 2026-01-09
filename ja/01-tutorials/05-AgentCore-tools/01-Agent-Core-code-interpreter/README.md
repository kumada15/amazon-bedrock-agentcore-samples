# Amazon Bedrock AgentCore コードインタープリター

## 概要
Amazon Bedrock AgentCore コードインタープリターは、AI エージェントがコードを直接記述・実行してエンドツーエンドのタスクを完了できる、セキュアでサーバーレスな環境です。複雑なデータ分析、シミュレーションの実行、可視化の生成、プログラミングタスクの自動化を実現します。

## 仕組み

コード実行サンドボックスは、コードインタープリター、シェル、ファイルシステムを備えた隔離環境を作成することで、ユーザークエリを安全に処理できます。大規模言語モデルがツール選択を支援した後、このセッション内でコードが実行され、ユーザーまたはエージェントに返されて統合されます。

![アーキテクチャ](../01-Agent-Core-code-interpreter/images/code-interpreter.png)

## 主な機能

### 環境内のセッション

実行間でセッションを永続化する機能

### VPC サポートとインターネットアクセス

VPC 接続と外部インターネットアクセスを含むエンタープライズグレードの機能を提供

### 複数のビルド済み環境ランタイム

Python、NodeJS、TypeScript を含む複数のビルド済みランタイム（近日公開予定：カスタムライブラリを備えたカスタムランタイムコード実行エンジンのサポート）

### 統合

Amazon Bedrock AgentCore コードインタープリターは、統合 SDK を通じて他の Amazon Bedrock AgentCore 機能と統合できます：

- Amazon Bedrock AgentCore Runtime
- Amazon Bedrock AgentCore Identity
- Amazon Bedrock AgentCore Memory
- Amazon Bedrock AgentCore Observability

この統合により、開発プロセスを簡素化し、強力なコード実行機能を備えた AI エージェントの構築、デプロイ、管理のための包括的なプラットフォームを提供することを目指しています。

### ユースケース

Amazon Bedrock AgentCore コードインタープリターは、以下を含む幅広いアプリケーションに適しています：

- コード実行とレビュー
- データ分析と可視化

## チュートリアル概要

これらのチュートリアルでは、以下の機能をカバーします：

- [Amazon Bedrock AgentCore コードインタープリターを使用したファイル操作](01-file-operations-using-code-interpreter)
- [Amazon Bedrock AgentCore コードインタープリターを使用したエージェントによるコード実行](02-code-execution-with-agent-using-code-interpreter)
- [Amazon Bedrock AgentCore コードインタープリターを使用した AI エージェントによる高度なデータ分析](03-advanced-data-analysis-with-agent-using-code-interpreter)
- [Amazon Bedrock AgentCore コードインタープリターを使用したコマンド実行](04-run-commands-using-code-interpreter)

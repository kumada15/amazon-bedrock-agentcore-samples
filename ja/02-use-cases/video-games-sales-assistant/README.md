# Amazon Bedrock AgentCore を使用した対話型データアナリストアシスタントソリューションのデプロイ

> [!IMPORTANT]
> **すぐにデプロイ可能なエージェント Web アプリケーション**: このリファレンスソリューションを使用して、さまざまな業界にわたる他のエージェント駆動型 Web アプリケーションを構築できます。特定の業界ワークフロー向けのカスタムツールを追加してエージェント機能を拡張し、さまざまなビジネスドメインに適応させてください。

このソリューションは、ユーザーが自然言語インターフェースを通じてデータと対話できる生成 AI アプリケーションリファレンスを提供します。このソリューションは、カスタムエージェントアプリケーションをデプロイ、実行、スケーリングできるマネージドサービスである **[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** と **[Strands Agents SDK](https://strandsagents.com/)** を活用して、PostgreSQL データベースに接続し、Web アプリケーションインターフェースを通じてデータ分析機能を提供するエージェントを構築します。

<div align="center">
<img src="./images/data-analyst-assistant-agentcore-strands-agents-sdk.gif" alt="Conversational Data Analyst Assistant Solution with Amazon Bedrock AgentCore">
</div>

データアナリストアシスタントは、複雑な SQL クエリではなく自然言語での会話を通じて企業が構造化データと対話できるデータ分析へのアプローチを提供します。この種のアシスタントは、データ分析の会話に対する直感的な質疑応答を提供し、ユーザーエクスペリエンスを向上させるデータ可視化を提供することで改善できます。

このソリューションにより、ユーザーは以下が可能になります：

- ビデオゲームの売上データについて自然言語で質問
- PostgreSQL データベースへの SQL クエリに基づく AI 生成の回答を受信
- クエリ結果を表形式で表示
- 自動生成された可視化を通じてデータを探索
- AI アシスタントからインサイトと分析を取得

このリファレンスソリューションは、以下のようなユースケースの探索に役立ちます：

- リアルタイムのビジネスインテリジェンスでアナリストを強化
- 一般的なビジネス質問に対する C レベル幹部への迅速な回答を提供
- データ収益化（消費者行動、オーディエンスセグメンテーション）による新しい収益源の開拓
- パフォーマンスインサイトによるインフラストラクチャの最適化

## ソリューション概要

以下のアーキテクチャ図は、Strands Agents SDK を使用して構築され、Amazon Bedrock を活用した生成 AI データアナリストアシスタントのリファレンスソリューションを示しています。このアシスタントにより、ユーザーは質疑応答インターフェースを通じて PostgreSQL データベースに保存された構造化データにアクセスできます。

![Video Games Sales Assistant](./images/gen-ai-assistant-diagram.png)

> [!IMPORTANT]
> このサンプルアプリケーションはデモ目的であり、本番環境には対応していません。組織のセキュリティベストプラクティスでコードを検証してください。

### AgentCore Runtime と Memory インフラストラクチャ

**Amazon Bedrock AgentCore** は、組み込みのランタイムとメモリ機能を備えたカスタムエージェントアプリケーションをデプロイ、実行、スケーリングできるフルマネージドサービスです。

- **[Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)**: エージェントインスタンス用の呼び出しエンドポイント（`/invocations`）とヘルスモニタリング（`/ping`）を備えたマネージド実行環境を提供
- **[Amazon Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)**: AI エージェントがイベントをキャプチャし、メモリに変換し、必要に応じて関連するコンテキストを取得することで、対話を通じて記憶、学習、進化する能力を与えるフルマネージドサービス

AgentCore インフラストラクチャはすべてのストレージの複雑さを処理し、開発者が基盤となるインフラストラクチャを管理することなく効率的な取得を提供し、エージェント対話間の継続性と追跡可能性を確保します。

### CDK インフラストラクチャデプロイメント

AWS CDK スタックは以下のマネージドサービスをデプロイおよび設定します：

- **IAM AgentCore 実行ロール**: Amazon Bedrock AgentCore 実行に必要な権限を提供
- **VPC とプライベートサブネット**: データベースリソースのネットワーク分離とセキュリティ
- **Amazon Aurora Serverless PostgreSQL**: RDS Data API 統合でビデオゲームの売上データを保存
- **Amazon DynamoDB**: データ分析の監査証跡用に生のクエリ結果を保存
- **Parameter Store 設定管理**: アプリケーション設定を安全に管理

### フロントエンドアプリケーションの Amplify デプロイメント

- **React Web アプリケーション**: アシスタントのユーザーインターフェースを提供
    - ユーザー認証と権限管理に Amazon Cognito を使用
    - アプリケーションはアシスタントとの対話のために Amazon Bedrock AgentCore を呼び出し
    - チャート生成のため、アプリケーションは Claude 3.7 Sonnet モデルを直接呼び出し

### Strands Agent の機能

| 機能 | 説明 |
|----------|----------|
| ネイティブツール   | current_time - ユーザーのタイムゾーンに基づいて現在の日時情報を提供する組み込み Strands ツール。 |
| カスタムツール | get_tables_information - エージェントがデータベーススキーマを理解するのに役立つ、テーブルの構造、カラム、リレーションシップを含むデータベーステーブルに関するメタデータを取得するカスタムツール。<br>execute_sql_query - ユーザーの自然言語の質問に基づいて PostgreSQL データベースに対して SQL クエリを実行し、分析用に要求されたデータを取得するカスタムツール。 |
| モデルプロバイダー | Amazon Bedrock |

> [!NOTE]
> React Web アプリケーションは、ユーザー認証と権限管理に Amazon Cognito を使用し、認証されたユーザーロールを通じて Amazon Bedrock AgentCore と Amazon DynamoDB サービスへの安全なアクセスを提供します。

> [!TIP]
> エージェントの指示とツール実装を適応させることで、好みのデータベースエンジンに接続するようにデータソースを変更することもできます。

> [!IMPORTANT]
> **[Strands Agents SDK](https://strandsagents.com/latest/user-guide/safety-security/guardrails/)** が提供するシームレスな統合により、AI アプリケーションに **[Amazon Bedrock Guardrails](https://aws.amazon.com/bedrock/guardrails/)** を実装して AI の安全性とコンプライアンスを強化してください。

**ユーザー対話ワークフロー**は以下のように動作します：

- Web アプリケーションがユーザーのビジネス質問を AgentCore Invoke に送信
- Strands Agent（Claude 3.7 Sonnet を使用）が自然言語を処理し、データベースクエリを実行するタイミングを決定
- エージェントの組み込みツールが Aurora PostgreSQL データベースに対して SQL クエリを実行し、質問への回答を作成
- AgentCore Memory がセッション対話をキャプチャし、コンテキストのために以前の会話を取得
- エージェントの応答が Web アプリケーションに受信された後、生のデータクエリ結果が DynamoDB テーブルから取得され、回答と対応するレコードの両方を表示
- チャート生成のため、アプリケーションはモデル（Claude 3.7 Sonnet を使用）を呼び出してエージェントの回答と生のデータクエリ結果を分析し、適切なチャート可視化をレンダリングするために必要なデータを生成

## デプロイメント手順

デプロイメントは2つの主要なステップで構成されます：

1. **バックエンドデプロイメント - [CDK でのデータソースと設定管理デプロイメント](./cdk-agentcore-strands-data-analyst-assistant/)**
1. **エージェントデプロイメント - [AgentCore での Strands Agent インフラストラクチャデプロイメント](./agentcore-strands-data-analyst-assistant/)**
2. **フロントエンド実装 - [すぐに使えるデータアナリストアシスタントアプリケーションとの AgentCore 統合](./amplify-video-games-sales-assistant-agentcore-strands/)**

> [!NOTE]
> *アプリケーションのデプロイには Oregon（us-west-2）または N. Virginia（us-east-1）リージョンの使用を推奨します。*

> [!IMPORTANT]
> 提供されているクリーンアップ手順に従って、テスト後に不要なコストを避けるためにリソースをクリーンアップしてください。

## アプリケーション機能

以下の画像は、自然言語の回答、SQL クエリを生成するために LLM が使用した推論プロセス、それらのクエリから取得されたデータベースレコード、結果のチャート可視化を含む対話型エクスペリエンス分析を紹介しています。

![Video Games Sales Assistant](./images/preview.png)

- **ユーザーの質問に応答するエージェントとの対話型インターフェース**

![Video Games Sales Assistant](./images/preview1.png)

- **表形式で表示される生のクエリ結果**

![Video Games Sales Assistant](./images/preview2.png)

- **エージェントの回答とデータクエリ結果から生成されたチャート可視化（[Apexcharts](https://apexcharts.com/) を使用して作成）**

![Video Games Sales Assistant](./images/preview3.png)

- **データ分析会話から導出されたサマリーと結論**

![Video Games Sales Assistant](./images/preview4.png)

## ありがとうございます

## ライセンス

このプロジェクトは Apache-2.0 ライセンスの下でライセンスされています。

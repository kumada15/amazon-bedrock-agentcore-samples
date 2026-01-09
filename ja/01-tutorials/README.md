# 📚 Amazon Bedrock AgentCore チュートリアル

Amazon Bedrock AgentCore サンプルリポジトリのチュートリアルセクションへようこそ！

このフォルダには、ハンズオン形式のサンプルを通じて Amazon Bedrock AgentCore の基本的な機能を学ぶためのインタラクティブなノートブックベースのチュートリアルが含まれています。

チュートリアルは Amazon Bedrock AgentCore のコンポーネントごとに整理されています：

* **Runtime**：Amazon Bedrock AgentCore Runtime は、フレームワーク、プロトコル、モデルの選択に関係なく、AIエージェントとツールの両方をデプロイしてスケールできる、安全でサーバーレスなランタイム機能です。迅速なプロトタイピング、シームレスなスケーリング、市場投入までの時間短縮を可能にします。
* **Gateway**：AIエージェントは、データベースの検索からメッセージの送信まで、現実世界のタスクを実行するためのツールを必要とします。Amazon Bedrock AgentCore Gateway は、API、Lambda関数、既存のサービスを自動的にMCP互換ツールに変換し、開発者が統合を管理することなく、これらの重要な機能をエージェントに迅速に利用可能にします。
* **Memory**：Amazon Bedrock AgentCore Memory により、開発者はフルマネージドなメモリインフラストラクチャと、ニーズに合わせてメモリをカスタマイズする機能を使用して、豊かでパーソナライズされたエージェント体験を簡単に構築できます。
* **Identity**：Amazon Bedrock AgentCore Identity は、AWSサービスとSlackやZoomなどのサードパーティアプリケーション全体でシームレスなエージェントIDとアクセス管理を提供し、Okta、Entra、Amazon Cognitoなどの標準的なIDプロバイダーをサポートします。
* **Tools**：Amazon Bedrock AgentCore は、エージェント型AIアプリケーション開発を簡素化する2つの組み込みツールを提供します。Amazon Bedrock AgentCore **Code Interpreter** ツールは、AIエージェントがコードを安全に記述・実行できるようにし、精度を向上させ、複雑なエンドツーエンドのタスクを解決する能力を拡大します。Amazon Bedrock AgentCore **Browser Tool** は、AIエージェントがウェブサイトをナビゲートし、複数ステップのフォームを完了し、複雑なウェブベースのタスクを人間のような精度で実行できるエンタープライズグレードの機能で、完全に管理された安全なサンドボックス環境内で低レイテンシで動作します。
* **Observability**：Observability は、統合された運用ダッシュボードを通じて、開発者がエージェントのパフォーマンスをトレース、デバッグ、モニタリングするのを支援します。OpenTelemetry 互換のテレメトリとエージェントワークフローの各ステップの詳細な可視化をサポートし、Amazon Bedrock AgentCore Observability により、開発者がエージェントの動作を容易に把握し、品質基準を大規模に維持できるようにします。


さらに、これらのコンポーネントを実践的なシナリオで組み合わせる方法を示す**エンドツーエンド**のサンプルも提供しています。

## Amazon Bedrock AgentCore

Amazon Bedrock AgentCore サービスは、独立して使用することも、組み合わせて本番環境対応のエージェントを作成することもできます。Strands Agents、LangChain、LangGraph、CrewAI などのあらゆるエージェントフレームワーク、および Amazon Bedrock で利用可能かどうかに関わらず、あらゆるモデルで動作します。

![Amazon Bedrock AgentCore 概要](images/agentcore_overview.png)

これらのチュートリアルでは、各サービスを個別に、または組み合わせて使用する方法を学びます。

## 🎯 対象者

これらのチュートリアルは以下のような方に最適です：

 - Amazon Bedrock AgentCore を始めたい方
 - 高度なアプリケーションを構築する前にコア概念を理解したい方
 - Amazon Bedrock AgentCore を使用したAIエージェント開発の基盤を固めたい方

# Amazon Bedrock AgentCore ブラウザツール

## 概要

Amazon Bedrock AgentCore ブラウザツールは、AI エージェントが人間と同じように Web サイトと安全にやり取りできる、完全マネージド型の方法を提供します。開発者がカスタム自動化スクリプトを作成・維持することなく、エージェントが Web ページのナビゲーション、フォームの入力、複雑なタスクの完了を行えるようにします。

## 仕組み

ブラウザツールサンドボックスは、AI エージェントが Web ブラウザと安全にやり取りできるセキュアな実行環境です。ユーザーがリクエストを行うと、大規模言語モデル（LLM）が適切なツールを選択してコマンドを変換します。これらのコマンドは、ヘッドレスブラウザとホストライブラリサーバー（Playwright などのツールを使用）を含む制御されたサンドボックス環境内で実行されます。サンドボックスは、Web インタラクションを制限された空間内に含め、不正なシステムアクセスを防止することで、隔離とセキュリティを提供します。エージェントはスクリーンショットを通じてフィードバックを受け取り、システムセキュリティを維持しながら自動化タスクを実行できます。このセットアップにより、AI エージェントの安全な Web 自動化が可能になります。

![アーキテクチャ](images/browser-tool.png)

## 主な機能

### セキュアでマネージドな Web インタラクション

AI エージェントが人間と同じように Web サイトと安全にやり取りできる完全マネージド型の方法を提供し、カスタム自動化スクリプトなしでナビゲーション、フォーム入力、複雑なタスク完了を可能にします。

### エンタープライズセキュリティ機能

ユーザーセッションとブラウザセッションの 1:1 マッピングによる VM レベルの分離を提供し、エンタープライズグレードのセキュリティを実現します。各ブラウザセッションは、エンタープライズセキュリティ要件を満たすために分離されたサンドボックス環境で実行されます。

### モデル非依存の統合

様々な AI モデルとフレームワークをサポートしながら、interact()、parse()、discover() などのツールを通じてブラウザアクションの自然言語抽象化を提供し、特にエンタープライズ環境に適しています。このツールは任意のライブラリからブラウザコマンドを実行でき、Playwright や Puppeteer などの様々な自動化フレームワークをサポートします。

### 統合

Amazon Bedrock AgentCore ブラウザツールは、統合 SDK を通じて他の Amazon Bedrock AgentCore 機能と統合できます：

- Amazon Bedrock AgentCore Runtime
- Amazon Bedrock AgentCore Identity
- Amazon Bedrock AgentCore Memory
- Amazon Bedrock AgentCore Observability

この統合により、開発プロセスを簡素化し、ブラウザベースのタスクを実行する強力な機能を備えた AI エージェントの構築、デプロイ、管理のための包括的なプラットフォームを提供することを目指しています。

### ユースケース

Amazon Bedrock AgentCore ブラウザツールは、以下を含む幅広いアプリケーションに適しています：

- Web ナビゲーションとインタラクション
- フォーム入力を含むワークフロー自動化

## チュートリアル概要

これらのチュートリアルでは、様々なフレームワークと構成における AgentCore ブラウザツールの機能を示します：

### はじめに

**Browser Use の例**
- [Bedrock AgentCore ブラウザツールと Browser Use のはじめに](02-browser-with-browserUse/getting_started-agentcore-browser-tool-with-browser-use.ipynb)
- [Amazon Bedrock AgentCore ブラウザツール ライブビューと Browser Use](02-browser-with-browserUse/agentcore-browser-tool-live-view-with-browser-use.ipynb)

**Nova Act の例**
- [Bedrock AgentCore ブラウザツールと Nova Act のはじめに](01-browser-with-NovaAct/01_getting_started-agentcore-browser-tool-with-nova-act.ipynb)
- [Amazon Bedrock AgentCore ブラウザツール ライブビューと Nova Act](01-browser-with-NovaAct/02_agentcore-browser-tool-live-view-with-nova-act.ipynb)

**Strands の例**
- [Bedrock AgentCore ブラウザツールと Strands のはじめに](04-browser-with-Strands/01_getting_started-agentcore-browser-tool-with-strands.ipynb)

### 高度な機能

**オブザーバビリティ**
- [Amazon Bedrock AgentCore ブラウザツール オブザーバビリティ](03-browser-observability/01_browser_observability.ipynb)

**ライブビュー**
- [Amazon Bedrock AgentCore ブラウザツール DCV ライブビュー](05-browser-live-view/01-embed-dcv-live-view-tutorial.ipynb)

**Web Bot 認証**
- [Amazon Bedrock AgentCore ブラウザツール Web Bot 認証](06-Web-Bot-Auth-Signing/01_agentcore-browser-tool-with-web-bot-auth.ipynb)

### VPC 統合

**VPC 設定**
- [プライベート VPC からパブリックブラウザへの接続](07-connecting-public-browser-from-private-vpc/01-connecting-public-browser-from-private-vpc-runtime.ipynb)
- [VPC から VPC ベースのブラウザとのやり取り](08-Interacting-with-vpc-based-browser-from-vpc/01-Interacting-with-vpc-based-browser-from-vpc.ipynb)

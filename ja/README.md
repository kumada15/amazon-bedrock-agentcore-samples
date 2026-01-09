<div align="center">
  <div>
    <a href="https://aws.amazon.com/bedrock/agentcore/">
      <img width="150" height="150" alt="image" src="https://github.com/user-attachments/assets/b8b9456d-c9e2-45e1-ac5b-760f21f1ac18" />
   </a>
  </div>

  <h1>
      Amazon Bedrock AgentCore サンプル集
  </h1>

  <h2>
    あらゆるフレームワークとモデルを使用して、AIエージェントを安全かつスケーラブルにデプロイ・運用
  </h2>

  <div align="center">
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/graphs/commit-activity"><img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/awslabs/amazon-bedrock-agentcore-samples"/></a>
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues"><img alt="GitHub open issues" src="https://img.shields.io/github/issues/awslabs/amazon-bedrock-agentcore-samples"/></a>
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/pulls"><img alt="GitHub open pull requests" src="https://img.shields.io/github/issues-pr/awslabs/amazon-bedrock-agentcore-samples"/></a>
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/awslabs/amazon-bedrock-agentcore-samples"/></a>
  </div>

  <p>
    <a href="https://docs.aws.amazon.com/bedrock-agentcore/">ドキュメント</a>
    ◆ <a href="https://github.com/aws/bedrock-agentcore-sdk-python">Python SDK</a>
    ◆ <a href="https://github.com/aws/bedrock-agentcore-starter-toolkit">スターターツールキット</a>
    ◆ <a href="https://discord.gg/bedrockagentcore-preview">Discord</a>
  </p>
</div>

> **注意**: このリポジトリは [awslabs/amazon-bedrock-agentcore-samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples) の非公式日本語翻訳版です。

Amazon Bedrock AgentCore サンプルリポジトリへようこそ！

Amazon Bedrock AgentCore は、フレームワークにもモデルにも依存しない設計となっており、高度なAIエージェントを安全かつスケーラブルにデプロイ・運用する柔軟性を提供します。[Strands Agents](https://strandsagents.com/latest/)、[CrewAI](https://www.crewai.com/)、[LangGraph](https://www.langchain.com/langgraph)、[LlamaIndex](https://www.llamaindex.ai/)、その他どのフレームワークで構築していても、また任意の大規模言語モデル（LLM）で実行していても、Amazon Bedrock AgentCore がインフラストラクチャをサポートします。専用のエージェントインフラストラクチャの構築・管理という差別化に繋がらない重労働を排除し、お好みのフレームワークとモデルを持ち込み、コードを書き直すことなくデプロイできます。

このコレクションは、Amazon Bedrock AgentCore の機能を理解し、実装し、アプリケーションに統合するためのサンプルとチュートリアルを提供します。

## 🎥 動画

Amazon Bedrock AgentCore で初めての本番環境対応AIエージェントを構築しましょう。プロトタイピングを超えて、Amazon Bedrock AgentCore を使用して初めてのエージェント型AIアプリケーションを本番環境に導入する方法をご紹介します。

<p align="center">
  <a href="https://www.youtube.com/watch?v=wzIQDPFQx30"><img src="https://markdown-videos-api.jorgenkh.no/youtube/wzIQDPFQx30?width=640&height=360&filetype=jpeg" /></a>
</p>

## 📁 リポジトリ構成

### 📚 [`01-tutorials/`](./01-tutorials/)
**インタラクティブな学習と基礎**

このフォルダには、ハンズオン形式のサンプルを通じてAmazon Bedrock AgentCore の機能の基礎を学ぶノートブックベースのチュートリアルが含まれています。

構成はAgentCore コンポーネントごとに分かれています：
* **[Runtime](./01-tutorials/01-AgentCore-runtime)**：Amazon Bedrock AgentCore Runtime は、フレームワーク、プロトコル、モデルの選択に関係なく、AIエージェントとツールの両方をデプロイしてスケールできる、安全でサーバーレスなランタイム機能です。迅速なプロトタイピング、シームレスなスケーリング、市場投入までの時間短縮を可能にします。
* **[Gateway](./01-tutorials/02-AgentCore-gateway)**：AIエージェントは、データベースの検索からメッセージの送信まで、現実世界のタスクを実行するためのツールを必要とします。Amazon Bedrock AgentCore Gateway は、API、Lambda関数、既存のサービスを自動的にMCP互換ツールに変換し、開発者が統合を管理することなく、これらの重要な機能をエージェントに迅速に利用可能にします。
* **[Memory](./01-tutorials/04-AgentCore-memory)**：Amazon Bedrock AgentCore Memory により、開発者はフルマネージドなメモリインフラストラクチャと、ニーズに合わせてメモリをカスタマイズする機能を使用して、豊かでパーソナライズされたエージェント体験を簡単に構築できます。
* **[Identity](./01-tutorials/03-AgentCore-identity)**：Amazon Bedrock AgentCore Identity は、AWSサービスとSlackやZoomなどのサードパーティアプリケーション全体でシームレスなエージェントIDとアクセス管理を提供し、Okta、Entra、Amazon Cognitoなどの標準的なIDプロバイダーをサポートします。
* **[Tools](./01-tutorials/05-AgentCore-tools)**：Amazon Bedrock AgentCore は、エージェント型AIアプリケーション開発を簡素化する2つの組み込みツールを提供します。Amazon Bedrock AgentCore **Code Interpreter** ツールは、AIエージェントがコードを安全に記述・実行できるようにし、精度を向上させ、複雑なエンドツーエンドのタスクを解決する能力を拡大します。Amazon Bedrock AgentCore **Browser Tool** は、AIエージェントがウェブサイトをナビゲートし、複数ステップのフォームを完了し、複雑なウェブベースのタスクを人間のような精度で実行できるエンタープライズグレードの機能で、完全に管理された安全なサンドボックス環境内で低レイテンシで動作します。
* **[Observability](./01-tutorials/06-AgentCore-observability)**：Amazon Bedrock AgentCore Observability は、統合された運用ダッシュボードを通じて、開発者がエージェントのパフォーマンスをトレース、デバッグ、モニタリングするのを支援します。OpenTelemetry 互換のテレメトリとエージェントワークフローの各ステップの詳細な可視化をサポートし、開発者がエージェントの動作を容易に把握し、品質基準を大規模に維持できるようにします。

* **[AgentCore エンドツーエンド](./01-tutorials/07-AgentCore-E2E)**：このチュートリアルでは、Amazon Bedrock AgentCore サービスを使用して、カスタマーサポートエージェントをプロトタイプから本番環境に移行します。


提供されているサンプルは、AIエージェントアプリケーションを構築する前に基礎概念を理解したい初心者や方々に最適です。

### 💡 [`02-use-cases/`](./02-use-cases/)
**エンドツーエンドアプリケーション**

実際のビジネス課題を解決するためにAmazon Bedrock AgentCore 機能を適用する方法を示す、実践的なユースケース実装をご覧ください。

各ユースケースには、AgentCore コンポーネントに焦点を当てた完全な実装と詳細な説明が含まれています。

### 🔌 [`03-integrations/`](./03-integrations/)
**フレームワークとプロトコルの統合**

Strands Agents、LangChain、CrewAI などの人気のあるエージェントフレームワークと Amazon Bedrock AgentCore 機能を統合する方法を学びます。

A2Aによるエージェント間通信と様々なマルチエージェントコラボレーションパターンを設定できます。エージェントインターフェースを統合し、様々なエントリーポイントで Amazon Bedrock AgentCore を使用する方法を学びます。

### 🏗️ [`04-infrastructure-as-code/`](./04-infrastructure-as-code/)
**デプロイ自動化とインフラストラクチャ**

Infrastructure as Code として Amazon Bedrock AgentCore リソースをデプロイします。CloudFormation、AWS CDK、または Terraform を使用したサンプルを提供しています。

基本的なランタイム、MCPサーバー、マルチエージェントシステム、ツールとメモリを備えた完全なエージェントソリューション向けの本番環境対応テンプレートでインフラストラクチャのプロビジョニングを自動化します。

### 🚀 [`05-blueprints/`](./05-blueprints/)
**フルスタックリファレンスアプリケーション**

Amazon Bedrock AgentCore 上に構築された、完全でデプロイ可能なエージェントアプリケーションで開発をジャンプスタートしましょう。

各ブループリントは、統合されたサービス、認証、ビジネスロジックを備えた包括的な基盤を提供し、ユースケースに合わせてカスタマイズしてデプロイできます。

## ノートブックの実行方法

1. 仮想環境を作成してアクティベート
```bash
python -m venv .venv
source .venv/bin/activate
```

2. 依存関係をインストール
```bash
pip install -r requirements.txt
```

3. ノートブックを実行するために必要なAWS認証情報をエクスポート/アクティベート

4. 仮想環境をJupyterノートブックで使用するカーネルとして登録
```bash
python -m ipykernel install --user --name=notebook-venv --display-name="Python (notebook-venv)"
```

カーネルの一覧は以下で確認できます：
```bash
jupyter kernelspec list
```

5. ノートブックを実行し、正しいカーネルが選択されていることを確認
```bash
jupyter notebook path/to/your/notebook.ipynb
```

**重要:** Jupyterでノートブックを開いた後、`Kernel` → `Change kernel` → "Python (notebook-venv)" を選択して、仮想環境のパッケージが利用可能であることを確認してください。


## クイックスタート - [Amazon Bedrock AgentCore Runtime](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/runtime/quickstart.md)

### ステップ 1: 前提条件

- 認証情報が設定された [AWSアカウント](https://signin.aws.amazon.com/signin?redirect_uri=https%3A%2F%2Fportal.aws.amazon.com%2Fbilling%2Fsignup%2Fresume&client_id=signup)（`aws configure`）
- [Python 3.10](https://www.python.org/downloads/) 以降
- [Docker](https://www.docker.com/) または [Finch](https://runfinch.com/) がインストールされ実行中 - ローカル開発用のみ
- モデルアクセス: [Amazon Bedrock コンソール](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html)で Anthropic Claude 4.0 を有効化
- AWS権限:
    - `BedrockAgentCoreFullAccess` マネージドポリシー
    - `AmazonBedrockFullAccess` マネージドポリシー
    - `呼び出し元の権限`: 詳細なポリシーは[こちら](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/runtime/permissions.md#developercaller-permissions)を参照

### ステップ 2: インストールとエージェントの作成

```bash
# 両方のパッケージをインストール
pip install bedrock-agentcore strands-agents bedrock-agentcore-starter-toolkit
```

`my_agent.py` を作成:

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
def invoke(payload):
    """AIエージェント関数"""
    user_message = payload.get("prompt", "こんにちは！何かお手伝いできることはありますか？")
    result = agent(user_message)
    return {"result": result.message}

if __name__ == "__main__":
    app.run()
```
`requirements.txt` を作成:

```bash
cat > requirements.txt << EOF
bedrock-agentcore
strands-agents
EOF
```
### ステップ 3: ローカルでテスト

```bash
# エージェントを起動
python my_agent.py

# テスト（別のターミナルで）
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "こんにちは！"}'
```
成功: `{"result": "こんにちは！お手伝いします..."}` のようなレスポンスが表示されるはずです

### ステップ 4: AWSにデプロイ

```bash
# 設定してデプロイ（必要なリソースを自動作成）
agentcore configure -e my_agent.py
agentcore launch

# デプロイしたエージェントをテスト
agentcore invoke '{"prompt": "ジョークを教えて"}'
```

おめでとうございます！エージェントが Amazon Bedrock AgentCore Runtime で実行されるようになりました！

[Gateway](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/gateway/quickstart.md)、[Identity](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/identity/quickstart.md)、[Memory](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/memory/quickstart.md)、[Observability](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/observability/quickstart.md)、[組み込みツール](https://github.com/aws/bedrock-agentcore-starter-toolkit/tree/main/documentation/docs/user-guide/builtin-tools)のクイックスタートガイドもご覧ください。

## 🔗 関連リンク:

- [Amazon Bedrock AgentCore 入門 - ワークショップ](https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979/en-US)
- [Bedrock AgentCore ディープダイブ - ワークショップ](https://catalog.workshops.aws/agentcore-deep-dive/en-US)
- [Amazon Bedrock AgentCore 料金](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Amazon Bedrock AgentCore よくある質問](https://aws.amazon.com/bedrock/agentcore/faqs/)

## 🤝 コントリビューション

コントリビューションを歓迎します！以下の詳細については [コントリビューションガイドライン](../CONTRIBUTING.md) をご覧ください：

- 新しいサンプルの追加
- 既存サンプルの改善
- 問題の報告
- 機能強化の提案


## 📄 ライセンス

このプロジェクトは Apache License 2.0 の下でライセンスされています - 詳細は [LICENSE](../LICENSE) ファイルをご覧ください。


## コントリビューター

<a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=awslabs/amazon-bedrock-agentcore-samples" />
</a>

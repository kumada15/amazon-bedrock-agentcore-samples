# Amazon Bedrock AgentCore Gateway と Amazon Bedrock AgentCore Runtime の統合

[Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) は、既存の AWS Lambda 関数と API（OpenAPI および Smithy）をインフラやホスティングを管理することなく、フルマネージドの MCP サーバーに変換する方法を提供します。[Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html) は、AI エージェントやツールをデプロイおよび実行するための安全でサーバーレスの専用ホスティング環境を提供します。このチュートリアルでは、Amazon Bedrock AgentCore Gateway を AgentCore Runtime および [Strands agents](https://strandsagents.com/latest/) と統合します。

## チュートリアル詳細

| 情報                 | 詳細                                                      |
|:---------------------|:----------------------------------------------------------|
| チュートリアルタイプ  | インタラクティブ                                           |
| AgentCore コンポーネント | AgentCore Gateway、AgentCore Identity、AgentCore Runtime |
| エージェントフレームワーク | Strands Agents                                         |
| Gateway ターゲットタイプ | AWS Lambda、OpenAPI ターゲット                          |
| Inbound Auth IdP     | AWS IAM                                                   |
| Outbound Auth        | AWS IAM（AWS Lambda）、API キー（OpenAPI ターゲット）     |
| LLM モデル           | Anthropic Claude Haiku 4.5、Amazon Nova Pro               |
| チュートリアル構成    | AgentCore Gateway の作成と AgentCore Gateway の呼び出し    |
| チュートリアル分野    | クロスバーティカル                                         |
| 例の複雑さ           | 中級                                                       |
| 使用 SDK             | boto3                                                      |

## チュートリアルアーキテクチャ

このチュートリアルでは、AWS Lambda 関数と RESTful API で定義された操作を MCP ツールに変換し、Bedrock AgentCore Gateway でホストします。AWS Sigv4 形式の AWS IAM 認証情報を使用したイングレス認証をデモンストレーションします。AgentCore Gateway ツールを利用する Strands Agent を AgentCore Runtime にデプロイします。

デモンストレーション目的で、[Amazon Bedrock](https://aws.amazon.com/bedrock/) モデルを使用する Strands Agent を使用します。

![runtime gateway](./images/runtime_gateway.png)

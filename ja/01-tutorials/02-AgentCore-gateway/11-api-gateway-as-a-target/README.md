# API Gateway を AgentCore Gateway ターゲットとして統合

## 概要

組織がエージェントアプリケーションの可能性を探求する中、安全かつエンタープライズポリシーに沿った方法で大規模言語モデル（LLM）への呼び出しリクエストのコンテキストとしてエンタープライズデータを使用する際の課題に引き続き取り組んでいます。これらのインタラクションを標準化し保護するために、多くの組織はエージェントアプリケーションがデータソースやツールに安全に接続する方法を定義する Model Context Protocol（MCP）仕様を使用しています。

MCP は新しいユースケースに有利でしたが、組織は既存の API 資産をエージェント時代に持ち込む際の課題にも直面しています。MCP は確かに既存の API をラップできますが、MCP から RESTful API へのリクエストの変換、リクエストフロー全体を通じたセキュリティの維持、本番デプロイに必要な標準的なオブザーバビリティの適用など、追加の作業が必要です。

[Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) は、[Amazon API Gateway](https://aws.amazon.com/api-gateway/) をターゲットとしてサポートし、AgentCore Gateway（ACGW）への MCP リクエストを API Gateway（APIGW）への RESTful リクエストに変換するようになりました。組み込みのセキュリティとオブザーバビリティにより、APIGW からの新規および既存の API エンドポイントを MCP 経由でエージェントアプリケーションに公開できるようになりました。このノートブックでは、この新機能を取り上げ、実装方法を示します。

## 新機能

AgentCore Gateway はすでに複数のターゲットタイプ（Lambda 関数、OpenAPI スキーマ、Smithy モデル、MCP サーバーなど）をサポートしており、API Gateway もサポートするようになりました。


![](Images/agent-core-gateway-targets.png)


**お客様は API Gateway を使用して、多数のアプリケーションにわたるバックエンドを接続する広範な API エコシステムを構築することに成功しています。** 企業が次世代のエージェントアプリケーションに向けて進歩するにつれ、自然な進化として、これらの既存の API とバックエンドツールを AI 搭載システムに公開し、確立されたインフラストラクチャと最新のインテリジェントエージェント間のシームレスな統合を実現することです。

現在、お客様は APIGW API を OpenAPI 3 仕様としてエクスポートし、それを OpenAPI ターゲットとして ACGW に追加する手動ワークフローに従っています。この統合は、APIGW と ACGW 間の接続を自動化することでこのプロセスを合理化することを目的としています。


この統合により、お客様はこのエクスポート/インポートプロセスを自分で管理する必要がなくなります。ACGW に新しい API_GATEWAY ターゲットタイプが追加されます。REST API 所有者は、数回のコンソールクリックまたは単一の CLI コマンドで API を ACGW ターゲットとして追加でき、既存の REST API メソッドを ACGW 経由で MCP ツールとして公開できます。API コンシューマーは Model Context Protocol（MCP）を通じて AI エージェントをこれらの REST API に接続し、AI 統合でワークフローを強化できます。エージェントアプリケーションは新規または既存の APIGW API に接続できるようになりました。現在、ACGW と APIGW 間のこの統合は IAM 認可と API キー認可をサポートしています。

![](Images/agent-core-apigw-target.png)

### チュートリアル詳細


| 情報                  | 詳細                                                      |
|:---------------------|:----------------------------------------------------------|
| チュートリアルタイプ  | インタラクティブ                                           |
| AgentCore コンポーネント | AgentCore Gateway、AgentCore Identity                   |
| エージェントフレームワーク | Strands Agents                                        |
| Gateway ターゲットタイプ | API Gateway                                             |
| エージェント          | Strands                                                   |
| インバウンド認証 IdP  | Amazon Cognito、ただし他も使用可能                        |
| アウトバウンド認証    | IAM 認可と API キー                                       |
| LLM モデル            | Anthropic Claude Sonnet 4                                 |
| チュートリアルコンポーネント | AgentCore Gateway ターゲット経由での API Gateway 呼び出し |
| チュートリアル業種    | クロスバーティカル                                         |
| サンプルの複雑さ      | 簡単                                                      |
| 使用 SDK              | boto3                                                     |

## チュートリアルアーキテクチャ

このチュートリアルは、より広範なエンタープライズの課題の実践的な例として機能します：**次世代エージェントアプリケーション向けの集中型 Gateway アーキテクチャに API Gateway API を統合する方法。**
[ここからチュートリアルを開始](01-api-gateway-target.ipynb)してください。

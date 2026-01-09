# Dynatrace MCP Server と AgentCore Gateway の統合

## 概要
このチュートリアルでは、Dynatrace の MCP サーバーを Amazon Bedrock AgentCore Gateway と統合し、統一されたインターフェースを通じて可観測性機能への一元的なアクセスを提供する方法を示します。この統合により、カスタムクライアントコードの必要性がなくなり、複数のチーム間で可観測性ツールをスケーリングする際のエンタープライズの主要な課題に対応します。

![Architecture](images/dynatrace-mcp-server-target.png)

## チュートリアル詳細

| 情報                  | 詳細                                                      |
|:---------------------|:----------------------------------------------------------|
| チュートリアルタイプ  | インタラクティブ                                          |
| AgentCore コンポーネント | AgentCore Gateway、AgentCore Identity                  |
| エージェントフレームワーク | Strands Agents                                         |
| Gateway ターゲットタイプ | MCP サーバー                                            |
| エージェント          | Strands                                                   |
| インバウンド認証 IdP  | Amazon Cognito                                            |
| アウトバウンド認証    | OAuth2                                                    |
| LLM モデル            | Anthropic Claude Sonnet 4                                 |
| チュートリアルコンポーネント | AgentCore Gateway の作成と AgentCore Gateway の呼び出し |
| チュートリアル分野    | 可観測性                                                  |
| サンプルの複雑さ      | 簡単                                                      |
| 使用 SDK              | boto3                                                     |

## 主な機能

* Dynatrace MCP Server を AgentCore Gateway と統合
* Dynatrace 用の OAuth2 認証を設定
* Gateway を通じて可観測性ツールを検索および呼び出し
* Strands エージェントを使用して Dynatrace 機能と対話

## チュートリアル

- [Dynatrace MCP Server を AgentCore Gateway に統合](01-dynatrace-mcp-server-target.ipynb)

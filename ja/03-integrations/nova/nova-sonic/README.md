# Nova SonicとAgentCoreの統合

[Amazon Nova Sonicモデル](https://aws.amazon.com/ai/generative-ai/nova/speech/)は、双方向オーディオストリーミングを通じてリアルタイムの会話型インタラクションを提供し、自然で人間らしい会話体験を可能にします。エージェントワークフロー統合は、外部コンテキストを組み込むことでNova Sonicの機能を拡張します。

## AgentCoreとStrandsを使用したNova Sonicマルチエージェントアーキテクチャ

マルチエージェントアーキテクチャは、AIアシスタントを設計するために広く使用されているパターンです。Nova Sonicのような音声アシスタントでは、このアーキテクチャは複数の専門エージェントを調整して複雑なタスクを処理します。各エージェントは独立して動作でき、並列処理、モジュラー設計、スケーラブルなソリューションを可能にします。

この統合では、[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)に専門エージェントをデプロイする方法を示すサンプルとして、銀行音声アシスタントを使用します。Nova Sonicをオーケストレーターとして使用し、詳細な問い合わせを[AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)でホストされる[Strands Agents](https://strandsagents.com/latest/documentation/docs/)で記述されたサブエージェントに委任します。

![Nova Sonic Multi-Agent architecture](./images/nova-sonic-multi-agent-agentcore.png)

会話フローは挨拶とユーザー名の収集から始まり、その後、銀行または住宅ローンに関連する問い合わせを処理できます。専門ロジックを処理するために、AgentCoreでホストされる2つのサブエージェントを使用します：
- 銀行サブエージェント：口座残高確認、明細書、その他の銀行関連の問い合わせを処理します。
- 住宅ローンサブエージェント：借り換え、金利、返済オプションなど、住宅ローン関連の問い合わせを処理します。

> AgentCore Runtimeにデプロイされた住宅ローンエージェントと銀行エージェントは静的なレスポンスを返します。このサンプルは、アーキテクチャパターンとデプロイメントプロセスを紹介することを目的としています。実際のアプリケーションでは、これらのエージェントはAPI、データベース、RAG、その他のバックエンドサービスなどのソースからデータを取得します。

## 統合アーキテクチャ
Amazon Nova Sonicは、エージェントワークフローと統合するためにToolUseに依存しています。Nova Sonicのイベントライフサイクル中に、[PromptStart](https://docs.aws.amazon.com/nova/latest/userguide/input-events.html)イベントを通じてToolUse設定を提供できます。これは、Sonicが特定のタイプの入力を受信したときにトリガーされるように設計されています。

例えば、このAgentCoreサンプルでは、Sonic組み込み推論モデルが（インテント分類と同様に）問い合わせを銀行または住宅ローンサブエージェントにルーティングすべきと判断した場合にイベントをトリガーするようにToolUseを設定しました。

```
[
    {
        "toolSpec": {
            "name": "ac_bank_agent",
            "description": `Use this tool whenever the customer asks about their **bank account balance** or **bank statement**.
                    It should be triggered for queries such as:
                    - "What's my balance?"
                    - "How much money do I have in my account?"
                    - "Can I see my latest bank statement?"
                    - "Show me my account summary."`,
            "inputSchema": {
                "json": JSON.stringify({
                "type": "object",
                "properties": {
                    "accountId": {
                        "type": "string",
                        "description": "This is a user input. It is the bank account Id which is a numeric number."
                    },
                    "query": {
                        "type": "string",
                        "description": "The inquiry to the bank agent such as check account balance, get statement etc."
                    }
                },
                "required": [
                    "accountId", "query"
                ]
                })
            }
        }
    },
    {
        "toolSpec": {
            "name": "ac_mortgage_agent",
            "description": `Use this tool whenever the customer has a **mortgage-related inquiry**.
                            It should be triggered for queries such as:
                            - "What are the current mortgage rates?"
                            - "Can I refinance my mortgage?"
                            - "How do I apply for a mortgage?"
                            - "Tell me about mortgage repayment options.`,
            "inputSchema": {
                "json": JSON.stringify({
                "type": "object",
                    "properties": {
                        "accountId": {
                            "type": "string",
                            "description": "This is a user input. It is the bank account Id which is a numeric number."
                        },
                        "query": {
                            "type": "string",
                            "description": "The inquiry to the mortgage agent such as mortgage rates, refinance, bank reference letter, repayment etc."
                        }
                    },
                    "required": ["accountId", "query"]
                })
            }
        }
    }
]
```
Nova Sonicイベントをリッスンしているアプリケーションは、AgentCoreインスタンスを呼び出し、レスポンスを受信して、音声生成のためにNova Sonicに渡します。

## サンプルコードのデプロイ
サンプルコードと完全なデプロイメント手順については、[amazon-nova-sample](https://github.com/aws-samples/amazon-nova-samples/tree/main/speech-to-speech/workshops/agent-core)リポジトリを参照してください。

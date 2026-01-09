# AutoGen エージェントと Bedrock AgentCore の統合

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | 同期                                                                         |
| エージェントフレームワーク | Autogen                                                                 |
| LLM モデル          | Open AI GPT 4o                                                               |
| コンポーネント      | AgentCore Runtime                                                            |
| サンプルの複雑さ    | 簡単                                                                         |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK                                           |

このサンプルでは、AutoGen エージェントを AWS Bedrock AgentCore と統合し、ツール使用機能を持つ会話エージェントをマネージドサービスとしてデプロイする方法を示します。

## 前提条件

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock へのアクセス権を持つ AWS アカウント
- OpenAI API キー（モデルクライアント用）

## セットアップ手順

### 1. uv で Python 環境を作成

```bash
# uv がまだインストールされていない場合はインストール
pip install uv

# 仮想環境を作成してアクティベート
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
```

### 2. 依存関係のインストール

```bash
uv pip install -r requirements.txt
```

### 3. エージェントコードの理解

`autogen_agent_hello_world.py` ファイルには、天気ツール機能を持つ AutoGen エージェントが含まれており、Bedrock AgentCore と統合されています：

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
import logging

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("autogen_agent")

# モデルクライアントの初期化
model_client = OpenAIChatCompletionClient(
    model="gpt-4o",
)

# エージェントが使用できるシンプルな関数ツールを定義
async def get_weather(city: str) -> str:
    """指定された都市の天気を取得します。"""
    return f"The weather in {city} is 73 degrees and Sunny."

# モデルとツールを持つ AssistantAgent を定義
agent = AssistantAgent(
    name="weather_agent",
    model_client=model_client,
    tools=[get_weather],
    system_message="You are a helpful assistant.",
    reflect_on_tool_use=True,
    model_client_stream=True,  # ストリーミングトークンを有効化
)

# Bedrock AgentCore との統合
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def main(payload):
    # ユーザープロンプトを処理
    prompt = payload.get("prompt", "Hello! What can you help me with?")

    # エージェントを実行
    result = await Console(agent.run_stream(task=prompt))

    # JSON シリアライズ用にレスポンスコンテンツを抽出
    if result and hasattr(result, 'messages') and result.messages:
        last_message = result.messages[-1]
        if hasattr(last_message, 'content'):
            return {"result": last_message.content}

    return {"result": "No response generated"}

app.run()
```

### 4. Bedrock AgentCore Toolkit での設定とローンチ

```bash
# デプロイ用にエージェントを設定
agentcore configure -e

# OpenAI API キーを使用してエージェントをデプロイ
agentcore launch --env OPENAI_API_KEY=...
```


### 5. エージェントのテスト

ローカルでテストするためにローンチ：
`agentcore launch -l --env OPENAI_API_KEY=...`


```bash
agentcore invoke -l '{"prompt": "what is the weather in NYC?"}'
```

エージェントは以下を実行します：
1. クエリを処理
2. 適切な場合は天気ツールを使用
3. ツールの出力に基づいてレスポンスを提供

> 注意：クラウドでローンチおよび呼び出しを行うには -l を削除してください

## 動作の仕組み

このエージェントは AutoGen のエージェントフレームワークを使用して、以下が可能なアシスタントを作成します：

1. 自然言語クエリの処理
2. クエリに基づいてツールを使用するかどうかの判断
3. ツールの実行とその結果をレスポンスに統合
4. レスポンスのリアルタイムストリーミング

エージェントは Bedrock AgentCore フレームワークでラップされており、以下を処理します：
- AWS へのデプロイ
- スケーリングと管理
- リクエスト/レスポンスの処理
- 環境変数の管理

## その他のリソース

- [AutoGen ドキュメント](https://microsoft.github.io/autogen/)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)
- [OpenAI API ドキュメント](https://platform.openai.com/docs/api-reference)

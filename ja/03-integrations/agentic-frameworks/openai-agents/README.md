# OpenAI Agents と Bedrock AgentCore の統合

| 項目         | 詳細                                                                      |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ          | ハンドオフあり/なしの同期型                                                   |
| エージェントフレームワーク   | OpenAI Agents SDK                                                       |
| LLM モデル           | GPT-4o                                                              |
| コンポーネント          | AgentCore Runtime                                         |
| サンプルの複雑さ  | 中級                                                                       |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK、OpenAI Agents SDK                   |

この例では、OpenAI Agents を AWS Bedrock AgentCore と統合し、特殊なタスクのためのエージェントハンドオフを紹介する方法を示します。

## 前提条件

- Python 3.10 以上
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock へのアクセス権を持つ AWS アカウント
- OpenAI API キー

## セットアップ手順

### 1. uv で Python 環境を作成する

```bash
# まだインストールしていない場合は uv をインストール
pip install uv

# 仮想環境を作成してアクティベート
uv venv
source .venv/bin/activate  # Windows の場合: .venv\Scripts\activate
```

### 2. 必要なパッケージをインストール

```bash
uv pip install -r requirements.txt
```

## 例 1: Hello World エージェント

`openai_agents_hello_world.py` ファイルには、Web 検索機能と Bedrock AgentCore 統合を備えたシンプルな OpenAI エージェントが含まれています：

```python
from agents import Agent, Runner, WebSearchTool
import logging
import sys

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("openai_agents")

# Web 検索ツールを持つエージェントを初期化
agent = Agent(
    name="Assistant",
    tools=[WebSearchTool()],
)

async def main(query=None):
    if query is None:
        query = "Which coffee shop should I go to, taking into account my preferences and the weather today in SF?"

    logger.debug(f"Running agent with query: {query}")
    result = await Runner.run(agent, query)
    return result

# Bedrock AgentCore との統合
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_invocation(payload, context):
    query = payload.get("prompt", "How can I help you today?")
    result = await main(query)
    return {"result": result.final_output}

if __name__ == "__main__":
    app.run()
```

## 例 2: エージェントハンドオフ

`openai_agents_handoff_example.py` ファイルでは、相互にタスクをハンドオフできる専門的な役割を持つエージェントシステムの作成方法を示しています：

```python
# 異なるタスク用の専門エージェントを作成
travel_agent = Agent(
    name="Travel Expert",
    instructions=(
        "You are a travel expert who helps users plan their trips. "
        "Use web search to find up-to-date information about destinations, "
        "flights, accommodations, and travel requirements."
    ),
    tools=[WebSearchTool()]
)

food_agent = Agent(
    name="Food Expert",
    instructions=(
        "You are a food expert who helps users find great dining options. "
        "Use web search to find information about restaurants, local cuisine, "
        "food tours, and dietary accommodations."
    ),
    tools=[WebSearchTool()]
)

# 専門エージェントにハンドオフできるメインのトリアージエージェントを作成
triage_agent = Agent(
    name="Travel Assistant",
    instructions=(
        "You are a helpful travel assistant. "
        "If the user asks about travel planning, destinations, flights, or accommodations, "
        "hand off to the Travel Expert. "
        "If the user asks about food, restaurants, or dining options, "
        "hand off to the Food Expert."
    ),
    handoffs=[travel_agent, food_agent]
)
```

### ハンドオフの仕組み

1. トリアージエージェントが最初のユーザークエリを受け取ります
2. クエリの内容に基づいて、どの専門エージェントがリクエストを処理すべきかを判断します
3. 適切な専門エージェント（Travel Expert または Food Expert）が引き継ぎます
4. 専門エージェントはそのツール（Web 検索）を使用して情報を収集します
5. 最終的な応答がユーザーに返されます

このパターンにより以下が可能になります：
- 異なるドメインに対する専門的な知識と動作
- エージェント間の明確な責任分離
- ドメイン固有のクエリに対するより正確で関連性の高い応答

## Bedrock AgentCore での設定と起動

```bash
# デプロイ用にエージェントを設定
agentcore configure

# OpenAI API キーを使用してエージェントをデプロイ
agentcore deploy --app-file openai_agents_handoff_example.py -l --env OPENAI_API_KEY=your_api_key_here
```

## エージェントのテスト

```bash
agentcore invoke --prompt "I'm planning a trip to Japan next month. What should I know?"
```

システムは以下を行います：
1. トリアージエージェントを通じてクエリを処理
2. Travel Expert エージェントにハンドオフ
3. Web 検索を使用して日本旅行に関する情報を収集
4. 包括的な応答を返す

## その他のリソース

- [OpenAI Agents ドキュメント](https://platform.openai.com/docs/assistants/overview)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)

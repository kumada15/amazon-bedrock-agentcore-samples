# LangGraph エージェントと Bedrock AgentCore の統合

| 情報                | 詳細                                                                         |
|---------------------|------------------------------------------------------------------------------|
| エージェントタイプ  | 同期                                                                         |
| エージェントフレームワーク | Langgraph                                                               |
| LLM モデル          | Anthropic Claude 3 Haiku                                                     |
| コンポーネント      | AgentCore Runtime                                                            |
| サンプルの複雑さ    | 簡単                                                                         |
| 使用 SDK            | Amazon BedrockAgentCore Python SDK                                           |

このサンプルでは、LangGraph エージェントを AWS Bedrock AgentCore と統合し、Web 検索機能を持つエージェントをマネージドサービスとしてデプロイする方法を示します。

## 前提条件

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - 高速な Python パッケージインストーラーおよびリゾルバー
- Bedrock へのアクセス権を持つ AWS アカウント

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

`langgraph_agent_web_search.py` ファイルには、Web 検索機能を持つ LangGraph エージェントが含まれており、Bedrock AgentCore と統合されています：

```python
from typing import Annotated
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Bedrock で LLM を初期化
llm = init_chat_model(
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    model_provider="bedrock_converse",
)

# 検索ツールを定義
from langchain_community.tools import DuckDuckGoSearchRun
search = DuckDuckGoSearchRun()
tools = [search]
llm_with_tools = llm.bind_tools(tools)

# 状態を定義
class State(TypedDict):
    messages: Annotated[list, add_messages]

# グラフを構築
graph_builder = StateGraph(State)

def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile()

# Bedrock AgentCore との統合
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    tmp_msg = {"messages": [{"role": "user", "content": payload.get("prompt", "No prompt found in input")}]}
    tmp_output = graph.invoke(tmp_msg)
    return {"result": tmp_output['messages'][-1].content}

app.run()
```

### 4. Bedrock AgentCore Toolkit での設定とローンチ

```bash
# デプロイ用にエージェントを設定
agentcore configure

# エージェントをデプロイ
agentcore launch -e langgraph_agent_web_search.py
```

設定時に以下を指定するよう求められます：
- AWS リージョンの選択
- デプロイ名の選択
- その他のデプロイ設定

### 5. エージェントのテスト

デプロイ後、以下を使用してエージェントをテストできます：

```bash
agentcore invoke {"prompt":"What are the latest developments in quantum computing?"}
```

エージェントは以下を実行します：
1. クエリを処理
2. DuckDuckGo を使用して関連情報を検索
3. 検索結果に基づいた包括的な回答を提供

### 6. クリーンアップ

デプロイしたエージェントを削除するには：

```bash
agentcore destroy
```

## 動作の仕組み

このエージェントは LangGraph を使用してエージェント推論用の有向グラフを作成します：

1. ユーザークエリが chatbot ノードに送信される
2. chatbot がクエリに基づいてツールを使用するかどうかを判断
3. ツールが必要な場合、クエリが tools ノードに送信される
4. tools ノードが検索を実行して結果を返す
5. 結果が最終レスポンス生成のために chatbot に返される

Bedrock AgentCore フレームワークは、AWS でのエージェントのデプロイ、スケーリング、管理を処理します。

## その他のリソース

- [LangGraph ドキュメント](https://github.com/langchain-ai/langgraph)
- [LangChain ドキュメント](https://python.langchain.com/docs/get_started/introduction)
- [Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)

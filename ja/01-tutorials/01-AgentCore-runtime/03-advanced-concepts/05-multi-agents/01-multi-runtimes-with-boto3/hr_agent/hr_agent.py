from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import argparse
import json
import operator
import math

app = BedrockAgentCoreApp()

@tool
def get_vacation_info():
    """今年の残り有給休暇日数を取得する"""  # ダミー実装
    return "今年の残り有給休暇は12日です"

# 手動でLangGraphを構築してエージェントを定義
def create_agent():
    """LangGraph エージェントを作成して設定する"""
    from langchain_aws import ChatBedrock

    # LLMを初期化（モデルとパラメータは必要に応じて調整）
    llm = ChatBedrock(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",  # またはお好みのモデル
        model_kwargs={"temperature": 0.1}
    )

    # ツールをLLMにバインド
    tools = [get_vacation_info]
    llm_with_tools = llm.bind_tools(tools)

    # システムメッセージ
    system_message = f"""あなたは親切なHRサポートアシスタントです。休暇や福利厚生に関するユーザーの質問に回答できます。
    主な会社の福利厚生は以下の通りです：
    - 従業員の保険料100%、扶養家族75%をカバーする総合健康保険
    - 年間20日の有給休暇と5日の病気休暇を含む柔軟なPTOポリシー
    - 6%の会社マッチングと即時権利確定付きの401(k)プラン
    - ジムの会員権やフィットネス活動に使える月額100ドルのウェルネス手当

    追加のHR情報については、1-800-ASKHRに電話するようユーザーに案内してください"""

    # チャットボットノードを定義
    def chatbot(state: MessagesState):
        # システムメッセージがまだ存在しない場合は追加
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_message)] + messages

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # グラフを作成
    graph_builder = StateGraph(MessagesState)

    # ノードを追加
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))

    # エッジを追加
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")

    # エントリーポイントを設定
    graph_builder.set_entry_point("chatbot")

    # グラフをコンパイル
    return graph_builder.compile()

# エージェントを初期化
agent = create_agent()

@app.entrypoint
def langgraph_bedrock(payload):
    """ペイロードでエージェントを呼び出す"""
    user_input = payload.get("prompt")

    # LangGraphが期待する形式で入力を作成
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    # 最終メッセージの内容を抽出
    return response["messages"][-1].content

if __name__ == "__main__":
    app.run()

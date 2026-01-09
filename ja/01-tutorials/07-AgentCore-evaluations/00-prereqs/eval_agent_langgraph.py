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

# calculator ツールを作成
@tool
def calculator(expression: str) -> str:
    """
    Calculate the result of a mathematical expression.
    
    Args:
        expression: A mathematical expression as a string (e.g., "2 + 3 * 4", "sqrt(16)", "sin(pi/2)")
    
    Returns:
        The result of the calculation as a string
    """
    try:
        # 式で使用できる安全な関数を定義
        safe_dict = {
            "__builtins__": {},
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow,
            # 数学関数
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "exp": math.exp,
            "pi": math.pi, "e": math.e,
            "ceil": math.ceil, "floor": math.floor,
            "degrees": math.degrees, "radians": math.radians,
            # 基本演算子（明示的な使用用）
            "add": operator.add, "sub": operator.sub,
            "mul": operator.mul, "truediv": operator.truediv,
        }
        
        # 式を安全に評価
        result = eval(expression, safe_dict)
        return str(result)
        
    except ZeroDivisionError:
        return "Error: Division by zero"
    except ValueError as e:
        return f"Error: Invalid value - {str(e)}"
    except SyntaxError:
        return "Error: Invalid mathematical expression"
    except Exception as e:
        return f"Error: {str(e)}"

# カスタム weather ツールを作成
@tool
def weather():
    """天気を取得"""  # ダミー実装
    return "sunny"

# 手動の LangGraph 構成を使用してエージェントを定義
def create_agent():
    """LangGraph エージェントを作成して設定"""
    from langchain_aws import ChatBedrock
    
    # LLM を初期化（必要に応じてモデルとパラメータを調整）
    llm = ChatBedrock(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",  # または好みのモデル
        model_kwargs={"temperature": 0.1}
    )
    
    # ツールを LLM にバインド
    tools = [calculator, weather]
    llm_with_tools = llm.bind_tools(tools)
    
    # システムメッセージ
    system_message = "あなたは親切なアシスタントです。簡単な数学計算を行い、天気を教えることができます。"
    
    # chatbot ノードを定義
    def chatbot(state: MessagesState):
        # システムメッセージがまだない場合は追加
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
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    
    # LangGraph が期待する形式で入力を作成
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})
    
    # 最終メッセージの内容を抽出
    return response["messages"][-1].content

if __name__ == "__main__":
    app.run()
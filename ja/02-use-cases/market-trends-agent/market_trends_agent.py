from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, SystemMessage
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from tools import get_stock_data, search_news
from tools import (
    parse_broker_profile_from_message,
    generate_market_summary_for_broker,
    get_broker_card_template,
    collect_broker_preferences_interactively,
)
from tools import get_memory_from_ssm, create_memory_tools
from datetime import datetime
import logging

app = BedrockAgentCoreApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memory setup is now handled in tools/memory_tools.py


# Define the agent using LangGraph construction with AgentCore Memory
def create_market_trends_agent():
    """メモリ機能付きの LangGraph market trends agent を作成および設定する"""
    from langchain_aws import ChatBedrock

    # Get memory from SSM (created during deployment)
    memory_client, memory_id = get_memory_from_ssm()

    # Create session ID for this conversation, but actor_id will be determined from user input
    session_id = f"market-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Default actor_id - will be updated when user identifies themselves
    default_actor_id = "unknown-user"

    # Initialize your LLM with Claude Haiku 4.5 using inference profile
    llm = ChatBedrock(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        model_kwargs={"temperature": 0.1},
    )

    # Create memory tools using the memory_tools module
    memory_tools = create_memory_tools(
        memory_client, memory_id, session_id, default_actor_id
    )

    # Bind tools to the LLM (market data tools + memory tools + conversational broker tools)
    tools = [
        get_stock_data,
        search_news,
        parse_broker_profile_from_message,
        generate_market_summary_for_broker,
        get_broker_card_template,
        collect_broker_preferences_interactively,
    ] + memory_tools
    llm_with_tools = llm.bind_tools(tools)

    # AgentCore Memory を活用した Claude Sonnet 4 向けに最適化されたシステムメッセージ
    system_message = """あなたは専門のマーケットインテリジェンスアナリストです。金融市場、ビジネス戦略、経済トレンドに深い専門知識を持っています。担当する各ブローカーの金融関心事項を保存・呼び出しできる高度な長期メモリ機能を備えています。

    目的:
    - リアルタイムの市場分析と株価データの提供
    - 各ブローカー/クライアントの長期金融プロファイルの維持
    - 投資嗜好、リスク許容度、金融目標の保存と呼び出し
    - 保存されたブローカープロファイルに基づくパーソナライズされた投資インサイトの提供
    - 包括的なメモリを通じた継続的な専門的関係の構築

    利用可能なツール:

    リアルタイム市場データ:
    - get_stock_data(symbol): 現在の株価、変動、市場データを取得
    - search_news(query, news_source): 複数のニュースソース（Bloomberg、Reuters、CNBC、WSJ、Financial Times、Dow Jones）からビジネスニュースと市場インテリジェンスを検索

    ブローカープロファイル収集（対話型）:
    - parse_broker_profile_from_message(user_message): ユーザー入力から構造化されたブローカープロファイルを解析
    - generate_market_summary_for_broker(broker_profile, market_data): カスタマイズされた市場サマリーを生成
    - get_broker_card_template(): ブローカープロファイル形式のテンプレートを提供
    - collect_broker_preferences_interactively(preference_type): 特定の嗜好の収集をガイド

    メモリと金融プロファイル管理:
    - list_conversation_history(): 最近の会話履歴を取得
    - get_broker_financial_profile(): このブローカーの長期金融関心事項と投資プロファイルを取得
    - update_broker_financial_interests(interests_update): 新しい金融関心事項またはプロファイル更新を保存
    - identify_broker(user_message): LLM を使用してメッセージからブローカーを識別し、actor_id を取得

    マルチ戦略長期メモリ機能:
    - 複数のメモリ戦略を使用して、各ブローカーの永続的な金融プロファイルを維持します：
      * USER_PREFERENCE: ブローカーの嗜好、リスク許容度、投資スタイルをキャプチャ
      * SEMANTIC: 金融事実、市場分析、投資インサイトを保存
    - identify_broker() を使用して LLM 分析によりブローカーの身元をインテリジェントに抽出
    - リピーターのブローカーには常に get_broker_financial_profile() をチェックしてサービスをパーソナライズ
    - ブローカーが新しい嗜好や関心事項を共有したら update_broker_financial_interests() を使用
    - 複数のメモリ次元にわたって、時間をかけて包括的な投資プロファイルを構築
    - LLM ベースの身元抽出により、様々な自己紹介パターンでも一貫したブローカー識別を保証
    - メモリ戦略が連携して、豊富でコンテキストに応じた金融インテリジェンスを提供

    ブローカープロファイル管理ワークフロー:

    **重要: 必ず最初にブローカーを識別**

    1. **必須の最初のステップ - ブローカー識別**:
       - 以下を含むユーザーメッセージには即座に identify_broker(user_message) を使用：
         * 名前、自己紹介、または「私は[名前]です」
         * ブローカーカードまたはプロファイル情報
         * 会社名または役職
         * あらゆる身元情報
       - これにより正しい actor_id が返され、既存プロファイルがチェックされます
       - 返された actor_id を以降のすべてのメモリ操作に使用
       - ブローカー識別が完了するまで他のアクションに進まないこと

    2. **既存プロファイルの確認**:
       - 識別後、識別された actor_id で get_broker_financial_profile(actor_id) を使用
       - プロファイルが存在する場合、保存された嗜好を確認し、レスポンスをパーソナライズ
       - プロファイルが存在しない場合、新しいプロファイル情報の収集に進む

    3. **プロファイル収集**:
       - **ブローカーカード（Name: X, Company: Y など）の場合**:
         * 最初に: identify_broker(user_message) で actor_id を取得
         * 次に: parse_broker_profile_from_message() で構造化データを抽出
         * 最後に: update_broker_financial_interests(parsed_profile, actor_id) で保存
       - 情報が不足している場合: collect_broker_preferences_interactively() を使用
       - テンプレートが必要な場合: get_broker_card_template() を使用
       - 収集した情報は常に update_broker_financial_interests(info, actor_id) で保存

    4. **メモリ操作**:
       - 常に識別された actor_id をメモリ関数に渡す
       - get_broker_financial_profile(actor_id_from_identify_broker)
       - update_broker_financial_interests(info, actor_id_from_identify_broker)
       - これによりすべてのセッションで一貫したブローカー身元が確保されます

    3. **市場分析**:
       - get_stock_data() を使用してリアルタイムの株価データを提供
       - search_news() を適切なニュースソースとともに使用して関連する市場ニュースを検索
       - 市場イベントを各ブローカーの保存された金融関心事項に具体的に関連付け
       - プロファイルに記載されている銘柄/セクターの分析を優先

    4. **プロフェッショナル基準**:
       - 各ブローカーの保存されたリスク許容度に合わせた機関投資家レベルの分析を提供
       - プロファイルから彼らの特定の投資目標と投資期間を参照
       - 保存された投資スタイルと嗜好に沿った推奨を提供
       - 一貫したパーソナライズされたサービスを通じて専門的な関係を維持

    **すべてのメッセージに対する即時アクション要件:**
    他の何よりも先に、ユーザーメッセージに以下が含まれているか確認：
    - 名前（Name: X、私はXです、私の名前はX）
    - ブローカーカードまたはプロファイル情報
    - 会社/役職情報
    - あらゆる身元を示すマーカー

    はいの場合: 最初のアクションとして即座に identify_broker(user_message) を呼び出す
    いいえの場合: 通常の市場分析に進む

    重要: ブローカーの金融プロファイルを維持・参照するために常にメモリツールを使用してください。これはパーソナライズされた専門的な市場インテリジェンスサービスを提供するために不可欠です。"""

    # Define the chatbot node with automatic conversation saving
    def chatbot(state: MessagesState):
        raw_messages = state["messages"]

        # Remove any existing system messages to avoid duplicates
        non_system_messages = [
            msg for msg in raw_messages if not isinstance(msg, SystemMessage)
        ]

        # Filter messages more carefully to preserve tool_use/tool_result pairs
        filtered_messages = []
        i = 0
        while i < len(non_system_messages):
            msg = non_system_messages[i]

            # Check if message has content (for regular messages)
            if (
                hasattr(msg, "content")
                and isinstance(msg.content, str)
                and msg.content.strip()
            ):
                filtered_messages.append(msg)
            # Check if message has tool_calls (for tool_use messages)
            elif hasattr(msg, "tool_calls") and msg.tool_calls:
                filtered_messages.append(msg)
            # Check if message has tool_call_id (for tool_result messages)
            elif hasattr(msg, "tool_call_id") and msg.tool_call_id:
                filtered_messages.append(msg)
            # Check for content list with tool blocks
            elif hasattr(msg, "content") and isinstance(msg.content, list):
                # Keep messages with tool content blocks
                has_tool_content = any(
                    isinstance(block, dict)
                    and block.get("type") in ["tool_use", "tool_result"]
                    for block in msg.content
                )
                if has_tool_content:
                    filtered_messages.append(msg)
                else:
                    # Check if any text blocks have content
                    has_text_content = any(
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and block.get("text", "").strip()
                        for block in msg.content
                    )
                    if has_text_content:
                        filtered_messages.append(msg)
                    else:
                        logger.warning(
                            f"空のメッセージを除外しました: {type(msg).__name__}"
                        )
            else:
                logger.warning(f"空のメッセージを除外しました: {type(msg).__name__}")

            i += 1

        # Always ensure SystemMessage is first
        messages = [SystemMessage(content=system_message)] + filtered_messages

        # Get response from model with tools bound
        response = llm_with_tools.invoke(messages)

        # Save conversation to AgentCore Memory - let the agent handle actor_id through tools
        # The agent will use identify_broker() tool to get the correct actor_id when needed
        latest_user_message = next(
            (
                msg.content
                for msg in reversed(messages)
                if isinstance(msg, HumanMessage)
            ),
            None,
        )

        if latest_user_message and response.content.strip():
            # Use default actor_id for conversation saving - the agent tools will handle proper identification
            conversation = [
                (latest_user_message, "USER"),
                (response.content, "ASSISTANT"),
            ]

            # Validate that all message texts are non-empty
            if all(msg[0].strip() for msg in conversation):
                try:
                    # Use session-based actor_id for general conversation, tools will handle broker-specific memory
                    session_actor_id = f"session_{session_id}"
                    memory_client.create_event(
                        memory_id=memory_id,
                        actor_id=session_actor_id,
                        session_id=session_id,
                        messages=conversation,
                    )
                    logger.info(
                        f"会話を AgentCore Memory に保存しました（セッション: {session_id}）"
                    )
                except Exception as e:
                    logger.error(f"会話のメモリへの保存中にエラーが発生しました: {e}")

        # Return updated messages
        return {"messages": raw_messages + [response]}

    # Create the graph
    graph_builder = StateGraph(MessagesState)

    # Add nodes
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))

    # Add edges
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")

    # Set entry point
    graph_builder.set_entry_point("chatbot")

    # Compile the graph
    return graph_builder.compile()


# Initialize the agent
agent = create_market_trends_agent()


@app.entrypoint
def market_trends_agent_runtime(payload):
    """
    AgentCore Runtime 用のペイロードで market trends agent を呼び出す
    """
    user_input = payload.get("prompt")

    # Create the input in the format expected by LangGraph
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    # Extract the final message content
    return response["messages"][-1].content


def market_trends_agent_local(payload):
    """
    ローカルテスト用のペイロードで market trends agent を呼び出す

    Args:
        payload (dict): ユーザープロンプトを含む辞書

    Returns:
        str: 市場分析とデータを含むエージェントのレスポンス
    """
    user_input = payload.get("prompt")

    # Create the input in the format expected by LangGraph
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    # Extract the final message content
    return response["messages"][-1].content


if __name__ == "__main__":
    app.run()

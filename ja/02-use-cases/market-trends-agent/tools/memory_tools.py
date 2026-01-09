"""
Market Trends Agent 用 Memory Tools

このモジュールには、AgentCore Memory を使用してブローカープロファイル、
会話履歴、および財務関心事を管理するためのすべてのメモリ関連ツールが含まれています。
"""

from langchain_core.tools import tool
from bedrock_agentcore.memory import MemoryClient
import hashlib
import logging
import os
import re

# Configure logging
logger = logging.getLogger(__name__)


def cleanup_duplicate_memories():
    """重複するメモリインスタンスをクリーンアップし、最新の ACTIVE なもののみを保持する"""
    region = os.getenv("AWS_REGION", "us-east-1")
    client = MemoryClient(region_name=region)
    memory_name = "MarketTrendsAgentMultiStrategy"

    try:
        memories = client.list_memories()
        market_memories = [
            m for m in memories if m.get("id", "").startswith(memory_name + "-")
        ]

        if len(market_memories) <= 1:
            print(f"{len(market_memories)} 件のメモリインスタンスが見つかりました - クリーンアップ不要")
            return

        print(
            f"{len(market_memories)} 件のメモリインスタンスが見つかりました - 重複をクリーンアップ中..."
        )

        # Sort by creation time (if available) or just use the first active one
        active_memories = [m for m in market_memories if m.get("status") == "ACTIVE"]

        if active_memories:
            # Keep the first active one, delete the rest
            keep_memory = active_memories[0]
            delete_memories = active_memories[1:] + [
                m for m in market_memories if m.get("status") != "ACTIVE"
            ]

            print(f"メモリを保持: {keep_memory['id']}")

            # Save the kept memory ID to file
            with open(".memory_id", "w") as f:
                f.write(keep_memory["id"])

            for memory in delete_memories:
                try:
                    print(f"重複メモリを削除中: {memory['id']}")
                    client.delete_memory(memory["id"])
                except Exception as e:
                    print(f"メモリ {memory['id']} の削除中にエラー: {e}")

        print("メモリのクリーンアップが完了しました")

    except Exception as e:
        print(f"メモリクリーンアップ中にエラー: {e}")


def get_memory_from_ssm():
    """SSM Parameter Store から AgentCore Memory ARN を取得する"""
    import boto3

    region = os.getenv("AWS_REGION", "us-east-1")
    client = MemoryClient(region_name=region)
    ssm_client = boto3.client("ssm", region_name=region)

    # Get memory ARN from SSM Parameter Store
    param_name = "/bedrock-agentcore/market-trends-agent/memory-arn"
    try:
        response = ssm_client.get_parameter(Name=param_name)
        memory_arn = response["Parameter"]["Value"]

        # Extract memory ID from ARN (format: arn:aws:bedrock-agentcore:region:account:memory/memory-id)
        memory_id = memory_arn.split("/")[-1]

        logger.info(f"SSM からメモリを取得しました: {memory_id}")
        return client, memory_id

    except ssm_client.exceptions.ParameterNotFound:
        logger.error(
            "SSM Parameter Store にメモリ ARN が見つかりません。先にデプロイを実行してください。"
        )
        raise Exception(
            "Memory not deployed. Run 'AWS_PROFILE=burner python deploy.py' first."
        )
    except Exception as e:
        logger.error(f"SSM からのメモリ取得エラー: {e}")
        raise


def extract_actor_id(user_message: str) -> str:
    """broker card フォーマットまたはユーザーメッセージから actor_id を抽出する"""
    # Look for broker card format: "Name: [Name]"
    name_match = re.search(r"Name:\s*([^\n]+)", user_message, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip()
        if name and name.lower() != "unknown":
            # Clean name for actor_id
            clean_name = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())
            return f"broker_{clean_name}"

    # Look for "I'm [Name]" or "My name is [Name]" patterns
    intro_patterns = [
        r"I'?m\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
        r"My name is\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
        r"This is\s+([A-Z][a-zA-Z\s]+?)(?:\s+from|\s+at|\s*[,.]|$)",
    ]

    for pattern in intro_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name.split()) <= 3:  # Reasonable name length
                clean_name = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())
                return f"broker_{clean_name}"

    # Fallback: use message hash for anonymous users
    message_hash = hashlib.sha256(user_message.lower().encode()).hexdigest()[:8]
    return f"user_{message_hash}"


def get_namespaces(mem_client: MemoryClient, memory_id: str) -> dict:
    """メモリストラテジーの名前空間マッピングを取得する。"""
    try:
        strategies = mem_client.get_memory_strategies(memory_id)
        return {i["type"]: i["namespaces"][0] for i in strategies}
    except Exception as e:
        logger.error(f"名前空間の取得エラー: {e}")
        return {}


def create_memory_tools(
    memory_client: MemoryClient, memory_id: str, session_id: str, default_actor_id: str
):
    """提供されたメモリクライアントと設定でメモリツールを作成する"""

    @tool
    def list_conversation_history(actor_id_override: str = None):
        """メモリから最近の会話履歴とユーザー設定を取得する"""
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id

            events = memory_client.list_events(
                memory_id=memory_id,
                actor_id=current_actor_id,
                session_id=session_id,
                max_results=10,
            )

            if events:
                # Convert events to readable format
                history_parts = []
                for i, event in enumerate(events[-5:], 1):  # Show last 5 events
                    if "messages" in event:
                        for message in event["messages"]:
                            content = message.get("content", "").strip()
                            role = message.get("role", "unknown")
                            if content:
                                history_parts.append(
                                    f"{role.upper()}: {content[:100]}..."
                                )

                if history_parts:
                    return "Recent conversation history:\n" + "\n".join(history_parts)
                else:
                    return "No meaningful conversation history found"
            else:
                return "No conversation history available"

        except Exception as e:
            logger.error(f"会話履歴の取得エラー: {e}")
            return "No conversation history available"

    @tool
    def get_broker_financial_profile(actor_id_override: str = None):
        """複数のメモリストラテジーから長期的な財務関心事と投資プロファイルを取得する

        Args:
            actor_id_override: プロファイルを取得する特定の actor_id（identify_broker() から取得した actor_id を使用）
        """
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id

            if not actor_id_override:
                return "No actor_id provided. Please use identify_broker() first to get the correct actor_id, then call this function with that actor_id."

            # Get namespaces for all memory strategies
            namespaces_dict = get_namespaces(memory_client, memory_id)

            all_profile_info = []

            # Retrieve from all memory strategies
            for strategy_type, namespace_template in namespaces_dict.items():
                try:
                    namespace = namespace_template.format(actorId=current_actor_id)

                    memories = memory_client.retrieve_memories(
                        memory_id=memory_id,
                        namespace=namespace,
                        query="broker financial profile investment preferences risk tolerance",
                        top_k=3,
                    )

                    for memory in memories:
                        if isinstance(memory, dict):
                            content = memory.get("content", {})
                            if isinstance(content, dict):
                                text = content.get("text", "").strip()
                                if text and len(text) > 20:  # Meaningful content
                                    all_profile_info.append(
                                        f"[{strategy_type.upper()}] {text}"
                                    )

                except Exception as strategy_error:
                    logger.info(
                        f"{strategy_type} ストラテジーにメモリが見つかりません: {strategy_error}"
                    )

            if all_profile_info:
                return "Broker Financial Profile:\n" + "\n\n".join(all_profile_info)
            else:
                # Fallback: Get recent events to build profile from conversation history
                events = memory_client.list_events(
                    memory_id=memory_id,
                    actor_id=current_actor_id,
                    session_id=session_id,
                    max_results=10,
                )

                if events:
                    profile_elements = []
                    for event in events:
                        if "messages" in event:
                            for message in event["messages"]:
                                content = message.get("content", "")
                                # Look for profile-related information
                                if any(
                                    keyword in content.lower()
                                    for keyword in [
                                        "broker",
                                        "investment",
                                        "risk tolerance",
                                        "portfolio",
                                        "preference",
                                        "client",
                                    ]
                                ):
                                    if len(content) > 50:  # Meaningful content
                                        profile_elements.append(
                                            content[:200] + "..."
                                            if len(content) > 200
                                            else content
                                        )

                    if profile_elements:
                        return (
                            "Broker Profile (from conversation history):\n"
                            + "\n\n".join(profile_elements[-2:])
                        )
                    else:
                        return "Building financial profile from our conversations. Profile will be enhanced as we continue our discussions."
                else:
                    return "No financial profile found for this broker yet. This will be created as we learn about their investment preferences."

        except Exception as e:
            logger.error(f"ブローカー財務プロファイルの取得エラー: {e}")
            return "Unable to retrieve financial profile at this time"

    @tool
    def update_broker_financial_interests(
        interests_update: str, actor_id_override: str = None
    ):
        """ブローカーの財務関心事と投資設定を更新または追加する

        Args:
            interests_update: 保存する新しい財務関心事、設定、またはプロファイル更新
            actor_id_override: プロファイルを保存する特定の actor_id（identify_broker() から取得した actor_id を使用）
        """
        try:
            # Use provided actor_id or default
            current_actor_id = actor_id_override or default_actor_id

            if not actor_id_override:
                return "No actor_id provided. Please use identify_broker() first to get the correct actor_id, then call this function with that actor_id."

            # Create an event with proper roles for memory storage
            conversation = [
                (
                    f"Please update my financial profile with this information: {interests_update}",
                    "USER",
                ),
                (
                    "I've updated your financial profile with the new information. This will be included in your long-term investment profile for future reference.",
                    "ASSISTANT",
                ),
            ]

            memory_client.create_event(
                memory_id=memory_id,
                actor_id=current_actor_id,
                session_id=session_id,
                messages=conversation,
            )

            return (
                "Financial interests successfully updated in long-term memory profile"
            )

        except Exception as e:
            logger.error(f"財務関心の更新エラー: {e}")
            return "Unable to update financial interests at this time"

    @tool
    def identify_broker(user_message: str):
        """メッセージからブローカーを識別し、一貫した actor_id を返す

        Args:
            user_message: 識別情報を含むユーザーのメッセージ（broker card フォーマットまたは自己紹介）

        Returns:
            識別されたブローカーに関する情報と、他のメモリ関数で使用する actor_id
        """
        try:
            # Extract actor_id using simple parsing
            identified_actor_id = extract_actor_id(user_message)

            # Try to get existing profile for this broker across all sessions
            try:
                # Check all namespaces for existing profile data
                namespaces_dict = get_namespaces(memory_client, memory_id)
                found_existing_profile = False

                for strategy_type, namespace_template in namespaces_dict.items():
                    try:
                        namespace = namespace_template.format(
                            actorId=identified_actor_id
                        )
                        memories = memory_client.retrieve_memories(
                            memory_id=memory_id,
                            namespace=namespace,
                            query="broker profile investment preferences",
                            top_k=1,
                        )
                        if memories:
                            found_existing_profile = True
                            break
                    except Exception as memory_error:
                        logger.debug(
                            f"{strategy_type} にメモリが見つかりません: {memory_error}"
                        )
                        continue

                if found_existing_profile:
                    return f"ACTOR_ID: {identified_actor_id}\nSTATUS: Existing broker found\nACTION: Use get_broker_financial_profile('{identified_actor_id}') to retrieve their stored preferences."
                else:
                    return f"ACTOR_ID: {identified_actor_id}\nSTATUS: New broker\nACTION: Use update_broker_financial_interests(profile_info, '{identified_actor_id}') to store their preferences."

            except Exception as e:
                return f"ACTOR_ID: {identified_actor_id}\nSTATUS: Unable to check existing profile\nERROR: {e}\nACTION: Proceed as new broker and use update_broker_financial_interests(profile_info, '{identified_actor_id}')"

        except Exception as e:
            logger.error(f"ブローカー識別エラー: {e}")
            return f"ERROR: Unable to identify broker - {e}"

    return [
        list_conversation_history,
        get_broker_financial_profile,
        update_broker_financial_interests,
        identify_broker,
    ]

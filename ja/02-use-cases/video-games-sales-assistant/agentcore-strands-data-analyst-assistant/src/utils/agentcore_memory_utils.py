"""
AgentCore Memory ユーティリティ

このモジュールは、Bedrock Agent Core メモリシステムから会話メッセージを取得し
フォーマットするためのユーティリティ関数を提供します。
"""

import logging
from typing import List, Dict, Any
from bedrock_agentcore.memory import MemoryClient

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentcore-memory-utils")


def get_agentcore_memory_messages(
    memory_client: MemoryClient,
    memory_id: str,
    actor_id: str,
    session_id: str,
    last_k_turns: int = 20,
) -> List[Dict[str, Any]]:
    """
    AgentCore メモリから会話メッセージを取得しフォーマットする。

    この関数は、指定された数の会話ターンをメモリから取得し、
    role と content 構造を持つ標準的なメッセージフォーマットに整形します。

    Args:
        memory_client: Bedrock Agent Core メモリと対話するためのクライアント
        memory_id: メモリリソースの ID
        actor_id: ユーザー/アクターの ID
        session_id: 現在の会話セッションの ID
        last_k_turns: 履歴から取得する会話ターン数（デフォルト: 20）

    Returns:
        以下の形式でフォーマットされたメッセージのリスト:
        [
            {"role": "user", "content": [{"text": "こんにちは、Strands です！"}]},
            {"role": "assistant", "content": [{"text": "こんにちは！本日はどのようなお手伝いができますか？"}]}
        ]

    Raises:
        Exception: メモリからメッセージを取得する際にエラーが発生した場合
    """
    try:
        # メモリ取得開始の整形されたコンソール出力
        print("\n" + "=" * 70)
        print("🧠 AGENTCORE メモリ取得")
        print("=" * 70)
        print(f"📋 メモリ ID: {memory_id}")
        print(f"👤 アクター ID: {actor_id}")
        print(f"🔗 セッション ID: {session_id}")
        print(f"🔄 リクエストターン数: {last_k_turns}")
        print("-" * 70)

        # メモリから指定された数の会話ターンを読み込み
        print(f"⏳ メモリから {last_k_turns} 件の会話ターンを取得中...")

        recent_turns = memory_client.get_last_k_turns(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=last_k_turns,
        )

        formatted_messages = []

        if recent_turns:
            print(f"✅ {len(recent_turns)} 件の会話ターンを正常に取得しました")
            print("-" * 70)

            # 会話内の各ターンを処理
            for turn_idx, turn in enumerate(recent_turns, 1):
                print(f"📝 ターン {turn_idx} を処理中:")

                for msg_idx, message in enumerate(turn, 1):
                    # Extract role and content from the memory format
                    raw_role = message.get("role", "user")

                    # Normalize role to lowercase to match Bedrock Converse API requirements
                    role = raw_role.lower() if isinstance(raw_role, str) else "user"

                    if role not in ["user", "assistant"]:
                        print(f"⚠️  無効なロール '{role}' が見つかりました。'user' にデフォルト設定します")
                        role = "user"

                    # 異なるコンテンツ形式を処理
                    content_text = ""
                    if "content" in message:
                        if (
                            isinstance(message["content"], dict)
                            and "text" in message["content"]
                        ):
                            content_text = message["content"]["text"]
                        elif isinstance(message["content"], str):
                            content_text = message["content"]
                        elif isinstance(message["content"], list):
                            # コンテンツアイテムのリストを処理
                            for content_item in message["content"]:
                                if (
                                    isinstance(content_item, dict)
                                    and "text" in content_item
                                ):
                                    content_text = content_item["text"]
                                    break
                                elif isinstance(content_item, str):
                                    content_text = content_item
                                    break

                    # 空のコンテンツを持つメッセージをスキップ
                    if not content_text.strip():
                        print(f"⚠️  空のコンテンツを持つメッセージ {msg_idx} をスキップ")
                        continue

                    # 必要な構造でメッセージをフォーマット
                    formatted_message = {
                        "role": role,
                        "content": [{"text": content_text}],
                    }

                    formatted_messages.append(formatted_message)

                    # 処理された各メッセージの整形出力
                    role_icon = "🤖" if role == "assistant" else "👤"
                    content_preview = (
                        content_text[:100] + "..."
                        if len(content_text) > 100
                        else content_text
                    )
                    print(f"   {role_icon} {role.upper()}: {content_preview}")

            print("-" * 70)
            print(f"✨ {len(formatted_messages)} 件のメッセージを正常にフォーマットしました")
        else:
            print("📭 メモリに会話履歴が見つかりません")

        print("=" * 70 + "\n")
        # 逆順でメッセージを返す（最新のものが最初）
        return formatted_messages[::-1]

    except Exception as e:
        print("❌ エラー: AgentCore メモリからのメッセージ取得に失敗しました")
        print(f"💥 例外: {str(e)}")
        print("=" * 70 + "\n")
        logger.error(f"メモリからのメッセージ取得エラー: {e}")
        raise Exception(f"AgentCore メモリからのメッセージ取得に失敗しました: {str(e)}")

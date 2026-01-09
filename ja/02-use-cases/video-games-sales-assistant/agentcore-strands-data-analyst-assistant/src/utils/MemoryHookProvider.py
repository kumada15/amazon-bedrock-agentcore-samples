"""
Bedrock Agent Core 用メモリフックプロバイダー

このモジュールは、会話メモリを管理する Bedrock Agent Core 用のフックプロバイダーを提供します。
エージェント開始時に最近の会話履歴を読み込み、会話に新しいメッセージが追加されると
それを保存する処理を行います。

MemoryHookProvider クラスは Bedrock Agent Core メモリシステムと統合し、
セッション間で永続的な会話履歴を提供します。
"""

import logging

from strands.hooks.events import MessageAddedEvent
from strands.hooks.registry import HookProvider, HookRegistry
from bedrock_agentcore.memory import MemoryClient

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("personal-agent")


class MemoryHookProvider(HookProvider):
    """
    Bedrock Agent Core で会話メモリを管理するためのフックプロバイダー。

    このクラスは、エージェント初期化時に会話履歴を読み込み、
    会話にメッセージが追加されるとそれを保存するためのフックを提供します。

    Attributes:
        memory_client: Bedrock Agent Core メモリと対話するためのクライアント
        memory_id: メモリリソースの ID
        actor_id: ユーザー/アクターの ID
        session_id: 現在の会話セッションの ID
        last_k_turns: 履歴から取得する会話ターン数
    """

    def __init__(
        self,
        memory_client: MemoryClient,
        memory_id: str,
        actor_id: str,
        session_id: str,
        last_k_turns: int = 20,
    ):
        """
        メモリフックプロバイダーを初期化する。

        Args:
            memory_client: Bedrock Agent Core メモリと対話するためのクライアント
            memory_id: メモリリソースの ID
            actor_id: ユーザー/アクターの ID
            session_id: 現在の会話セッションの ID
            last_k_turns: 履歴から取得する会話ターン数（デフォルト: 20）
        """
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.actor_id = actor_id
        self.session_id = session_id
        self.last_k_turns = last_k_turns

    def on_message_added(self, event: MessageAddedEvent):
        """
        会話にメッセージが追加されるとメモリに保存する。

        このメソッドは、各新規メッセージを将来の参照のために
        Bedrock Agent Core メモリシステムに保存します。

        Args:
            event: メッセージ追加イベント
        """
        messages = event.agent.messages

        print("\n" + "=" * 70)
        print("💾 メモリフック - メッセージ追加イベント")
        print("=" * 70)
        print("📨 エージェントメッセージ:")
        print("-" * 70)

        # すべてのメッセージを整形して表示
        for idx, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown")
            role_icon = (
                "🤖" if role == "assistant" else "👤" if role == "user" else "❓"
            )
            print(f"  {idx}. {role_icon} {role.upper()}:")

            if "content" in msg and msg["content"]:
                for content_idx, content_item in enumerate(msg["content"], 1):
                    if "text" in content_item:
                        text_preview = (
                            content_item["text"][:150] + "..."
                            if len(content_item["text"]) > 150
                            else content_item["text"]
                        )
                        print(f"     📝 テキスト: {text_preview}")
                    elif "toolResult" in content_item:
                        print(
                            f"     🔧 ツール結果: {content_item['toolResult'].get('toolUseId', 'N/A')}"
                        )

        print("-" * 70)

        try:
            last_message = messages[-1]

            print("🔍 最新メッセージを処理中:")
            print(f"   📋 ロール: {last_message.get('role', 'unknown')}")
            print(f"   📊 コンテンツアイテム数: {len(last_message.get('content', []))}")

            # Check if the message has the expected structure
            if (
                "role" in last_message
                and "content" in last_message
                and last_message["content"]
            ):
                role = last_message["role"]

                # テキストコンテンツまたは特定の toolResult コンテンツを検索
                content_to_save = None

                print("   🔎 保存可能なコンテンツを検索中...")

                for content_idx, content_item in enumerate(last_message["content"], 1):
                    print(
                        f"      コンテンツアイテム {content_idx}: {list(content_item.keys())}"
                    )

                    # 通常のテキストコンテンツをチェック
                    if "text" in content_item:
                        content_to_save = content_item["text"]
                        print(
                            f"      ✅ テキストコンテンツを発見（長さ: {len(content_to_save)}）"
                        )
                        break

                    # get_tables_information の toolResult をチェック
                    elif "toolResult" in content_item:
                        tool_result = content_item["toolResult"]
                        if (
                            "content" in tool_result
                            and tool_result["content"]
                            and "text" in tool_result["content"][0]
                        ):
                            tool_text = tool_result["content"][0]["text"]
                            # 特定の toolUsed マーカーを含むかチェック
                            if "'toolUsed': 'get_tables_information'" in tool_text:
                                content_to_save = tool_text
                                print(
                                    f"      ✅ get_tables_information ツール結果を発見（長さ: {len(content_to_save)}）"
                                )
                                break
                            else:
                                print(
                                    "      ❌ ツール結果に get_tables_information マーカーが含まれていません"
                                )
                        else:
                            print(
                                "      ❌ ツール結果に期待されるコンテンツ構造がありません"
                            )

                if content_to_save:
                    print("\n" + "=" * 50)
                    print("💾 メモリに保存中")
                    print("=" * 50)
                    print(
                        f"📝 コンテンツプレビュー: {content_to_save[:200]}{'...' if len(content_to_save) > 200 else ''}"
                    )
                    print(f"👤 ロール: {role}")
                    print(f"🆔 メモリ ID: {self.memory_id}")
                    print(f"👤 アクター ID: {self.actor_id}")
                    print(f"🔗 セッション ID: {self.session_id}")
                    print("=" * 50)

                    self.memory_client.save_conversation(
                        memory_id=self.memory_id,
                        actor_id=self.actor_id,
                        session_id=self.session_id,
                        messages=[(content_to_save, role)],
                    )
                    print("✅ メモリに正常に保存されました")
                else:
                    print("❌ 保存可能なコンテンツが見つかりません")
                    print(
                        "   理由: テキストコンテンツまたは get_tables_information ツール結果が見つかりません"
                    )
            else:
                print("❌ 無効なメッセージ構造")
                print("   必須フィールドがありません: role、content、またはコンテンツが空です")

        except Exception as e:
            print(f"💥 メモリ保存エラー: {str(e)}")
            logger.error(f"メモリ保存エラー: {e}")

        print("=" * 70 + "\n")

    def register_hooks(self, registry: HookRegistry):
        """
        フックレジストリにメモリフックを登録する。

        Args:
            registry: 登録先のフックレジストリ
        """
        # メモリフックを登録
        registry.add_callback(MessageAddedEvent, self.on_message_added)

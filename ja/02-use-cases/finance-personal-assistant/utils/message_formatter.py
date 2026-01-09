"""
エージェントメッセージを読みやすい形式でフォーマット・表示するためのユーティリティ関数。
"""


def pretty_print_messages(messages, max_content_length=500, show_indices=True):
    """
    エージェントメッセージをフォーマットして見やすく出力します。

    Args:
        messages: agent.messages からのメッセージオブジェクトのリスト
        max_content_length: 表示するコンテンツの最大長（デフォルト: 500）
        show_indices: メッセージインデックスを表示するかどうか（デフォルト: True）
    """
    if not messages:
        print("会話履歴にメッセージがありません")
        return

    print(f"会話履歴 ({len(messages)} 件のメッセージ)")
    print("=" * 80)

    for i, message in enumerate(messages):
        role = message.get("role", "unknown").upper()
        content = message.get("content", [])

        # ロールにマーカーをフォーマット
        role_emoji = "[ユーザー]" if role == "USER" else "[アシスタント]" if role == "ASSISTANT" else "[システム]"

        if show_indices:
            print(f"\n{role_emoji} メッセージ {i+1} ({role}):")
        else:
            print(f"\n{role_emoji} {role}:")

        print("-" * 40)

        # コンテンツを処理（通常はコンテンツブロックのリスト）
        if isinstance(content, list):
            for j, content_block in enumerate(content):
                if isinstance(content_block, dict):
                    # テキストコンテンツブロックを処理
                    if "text" in content_block:
                        text = content_block["text"]

                        # 長いコンテンツを切り捨て
                        if len(text) > max_content_length:
                            text = (
                                text[:max_content_length] + "\n... [コンテンツが切り捨てられました]"
                            )

                        if len(content) > 1:
                            print(f"  コンテンツブロック {j+1}:")

                        # 適切なインデントでテキストをフォーマット
                        formatted_text = "\n".join(
                            ["  " + line for line in text.split("\n")]
                        )
                        print(formatted_text)

                    # その他のコンテンツタイプを処理（画像など）
                    elif "type" in content_block:
                        print(f"  コンテンツタイプ: {content_block['type']}")
                        if "source" in content_block:
                            print(
                                f"     ソース: {content_block.get('source', {}).get('type', 'unknown')}"
                            )
                else:
                    # シンプルな文字列コンテンツを処理
                    print(f"  {content_block}")
        else:
            # 直接の文字列コンテンツを処理
            text = str(content)
            if len(text) > max_content_length:
                text = text[:max_content_length] + "\n... [コンテンツが切り捨てられました]"
            formatted_text = "\n".join(["  " + line for line in text.split("\n")])
            print(formatted_text)

    print("\n" + "=" * 80)
    print(f"サマリー: 合計 {len(messages)} 件のメッセージ")

    # ロール別にメッセージをカウント
    role_counts = {}
    for message in messages:
        role = message.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    for role, count in role_counts.items():
        print(f"   - {role.capitalize()}: {count} 件のメッセージ")


def print_conversation_stats(messages):
    """
    会話に関する詳細な統計情報を出力します。

    Args:
        messages: agent.messages からのメッセージオブジェクトのリスト
    """
    if not messages:
        print("分析する会話データがありません")
        return

    print("会話統計")
    print("=" * 50)

    total_messages = len(messages)
    user_messages = sum(1 for msg in messages if msg.get("role") == "user")
    assistant_messages = sum(1 for msg in messages if msg.get("role") == "assistant")

    # コンテンツの長さを計算
    total_chars = 0
    content_blocks = 0

    for message in messages:
        content = message.get("content", [])
        if isinstance(content, list):
            content_blocks += len(content)
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total_chars += len(block["text"])
        else:
            total_chars += len(str(content))

    print(f"メッセージ数: {total_messages}")
    print(f"   - ユーザー: {user_messages}")
    print(f"   - アシスタント: {assistant_messages}")
    print(f"コンテンツブロック数: {content_blocks}")
    print(f"合計文字数: {total_chars:,}")
    print(
        f"メッセージあたりの平均文字数: {total_chars // total_messages if total_messages > 0 else 0}"
    )


def print_last_exchange(messages, num_pairs=1):
    """
    最後の N 件のメッセージペア（ユーザー + アシスタント）のみを出力します。

    Args:
        messages: agent.messages からのメッセージオブジェクトのリスト
        num_pairs: 表示するメッセージペアの数（デフォルト: 1）
    """
    if not messages:
        print("表示するメッセージがありません")
        return

    # 最後の N ペアを検索
    pairs_found = 0
    start_index = len(messages)

    # 後ろからメッセージペアを検索
    i = len(messages) - 1
    while i >= 0 and pairs_found < num_pairs:
        if (
            messages[i].get("role") == "assistant"
            and i > 0
            and messages[i - 1].get("role") == "user"
        ):
            pairs_found += 1
            if pairs_found == num_pairs:
                start_index = i - 1
        i -= 1

    recent_messages = messages[start_index:]

    print(f"最後の {pairs_found} 件のメッセージペア")
    pretty_print_messages(recent_messages, show_indices=False)

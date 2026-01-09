"""
ショッピングサブエージェント

ゲートウェイを介してショッピングツールに接続し、商品検索およびショッピング関連のクエリを処理するサブエージェント。
メインのスーパーバイザーエージェント用のツールとして公開されます。
"""

import os
import logging
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from gateway_client import get_gateway_client

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-east-1")

# =============================================================================
# ショッピングエージェントシステムプロンプト
# =============================================================================

SHOPPING_AGENT_PROMPT = """
あなたは、ユーザーが商品を見つけたり、旅行用のパッキングリストを作成したりするのを手伝うショッピングアシスタントです。
参考として、今日の日付は 2025年12月3日です。

主な責任は以下の通りです:
1. ユーザーのクエリに基づいて商品を検索する
2. 商品推奨付きのパッキングリストを生成する
3. ASIN（Amazon 標準識別番号）を含む商品情報を提供する
4. ユーザーが旅行に必要な適切な商品を見つけるのを手伝う

以下のツールにアクセスできます:
- `search_products_tool`: Serp API Amazon 検索で商品を検索
- `generate_packing_list_tool`: 商品推奨付きのパッキングリストを生成

重要なガイドライン:

1. ユーザーが商品やショッピングについて尋ねたら、適切なツールを使用する
2. 一般的な商品検索には search_products_tool を使用する
3. パッキングリスト生成には generate_packing_list_tool を使用する
4. 利用可能な場合は常に商品 ASIN を含めるが、生の ASIN ではなく、次のような Amazon 商品ページへのリンクとして表示する: https://www.amazon.com/dp/B08T1MQZRH/?th=1
5. 明確な商品説明と推奨を提供する
6. ユーザーのリクエストが不明確な場合は、明確化のための質問をする


リトライ戦略:
- 検索で結果がないか関連性のない結果が返された場合、クエリを精緻化してリトライする
- 商品検索では、より広いまたはより具体的な用語を試す
- ブランド名、サイズ、または機能を追加または削除してみる
- 結果が見つからないと報告する前に最大3回試行する

応答時の注意:
- 明確で役立つ対応をする
- 名前、説明、ASIN などの商品詳細を含める
- パッキングリストをカテゴリ別に整理する（衣類、電子機器、洗面用品など）
- ユーザーの旅行計画に基づいた文脈に適した推奨を提供する
- 読みやすい形式で回答をフォーマットする

目標は、ユーザーが旅行に必要な適切な商品を見つけるのを手伝うことです。
"""


# =============================================================================
# ショッピングツール用の Gateway クライアント
# =============================================================================


def get_shopping_tools_client() -> MCPClient:
    """
    ゲートウェイ経由でショッピングツールに接続された MCPClient を取得する。
    """
    return get_gateway_client("^shoppingtools___")


# =============================================================================
# Bedrock モデル
# =============================================================================

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    temperature=0.2,
)


# =============================================================================
# ショッピングサブエージェントツール
# =============================================================================


@tool
async def shopping_assistant(query: str, user_id: str = "", session_id: str = ""):
    """
    商品検索とショッピングクエリを処理する。

    利用可能なツール:
    - search_products_tool(user_id, question): クエリに一致する商品を Amazon で検索
    - generate_packing_list_tool(user_id, question): 商品推奨付きのパッキングリストを生成

    ここにルーティング:
    - 商品検索: 「トラベルバックパックを探して」「防水ジャケットを検索」
    - パッキングリスト: 「ビーチバケーションに何が必要?」「ヨーロッパ旅行用のパッキングリストを作成」
    - ショッピング推奨: 「ハイキング用にどんな商品を買うべき?」

    重要: 結果にはカートに追加するための ASIN と商品リンクが含まれます。
    初期結果が不十分な場合は、クエリを精緻化して検索をリトライします。

    Args:
        query: ショッピング/商品リクエスト。
        user_id: パーソナライゼーション用のユーザー識別子。
        session_id: コンテキスト用のセッション識別子。

    Returns:
        ASIN、価格、Amazon リンク付きの商品推奨。
    """
    try:
        logger.info(f"ショッピングサブエージェント (async) 処理中: {query[:100]}...")

        shopping_client = get_shopping_tools_client()

        agent = Agent(
            name="shopping_agent",
            model=bedrock_model,
            tools=[shopping_client],
            system_prompt=SHOPPING_AGENT_PROMPT,
            trace_attributes={
                "user.id": user_id,
                "session.id": session_id,
                "agent.type": "shopping_subagent",
            },
        )

        result = ""
        async for event in agent.stream_async(query):
            if "data" in event:
                yield {"data": event["data"]}
            if "current_tool_use" in event:
                yield {"current_tool_use": event["current_tool_use"]}
            if "result" in event:
                result = str(event["result"])

        yield {"result": result}

    except Exception as e:
        logger.error(f"ショッピングサブエージェントの非同期エラー: {e}", exc_info=True)
        yield {"error": str(e)}

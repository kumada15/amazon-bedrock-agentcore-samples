"""
トラベルサブエージェント

ゲートウェイを介してトラベルツールに接続し、旅行関連のクエリを処理するサブエージェント。
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
# トラベルエージェントシステムプロンプト
# =============================================================================

TRAVEL_AGENT_PROMPT = """
あなたは旅行の計画と準備をサポートするトラベルアシスタントです。
参考として、今日の日付は 2025年12月3日です。

主な責任は以下の通りです:
1. 目的地情報と旅程の推奨を提供する
2. フライトとホテルを検索する
3. レストランと観光スポットを検索する
4. インターネット検索を通じて最新の旅行情報を提供する

以下のツールにアクセスできます:
- `travel_search`: インターネットから最新情報を検索（天気を含む）
- `travel_flight_search`: フライトを検索（departure_id、arrival_id、outbound_date、オプションで return_date）
- `travel_hotel_search`: ホテルを検索（query、check_in_date、check_out_date）
- `travel_places_search`: Google Places 経由でレストラン、観光スポット、場所を検索

重要なガイドライン:

1. 現在のクエリに集中する - 関連する場合は会話履歴からコンテキストを維持する
2. 天気に関する質問には、travel_search を使用して現在の天気情報を検索する
3. フライト検索では、提供されていない場合は出発地、目的地、日付を尋ねる
4. ホテル検索では、提供されていない場合は都市、チェックイン/チェックアウト日を尋ねる
5. イベント/観光スポットの結果をタイプ別に分類する（文化、スポーツ、グルメなど）
6. イベントや観光スポットには日付、時間、場所を含める
7. 具体的で実行可能な推奨を提供する

旅程の要件（重要）:
- 複数日の旅程では、1日あたり少なくとも2〜3件のレストラン推奨を必ず含める
- すべての場所に基づくアイテム（ホテル、レストラン、アクティビティ、観光スポット）には必ず Google Maps リンクを含める
- Google Maps リンクの形式: https://www.google.com/maps/search/?api=1&query=PLACE_NAME,CITY
- レストランについては、travel_places_search を使用して住所付きの具体的なオプションを検索する
- "location" フィールドに Google Maps リンクを保存: "Address - https://www.google.com/maps/search/?api=1&query=..."
- ユーザーに表示する際は、リンクを Markdown 形式でフォーマット: [Address](https://www.google.com/maps/search/?api=1&query=...)

リトライ戦略:
- 検索で結果がないか関連性のない結果が返された場合、クエリを精緻化してリトライする
- 異なるクエリの表現を試す（例: 「東京のレストラン」vs「東京のおすすめグルメ」）
- 場所検索では、より広いまたはより具体的な用語を試す
- フライト/ホテルでは、空港コードと日付形式が正しいことを確認する
- 結果が見つからないと報告する前に最大3回試行する

応答時の注意:
- 明確で簡潔にする
- 価格、評価、場所などの関連詳細を含める
- インターネット検索結果を使用する場合は出典を引用する
- 必要に応じて明確化のための質問をする
- 読みやすい形式で回答をフォーマットする

目標は、ユーザーが成功した楽しい旅行を計画できるよう支援することです。
"""


# =============================================================================
# トラベルツール用の Gateway クライアント
# =============================================================================


def get_travel_tools_client() -> MCPClient:
    """トラベルツールのみにフィルタリングされた MCPClient を取得する"""
    return get_gateway_client("^traveltools___")


# =============================================================================
# Bedrock モデル
# =============================================================================

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    temperature=0.2,
)


# =============================================================================
# トラベルサブエージェントツール
# =============================================================================


@tool
async def travel_assistant(query: str, user_id: str = "", session_id: str = ""):
    """
    専門のトラベルツールを使用して旅行計画クエリを処理する。

    利用可能なツール:
    - travel_search: 旅行情報のインターネット検索（query）
    - travel_places_search: Google Places 経由でレストラン、観光スポットを検索（query）
    - travel_hotel_search: ホテルを検索（query、check_in_date YYYY-MM-DD、check_out_date YYYY-MM-DD）
    - travel_flight_search: フライトを検索（departure_id、arrival_id を空港コードで、outbound_date YYYY-MM-DD、オプションで return_date）

    ここにルーティング:
    - フライト検索: 「2025-12-20 にボストンからパリへのフライトを探して」
    - ホテル検索: 「2025-12-20 から 2025-12-25 までローマのホテル」
    - レストラン/観光スポット検索: 「東京の最高の寿司レストラン」
    - 一般的な旅行情報: 「バルセロナで何をすべき?」「日本への旅行のヒント」
    - 旅行計画: 「マドリードの3日間の旅程を計画して」

    重要: 利用可能な場合は、特定の日付（YYYY-MM-DD 形式）と空港コードを含める。
    フライトには3文字の空港コード（BOS、JFK、CDG、NRT など）を使用。

    Args:
        query: できるだけ詳細な旅行リクエスト。
        user_id: パーソナライゼーション用のユーザー識別子。
        session_id: コンテキスト用のセッション識別子。

    Returns:
        旅行情報、検索結果、または推奨事項。
        初期結果が不十分な場合は、クエリを精緻化して検索をリトライします。
    """
    try:
        logger.info(f"トラベルサブエージェント (async) 処理中: {query[:100]}...")

        travel_client = get_travel_tools_client()

        agent = Agent(
            name="travel_agent",
            model=bedrock_model,
            tools=[travel_client],
            system_prompt=TRAVEL_AGENT_PROMPT,
            trace_attributes={
                "user.id": user_id,
                "session.id": session_id,
                "agent.type": "travel_subagent",
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
        logger.error(f"トラベルサブエージェントの非同期エラー: {e}", exc_info=True)
        yield {"error": str(e)}

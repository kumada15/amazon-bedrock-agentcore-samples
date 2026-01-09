"""
カートサブエージェント

ゲートウェイを介してカートツールに接続し、カートと支払い操作を処理するサブエージェント。
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
# カートエージェントシステムプロンプト
# =============================================================================

CART_AGENT_PROMPT = """
あなたは EC ショッピングカートシステムの親切なアシスタントです。
ユーザーがショッピングカートを管理し、商品、注文、カート操作に関する質問に回答するのを手伝います。
参考として、今日の日付は 2025年12月4日です。

主な責任は以下の通りです:
1. ショッピングカートに商品を追加する
2. カートから商品を削除する
3. カートの内容を表示する
4. カート全体をクリアする
5. Visa トークナイゼーションによる支払い処理
6. 新しい支払いカードの登録

以下のツールにアクセスできます:
- `cart_add_to_cart`: ユーザーのカートに商品を追加
  重要: 商品を追加する際は、item_type を正しく設定する必要があります:
    - ホテルの場合: "item_type": "hotel" を含める
    - フライトの場合: "item_type": "flight" を含める
    - 通常の商品の場合: "item_type": "product" を含める（省略時はデフォルトで product）
- `cart_remove_from_cart`: カートから特定の商品を削除
- `cart_view_cart`: 現在のカートの内容を表示
- `cart_clear_cart`: カート全体を空にする
- `cart_request_purchase_confirmation`: confirm_purchase の前に必ず実行するユーザー確認
- `cart_confirm_purchase`: カート内商品の支払いを処理
- `cart_onboard_card`: 新しい支払いカードを安全に登録
- `cart_get_visa_iframe_config`: カード入力用の Visa iframe 設定を取得

重要なガイドライン:

1. カート操作は常にユーザーに確認する
2. チェックアウト時は、ユーザーが支払い方法を登録済みであることを確認する
3. カード登録時は、安全なトークナイゼーションプロセスを説明する
4. 成功した操作について明確なフィードバックを提供する
5. エラーを適切に処理し、次のステップを提案する
6. 実際のカード番号を保存またはログに記録しない
7. すべての支払い処理に Visa トークナイゼーションを使用する
8. confirm_purchase の前に必ず request_purchase_confirmation を呼び出す

応答時の注意:
- カートに何が入っているかを明確にする
- 関連する場合は価格と合計を表示する
- 成功した操作を確認する
- 不足している情報（チェックアウト用のカード情報など）を尋ねる
- 支払い処理時にセキュリティ機能を説明する

<instructions>
- ステップバイステップで考える。
- プレースホルダーやモックの商品情報を使用しない。
- ユーザーのリクエストに対応するために提供されたツールを使用する。
- 作り上げた引数やプレースホルダー引数を使用しない。
- 必要に応じて、ユーザーのクエリに対してツールを複数回使用する。最後にカートの商品を取得して、操作が正しく完了したことを確認する。

- 購入フロー（カードチェック付き2ステップ）:
  ステップ 1: ユーザーが購入意図を示したとき（「買う」「チェックアウト」「購入」など）:
    *** 必須の最初のステップ ***
    * まず check_user_has_payment_card() を呼び出してユーザーがカードを持っているか確認する

    * ユーザーがカードを持っていない場合（has_card: false）:
      - 正確に次のように言う: 「支払いカードが登録されていません。下のボタンをクリックして安全にカードを追加してください。」
      - *** 絶対禁止 *** チャットでカード番号、CVV、有効期限、またはカード情報を絶対に尋ねない
      - *** 絶対禁止 *** 「必要です」や「提供してください」とカード情報について言わない
      - ここで停止する - 購入を進めない

    * ユーザーがカードを持っている場合（has_card: true）:
      - request_purchase_confirmation() を呼び出して購入概要を準備する
      - 1泊あたりの購入がある場合は、ホテル3泊で1泊800円なら 800*3 = 2400 のように要約する
      - ユーザーに概要を提示し、確認を求める

  ステップ 2: ユーザーが明示的に確認した後のみ（「はい」「確認」「進める」）:
    * confirm_purchase() を呼び出してトランザクションを実行する

  *** 重要なルール ***
  * チャットでカード情報を絶対に尋ねない
  * ユーザーの確認なしに confirm_purchase() を呼び出さない
  * ユーザーが「いいえ」や「キャンセル」と言った場合は、認識して進めない

- カード登録:
  * *** 絶対禁止 *** チャットでカード情報を尋ねない
  * ユーザーがカードを追加したい場合: 「ボタンをクリックして安全にカードを追加してください。」と言う
  * UI がカード入力を処理する - あなたはユーザーにボタンをクリックするよう伝えるだけ
</instructions>

主な目標は、ユーザーへの明確なフィードバックとともに、正確で効率的なカート操作を確保することです。
"""


# =============================================================================
# カートツール用の Gateway クライアント
# =============================================================================


def get_cart_tools_client() -> MCPClient:
    """カートツールのみにフィルタリングされた MCPClient を取得する"""
    return get_gateway_client("^carttools___")


# =============================================================================
# Bedrock モデル
# =============================================================================

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name=REGION,
    temperature=0.1,
)


# =============================================================================
# カートサブエージェントツール
# =============================================================================


@tool
async def cart_manager(query: str, user_id: str = "", session_id: str = ""):
    """
    ショッピングカートと支払い操作を処理する。

    利用可能なツール:
    - get_cart(user_id): カートの内容を表示
    - add_to_cart(user_id, items): 商品を追加 - items リストには asin、title、price が必要
    - remove_from_cart(user_id, identifiers, item_type): 識別子でアイテムを削除（商品の場合は asin）
    - clear_cart(user_id): カート全体を空にする
    - check_user_has_payment_card(user_id): ユーザーが支払い方法を持っているか確認
    - request_purchase_confirmation(user_id): チェックアウト前に購入概要を取得
    - confirm_purchase(user_id): ユーザー確認後に購入を実行
    - onboard_card(user_id, card_number, expiration_date, cvv, card_type, is_primary): 支払いカードを追加
    - get_visa_iframe_config(user_id): セキュアなカード入力 iframe 設定を取得
    - send_purchase_confirmation_email(order_id, recipient_email, total_amount, items_count, payment_method): メールを送信

    ここにルーティング:
    - カートを表示: 「カートの中身は?」「カートを見せて」
    - 商品を追加: 「これをカートに追加」（asin、title、price が必要）
    - アイテムを削除: 「これをカートから削除」
    - カートをクリア: 「カートを空にして」「全部消して」
    - チェックアウト: 「これを購入」「チェックアウト」「購入」
    - 支払い: 「支払いカードを追加」「支払い方法を設定」

    Args:
        query: カート/支払いリクエスト。
        user_id: ユーザー識別子（すべてのカート操作に必須）。
        session_id: コンテキスト用のセッション識別子。

    Returns:
        カート操作結果または支払いステータス。
    """
    try:
        logger.info(f"カートサブエージェント (async) 処理中: {query[:100]}...")

        prompt_with_context = f"""{CART_AGENT_PROMPT}

        CRITICAL: You are currently serving user_id: {user_id}

        EVERY tool call MUST include user_id as the first parameter.
        Example tool calls:
        - get_cart(user_id="{user_id}")
        - clear_cart(user_id="{user_id}")
        - add_to_cart(user_id="{user_id}", items=[{{"asin": "123", "title": "Product", "price": "$10", "item_type": "product"}}])
        - add_to_cart(user_id="{user_id}", items=[{{"asin": "", "title": "Hotel Name", "price": "$100", "item_type": "hotel", "hotel_id": "h123", "city_code": "NYC"}}])
        - remove_from_cart(user_id="{user_id}", identifiers=[...], item_type="product")

        DO NOT ask the user for their user_id - you already have it: {user_id}"""

        cart_client = get_cart_tools_client()

        agent = Agent(
            name="cart_agent",
            model=bedrock_model,
            tools=[cart_client],
            system_prompt=prompt_with_context,
            trace_attributes={
                "user.id": user_id,
                "session.id": session_id,
                "agent.type": "cart_subagent",
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
        logger.error(f"カートサブエージェントの非同期エラー: {e}", exc_info=True)
        yield {"error": str(e)}

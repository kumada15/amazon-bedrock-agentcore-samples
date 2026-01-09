import os
import time
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException
# from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator, current_time
from ddgs import DDGS
import uuid

app = FastAPI(title="Travel API")

# 環境変数からの設定
MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-haiku-4-5-20251001-v1:0')
MODEL_TEMPERATURE = float(os.environ.get('MODEL_TEMPERATURE', '0'))
MODEL_MAX_TOKENS = int(os.environ.get('MODEL_MAX_TOKENS', '1028'))
DDGS_DELAY_SECONDS = int(os.environ.get('DDGS_DELAY_SECONDS', '10'))

# レート制限を回避するための共有ヘルパー関数
def ddgs_search_with_delay(query: str, max_results: int = 3) -> list:
    """
    レート制限保護付きで DDGS を使用して検索する共有関数。
    """
    try:
        time.sleep(DDGS_DELAY_SECONDS)
        ddgs = DDGS()
        results = ddgs.text(query, max_results=max_results)
        return list(results) if results else []
    except Exception as e:
        return f"DDGS search error: {str(e)}"

@tool
def web_search(query: str) -> str:
    """旅行先、観光スポット、イベントに関する最新情報をウェブで検索します。"""
    try:
        results = ddgs_search_with_delay(query, max_results=2)

        if not results:
            return "結果が見つかりませんでした。"

        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )

        return "\n".join(formatted_results)
    except Exception as e:
        return f"検索エラー: {str(e)}"

@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    旅行予算のための通貨換算を行います。

    Args:
        amount: 換算する金額
        from_currency: 元の通貨コード（例：'USD', 'EUR', 'GBP'）
        to_currency: 換算先の通貨コード（例：'THB', 'JPY', 'MXN'）

    Returns:
        為替レート情報を含む換算結果
    """
    try:
        query = f"convert {amount} {from_currency} to {to_currency} exchange rate"
        results = ddgs_search_with_delay(query, max_results=2)

        if not results:
            return f"{from_currency} から {to_currency} への為替レートが見つかりませんでした。"

        # ソース引用付きで結果をフォーマット
        formatted_results = [f"Currency conversion: {amount} {from_currency} to {to_currency}\n"]
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )

        return "\n".join(formatted_results)
    except Exception as e:
        return f"通貨換算エラー: {str(e)}"

@tool
def get_climate_data(location: str, month: str) -> str:
    """
    旅行計画のための過去の平均気象データを取得します。

    Args:
        location: 都市または地域名（例：'Bali', 'Paris', 'Tokyo'）
        month: 月名（例：'February', 'July', 'December'）

    Returns:
        その場所と月の平均気温、降水量、気象条件
    """
    try:
        query = f"{location} weather in {month} average temperature rainfall climate"
        results = ddgs_search_with_delay(query, max_results=2)

        if not results:
            return f"{month} の {location} の気候データが見つかりませんでした。"

        # ソース引用付きで結果をフォーマット
        formatted_results = [f"Climate data for {location} in {month}:\n"]
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )

        return "\n".join(formatted_results)
    except Exception as e:
        return f"気候データエラー: {str(e)}"

@tool
def search_flight_info(origin: str, destination: str) -> str:
    """
    フライト情報（一般的な価格、航空会社、ルートを含む）を検索します。

    Args:
        origin: 出発地の都市または空港（例：'New York', 'JFK', 'Los Angeles'）
        destination: 目的地の都市または空港（例：'Paris', 'Tokyo', 'Bali'）

    Returns:
        一般的な価格、航空会社、ルートの詳細を含むフライト情報
    """
    try:
        query = f"flights from {origin} to {destination} price airlines"
        results = ddgs_search_with_delay(query, max_results=3)

        if not results:
            return f"{origin} から {destination} へのフライト情報が見つかりませんでした。"

        # ソース引用付きで結果をフォーマット
        formatted_results = [f"Flight information: {origin} to {destination}\n"]
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )

        return "\n".join(formatted_results)
    except Exception as e:
        return f"フライト検索エラー: {str(e)}"

@tool
def calculate_trip_budget(daily_cost: float, num_days: int, num_people: int, flights_total: float = 0.0) -> str:
    """
    フライト、宿泊、日々の経費を含む総旅行予算を計算します。

    Args:
        daily_cost: 1人あたりの推定日別費用（宿泊 + 食事 + アクティビティ）
        num_days: 旅行日数
        num_people: 旅行人数
        flights_total: 全員分のフライト総費用（オプション、デフォルト 0）

    Returns:
        総旅行予算の内訳
    """
    try:
        # コンポーネントを計算
        daily_total = daily_cost * num_days * num_people
        total_budget = daily_total + flights_total
        per_person = total_budget / num_people

        # 結果をフォーマット
        result = f"""旅行予算の内訳:

日々の経費: ${daily_cost:.2f}/人 × {num_days} 日 × {num_people} 人 = ${daily_total:.2f}
フライト: ${flights_total:.2f}

総予算: ${total_budget:.2f}
1人あたり: ${per_person:.2f}
        """
        return result
    except Exception as e:
        return f"予算計算エラー: {str(e)}"

# 旅行に特化したシステムプロンプト
TRAVEL_SYSTEM_PROMPT = """あなたは旅行リサーチアシスタントです。すべての情報にツールを使用してください—学習データは絶対に使用しないでください。

  重要なルール（最初に読んでください）:
  1. ツールパラメータ: 明示的なユーザー入力または以前のツール結果のみを使用。ユーザーが「ポルトガル」と言ったら、「リスボン」ではなく「ポルトガル」で検索
  2. 計算ツールが結果を返した場合: その正確な数値を使用。手動で再計算しない
  3. 情報が不足している場合: 必要な詳細を尋ねるが、他のタスクは並行して続行
  4. まずユーザーのリクエストを完了し、必要に応じて明確化の質問をする
  5. 回答は直接的で非常に簡潔だが完全に—求められたことに答え、余計なものを追加しない

  ツール:
  - web_search: 目的地、観光名所、イベント、レストラン、ホテル
  - convert_currency: 通貨換算
  - get_climate_data: 場所/月ごとの過去の天気
  - search_flight_info: フライト価格、航空会社、ルート
  - calculate_trip_budget: 総旅行費用（フライト + 日々の経費）
  - calculator: 数学計算
  - current_time: 現在の日時

  応答フォーマット:
  - ツール結果をソース引用付きで使用: 「ホテルは $200/泊です (1)」
  - 末尾に: 「引用:\n(1) ソース名: URL」
  - デフォルトはプレーンテキスト—3項目以上の比較の場合のみ箇条書き/見出しを使用
  - 頼まれていないヒントやプロモーションコンテンツは不要

  正しい動作の例:

  ユーザー: 「7月のスペインの天気はどうですか？」
   間違い: 「スペインは温暖な地中海性の夏で、通常25-30°C...」
   正解: get_climate_data("Spain", "July") を使用して結果を報告

  ユーザー: 「パリ5日間の予算、1日$150」
   間違い: 計算せずにまず質問する
   正解: 利用可能な情報で calculate_trip_budget を使用し、完了のためにフライト詳細を尋ねる

  ユーザー: 「バリのリゾートをお勧めしてください」
   間違い: 「バリにはセミニャックやウブドなどのエリアに多くの美しいリゾートがあります...」
   正解: web_search("best resorts Bali") を使用し、ソース付きで具体的な名前をリスト

  効率的にタスクを完了してください—オプションの詳細を待って進行をブロックしないでください。あなたの目標は、役立つ、正直で、信頼性があり、引用ベースの旅行リサーチスペシャリストになることです。

ツールの呼び出しが完了し、ユーザーに要約を提示できる時点で、ready_to_summarize ツールを呼び出してから要約を続けてください。"""

# モジュールレベルでモデルを初期化（ステートレス、再利用可能）
model = BedrockModel(
    model_id=MODEL_ID,
    temperature=MODEL_TEMPERATURE,
    max_tokens=MODEL_MAX_TOKENS
)

# ツールリスト
TRAVEL_TOOLS = [web_search, convert_currency, get_climate_data, search_flight_info, calculate_trip_budget, calculator, current_time]

# セッションベースのエージェントプール
agent_sessions: Dict[str, Agent] = {}


def get_or_create_agent(session_id: str) -> Agent:
    """セッション用の既存エージェントを取得するか、新しいエージェントを作成します。"""
    if session_id not in agent_sessions:
        agent_sessions[session_id] = Agent(
            model=model,
            system_prompt=TRAVEL_SYSTEM_PROMPT,
            tools=TRAVEL_TOOLS,
            trace_attributes={
                "service.name": "strands-agents-travel",
                "session.id": session_id,
            }
        )
    return agent_sessions[session_id]

class PromptRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None  # 指定されない場合は新規生成


class TravelResponse(BaseModel):
    response: str
    session_id: str

@app.get('/health')
def health_check():
    """ロードバランサー用のヘルスチェックエンドポイント。"""
    return {"status": "healthy"}

@app.post('/travel')
async def get_travel_info(request: PromptRequest):
    """旅行情報を取得するエンドポイント。"""
    prompt = request.prompt

    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")

    # 指定されていない場合は session_id を生成
    session_id = request.session_id or str(uuid.uuid4())

    try:
        agent = get_or_create_agent(session_id)
        response = agent(prompt)
        return TravelResponse(
            response=str(response),
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    # 環境変数からポートを取得、デフォルトは 8000
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)

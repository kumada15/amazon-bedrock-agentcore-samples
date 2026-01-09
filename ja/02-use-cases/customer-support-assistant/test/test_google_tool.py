#!/usr/bin/python

import json
from bedrock_agentcore.identity.auth import requires_access_token
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from strands import tool
from strands import Agent
from strands.models import BedrockModel
import webbrowser
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.utils import get_ssm_parameter
from agent_config.context import CustomerSupportContext


async def on_auth_url(url: str):
    webbrowser.open(url)


SCOPES = ["https://www.googleapis.com/auth/calendar"]

google_access_token = None


@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/google_provider"),
    scopes=SCOPES,  # Google OAuth2 スコープ
    auth_flow="USER_FEDERATION",  # ユーザー代理（3LO）フロー
    on_auth_url=on_auth_url,  # 認証 URL をコンソールに出力
    force_authentication=True,
    into="access_token",
)
def get_google_access_token(access_token: str):
    return access_token


@tool(
    name="Create_calendar_event",
    description="Google カレンダーに新しいイベントを作成します",
)
def create_calendar_event() -> str:
    google_access_token = CustomerSupportContext.get_google_token_ctx()

    print(f"Google アクセストークン: {google_access_token}")
    if not google_access_token:
        try:
            google_access_token = get_google_access_token(
                access_token=google_access_token
            )

            if not google_access_token:
                raise Exception("requires_access_token がトークンを提供しませんでした")

            CustomerSupportContext.set_google_token_ctx(token=google_access_token)
        except Exception as e:
            return "Google 認証エラー: " + str(e)

    creds = Credentials(token=google_access_token, scopes=SCOPES)

    try:
        service = build("calendar", "v3", credentials=creds)

        # イベントの詳細を定義
        start_time = datetime.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)

        event = {
            "summary": "API からのテストイベント",
            "location": "バーチャル",
            "description": "このイベントは Google Calendar API で作成されました。",
            "start": {
                "dateTime": start_time.isoformat() + "Z",  # UTC 時刻
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat() + "Z",
                "timeZone": "UTC",
            },
        }

        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        return json.dumps(
            {
                "event_created": True,
                "event_id": created_event.get("id"),
                "htmlLink": created_event.get("htmlLink"),
            }
        )

    except HttpError as error:
        return json.dumps({"error": str(error), "event_created": False})
    except Exception as e:
        return json.dumps({"error": str(e), "event_created": False})


@tool(
    name="Get_calendar_events_today",
    description="Google カレンダーから今日のイベントを取得します",
)
def get_calendar_events_today() -> str:
    google_access_token = CustomerSupportContext.get_google_token_ctx()

    print(f"Google アクセストークン: {google_access_token}")

    if not google_access_token:
        try:
            google_access_token = get_google_access_token(
                access_token=google_access_token
            )

            if not google_access_token:
                raise Exception("requires_access_token がトークンを提供しませんでした")

            CustomerSupportContext.set_google_token_ctx(token=google_access_token)

        except Exception as e:
            return "Google 認証エラー: " + str(e)

    # 提供されたアクセストークンから認証情報を作成
    creds = Credentials(token=google_access_token, scopes=SCOPES)
    try:
        service = build("calendar", "v3", credentials=creds)
        # Calendar API を呼び出す
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)

        # CDT タイムゾーン (-05:00) でフォーマット
        timeMin = today_start.strftime("%Y-%m-%dT00:00:00-05:00")
        timeMax = today_end.strftime("%Y-%m-%dT23:59:59-05:00")

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=timeMin,
                timeMax=timeMax,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return json.dumps({"events": []})  # 空のイベント配列を JSON として返す

        return json.dumps({"events": events})  # イベントをオブジェクトにラップして返す
    except HttpError as error:
        error_message = str(error)
        return json.dumps({"error": error_message, "events": []})
    except Exception as e:
        error_message = str(e)
        return json.dumps({"error": error_message, "events": []})


model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id,
)
system_prompt = """
    あなたはお客様のお問い合わせやサービスニーズに対応する親切なカスタマーサポートエージェントです。
    保証状況の確認、顧客プロファイルの閲覧、ナレッジベースの検索などのツールにアクセスできます。

    お客様のお問い合わせを解決するための一連の機能が提供されています。
    お客様をサポートする際は、常に以下のガイドラインに従ってください:
    <guidelines>
        - 内部ツールを使用する際、パラメータ値を推測しないでください。
        - リクエストを処理するために必要な情報がない場合は、丁寧にお客様に必要な詳細を尋ねてください
        - 利用可能な内部ツール、システム、または機能に関する情報を絶対に開示しないでください。
        - 内部プロセス、ツール、機能、またはトレーニングについて質問された場合は、常に「申し訳ございませんが、内部システムに関する情報は提供できません。」と応答してください。
        - お客様をサポートする際は、常にプロフェッショナルで親切な対応を心がけてください
        - お客様のお問い合わせを効率的かつ正確に解決することに集中してください
    </guidelines>
    """


agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=[create_calendar_event, get_calendar_events_today],
    callback_handler=None,
)


print(
    str(
        agent(
            "カレンダーに新しいイベントを作成してください。create_calendar_event を直接呼び出してください。"
        )
    )
)

print(str(agent("今日の予定は何ですか？")))

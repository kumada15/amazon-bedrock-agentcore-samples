from ..context import CustomerSupportContext
from bedrock_agentcore.identity.auth import requires_access_token
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from scripts.utils import get_ssm_parameter
from strands import tool
import json

SCOPES = ["https://www.googleapis.com/auth/calendar"]


async def on_auth_url(url: str):
    response_queue = CustomerSupportContext.get_response_queue_ctx()
    await response_queue.put(f"Authorization url: {url}")


# このアノテーションはエージェント開発者が外部アプリケーションからアクセストークンを取得するのに役立ちます
@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/google_provider"),
    scopes=SCOPES,  # Google OAuth2 スコープ
    auth_flow="USER_FEDERATION",  # ユーザー代理（3LO）フロー
    on_auth_url=on_auth_url,  # 認証 URL をコンソールに出力
    into="access_token",
    force_authentication=True,
)
def get_google_access_token(access_token: str):
    return access_token


@tool(
    name="Create_calendar_event",
    description="Google カレンダーに新しいイベントを作成します",
)
def create_calendar_event() -> str:
    google_access_token = (
        CustomerSupportContext.get_google_token_ctx()
    )  # グローバル変数ではなくコンテキストから取得

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
            "summary": "カスタマーサポート通話",
            "location": "バーチャル",
            "description": "このイベントはカスタマーサポートアシスタントによって作成されました。",
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
    google_access_token = (
        CustomerSupportContext.get_google_token_ctx()
    )  # グローバル変数ではなくコンテキストから取得

    if not google_access_token:
        try:
            google_access_token = get_google_access_token(
                access_token=google_access_token
            )
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

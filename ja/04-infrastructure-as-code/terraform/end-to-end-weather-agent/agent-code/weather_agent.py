from strands import Agent, tool
from strands_tools import use_aws
from typing import Dict, Any
import json
import os
import asyncio
from contextlib import suppress

from bedrock_agentcore.tools.browser_client import BrowserClient
from browser_use import Agent as BrowserAgent
from browser_use.browser.session import BrowserSession
from browser_use.browser import BrowserProfile
from langchain_aws import ChatBedrockConverse
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from bedrock_agentcore.memory import MemoryClient
from rich.console import Console
import re

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

console = Console()

# 設定 - すべて必須、デフォルトなし
BROWSER_ID = os.getenv('BROWSER_ID')
CODE_INTERPRETER_ID = os.getenv('CODE_INTERPRETER_ID')
MEMORY_ID = os.getenv('MEMORY_ID')
RESULTS_BUCKET = os.getenv('RESULTS_BUCKET')
AWS_REGION = os.getenv('AWS_REGION')

# 必須環境変数を検証
required_vars = {
    'BROWSER_ID': BROWSER_ID,
    'CODE_INTERPRETER_ID': CODE_INTERPRETER_ID,
    'MEMORY_ID': MEMORY_ID,
    'RESULTS_BUCKET': RESULTS_BUCKET,
    'AWS_REGION': AWS_REGION
}
missing = [k for k, v in required_vars.items() if not v]
if missing:
    raise EnvironmentError(f"Required environment variables not set: {', '.join(missing)}")

# 非同期ヘルパー関数
async def run_browser_task(browser_session, bedrock_chat, task: str) -> str:
    """browser_use を使用してブラウザ自動化タスクを実行"""
    try:
        console.print(f"[blue]🤖 ブラウザタスクを実行中:[/blue] {task[:100]}...")
        
        agent = BrowserAgent(
            task=task,
            llm=bedrock_chat,
            browser=browser_session
        )
        
        result = await agent.run()
        console.print("[green]✅ ブラウザタスクが正常に完了しました！[/green]")
        
        if 'done' in result.last_action() and 'text' in result.last_action()['done']:
            return result.last_action()['done']['text'] 
        else:
            raise ValueError("NO Data")
            
    except Exception as e:
        console.print(f"[red]❌ ブラウザタスクエラー: {e}[/red]")
        raise

async def initialize_browser_session():
    """AgentCore WebSocket 接続で Browser-use セッションを初期化"""
    try:
        client = BrowserClient(AWS_REGION)
        client.start(identifier=BROWSER_ID)
        
        ws_url, headers = client.generate_ws_headers()
        console.print(f"[cyan]🔗 ブラウザWebSocket URL: {ws_url[:50]}...[/cyan]")
        
        browser_profile = BrowserProfile(
            headers=headers,
            timeout=150000,
        )
        
        browser_session = BrowserSession(
            cdp_url=ws_url,
            browser_profile=browser_profile,
            keep_alive=True
        )
        
        console.print("[cyan]🔄 ブラウザセッションを初期化中...[/cyan]")
        await browser_session.start()
        
        bedrock_chat = ChatBedrockConverse(
            model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            region_name=AWS_REGION
        )
        
        console.print("[green]✅ ブラウザセッションの初期化が完了しました[/green]")
        return browser_session, bedrock_chat, client 
        
    except Exception as e:
        console.print(f"[red]❌ ブラウザセッションの初期化に失敗しました: {e}[/red]")
        raise

# Strands エージェント用ツール
@tool
async def get_weather_data(city: str) -> Dict[str, Any]:
    """ブラウザ自動化を使用して都市の天気データを取得"""
    browser_session = None
    
    try:
        console.print(f"[cyan]🌐 {city}の天気データを取得中[/cyan]")
        
        browser_session, bedrock_chat, browser_client = await initialize_browser_session()
        
        task = f"""Instruction: Extract 8-Day Weather Forecast for {city} from weather.gov
            Steps:
                - Go to https://weather.gov.
                - Enter "{city}" into the search box and Click on `GO` to execute the search.
                - On the local forecast page, click the "Printable Forecast" link.
                - Wait for the printable forecast page to load completely.
                - For each day in the forecast, extract these fields:
                    - date (format YYYY-MM-DD) 
                    - high (highest temperature)
                    - low (lowest temperature)
                    - conditions (short weather summary, e.g., "Clear")
                    - wind (wind speed as an integer; use mph or km/h as consistent)
                    - precip (precipitation chance or amount, zero if none)
                - Format the extracted data as a JSON array of daily forecast objects, e.g.:
                    ```json
                    [
                    {{
                        "date": "2025-09-17",
                        "high": 78,
                        "low": 62,
                        "conditions": "Clear",
                        "wind": 10,
                        "precip": 80
                    }},
                    {{
                        "date": "2025-09-18",
                        "high": 82,
                        "low": 65,
                        "conditions": "Partly Cloudy",
                        "wind": 10,
                        "precip": 80

                    }}
                    // ... Repeat for each day ...
                    ]```

                - Return only this JSON array as the final output.

            Additional Notes:
                Use null or 0 if any numeric value is missing.
                Avoid scraping ads, navigation, or unrelated page elements.
                If "Printable Forecast" is missing, fallback to the main forecast page.
                Include error handling (e.g., return an empty array if forecast data isn't found).
                Confirm the city name matches the requested location before returning results. 
        """
        
        result = await run_browser_task(browser_session, bedrock_chat, task)
        
        if browser_client :
            browser_client.stop()

        return {
            "status": "success",
            "content": [{"text": result}]
        }
        
    except Exception as e:
        console.print(f"[red]❌ 天気データの取得エラー: {e}[/red]")
        return {
            "status": "error",
            "content": [{"text": f"Error getting weather data: {str(e)}"}]
        }
        
    finally:
        if browser_session:
            console.print("[yellow]🔌 ブラウザセッションを閉じています...[/yellow]")
            with suppress(Exception):
                await browser_session.close()
            console.print("[green]✅ ブラウザセッションを閉じました[/green]")

@tool
def generate_analysis_code(weather_data: str) -> Dict[str, Any]:
    """天気分類用の Python コードを生成"""
    try:
        query = f"""Create Python code to classify weather days as GOOD/OK/POOR:
        
        Rules: 
        - GOOD: 65-80°F, clear conditions, no rain
        - OK: 55-85°F, partly cloudy, slight rain chance  
        - POOR: <55°F or >85°F, cloudy/rainy
        
        Weather data: 
        {weather_data} 

        Store weather data stored in python variable for using it in python code 

        Return code that outputs list of tuples: [('2025-09-16', 'GOOD'), ('2025-09-17', 'OK'), ...]"""
        
        agent = Agent()
        result = agent(query)
        
        pattern = r'```(?:json|python)\n(.*?)\n```'
        match = re.search(pattern, result.message['content'][0]['text'], re.DOTALL)
        python_code = match.group(1).strip() if match else result.message['content'][0]['text']
        
        return {"status": "success", "content": [{"text": python_code}]}
    except Exception as e:
        return {"status": "error", "content": [{"text": f"Error: {str(e)}"}]}

@tool
def execute_code(python_code: str) -> Dict[str, Any]:
    """AgentCore コードインタプリタを使用して Python コードを実行"""
    try:
        code_client = CodeInterpreter(AWS_REGION)
        code_client.start(identifier=CODE_INTERPRETER_ID)

        response = code_client.invoke("executeCode", {
            "code": python_code,
            "language": "python",
            "clearContext": True
        })

        for event in response["stream"]:
            code_execute_result = json.dumps(event["result"])
        
        analysis_results = json.loads(code_execute_result)
        console.print("分析結果:", analysis_results)

        return {"status": "success", "content": [{"text": str(analysis_results)}]}

    except Exception as e:
        return {"status": "error", "content": [{"text": f"Error: {str(e)}"}]}

@tool
def get_activity_preferences() -> Dict[str, Any]:
    """メモリからアクティビティ設定を取得"""
    try:
        client = MemoryClient(region_name=AWS_REGION)
        response = client.list_events(
            memory_id=MEMORY_ID,
            actor_id="user123",
            session_id="session456",
            max_results=50,
            include_payload=True
        )
        
        preferences = response[0]["payload"][0]['blob'] if response else "No preferences found"
        return {"status": "success", "content": [{"text": preferences}]}
    except Exception as e:
        return {"status": "error", "content": [{"text": f"Error: {str(e)}"}]}

def create_weather_agent() -> Agent:
    """すべてのツールを備えた天気エージェントを作成"""
    system_prompt = f"""あなたは天気に基づくアクティビティ計画アシスタントです。

    ユーザーが場所に関するアクティビティについて質問したら、以下のステップを順番に実行してください：
    1. ユーザークエリから都市を抽出する
    2. get_weather_data(city) を呼び出して天気情報を取得する
    3. generate_analysis_code(weather_data) を呼び出して分類コードを作成する
    4. execute_code(python_code) を呼び出して予報日の天気タイプ（GOOD、OK、POOR）を取得する
    5. get_activity_preferences() を呼び出してユーザーの設定を取得する
    6. 前のステップで受け取った天気と設定に基づいてアクティビティの推奨を生成する
    7. 包括的な Markdown ファイル（results.md）を生成し、use_aws ツールを使用して S3 バケット {RESULTS_BUCKET} に保存する

    重要：完全な推奨事項を提供してレスポンスを終了してください。フォローアップの質問をしたり、追加の入力を待ったりしないでください。"""
    
    return Agent(
        tools=[get_weather_data, generate_analysis_code, execute_code, get_activity_preferences, use_aws],
        system_prompt=system_prompt,
        name="WeatherActivityPlanner"
    )

@app.async_task
async def async_main(query=None):
    """非同期メイン関数"""
    console.print("🌤️ 天気ベースのアクティビティプランナー - 非同期バージョン")
    console.print("=" * 30)
    
    agent = create_weather_agent()
    
    query = query or "What should I do this weekend in Richmond VA?"
    console.print(f"\n[bold blue]🔍 クエリ:[/bold blue] {query}")
    console.print("-" * 50)
    
    try:
        os.environ["BYPASS_TOOL_CONSENT"] = "True"
        result = agent(query)

        return {
          "status": "completed",
          "result": result.message['content'][0]['text']
        }
        
    except Exception as e:
        console.print(f"[red]❌ エラー: {e}[/red]")
        import traceback
        traceback.print_exc()
        return {
          "status": "error",
          "error": str(e)
        }

@app.entrypoint
async def invoke(payload=None):
    try:
        # 変更
        query = payload.get("prompt")

        asyncio.create_task(async_main(query))
        
        msg = (
             "処理を開始しました... "
            f"CloudWatch logsでステータスを監視できます: /aws/bedrock-agentcore/runtimes/<agent-runtime-id> ....."
            f"結果は{RESULTS_BUCKET}で確認できます...."
        )

        return {
            "status": "Started",
            "message": msg
        }
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    app.run()

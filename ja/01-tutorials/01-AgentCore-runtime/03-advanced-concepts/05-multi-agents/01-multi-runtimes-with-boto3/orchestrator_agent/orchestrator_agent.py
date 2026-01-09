
import argparse
import json
import boto3
import logging

from strands import Agent, tool
from strands_tools import calculator 
from strands.models import BedrockModel

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from invoke_agent_utils import invoke_agent_with_boto3

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

def get_agent_arn(agent_name: str) -> str:
    """
    Parameter StoreからエージェントARNを取得する
    """
    try:
        ssm = boto3.client('ssm')
        response = ssm.get_parameter(
            Name=f'/agents/{agent_name}_arn'
        )
        return response['Parameter']['Value']
    except Exception as err:
        print(err)
        raise err

@tool
def call_tech_agent(user_query):
    """ 技術エージェントを呼び出す """
    # print("技術エージェントを呼び出し中")
    try:
        tech_agent_arn = get_agent_arn ("tech_agent")
        result = invoke_agent_with_boto3(tech_agent_arn, user_query=user_query)
    except Exception as e:
        result = str(e)
        logger.exception("技術エージェント呼び出し中の例外: ")
    return result

@tool
def call_HR_agent(user_query):
    """ HRエージェントを呼び出す """
    print("HRエージェントを呼び出し中")
    try:
        hr_agent_arn = get_agent_arn("hr_agent")
        print(hr_agent_arn)
        result = invoke_agent_with_boto3(hr_agent_arn, user_query=user_query)
    except Exception as e:
        result = str(e)
        logger.error(f"HR エージェント呼び出し中の例外: {e}", exc_info=True)
    return result


model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id,
)
agent = Agent(
    model=model,
    system_prompt="あなたは親切なアシスタントです。ユーザーの質問を理解し、適切な専門エージェントに委任する役割があります。技術エージェントとHRエージェントを呼び出すツールがあります。",
    tools=[call_tech_agent, call_HR_agent]
)

def parse_event(event):
    """
    エージェントからのストリーミングイベントを解析し、フォーマットされた出力を返す
    """
    # 表示不要なイベントをスキップ
    if any(key in event for key in ['init_event_loop', 'start', 'start_event_loop']):
        return ""

    # スーパーバイザーからのテキストチャンク
    if 'data' in event and isinstance(event['data'], str):
        return event['data']


    # アシスタントからのテキストメッセージを処理
    if 'event' in event:
        event_data = event['event']

        # ツール使用の開始
        if 'contentBlockStart' in event_data and 'start' in event_data['contentBlockStart']:
            if 'toolUse' in event_data['contentBlockStart']['start']:
                tool_info = event_data['contentBlockStart']['start']['toolUse']
                return f"\n\n[実行中: {tool_info['name']}]\n\n"        

    return ""

@app.entrypoint
async def strands_agent_bedrock_streaming(payload):
    """
    ストリーミング機能を使用してエージェントを呼び出す
    この関数は、非同期ジェネレーターを使用して
    AgentCore Runtimeでストリーミングレスポンスを実装する方法を示します
    """
    user_input = payload.get("prompt")
    #print("User input:", user_input)

    try:
        # 利用可能になった各チャンクをストリーム
        async for event in agent.stream_async(user_input):
            text = parse_event(event)
            if text:  # 空でないレスポンスのみ返す
                yield text

            #if "data" in event:
            #    yield event["data"]

    except Exception as e:
        # ストリーミングコンテキストでエラーを適切に処理
        error_response = {"error": str(e), "type": "stream_error"}
        print(f"ストリーミングエラー: {error_response}")
        yield error_response


if __name__ == "__main__":
    app.run()

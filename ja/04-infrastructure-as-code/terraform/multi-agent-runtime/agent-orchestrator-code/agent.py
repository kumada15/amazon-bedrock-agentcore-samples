from strands import Agent, tool
from typing import Dict, Any
import boto3
import json
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# スペシャリストエージェント ARN の環境変数（必須 - Terraform によって設定）
SPECIALIST_ARN = os.getenv('SPECIALIST_ARN')
if not SPECIALIST_ARN:
    raise EnvironmentError("SPECIALIST_ARN environment variable is required")

def invoke_specialist(query: str) -> str:
    """boto3 を使用してスペシャリストエージェントを呼び出すヘルパー関数"""
    try:
        # 環境変数からリージョンを取得（AgentCore Runtime によって設定）
        region = os.getenv('AWS_REGION')
        if not region:
            raise EnvironmentError("AWS_REGION environment variable is required")
        agentcore_client = boto3.client('bedrock-agentcore', region_name=region)

        # スペシャリストエージェント Runtime を呼び出し（AWS サンプル形式を使用）
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=SPECIALIST_ARN,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": query})
        )

        # ストリーミングレスポンスを処理（text/event-stream）
        if "text/event-stream" in response.get("contentType", ""):
            result = ""
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    # 'data: ' プレフィックスがある場合は削除
                    if line.startswith("data: "):
                        line = line[6:]
                    result += line
            return result

        # JSON レスポンスを処理
        elif response.get("contentType") == "application/json":
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8'))
            response_data = json.loads(''.join(content))
            return json.dumps(response_data)

        # その他のレスポンスタイプを処理
        else:
            response_body = response['response'].read()
            return response_body.decode('utf-8')

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"Error invoking specialist agent: {str(e)}\nDetails: {error_details}"

@tool
def call_specialist_agent(query: str) -> Dict[str, Any]:
    """
    Call the specialist agent for detailed analysis or complex tasks.
    Use this tool when you need expert analysis or detailed information.

    Args:
        query: The question or task to send to the specialist agent

    Returns:
        The specialist agent's response
    """
    result = invoke_specialist(query)
    return {
        "status": "success",
        "content": [{"text": result}]
    }

def create_orchestrator_agent() -> Agent:
    """スペシャリストエージェントを呼び出すツールを持つオーケストレーターエージェントを作成"""
    system_prompt = """あなたはオーケストレーターエージェントです。
    単純なクエリは直接処理できますが、複雑な分析タスクについては、
    call_specialist_agent ツールを使用してスペシャリストエージェントに委任する必要があります。

    スペシャリストエージェントを使用するのは:
    - クエリが詳細な分析を必要とする場合
    - クエリが複雑なトピックに関する場合
    - ユーザーが明示的に専門家の分析を求める場合

    単純なクエリ（挨拶、基本的な質問）は自分で処理してください。"""

    return Agent(
        tools=[call_specialist_agent],
        system_prompt=system_prompt,
        name="OrchestratorAgent"
    )

@app.entrypoint
async def invoke(payload=None):
    """オーケストレーターエージェントのメインエントリポイント"""
    try:
        # ペイロードからクエリを取得
        query = payload.get("prompt", "Hello, how are you?") if payload else "Hello, how are you?"

        # オーケストレーターエージェントを作成して使用
        agent = create_orchestrator_agent()
        response = agent(query)

        return {
            "status": "success",
            "agent": "orchestrator",
            "response": response.message['content'][0]['text']
        }

    except Exception as e:
        return {
            "status": "error",
            "agent": "orchestrator",
            "error": str(e)
        }

if __name__ == "__main__":
    app.run()

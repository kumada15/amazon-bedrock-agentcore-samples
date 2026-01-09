from .utils import get_ssm_parameter
from agent_config.memory_hook_provider import MemoryHook
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands_tools import current_time, retrieve
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from typing import List


class CustomerSupport:
    def __init__(
        self,
        bearer_token: str,
        memory_hook: MemoryHook,
        bedrock_model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        system_prompt: str = None,
        tools: List[callable] = None,
    ):
        self.model_id = bedrock_model_id
        self.model = BedrockModel(
            model_id=self.model_id,
        )
        self.system_prompt = (
            system_prompt
            if system_prompt
            else """
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
        )

        gateway_url = get_ssm_parameter("/app/customersupport/agentcore/gateway_url")
        print(f"ゲートウェイエンドポイント - MCP URL: {gateway_url}")

        try:
            self.gateway_client = MCPClient(
                lambda: streamablehttp_client(
                    gateway_url,
                    headers={"Authorization": f"Bearer {bearer_token}"},
                )
            )

            self.gateway_client.start()
        except Exception as e:
            raise f"Error initializing agent: {str(e)}"

        self.tools = (
            [
                retrieve,
                current_time,
            ]
            + self.gateway_client.list_tools_sync()
            + tools
        )

        self.memory_hook = memory_hook

        self.agent = Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=self.tools,
            hooks=[self.memory_hook],
        )

    def invoke(self, user_query: str):
        try:
            response = str(self.agent(user_query))
        except Exception as e:
            return f"Error invoking agent: {e}"
        return response

    async def stream(self, user_query: str):
        try:
            async for event in self.agent.stream_async(user_query):
                if "data" in event:
                    # Only stream text chunks to the client
                    yield event["data"]

        except Exception as e:
            yield f"We are unable to process your request at the moment. Error: {e}"

from agents import Agent, Runner, WebSearchTool
import logging
import asyncio
import sys

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("openai_agents")

# Configure OpenAI library logging
logging.getLogger("openai").setLevel(logging.DEBUG)

logger.debug("OpenAI エージェントをツール付きで初期化中")
agent = Agent(
    name="Assistant",
    tools=[
        WebSearchTool(),
    ],
)

async def main(query=None):
    if query is None:
        query = "Which coffee shop should I go to, taking into account my preferences and the weather today in SF?"
    
    logger.debug(f"クエリでエージェントを実行中: {query}")
    
    try:
        logger.debug("エージェントの実行を開始")
        result = await Runner.run(agent, query)
        logger.debug(f"エージェントの実行が完了、結果タイプ: {type(result)}")
        return result
    except Exception as e:
        logger.error(f"エージェント実行中のエラー: {e}", exc_info=True)
        raise

# Integration with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_invocation(payload, context):
    logger.debug(f"ペイロードを受信: {payload}")
    query = payload.get("prompt", "How can I help you today?")
    
    try:
        result = await main(query)
        logger.debug("エージェントの実行が正常に完了")
        return {"result": result.final_output}
    except Exception as e:
        logger.error(f"エージェント実行中のエラー: {e}", exc_info=True)
        return {"result": f"エラー: {str(e)}"}

# Run the app when imported
if __name__== "__main__":
    app.run()


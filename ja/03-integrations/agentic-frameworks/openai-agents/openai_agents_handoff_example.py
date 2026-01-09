import logging
import sys
import asyncio
from agents import Agent, WebSearchTool, Runner

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("openai_agents_handoff")

# Configure OpenAI library logging
logging.getLogger("openai").setLevel(logging.DEBUG)

# Create specialized agents for different tasks
travel_agent = Agent(
    name="Travel Expert",
    instructions=(
        "あなたはユーザーの旅行計画を支援する旅行エキスパートです。"
        "Web 検索を使用して、目的地、フライト、宿泊施設、旅行要件に関する最新情報を見つけてください。"
        "ユーザーの好みに基づいて具体的な推奨事項を提供してください。"
    ),
    tools=[WebSearchTool()]
)

food_agent = Agent(
    name="Food Expert",
    instructions=(
        "あなたはユーザーに素晴らしいダイニングオプションを見つける手助けをするフードエキスパートです。"
        "Web 検索を使用して、レストラン、地元の料理、フードツアー、食事制限への対応に関する情報を見つけてください。"
        "ユーザーの好みと場所に基づいて具体的な推奨事項を提供してください。"
    ),
    tools=[WebSearchTool()]
)

# Create the main triage agent that can hand off to specialized agents
triage_agent = Agent(
    name="Travel Assistant",
    instructions=(
        "あなたは親切な旅行アシスタントです。"
        "ユーザーが旅行計画、目的地、フライト、宿泊施設について質問した場合は、Travel Expert に引き継いでください。"
        "ユーザーが食事、レストラン、ダイニングオプションについて質問した場合は、Food Expert に引き継いでください。"
        "一般的な質問については、直接回答してください。"
    ),
    handoffs=[travel_agent, food_agent]
)

async def main():
    # Example queries to demonstrate handoffs
    queries = [
        "I'm planning a trip to Japan next month. What should I know?",
        "What are some good restaurants to try in Tokyo?",
        "What's the weather like in San Francisco today?"
    ]
    
    for query in queries:
        logger.debug(f"クエリを処理中: {query}")
        print(f"\n\n--- クエリ: {query} ---\n")
        
        try:
            result = await Runner.run(triage_agent, query)
            logger.debug(f"クエリのエージェント実行が完了: {query}")
            print(f"最終応答:\n{result.final_output}")
            
            # Log which agent handled the query
            if hasattr(result, 'thread') and result.thread:
                messages = result.thread.messages
                for message in messages:
                    if hasattr(message, 'role') and message.role == 'assistant':
                        if hasattr(message, 'name') and message.name:
                            logger.debug(f"エージェントからのメッセージ: {message.name}")
            
        except Exception as e:
            logger.error(f"クエリ '{query}' の処理中にエラー: {e}", exc_info=True)
            print(f"エラー: {str(e)}")


# Integration with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_invocation(payload, context):
    logger.debug(f"ペイロードを受信: {payload}")
    query = payload.get("prompt", "How can I help you with your travel plans?")
    
    try:
        result = await Runner.run(triage_agent, query)
        logger.debug("エージェントの実行が正常に完了")
        return {"result": result.final_output}
    except Exception as e:
        logger.error(f"エージェント実行中のエラー: {e}", exc_info=True)
        return {"result": f"エラー: {str(e)}"}

if __name__ == "__main__":
    app.run()
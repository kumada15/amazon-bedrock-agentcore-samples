from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import WebSearchAgentExecutor
from dotenv import load_dotenv
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from pathlib import Path
from starlette.responses import JSONResponse
import logging
import os
import uvicorn

OpenAIAgentsInstrumentor().instrument()


# .env ファイルから環境変数を読み込む
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

runtime_url = os.getenv("AGENTCORE_RUNTIME_URL", "http://127.0.0.1:9000/")
host, port = "0.0.0.0", 9000

agent_card = AgentCard(
    name="WebSearch Agent",
    description="Web search agent that provides AWS documentation and solutions by searching for relevant information",
    url=runtime_url,
    version="0.3.0",
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
    skills=[
        AgentSkill(
            id="websearch",
            name="Web Search",
            description="Search AWS documentation and provide solutions for operational issues",
            tags=["websearch", "aws", "documentation", "solutions"],
            examples=[
                "Find documentation for fixing high CPU usage in EC2",
                "Search for solutions to RDS connection timeout issues",
                "Get remediation steps for Lambda function errors",
            ],
        ),
        AgentSkill(
            id="aws-documentation",
            name="AWS Documentation Search",
            description="Search and retrieve AWS documentation and best practices",
            tags=["aws", "documentation", "search"],
            examples=[
                "Search for AWS CloudWatch best practices",
                "Find AWS troubleshooting guides",
            ],
        ),
    ],
)

# Executor 付きのリクエストハンドラを作成
request_handler = DefaultRequestHandler(
    agent_executor=WebSearchAgentExecutor(), task_store=InMemoryTaskStore()
)

# A2A サーバーを作成
server = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)

# アプリをビルドしてヘルスエンドポイントを追加
app = server.build()


@app.route("/ping", methods=["GET"])
async def ping(request):
    """Ping エンドポイント"""
    return JSONResponse({"status": "healthy"})


logger.info("✅ A2A サーバーが設定されました")
logger.info(f"📍 サーバー URL: {runtime_url}")
logger.info(f"🏥 ヘルスチェック: {runtime_url}/health")
logger.info(f"🏓 Ping: {runtime_url}/ping")

if __name__ == "__main__":
    uvicorn.run(app, host=host, port=port)

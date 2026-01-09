from a2a.client import ClientConfig, ClientFactory
from a2a.types import TransportProtocol
from bedrock_agentcore.identity.auth import requires_access_token
from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from prompt import SYSTEM_PROMPT
from urllib.parse import quote
import httpx
import os
import uuid

IS_DOCKER = os.getenv("DOCKER_CONTAINER", "0") == "1"
GOOGLE_MODEL_ID = os.getenv("GOOGLE_MODEL_ID", "gemini-2.5-flash")

if IS_DOCKER:
    from utils import get_ssm_parameter, get_aws_info
else:
    from host_adk_agent.utils import get_ssm_parameter, get_aws_info


# AWS とエージェントの設定
account_id, region = get_aws_info()

MONITOR_AGENT_ID = get_ssm_parameter("/monitoragent/agentcore/runtime-id")
MONITOR_PROVIDER_NAME = get_ssm_parameter("/monitoragent/agentcore/provider-name")
MONITOR_AGENT_ARN = (
    f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{MONITOR_AGENT_ID}"
)

WEBSEARCH_AGENT_ID = get_ssm_parameter("/websearchagent/agentcore/runtime-id")
WEBSEARCH_PROVIDER_NAME = get_ssm_parameter("/websearchagent/agentcore/provider-name")
WEBSEARCH_AGENT_ARN = (
    f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{WEBSEARCH_AGENT_ID}"
)


def _create_client_factory(provider_name: str, session_id: str, actor_id: str):
    """オンデマンドで新しい httpx クライアントを作成する遅延クライアントファクトリを作成する。"""

    def _get_authenticated_client() -> httpx.AsyncClient:
        """現在のイベントループで認証済みの新しい httpx クライアントを作成する。"""

        @requires_access_token(
            provider_name=provider_name,
            scopes=[],
            auth_flow="M2M",
            into="bearer_token",
            force_authentication=True,
        )
        def _create_client(bearer_token: str = str()) -> httpx.AsyncClient:
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
                "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actorid": actor_id,
            }

            return httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=300.0),
                headers=headers,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )

        return _create_client()

    class LazyClientFactory:
        """各 create() 呼び出しで新しい httpx クライアントを作成するファクトリ。"""

        def __init__(self):
            # エージェントカード解決用の認証済み httpx クライアントを作成
            # これは RemoteA2aAgent._ensure_httpx_client() で使用される
            initial_client = _get_authenticated_client()

            base_config = ClientConfig(
                httpx_client=initial_client,
                streaming=False,
                supported_transports=[TransportProtocol.jsonrpc],
            )
            self._base_factory = ClientFactory(config=base_config)

        @property
        def _config(self):
            """RemoteA2aAgent 用に _config を公開する。"""
            return self._base_factory._config

        @property
        def _registry(self):
            """RemoteA2aAgent 用に _registry を公開する。"""
            return self._base_factory._registry

        @property
        def _consumers(self):
            """RemoteA2aAgent 用に _consumers を公開する。"""
            return self._base_factory._consumers

        def register(self, label, generator):
            """register 呼び出しをベースファクトリに転送する。"""
            return self._base_factory.register(label, generator)

        def create(self, agent_card):
            """現在のイベントループで新しい httpx クライアントを作成し A2AClient を返す。"""
            # 現在のイベントループコンテキストで新しい httpx クライアントを作成
            httpx_client = _get_authenticated_client()

            # 新しいクライアントで新しい設定を作成
            fresh_config = ClientConfig(
                httpx_client=httpx_client,
                streaming=False,
                supported_transports=[TransportProtocol.jsonrpc],
            )

            # 新しいクライアントで新しいファクトリを作成し、処理を委譲
            fresh_factory = ClientFactory(config=fresh_config)
            return fresh_factory.create(agent_card)

    return LazyClientFactory()


def get_root_agent(session_id: str, actor_id: str):
    # 監視エージェントを作成
    monitor_agent_card_url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{quote(MONITOR_AGENT_ARN, safe='')}/invocations/.well-known/agent-card.json"
    )

    monitor_agent = RemoteA2aAgent(
        name="monitor_agent",
        description="Agent that handles monitoring tasks.",
        agent_card=monitor_agent_card_url,
        a2a_client_factory=_create_client_factory(
            provider_name=MONITOR_PROVIDER_NAME,
            session_id=session_id,
            actor_id=actor_id,
        ),
    )

    # Web 検索エージェントを作成
    websearch_agent_card_url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{quote(WEBSEARCH_AGENT_ARN, safe='')}/invocations/.well-known/agent-card.json"
    )

    websearch_agent = RemoteA2aAgent(
        name="websearch_agent",
        description="Web search agent for finding AWS solutions, documentation, and best practices.",
        agent_card=websearch_agent_card_url,
        a2a_client_factory=_create_client_factory(
            provider_name=WEBSEARCH_PROVIDER_NAME,
            session_id=session_id,
            actor_id=actor_id,
        ),
    )

    # ルートエージェントを作成
    root_agent = Agent(
        model=GOOGLE_MODEL_ID,
        name="root_agent",
        instruction=SYSTEM_PROMPT,
        sub_agents=[monitor_agent, websearch_agent],
    )

    return root_agent


async def get_agent_and_card(session_id: str, actor_id: str):
    """
    ルートエージェントの遅延初期化。
    ワークロード ID が利用可能なエントリーポイント内で呼び出される。
    """

    root_agent = get_root_agent(session_id=session_id, actor_id=actor_id)

    async def get_agents_cards():
        agents_info = {}
        sub_agents = root_agent.sub_agents

        for agent in sub_agents:
            agent_data = {}

            # 解決前にソース URL にアクセス
            if hasattr(agent, "_agent_card_source"):
                agent_data["agent_card_url"] = agent._agent_card_source

            # 解決を確認し、完全なエージェントカードにアクセス
            if hasattr(agent, "_ensure_resolved"):
                await agent._ensure_resolved()

                if hasattr(agent, "_agent_card") and agent._agent_card:
                    card = agent._agent_card
                    agent_data["agent_card"] = card.model_dump(exclude_none=True)

            agents_info[agent.name] = agent_data

        return agents_info

    # エージェントカード情報を取得
    agents_cards = await get_agents_cards()

    return root_agent, agents_cards


if not IS_DOCKER:
    session_id = str(uuid.uuid4())
    actor_id = "webadk"
    root_agent = get_root_agent(session_id=session_id, actor_id=actor_id)

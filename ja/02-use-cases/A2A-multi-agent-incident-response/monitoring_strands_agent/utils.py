from datetime import timedelta
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
import boto3
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ssm = boto3.client("ssm")
agentcore_client = boto3.client("bedrock-agentcore")

GATEWAY_PROVIDER_NAME = os.getenv("GATEWAY_PROVIDER_NAME")


def get_gateway_url() -> str:
    """SSM から Gateway URL を取得する（キャッシュ）。"""

    response = ssm.get_parameter(
        Name="/monitoragent/agentcore/gateway/gateway_url", WithDecryption=True
    )
    logger.info("Gateway URL を SSM から読み込みました")
    return response["Parameter"]["Value"]


def create_gateway_client(workload_token: str) -> MCPClient:
    """OAuth2 認証付きの MCP Gateway クライアントを作成する。"""
    # Get OAuth2 access token for gateway
    response = agentcore_client.get_resource_oauth2_token(
        workloadIdentityToken=workload_token,
        resourceCredentialProviderName=GATEWAY_PROVIDER_NAME,
        scopes=[],
        oauth2Flow="M2M",
        forceAuthentication=False,
    )

    gateway_access_token = response["accessToken"]
    gateway_url = get_gateway_url()

    logger.info("Gateway アクセストークンを取得しました")
    return MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {gateway_access_token}"},
            timeout=timedelta(seconds=120),
        )
    )

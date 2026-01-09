"""エージェント管理用の BedrockAgentCore サービスクライアント。"""

import json
import logging
import os
import time
import urllib.parse
import uuid
from typing import Any, Dict, Optional

import boto3
import requests
from boto3.session import Session

# from ..utils.endpoints import get_control_plane_endpoint, get_data_plane_endpoint

# Environment-configurable constants with fallback defaults
DP_ENDPOINT_OVERRIDE = os.getenv("BEDROCK_AGENTCORE_DP_ENDPOINT")
CP_ENDPOINT_OVERRIDE = os.getenv("BEDROCK_AGENTCORE_CP_ENDPOINT")

boto_session = Session()
DEFAULT_REGION = boto_session.region_name


def get_data_plane_endpoint(region: str = DEFAULT_REGION) -> str:
    return DP_ENDPOINT_OVERRIDE or f"https://bedrock-agentcore.{region}.amazonaws.com"


def get_control_plane_endpoint(region: str = DEFAULT_REGION) -> str:
    return (
        CP_ENDPOINT_OVERRIDE
        or f"https://bedrock-agentcore-control.{region}.amazonaws.com"
    )


def generate_session_id() -> str:
    """セッション ID を生成します。"""
    return str(uuid.uuid4())


def _handle_http_response(response) -> dict:
    response.raise_for_status()
    if "text/event-stream" in response.headers.get("content-type", ""):
        return _handle_streaming_response(response)
    else:
        # Check if response has content
        if not response.content:
            raise ValueError("Empty response from agent endpoint")

        return {"response": response.text}


def _handle_aws_response(response) -> dict:
    if "text/event-stream" in response.get("contentType", ""):
        return _handle_streaming_response(response["response"])
    else:
        try:
            events = []
            for event in response.get("response", []):
                events.append(event)
        except Exception as e:
            events = [f"Error reading EventStream: {e}"]

        response["response"] = events
        return response


def _handle_streaming_response(response) -> Dict[str, Any]:
    logger = logging.getLogger("bedrock_agentcore.stream")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

    content = []
    for line in response.iter_lines(chunk_size=1):
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                line = line[6:]
                logger.info(line)
                content.append(line)

    return {"response": "\n".join(content)}


class BedrockAgentCoreClient:
    """エージェント管理用の Bedrock AgentCore クライアント。"""

    def __init__(self, region: str):
        """Bedrock AgentCore クライアントを初期化します。

        Args:
            region: クライアントの AWS リージョン
        """
        self.region = region
        self.logger = logging.getLogger(f"bedrock_agentcore.runtime.{region}")

        # Get endpoint URLs and log them
        control_plane_url = get_control_plane_endpoint(region)
        data_plane_url = get_data_plane_endpoint(region)

        self.logger.debug(
            "リージョン %s 用の Bedrock AgentCore クライアントを初期化しています", region
        )
        self.logger.debug("コントロールプレーン: %s", control_plane_url)
        self.logger.debug("データプレーン: %s", data_plane_url)

        self.client = boto3.client(
            "bedrock-agentcore-control",
            region_name=region,
            endpoint_url=control_plane_url,
        )
        self.dataplane_client = boto3.client(
            "bedrock-agentcore", region_name=region, endpoint_url=data_plane_url
        )

    def create_agent(
        self,
        agent_name: str,
        image_uri: str,
        execution_role_arn: str,
        network_config: Optional[Dict] = None,
        authorizer_config: Optional[Dict] = None,
        protocol_config: Optional[Dict] = None,
        env_vars: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """新しいエージェントを作成します。"""
        self.logger.info(
            "イメージ URI: %s でエージェント '%s' を作成しています", image_uri, agent_name
        )
        try:
            # Build parameters dict, only including optional configs when present
            params = {
                "agentRuntimeName": agent_name,
                "agentRuntimeArtifact": {
                    "containerConfiguration": {"containerUri": image_uri}
                },
                "roleArn": execution_role_arn,
            }

            if network_config is not None:
                params["networkConfiguration"] = network_config

            if authorizer_config is not None:
                params["authorizerConfiguration"] = authorizer_config

            if protocol_config is not None:
                params["protocolConfiguration"] = protocol_config

            if env_vars is not None:
                params["environmentVariables"] = env_vars

            resp = self.client.create_agent_runtime(**params)
            agent_id = resp["agentRuntimeId"]
            agent_arn = resp["agentRuntimeArn"]
            self.logger.info(
                "エージェント '%s' を正常に作成しました。ID: %s, ARN: %s",
                agent_name,
                agent_id,
                agent_arn,
            )
            return {"id": agent_id, "arn": agent_arn}
        except Exception as e:
            self.logger.error("エージェント '%s' の作成に失敗しました: %s", agent_name, str(e))
            raise

    def update_agent(
        self,
        agent_id: str,
        image_uri: str,
        execution_role_arn: str,
        network_config: Optional[Dict] = None,
        authorizer_config: Optional[Dict] = None,
        protocol_config: Optional[Dict] = None,
        env_vars: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """既存のエージェントを更新します。"""
        self.logger.info(
            "イメージ URI: %s でエージェント ID '%s' を更新しています", image_uri, agent_id
        )
        try:
            # Build parameters dict, only including optional configs when present
            params = {
                "agentRuntimeId": agent_id,
                "agentRuntimeArtifact": {
                    "containerConfiguration": {"containerUri": image_uri}
                },
                "roleArn": execution_role_arn,
            }

            if network_config is not None:
                params["networkConfiguration"] = network_config

            if authorizer_config is not None:
                params["authorizerConfiguration"] = authorizer_config

            if protocol_config is not None:
                params["protocolConfiguration"] = protocol_config

            if env_vars is not None:
                params["environmentVariables"] = env_vars

            resp = self.client.update_agent_runtime(**params)
            agent_arn = resp["agentRuntimeArn"]
            self.logger.info(
                "エージェント ID '%s' を正常に更新しました。ARN: %s", agent_id, agent_arn
            )
            return {"id": agent_id, "arn": agent_arn}
        except Exception as e:
            self.logger.error("エージェント ID '%s' の更新に失敗しました: %s", agent_id, str(e))
            raise

    def create_or_update_agent(
        self,
        agent_id: Optional[str],
        agent_name: str,
        image_uri: str,
        execution_role_arn: str,
        network_config: Optional[Dict] = None,
        authorizer_config: Optional[Dict] = None,
        protocol_config: Optional[Dict] = None,
        env_vars: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """エージェントを作成または更新します。"""
        if agent_id:
            return self.update_agent(
                agent_id,
                image_uri,
                execution_role_arn,
                network_config,
                authorizer_config,
                protocol_config,
                env_vars,
            )
        return self.create_agent(
            agent_name,
            image_uri,
            execution_role_arn,
            network_config,
            authorizer_config,
            protocol_config,
            env_vars,
        )

    def wait_for_agent_endpoint_ready(
        self, agent_id: str, endpoint_name: str = "DEFAULT", max_wait: int = 120
    ) -> str:
        """エージェントエンドポイントが準備完了になるまで待機します。

        Args:
            agent_id: 待機するエージェント ID
            endpoint_name: エンドポイント名、デフォルトは "DEFAULT"
            max_wait: 最大待機時間（秒）

        Returns:
            準備完了時のエージェントエンドポイント ARN
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                resp = self.client.get_agent_runtime_endpoint(
                    agentRuntimeId=agent_id,
                    endpointName=endpoint_name,
                )
                status = resp.get("status", "UNKNOWN")

                if status == "READY":
                    return resp["agentRuntimeEndpointArn"]
                elif status in ["CREATE_FAILED", "UPDATE_FAILED"]:
                    raise Exception(
                        f"Agent endpoint {status.lower().replace('_', ' ')}: {resp.get('failureReason', 'Unknown')}"
                    )
                elif status not in ["CREATING", "UPDATING"]:
                    pass
            except self.client.exceptions.ResourceNotFoundException:
                pass
            except Exception as e:
                if "ResourceNotFoundException" not in str(e):
                    raise
            time.sleep(2)
        return (
            f"Endpoint is taking longer than {max_wait} seconds to be ready, "
            f"please check status and try to invoke after some time"
        )

    def get_agent_runtime(self, agent_id: str) -> Dict:
        """エージェントランタイムの詳細を取得します。

        Args:
            agent_id: 詳細を取得するエージェント ID

        Returns:
            エージェントランタイムの詳細
        """
        return self.client.get_agent_runtime(agentRuntimeId=agent_id)

    def get_agent_runtime_endpoint(
        self, agent_id: str, endpoint_name: str = "DEFAULT"
    ) -> Dict:
        """エージェントランタイムエンドポイントの詳細を取得します。

        Args:
            agent_id: エンドポイントを取得するエージェント ID
            endpoint_name: エンドポイント名、デフォルトは "DEFAULT"

        Returns:
            エージェントエンドポイントの詳細
        """
        return self.client.get_agent_runtime_endpoint(
            agentRuntimeId=agent_id,
            endpointName=endpoint_name,
        )

    def invoke_endpoint(
        self,
        agent_arn: str,
        payload: str,
        session_id: str,
        endpoint_name: str = "DEFAULT",
    ) -> Dict:
        """エージェントエンドポイントを呼び出します。"""
        response = self.dataplane_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier=endpoint_name,
            runtimeSessionId=session_id,
            payload=payload,
        )

        return _handle_aws_response(response)


class HttpBedrockAgentCoreClient:
    """ベアラートークンを使用した HTTP リクエストによるエージェント管理用の Bedrock AgentCore クライアント。"""

    def __init__(self, region: str):
        """HttpBedrockAgentCoreClient を初期化します。

        Args:
            region: クライアントの AWS リージョン
        """
        self.region = region
        self.dp_endpoint = get_data_plane_endpoint(region)
        self.logger = logging.getLogger(f"bedrock_agentcore.http_runtime.{region}")

        self.logger.debug(
            "リージョン %s 用の HTTP Bedrock AgentCore クライアントを初期化しています", region
        )
        self.logger.debug("データプレーン: %s", self.dp_endpoint)

    def invoke_endpoint(
        self,
        agent_arn: str,
        payload,
        session_id: str,
        bearer_token: Optional[str],
        endpoint_name: str = "DEFAULT",
    ) -> Dict:
        """ベアラートークンを使用した HTTP リクエストでエージェントエンドポイントを呼び出します。

        Args:
            agent_arn: 呼び出すエージェント ARN
            payload: 送信するペイロード（dict または string）
            session_id: リクエストのセッション ID
            bearer_token: 認証用ベアラートークン
            endpoint_name: エンドポイント名、デフォルトは "DEFAULT"

        Returns:
            エージェントエンドポイントからのレスポンス
        """
        # Escape agent ARN for URL
        escaped_arn = urllib.parse.quote(agent_arn, safe="")

        # Build URL
        url = f"{self.dp_endpoint}/runtimes/{escaped_arn}/invocations"
        # Headers
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        }

        # Parse the payload string back to JSON object to send properly
        # This ensures consistent payload structure between boto3 and HTTP clients
        try:
            body = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            # Fallback for non-JSON strings - wrap in payload object
            self.logger.warning(
                "ペイロードを JSON として解析できませんでした。ペイロードオブジェクトにラップします"
            )
            body = {"payload": payload}

        try:
            # Make request with timeout
            response = requests.post(
                url,
                params={"qualifier": endpoint_name},
                headers=headers,
                json=body,
                timeout=100,
                stream=True,
            )
            return _handle_http_response(response)
        except requests.exceptions.RequestException as e:
            self.logger.error("エージェントエンドポイントの呼び出しに失敗しました: %s", str(e))
            raise


class LocalBedrockAgentCoreClient:
    """エンドポイント呼び出し用のローカル Bedrock AgentCore クライアント。"""

    def __init__(self, endpoint: str):
        """指定されたエンドポイントでローカルクライアントを初期化します。"""
        self.endpoint = endpoint
        self.logger = logging.getLogger("bedrock_agentcore.http_local")

    def invoke_endpoint(self, payload: str, workload_access_token: str):
        """指定されたパラメータでエンドポイントを呼び出します。"""
        url = f"{self.endpoint}/invocations"

        headers = {
            "Content-Type": "application/json",
            "AgentAccessToken": workload_access_token,
        }

        try:
            body = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            # Fallback for non-JSON strings - wrap in payload object
            self.logger.warning(
                "ペイロードを JSON として解析できませんでした。ペイロードオブジェクトにラップします"
            )
            body = {"payload": payload}

        try:
            # Make request with timeout
            response = requests.post(
                url, headers=headers, json=body, timeout=100, stream=True
            )
            return _handle_http_response(response)
        except requests.exceptions.RequestException as e:
            self.logger.error("エージェントエンドポイントの呼び出しに失敗しました: %s", str(e))
            raise

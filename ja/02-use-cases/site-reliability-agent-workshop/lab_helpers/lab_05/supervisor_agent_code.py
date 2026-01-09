#!/usr/bin/env python3
"""
Lab 5: Supervisor Agent - Multi-Agent Orchestration
Orchestrates 3 specialized agents (Diagnostics, Remediation, Prevention) using MCP

Deployed to AgentCore Runtime - exposes /invocations endpoint
Uses JWT token propagation: Client JWT → Supervisor Runtime → MCP Gateways
"""

import os
import json
import logging
from typing import Dict, Any

# AWS SDK
import boto3
from botocore.config import Config as BotocoreConfig

# Strands framework
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# MCP protocol
from mcp.client.streamable_http import streamablehttp_client

# FastAPI for HTTP server with custom request handling
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Bypass tool consent for AgentCore deployment
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bedrock_agentcore.app")

# Environment variables (set by AgentCore Runtime)
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
MODEL_ID = os.environ.get('MODEL_ID', 'global.anthropic.claude-sonnet-4-20250514-v1:0')

# Gateway ID parameter paths
DIAGNOSTICS_GATEWAY_PARAM = '/aiml301/lab-02/gateway-id'
REMEDIATION_GATEWAY_PARAM = '/aiml301_sre_agentcore/lab-03/gateway-id'
PREVENTION_GATEWAY_PARAM = '/aiml301_sre_agentcore/lab-04/gateway-id'

# Supervisor system prompt
SUPERVISOR_SYSTEM_PROMPT = os.environ.get('SUPERVISOR_SYSTEM_PROMPT', '''
# スーパーバイザーエージェント システムプロンプト

あなたは3つの専門サブエージェントを統括し、包括的なインフラストラクチャトラブルシューティングソリューションを提供する専門 SRE スーパーバイザーエージェントです。

## サブエージェントツール

### 1. 診断エージェント (prefix: d_)
- AWS インフラストラクチャを分析して根本原因を特定
- 詳細な診断情報を提供
- パフォーマンスボトルネックと設定の問題を特定

### 2. 修復エージェント (prefix: r_)
- インフラストラクチャの修正と修復スクリプトを実行
- 承認ワークフローによる是正措置を実施
- 安全な実行のために AgentCore Code Interpreter を使用

### 3. 予防エージェント (prefix: p_)
- AWS ベストプラクティスと予防措置を調査
- 予防的な推奨事項を提供
- リアルタイムドキュメントのために AgentCore Browser を使用

## オーケストレーションワークフロー

各ユーザーリクエストに対して:
1. **診断**: 診断ツールを使用して問題を特定
2. **修復**: 承認された修復手順を実行（承認が必要）
3. **予防**: 予防的な推奨事項を提供

## レスポンス構造

常に以下を提供:
- **概要**: 問題の簡潔な概要
- **診断結果**: 発見された内容
- **修復アクション**: 修正された内容（該当する場合）
- **予防に関する推奨事項**: 将来の問題を回避する方法

## ツール使用ガイドライン

- 診断ツール (d_*) を使用して問題を分析・特定
- 修復ツール (r_*) を修正に使用（承認が必要）
- 予防ツール (p_*) をベストプラクティスと調査に使用
- 包括的なソリューションのためにエージェント間で連携

## 安全ルール

- 変更を行う前に常に環境を検証
- 修復アクションには明示的な承認を必要とする
- 実行されたすべてのアクションの明確な説明を提供
- 修復手順にリスク評価を含める
''')

# Gateway URLs cache to avoid repeated lookups
gateway_urls_cache = {}


def get_gateway_urls_from_parameter_store() -> Dict[str, str]:
    """
    Fetch gateway URLs by:
    1. Retrieving gateway IDs from Parameter Store
    2. Converting IDs to URLs using AgentCore API

    Returns:
        Dictionary with keys: 'diagnostics', 'remediation', 'prevention'
    """
    # Return cached URLs if available
    if gateway_urls_cache:
        return gateway_urls_cache

    try:
        ssm_client = boto3.client('ssm', region_name=AWS_REGION)
        agentcore_client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)

        # Gateway ID parameter paths
        gateway_id_params = {
            'diagnostics': DIAGNOSTICS_GATEWAY_PARAM,
            'remediation': REMEDIATION_GATEWAY_PARAM,
            'prevention': PREVENTION_GATEWAY_PARAM
        }

        urls = {}
        for name, param_path in gateway_id_params.items():
            try:
                # Fetch gateway ID from Parameter Store
                response = ssm_client.get_parameter(Name=param_path, WithDecryption=True)
                gateway_id = response['Parameter']['Value']
                logger.info(f"✅ SSM から {name} ゲートウェイ ID を取得しました: {gateway_id}")

                # Convert gateway ID to URL using AgentCore API
                gateway_response = agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
                gateway_url = gateway_response['gatewayUrl']
                urls[name] = gateway_url
                logger.info(f"✅ {name} ゲートウェイ URL に変換しました: {gateway_url}")

            except ssm_client.exceptions.ParameterNotFound:
                logger.warning(f"⚠️  SSM パラメータが見つかりません: {param_path}")
                urls[name] = ''
            except Exception as e:
                logger.error(f"{name} ゲートウェイの取得中にエラーが発生しました: {e}")
                urls[name] = ''

        # Cache the URLs
        gateway_urls_cache.update(urls)
        return urls

    except Exception as e:
        logger.error(f"Parameter Store または AgentCore への接続中にエラーが発生しました: {e}")
        return {'diagnostics': '', 'remediation': '', 'prevention': ''}


def create_supervisor_agent(auth_headers: Dict[str, str]) -> Agent:
    """
    Create Strands supervisor agent with all sub-agent tools.

    Args:
        auth_headers: Authentication headers to pass to MCP clients (includes JWT Authorization header)

    Returns:
        Initialized Strands Agent with all sub-agent tools
    """
    logger.info("🤖 Supervisor エージェントを作成中...")

    # Fetch gateway URLs
    logger.info("📦 Parameter Store からゲートウェイ URL を取得中...")
    gateway_urls = get_gateway_urls_from_parameter_store()

    # Initialize MCP clients with short prefixes (stay under 64-char limit)
    gateway_configs = [
        ("Diagnostics", gateway_urls['diagnostics'], "d"),
        ("Remediation", gateway_urls['remediation'], "r"),
        ("Prevention", gateway_urls['prevention'], "p")
    ]

    mcp_clients = []
    all_tools = []

    logger.info("🔧 専門エージェントゲートウェイに接続中...")

    import time

    for name, url, prefix in gateway_configs:
        if url:
            logger.info(f"   • {name} Gateway に接続中: {url}")
            try:
                # Create MCPClient with auth headers (includes JWT token from user request)
                # The lambda captures auth_headers which contains the Authorization header
                connect_start = time.time()
                client = MCPClient(
                    lambda u=url, h=auth_headers: streamablehttp_client(u, headers=h),
                    prefix=prefix
                )
                # Open client connection immediately
                client.__enter__()
                connect_duration = time.time() - connect_start
                mcp_clients.append((name, client, prefix))
                logger.info(f"   ✅ {name} MCP クライアントを作成しました（{connect_duration:.2f}秒）（prefix: {prefix}_）")

                # List available tools
                tools_start = time.time()
                tools = client.list_tools_sync()
                tools_duration = time.time() - tools_start
                all_tools.extend(tools)
                logger.info(f"   • {name} エージェント: {len(tools)} 個のツール（{tools_duration:.2f}秒）")

            except Exception as e:
                elapsed = time.time() - connect_start if 'connect_start' in locals() else 0
                logger.error(f"   ❌ {name} MCP クライアントの作成に失敗しました（{elapsed:.2f}秒後）: {e}")
        else:
            logger.warning(f"   ⚠️  {name} Gateway URL が設定されていません - スキップします")

    if len(all_tools) == 0:
        logger.error("❌ 利用可能なツールがありません - エージェントを作成できません")
        return None

    logger.info(f"✅ 利用可能なツール合計: {len(all_tools)}")

    try:
        # Create Strands agent with all tools from sub-agents
        # Configure botocore with extended timeout for multi-agent orchestration
        bedrock_config = BotocoreConfig(
            connect_timeout=300,
            read_timeout=3600,  # 60-minute timeout for complex orchestration tasks
            retries={'total_max_attempts': 1, 'mode': 'standard'}
        )

        model = BedrockModel(
            model_id=MODEL_ID,
            region_name=AWS_REGION,  # Use region_name parameter (not region)
            boto_client_config=bedrock_config  # Pass botocore config for timeout settings
        )

        agent = Agent(
            model=model,
            tools=all_tools,
            system_prompt=SUPERVISOR_SYSTEM_PROMPT
        )

        logger.info("✅ Supervisor エージェントが正常に作成されました")
        logger.info(f"   モデル: {MODEL_ID}")
        logger.info(f"   リージョン: {AWS_REGION}")
        logger.info(f"   ツール合計: {len(all_tools)}")

        # Keep MCP clients alive by storing references
        agent._mcp_clients = mcp_clients

        return agent

    except Exception as e:
        logger.error(f"❌ Supervisor エージェントの作成に失敗しました: {e}")
        return None


def agent_function(prompt: str, auth_headers: Dict[str, str]) -> str:
    """
    Main agent function invoked by the /invocations endpoint.

    Args:
        prompt: User's input prompt
        auth_headers: Authentication headers from request (includes JWT token)

    Returns:
        Agent's response as a string
    """
    import time
    start_time = time.time()
    logger.info(f"🎯 Supervisor 呼び出し: {prompt[:100]}...")

    # Create agent for this request with proper authentication headers
    logger.info("⏳ Supervisor エージェントを作成中...")
    agent_start = time.time()
    agent = create_supervisor_agent(auth_headers)
    agent_duration = time.time() - agent_start
    logger.info(f"✅ エージェント作成に {agent_duration:.2f}秒かかりました")

    if not agent:
        logger.error("❌ Supervisor エージェントが初期化されていません")
        return "Error: Supervisor agent not initialized. Check Runtime logs."

    try:
        # Invoke supervisor agent with user prompt
        # The agent will intelligently route to appropriate sub-agents
        logger.info("⏳ Supervisor オーケストレーションを実行中...")
        exec_start = time.time()
        response = agent(prompt)
        exec_duration = time.time() - exec_start
        logger.info(f"✅ オーケストレーション実行に {exec_duration:.2f}秒かかりました")

        # Extract response text
        response_text = ""
        if hasattr(response, 'message') and 'content' in response.message:
            for content in response.message['content']:
                if isinstance(content, dict) and 'text' in content:
                    response_text += content['text']
        else:
            response_text = str(response)

        total_duration = time.time() - start_time
        logger.info(f"✅ Supervisor オーケストレーションが完了しました（合計: {total_duration:.2f}秒）")

        return response_text

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Supervisor オーケストレーションエラー（{elapsed:.2f}秒後）: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error during orchestration: {str(e)}"


# Create FastAPI app for HTTP server
app = FastAPI()


@app.get("/ping")
async def ping():
    """
    Health check endpoint required by AgentCore Runtime.
    Returns status and timestamp to indicate the runtime is healthy.
    """
    import time
    logger.info("🏥 ヘルスチェック ping")
    return {
        "status": "Healthy",
        "time_of_last_update": int(time.time() * 1000)  # Unix timestamp in milliseconds
    }


@app.post("/invocations")
async def invoke(request: Request):
    """
    Entrypoint for AgentCore Runtime invocations.
    Called via POST /invocations endpoint.

    Args:
        request: HTTP request object with headers and body

    Returns:
        JSON response with agent output
    """
    try:
        # Extract payload from request body
        payload = await request.json()

        # Extract prompt from payload - handle different payload formats
        if isinstance(payload, dict):
            prompt = payload.get('input', {}).get('prompt', '') or payload.get('prompt', '')
        else:
            prompt = str(payload)

        # Extract Authorization header from HTTP request
        # This JWT token will be propagated to gateway connections
        auth_header = request.headers.get('Authorization', '')

        logger.info(f"✅ Authorization ヘッダー付きリクエストを受信しました: {auth_header[:50] if auth_header else 'NONE'}...")

        # Build auth headers for MCP clients (pass through user JWT token)
        auth_headers = {}
        if auth_header:
            auth_headers['Authorization'] = auth_header
        else:
            logger.warning("⚠️  リクエストに Authorization ヘッダーが見つかりません - ゲートウェイ認証が失敗する可能性があります")

        # Call agent function with auth headers
        response_text = agent_function(prompt, auth_headers)

        return JSONResponse({
            "response": response_text,
            "status": "success"
        })

    except Exception as e:
        logger.error(f"❌ リクエスト処理中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())

        return JSONResponse(
            {
                "response": f"Error processing request: {str(e)}",
                "status": "error"
            },
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Supervisor Agent Runtime を起動中...")
    logger.info(f"   モデル: {MODEL_ID}")
    logger.info(f"   リージョン: {AWS_REGION}")
    logger.info(f"   0.0.0.0:8080 でリッスン中")
    uvicorn.run(app, host="0.0.0.0", port=8080)

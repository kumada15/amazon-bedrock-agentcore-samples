#!/usr/bin/env python3
"""
Lab 4: Strands Prevention Agent with AgentCore Browser - AgentCore Runtime Deployment
Uses FastMCP to implement MCP protocol for Gateway-to-Runtime communication

Focuses on:
- MCP protocol implementation with FastMCP
- Prevention-focused infrastructure analysis
- Real-time AWS documentation research using AgentCore Browser
- Proactive recommendations to prevent issues
- Current AWS best practices

Deployed to AgentCore Runtime for serverless execution
"""

import os
import json
import boto3
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

# FastMCP for MCP protocol implementation
from fastmcp import FastMCP

# Strands framework
from strands import Agent
from strands.models import BedrockModel
from strands_tools.browser import AgentCoreBrowser

# Bypass tool consent for AgentCore deployment
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Configure logging with explicit StreamHandler for CloudWatch capture
import sys
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    stream=sys.stdout,
    force=True
)

# Use bedrock_agentcore.app namespace for proper AgentCore logging capture
logger = logging.getLogger("bedrock_agentcore.app")

# Ensure handler exists
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# Environment variables (set by AgentCore Runtime)
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')

# Log environment diagnostics
logger.info("=" * 80)
logger.info("エージェント初期化診断")
logger.info("=" * 80)
logger.info(f"Python バージョン: {sys.version}")
logger.info(f"AWS_REGION: {AWS_REGION}")
logger.info(f"MODEL_ID: {MODEL_ID}")
logger.info(f"DOCKER_CONTAINER: {os.environ.get('DOCKER_CONTAINER', 'NOT SET')}")
logger.info(f"PYTHONUNBUFFERED: {os.environ.get('PYTHONUNBUFFERED', 'NOT SET')}")
logger.info("=" * 80)

# Initialize FastMCP server for AgentCore Runtime
# host="0.0.0.0" - Listens on all interfaces as required by AgentCore
# stateless_http=True - Enables session isolation for enterprise security
mcp = FastMCP("SRE Prevention Agent", host="0.0.0.0", stateless_http=True)

# Global variables for browser and agent
agentcore_browser = None
prevention_agent = None
BROWSER_AVAILABLE = False


def initialize_browser(region=AWS_REGION):
    """Web リサーチ用に AgentCore Browser を初期化する"""
    global agentcore_browser, BROWSER_AVAILABLE

    try:
        logger.debug(f"[診断] リージョン {region} で AgentCoreBrowser の初期化を試行中")
        agentcore_browser = AgentCoreBrowser(region=region)
        BROWSER_AVAILABLE = True
        logger.info("✅ AgentCore Browser が初期化されました")
        logger.debug(f"[診断] ブラウザタイプ: {type(agentcore_browser)}")
        return True
    except Exception as e:
        BROWSER_AVAILABLE = False
        logger.error(f"❌ AgentCore Browser の初期化に失敗しました", exc_info=True)
        logger.warning(f"⚠️ AgentCore Browser が利用できません: {e}")
        return False

# Define FastMCP Tools
logger.debug("[診断] FastMCP ツールを登録中...")


@mcp.tool()
def research_agent(research_topic_query: str):
    """AgentCore Browser を使用して AWS ベストプラクティスと予防戦略を調査する

    リアルタイムの AWS ドキュメントにアクセスして、プロアクティブな改善のためのインフラストラクチャ分析を行います。予防推奨事項、実装ロードマップ、監視ベストプラクティスを提供します。

    Args:
        research_topic_query: 調査するトピック（例: "DynamoDB performance optimization"、"EC2 cost reduction strategies"、"S3 security hardening"）

    Returns:
        予防機会、AWS ベストプラクティス、実装ガイダンスを含む分析結果
    """

    global prevention_agent, agentcore_browser, BROWSER_AVAILABLE

    try:
        logger.debug("[診断] setup_prevention_agent() が呼び出されました")
        logger.info("=" * 80)
        logger.info("📥 リクエスト受信")
        logger.info(f"research_topic_query: {research_topic_query}")
        logger.info("=" * 80)

        logger.debug("[診断] setup_prevention_agent() が呼び出されました")

        if not BROWSER_AVAILABLE:
            logger.debug("[診断] ブラウザが利用できません。初期化中...")
            initialize_browser(AWS_REGION)

        if not BROWSER_AVAILABLE:
            logger.debug("[診断] ブラウザの初期化に失敗しました。None を返します")
            return None

        # Reuse the global browser instance (already initialized)
        logger.debug("[診断] 既存の AgentCoreBrowser インスタンスを使用中...")
        if not agentcore_browser:
            logger.error("[診断] ブラウザフラグは True ですが、インスタンスが None です！")
            return None

        # Setup Bedrock model
        logger.debug(f"[診断] BedrockModel をセットアップ中（model_id: {MODEL_ID}）")
        model = BedrockModel(
            model_id=MODEL_ID,
            streaming=True,
        )

        # Create agent with browser tool (reuse existing browser instance)
        logger.debug("[診断] ブラウザツールを使用して Strands Agent を作成中...")
        system_prompt = """ I need you to analyze our CRM infrastructure for prevention opportunities using the available tool to access AWS documentation. 

    
    Please use the browser tool to access these specific AWS documentation pages and provide analysis:
    
    1. First, use the browser tool to visit: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html
    2. Then visit: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-best-practices.html  
    3. Finally visit: https://docs.aws.amazon.com/wellarchitected/latest/framework/
    
    Based on what you find in the AWS documentation, provide analysis focusing on:
    
    1. **Proactive Infrastructure Management**: Best practices we should implement
    4. **Monitoring and Alerting**: Best practices for proactive monitoring
    
    Provide your analysis with:
    - Executive summary of prevention opportunities
    - Implementation roadmap with AWS best practices
    - Success metrics for measuring prevention effectiveness
    
    """
        prevention_agent = Agent(system_prompt=system_prompt,
            model=model,
            tools=[agentcore_browser.browser]
        )

        logger.info("✅ ブラウザツールを使用した Prevention エージェントが初期化されました")
        logger.debug(f"[診断] エージェントタイプ: {type(prevention_agent)}")
        #logger.debug(f"System prompt length: {len(system_prompt)}")
        #logger.debug(f"Tools: {[tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in prevention_agent.tools]}")


    except Exception as e:
        logger.error(f"❌ Prevention エージェントのセットアップに失敗しました", exc_info=True)
        logger.error(f"例外: {e}")
        return f"Error: Failed to initialize agent - {str(e)}"

    
    return_text=""
    response = prevention_agent(research_topic_query)
    # 3. LOG RAW RESPONSE OBJECT
    logger.info("=" * 80)
    logger.info("📤 生のエージェントレスポンス")
    logger.info(f"レスポンスタイプ: {type(response)}")
    logger.info(f"レスポンス属性: {dir(response)}")
    logger.debug(f"完全なレスポンスオブジェクト: {response}")
    logger.debug(f"Response.message: {response.message}")
    logger.info("=" * 80)
    response_content = response.message.get('content', [])
    if response_content:
        for content in response_content:
            if isinstance(content, dict) and 'text' in content:
                return_text = content['text']

    return return_text


# Note: Browser initialization is LAZY - happens on first tool call
# This prevents blocking during module import and FastMCP server startup

logger.info("=" * 80)
logger.info("🚀 モジュールがロードされました - ブラウザは最初のツール呼び出し時に初期化されます（遅延）")
logger.info("=" * 80)


# Run the FastMCP server
if __name__ == "__main__":
    # AgentCore Runtime requires stateless streamable-HTTP transport (NOT stdio)
    # Per AWS docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html
    # - Transport: streamable-http (stateless, HTTP-based)
    # - Port: 8000 (MCP protocol requirement)
    # - Host: 0.0.0.0 (listen on all interfaces)

    logger.info("=" * 80)
    logger.info("🚀 フェーズ 2: FastMCP サーバー起動")
    logger.info("=" * 80)
    logger.info("ポート 8000 で streamable-http トランスポートを使用して FastMCP サーバーを起動中")
    logger.debug(f"[診断] FastMCP インスタンス: {mcp}")
    logger.debug(f"[診断] FastMCP ツール: {mcp.list_tools() if hasattr(mcp, 'list_tools') else 'メソッドが利用できません'}")
    logger.info("=" * 80)

    try:
        logger.info("🔌 mcp.run(transport='streamable-http') を呼び出し中...")
        mcp.run(transport="streamable-http")
    except Exception as e:
        logger.error("❌ FastMCP サーバーの起動に失敗しました", exc_info=True)
        logger.error(f"例外: {e}")
        raise

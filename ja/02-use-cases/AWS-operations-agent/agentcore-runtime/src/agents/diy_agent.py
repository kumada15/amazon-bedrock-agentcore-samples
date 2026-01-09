#!/usr/bin/env python3
"""
AWS ドキュメントの MCP パターンに正確に従ったシンプルな DIY Agent
参照: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-clients.html
"""

import functools
import logging
import sys
import os
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# AWS documented imports
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from strands_tools import think

# Shared utilities
from agent_shared.config_manager import AgentCoreConfigManager
from agent_shared.auth import setup_oauth, get_m2m_token, is_oauth_available
from agent_shared.memory import setup_memory, get_conversation_context, save_conversation, is_memory_available
from agent_shared.responses import format_diy_response, extract_text_from_event, format_error_response

import asyncio
import time
from agent_shared import mylogger
 
logger = mylogger.get_logger()

# ============================================================================
# EXACT AWS DOCUMENTATION PATTERNS
# ============================================================================

def _create_streamable_http_transport(url, headers=None):
    """
    AWS ドキュメントからの正確な関数
    https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-clients.html
    """
    return streamablehttp_client(url, headers=headers)

# def execute_agent(bedrock_model, prompt):
#     """
#     EXACT pattern from AWS documentation for Strands MCP Client
#     https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-clients.html
#     """
#     # Get configuration
#     config_manager = AgentCoreConfigManager()
#     gateway_url = config_manager.get_gateway_url()
    
#     if not gateway_url or not is_oauth_available():
#         # Fallback to local tools
#         logger.info("🏠 No MCP available - using local tools")
#         local_tools = [get_current_time, echo_message, think]
#         agent = Agent(model=bedrock_model, tools=local_tools)
#         return agent(prompt)
    
#     try:
#         access_token = get_m2m_token()
#         if not access_token:
#             raise Exception("No access token")
        
#         # Create headers for authentication
#         headers = {"Authorization": f"Bearer {access_token}"}
        
#         # EXACT AWS pattern: Create MCP client with functools.partial
#         mcp_client = MCPClient(functools.partial(
#             _create_streamable_http_transport,
#             url=gateway_url,
#             headers=headers
#         ))
        
#         # EXACT AWS pattern: Use context manager
#         with mcp_client:
#             tools = mcp_client.list_tools_sync()
            
#             # Add local tools
#             all_tools = [get_current_time, echo_message, think]
#             if tools:
#                 all_tools.extend(tools)
#                 logger.info(f"🛠️ Using {len(tools)} MCP tools + local tools")
            
#             logger.info("$$$$$$$$$$$$$$$$$$$$")
#             logger.info(tools)
#             logger.info("$$$$$$$$$$$$$$$$$$$$")
#             agent = Agent(model=bedrock_model, tools=all_tools)
#             return agent(prompt)
            
#     except Exception as e:
#         logger.error(f"❌ MCP execution failed: {e}")
#         # Fallback to local tools
#         local_tools = [get_current_time, echo_message, think]
#         agent = Agent(model=bedrock_model, tools=local_tools)
#         return agent(prompt)

async def execute_agent_streaming(bedrock_model, prompt):
    """
    AWS ドキュメント化されたパターンのストリーミング版
    """
    # Get configuration
    config_manager = AgentCoreConfigManager()
    gateway_url = config_manager.get_gateway_url()
    
    # Define system prompt for the agent
    system_prompt = """あなたは専用ツールを通じて AWS リソースへの読み取り専用アクセスを持つ AWS 運用アシスタントです。

🚨 必須動作: 絵文字を使用した即座の進捗更新 🚨

すべてのリクエストで以下のパターンを必ず守ってください:

1. 「[タスク]をお手伝いします。以下が私のプランです:」と番号付きステップで開始する
2. 絵文字を一貫して使用: 各チェック前に🔍、各結果後に✅
3. すべてのツール呼び出し後、即座に✅で結果を提示する
4. 必要に応じて echo_message ツールを使用して進捗更新を送信する
5. 進捗更新なしに複数のツールを実行しない

必須レスポンスパターン:
```
AWS アカウントの概要をお伝えします。以下が私のプランです:
1. EC2 インスタンスを確認
2. S3 バケットを一覧表示
3. Lambda 関数をレビュー
4. IAM リソースを確認
5. データベースを確認

🔍 EC2 インスタンスを確認中...
[EC2 ツールを実行]
✅ 2つの EC2 インスタンスを発見: 1つ実行中 (t3.large)、1つ停止中 (t3a.2xlarge)

🔍 S3 バケットを確認中...
[S3 ツールを実行]
✅ 47 個の S3 バケットを発見 - サービスと個人ストレージの混合

🔍 次に Lambda 関数をレビュー中...
[Lambda ツールを実行]
✅ 5つの Lambda 関数を発見（MCP ツールと API ハンドラーを含む）

[すべてのタスクでこのパターンを継続]

📊 **完全な概要:**
[最終的な詳細サマリー]
```

絶対的なルール - 例外なし:
- すべてのツール実行前に🔍を使用
- すべてのツール結果後に即座に✅を使用
- 各ツール呼び出し後に具体的な結果を提示
- 中間更新なしに複数のツール呼び出しをバッチ処理しない
- 必要に応じて echo_message ツールで進捗更新を送信
- 複雑な操作を小さなアトミックタスクに分解

アトミックタスク分解戦略:
複雑な AWS クエリを非常に小さなアトミックタスクに分解し、即座の進捗更新とともにステップバイステップで実行することが役割です。

実行ワークフロー:
1. **まず考える**: think ツールを使用して複雑なリクエストをアトミックステップに分解
2. **プランを発表**: 番号付きステップでステップバイステップのプランをユーザーに伝える
3. **更新付きで実行**: 各ステップで:
   - 「🔍 [これから確認すること]...」と言う
   - ツールを実行
   - 即座に「✅ [発見したこと]」と言う
4. **最終サマリー**: 📊で包括的なサマリーを提示

ツール使用戦略:
1. **think**: 複雑なリクエストをアトミックステップに分解するために常に最初に使用
2. **echo_message**: ストリーミングが機能しない場合の進捗アナウンスに使用
3. **AWS ツール**: 一度に1つのアトミック操作を実行
4. **get_current_time**: 時間ベースのクエリが必要な場合に使用
5. **stop**: 15回のツール呼び出しを超えた場合にサマリーと共に使用
6. **handoff_to_user**: ガイダンスが必要な場合に使用

進捗インジケーター（必須）:
- 🤔 思考/計画中
- 🔍 確認/クエリの直前（各ツールで必須）
- ✅ タスク完了（各ツールで必須）
- 📊 最終サマリー
- ⚠️ 問題発見
- 💡 推奨事項

アトミックタスクの例:

❌ 間違い - 進捗更新なし:
「AWS リソースを確認します... [長い沈黙] ...概要はこちらです」

✅ 正解 - 進捗更新あり:
「AWS リソースを確認します。以下が私のプランです:
1. EC2 インスタンス
2. S3 バケット
3. Lambda 関数

🔍 EC2 インスタンスを確認中...
✅ 2つのインスタンスを発見: 1つ実行中、1つ停止中

🔍 S3 バケットを確認中...
✅ 各種サービスにわたる47個のバケットを発見

🔍 次に Lambda 関数をレビュー中...
✅ MCP ツールを含む5つの関数を発見

📊 **完全な概要:** [詳細サマリー]」

成功のための重要要素:
- すべてのツール実行の前に🔍アナウンスが必要
- すべてのツール結果の後に✅サマリーが必要
- 進捗更新で具体的な数字と詳細を使用
- 一貫した絵文字使用を維持
- 即座のフィードバックを提供し、操作を黙ってバッチ処理しない

利用可能な AWS サービス: EC2、S3、Lambda、CloudFormation、IAM、RDS、CloudWatch、Cost Explorer、ECS、EKS、SNS、SQS、DynamoDB、Route53、API Gateway、SES、Bedrock、SageMaker。

注意: 絵文字を使用した進捗更新は必須であり、オプションではありません！上記の正確なパターンに従ってください。
"""
    # Fallback to local tools if gateway or oauth is not working
    if not gateway_url or not is_oauth_available():
        logger.info("MCP が利用できません - ローカルストリーミングを使用します")
        local_tools = [get_current_time, echo_message, think]
        #agent = Agent(model=bedrock_model, tools=local_tools, system_prompt=system_prompt)
        agent = Agent(model=bedrock_model, tools=local_tools)
        async for event in agent.stream_async(prompt):
            yield event
        return
    
    try:
        access_token = get_m2m_token()
        if not access_token:
            raise Exception("No access token")
        
        # Create headers for authentication
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # EXACT AWS pattern: Create MCP client with functools.partial
        mcp_client = MCPClient(functools.partial(
            _create_streamable_http_transport,
            url=gateway_url,
            headers=headers
        ))
        
        # EXACT AWS pattern: Use context manager
        with mcp_client:
            tools = mcp_client.list_tools_sync()
            
            # Add local tools
            all_tools = [get_current_time, echo_message]
            if tools:
                all_tools.extend(tools)
                logger.info(f"ストリーミング（{len(tools)} 個の MCP ツール + ローカルツール）")
            
            logger.info("$$$$$$$$$$$$$$$$$$$$")
            logger.info(f"全ツール数: {len(all_tools)}")
            logger.info("$$$$$$$$$$$$$$$$$$$$")

            agent = Agent(model=bedrock_model, tools=all_tools, system_prompt=system_prompt)
            async for event in agent.stream_async(prompt):
                    #logger.info("=" * 50)
                    #logger.info(f"Raw event: {event}")
                    #logger.info(f"Event type: {type(event)} at {time.time()}")
                    # Extract delta text if it's a contentBlockDelta event
                    if isinstance(event, dict) and 'event' in event:
                        inner_event = event['event']
                        if 'contentBlockDelta' in inner_event:
                            delta = inner_event['contentBlockDelta'].get('delta', {})
                            if 'text' in delta:
                                logger.info(delta['text'])
                    #logger.info("*" * 50)
                    yield event
                
    except Exception as e:
        logger.error(f"MCP ストリーミングに失敗しました: {e}")
        # Fallback to local streaming
        logger.info("ローカルストリーミングにフォールバックします")
        local_tools = [get_current_time, echo_message, think]
        agent = Agent(model=bedrock_model, tools=local_tools)
        async for event in agent.stream_async(prompt):
            logger.info('@@@@@@@@@@@@@@@@@@@@')
            logger.info(tools)
            logger.info('@@@@@@@@@@@@@@@@@@@@')
            yield event

# ============================================================================
# LOCAL TOOLS
# ============================================================================

@tool(name="get_current_time", description="Get the current date and time")
def get_current_time() -> str:
    """現在のタイムスタンプを取得する"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

@tool(name="echo_message", description="Echo back a message for testing")
def echo_message(message: str) -> str:
    """提供されたメッセージをエコーバックする"""
    return f"Echo: {message}"

# ============================================================================
# CONFIGURATION
# ============================================================================

config_manager = AgentCoreConfigManager()
model_settings = config_manager.get_model_settings()

logger.info(f"Simple DIY Agent（モデル: {model_settings['model_id']}）")

# ============================================================================
# STREAMING RESPONSE
# ============================================================================

async def stream_response(user_message: str, session_id: str = None, actor_id: str = "user") -> AsyncGenerator[str, None]:
    """AWS ドキュメント化されたパターンを使用してエージェントレスポンスをストリームする"""
    response_parts = []
    
    try:
        logger.info(f"処理中: {user_message[:50]}...")
        
        # Get conversation context if available
        context = ""
        if is_memory_available() and session_id:
            context = get_conversation_context(session_id, actor_id)
        
        # Prepare message with context
        final_message = user_message
        if context:
            final_message = f"{context}\n\nCurrent user message: {user_message}"
        
        # Create model with longer timeout for streaming
        model = BedrockModel(**model_settings, streaming=True, timeout=900)
        
        # Use AWS documented streaming pattern
        last_event_time = time.time()
        
        async for event in execute_agent_streaming(model, final_message):
            # Format and yield response
            formatted = format_diy_response(event)
            yield formatted
            last_event_time = time.time()
            
            # Collect text for memory
            text = extract_text_from_event(event)
            if text:
                response_parts.append(text)
                
            # Brief pause to prevent overwhelming the client
            #await asyncio.sleep(0.01)
        
        # Save to memory if available
        if is_memory_available() and session_id and response_parts:
            full_response = ''.join(response_parts)
            save_conversation(session_id, user_message, full_response, actor_id)
            logger.info("会話を保存しました")
            
    except Exception as e:
        logger.error(f"ストリーミングエラー: {e}")
        error_response = format_error_response(str(e), "diy")
        yield error_response

# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize():
    """OAuth と Memory を初期化する"""
    logger.info("Simple DIY Agent を初期化中...")
    
    if setup_oauth():
        logger.info("OAuth の初期化が完了しました")
    else:
        logger.warning("OAuth が利用できません")
    
    if setup_memory():
        logger.info("Memory の初期化が完了しました")
    else:
        logger.warning("Memory が利用できません")
    
    logger.info("Simple DIY Agent の準備が完了しました")

# Initialize on startup
try:
    initialize()
except Exception as e:
    logger.error(f"初期化に失敗しました: {e}")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Simple DIY Agent (AWS Pattern)", version="1.0.0")

class InvocationRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    actor_id: str = "user"

@app.post("/invocations")
async def invoke_agent(request: InvocationRequest):
    """正確な AWS MCP パターンを使用した AgentCore Runtime エンドポイント"""
    logger.info("呼び出しリクエストを受信しました")

    try:
        return StreamingResponse(
            stream_response(request.prompt, request.session_id, request.actor_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"#,
                #"X-Accel-Buffering": "no",  # Disable nginx buffering
                #"Transfer-Encoding": "chunked"
            }
        )
        
    except Exception as e:
        logger.error(f"リクエストに失敗しました: {e}")
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")

@app.get("/ping")
async def ping():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "agent_type": "diy_simple", "pattern": "aws_exact"}

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("AWS パターンで Simple DIY Agent を起動中...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

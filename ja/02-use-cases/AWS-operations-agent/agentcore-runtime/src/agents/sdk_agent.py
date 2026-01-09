#!/usr/bin/env python3
"""
BedrockAgentCoreApp を使用した AgentCore Runtime 用の SDK Agent
DIY エージェントとの一貫性を保つために共有ビジネスロジックを使用する
"""

# ============================================================================
# IMPORTS
# ============================================================================

from bedrock_agentcore.runtime import BedrockAgentCoreApp
import functools
import json
import logging
import sys
import os

# Add paths for both container and local development environments
current_dir = os.path.dirname(os.path.abspath(__file__))

# Detect container vs local environment
if current_dir.startswith('/app'):
    # Container environment - AgentCore CLI packages everything in /app
    sys.path.append('/app')  # For agent_shared
else:
    # Local development environment
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    sys.path.append(project_root)  # For shared.config_manager
    sys.path.append(os.path.dirname(current_dir))  # For agent_shared

# Strands imports
from strands import Agent, tool
from strands.models import BedrockModel

# Use AWS documented Strands MCP client pattern
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

# Import loop control tools from strands_tools
from strands_tools import think, stop, handoff_to_user

# Shared configuration manager (agent-local copy for CLI packaging)
from agent_shared.config_manager import AgentCoreConfigManager

# Agent-specific shared utilities
from agent_shared.auth import setup_oauth, get_m2m_token, is_oauth_available
from agent_shared.memory import setup_memory, get_conversation_context, save_conversation, is_memory_available
from agent_shared.responses import format_sdk_response, extract_text_from_event, format_error_response

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# EXACT AWS DOCUMENTATION PATTERNS
# ============================================================================

def _create_streamable_http_transport(url, headers=None):
    """
    AWS ドキュメントからの正確な関数
    https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-clients.html
    """
    return streamablehttp_client(url, headers=headers)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Initialize configuration manager
config_manager = AgentCoreConfigManager()

# Load model settings
model_settings = config_manager.get_model_settings()
gateway_url = config_manager.get_gateway_url()

logger.info(f"SDK Agent（CLI デプロイ可能）を起動中（モデル: {model_settings['model_id']}）")
if gateway_url:
    logger.info(f"Gateway 設定済み: {gateway_url}")
else:
    logger.info("🏠 No gateway configured - using local tools only")

# ============================================================================
# TOOLS
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
# STREAMING WITH MCP CONTEXT MANAGEMENT
# ============================================================================

async def execute_agent_streaming_sdk(bedrock_model, prompt):
    """
    SDK エージェント用の AWS ドキュメント化されたパターンのストリーミング版
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

利用可能な AWS サービス: EC2、S3、Lambda、CloudFormation、IAM、RDS、CloudWatch、Cost Explorer、ECS、EKS、SNS、SQS、DynamoDB、Route53、API Gateway、SES、Bedrock、SageMaker。

注意: 絵文字を使用した進捗更新は必須であり、オプションではありません！上記の正確なパターンに従ってください。
"""
    
    # Fallback to local tools if gateway or oauth is not working
    if not gateway_url or not is_oauth_available():
        logger.info("MCP が利用できません - ローカルストリーミングを使用します")
        local_tools = [get_current_time, echo_message, think, stop, handoff_to_user]
        agent = Agent(model=bedrock_model, tools=local_tools, system_prompt=system_prompt)
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
            all_tools = [get_current_time, echo_message, think, stop, handoff_to_user]
            if tools:
                all_tools.extend(tools)
                logger.info(f"SDK ストリーミング（{len(tools)} 個の MCP ツール + ローカルツール）")
            
            agent = Agent(model=bedrock_model, tools=all_tools, system_prompt=system_prompt)
            async for event in agent.stream_async(prompt):
                yield event
                
    except Exception as e:
        logger.error(f"MCP ストリーミングに失敗しました: {e}")
        # Fallback to local streaming
        logger.info("ローカルストリーミングにフォールバックします")
        local_tools = [get_current_time, echo_message, think, stop, handoff_to_user]
        agent = Agent(model=bedrock_model, tools=local_tools, system_prompt=system_prompt)
        async for event in agent.stream_async(prompt):
            yield event

# ============================================================================
# AGENT SETUP
# ============================================================================

def create_strands_agent(use_mcp=True):
    """AWS 準拠パターンを使用してローカルツールとオプションで MCP ツールを持つ Strands エージェントを作成する"""
    # Create BedrockModel
    model = BedrockModel(**model_settings)

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
    
    # Start with local tools including loop control tools
    tools = [get_current_time, echo_message, think, stop, handoff_to_user]
    
    # Add MCP tools if available and requested - but don't try to use them in agent creation
    # The MCP client context manager issue means we should fall back to local tools for now
    if use_mcp and gateway_url and is_oauth_available():
        logger.info("MCP ツールがリクエストされましたが、コンテキストマネージャーの制約によりローカルツールのみ使用します")
        logger.info("SDK Agent は信頼性の高い動作のためにローカルツールを使用します")
    else:
        if not gateway_url:
            logger.info("Gateway が設定されていません - ローカルツールのみ使用します")
        elif not is_oauth_available():
            logger.info("OAuth が利用できません - ローカルツールのみ使用します")
        else:
            logger.info(f"MCP 無効 - {len(tools)} 個のローカルツールのみ使用します")
    
    logger.info(f"SDK Agent を作成しました（{len(tools)} 個のローカルツール）")
    return Agent(model=model, tools=tools, system_prompt=system_prompt)

# ============================================================================
# AGENTCORE APP
# ============================================================================

app = BedrockAgentCoreApp()

# ============================================================================
# STREAMING
# ============================================================================

def extract_prompt_from_payload(payload):
    """直接形式とラップ形式の両方をサポートしてペイロードからプロンプトを抽出する"""
    try:
        # Direct format: {"prompt": "message", "session_id": "optional", "actor_id": "user"}
        if isinstance(payload, dict) and "prompt" in payload:
            return payload.get("prompt", "No prompt provided"), payload.get("session_id"), payload.get("actor_id", "user")
        
        # Wrapped format: {"payload": "{\"prompt\": \"message\"}"}
        if isinstance(payload, dict) and "payload" in payload:
            try:
                inner_payload = json.loads(payload["payload"])
                return inner_payload.get("prompt", "No prompt provided"), inner_payload.get("session_id"), inner_payload.get("actor_id", "user")
            except json.JSONDecodeError:
                logger.warning("ラップされたペイロード内の JSON が無効です")
                return "Invalid payload format", None, "user"
        
        # Fallback
        logger.warning(f"予期しないペイロード形式: {type(payload)}")
        return "No prompt found in input, please provide a JSON payload with prompt key", None, "user"
        
    except Exception as e:
        logger.error(f"プロンプトの抽出に失敗しました: {e}")
        return f"Error processing payload: {str(e)}", None, "user"

# ============================================================================
# SDK APP
# ============================================================================

# Using automatic ping handler from BedrockAgentCoreApp

@app.entrypoint
async def invoke(payload):
    """ユーザー入力を処理し、Memory サポートを含むレスポンスを返す"""
    logger.info("SDK 呼び出しリクエストを受信しました")
    
    response_parts = []
    
    try:
        # Extract prompt and metadata from payload
        user_message, session_id, actor_id = extract_prompt_from_payload(payload)
        
        logger.info(f"SDK Agent 呼び出し: {user_message[:50]}...")
        logger.info(f"セッション: {session_id}, アクター: {actor_id}")
        
        # Get conversation context if memory is available
        context = ""
        if is_memory_available() and session_id:
            context = get_conversation_context(session_id, actor_id)
            if context:
                logger.info(f"コンテキストを取得しました（長さ: {len(context)} 文字）")
        
        # Prepare final message with context
        final_message = user_message
        if context:
            final_message = f"{context}\n\nCurrent user message: {user_message}"
        
        # Create model with streaming enabled
        model = BedrockModel(**model_settings, streaming=True, timeout=900)
        
        # Use the streaming function with proper MCP context management
        async for event in execute_agent_streaming_sdk(model, final_message):
            # Format event for SDK (keeps format_sdk_response)
            formatted = format_sdk_response(event)
            yield formatted
            
            # Extract text for memory storage
            text = extract_text_from_event(event)
            if text:
                response_parts.append(text)
        
        # Save conversation to memory after streaming
        if is_memory_available() and session_id and response_parts:
            full_response = ''.join(response_parts)
            save_conversation(session_id, user_message, full_response, actor_id)
            logger.info("会話の保存に成功しました")
            
    except Exception as e:
        logger.error(f"SDK ストリーミングエラー: {e}")
        error_response = format_error_response(str(e), "sdk")
        yield error_response

# ============================================================================
# STARTUP INITIALIZATION
# ============================================================================

def initialize_services():
    """起動時にサービスを初期化する"""
    logger.info("SDK Agent を起動中...")
    
    # Initialize OAuth
    if setup_oauth():
        logger.info("OAuth の初期化が完了しました")
    else:
        logger.warning("OAuth が利用できません")
    
    # Initialize Memory
    if setup_memory():
        logger.info("Memory の初期化が完了しました")
    else:
        logger.warning("Memory が利用できません")
    
    logger.info("SDK Agent の準備が完了しました（ストリーミングパターン使用）")

def cleanup_resources():
    """シャットダウン時にリソースをクリーンアップする"""
    logger.info("SDK Agent をシャットダウン中...")
    logger.info("SDK Agent のシャットダウンが完了しました")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("SDK Agent を起動中...")
    
    # Initialize services before starting the app
    initialize_services()
    
    try:
        app.run()
    finally:
        # Clean up resources on shutdown
        cleanup_resources()
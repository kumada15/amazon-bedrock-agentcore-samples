"""
SRE AI エージェント - Streamlit チャットアプリケーション
ストリーミングサポート付きの Strands スーパーバイザーエージェント用チャットインターフェース。
すべての依存関係をインラインに持つ自己完結型バージョン。
"""

import streamlit as st
import json
from typing import Generator

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import boto3


# ============================================================================
# MCP CLIENT SETUP FUNCTIONS (inlined from mcp_client_setup.py)
# ============================================================================

def load_gateway_config():
    """
    gateway_config.json から Gateway 設定を読み込む

    Returns:
        dict: Gateway 設定
    """
    with open("gateway_config.json", "r") as f:
        return json.load(f)


def get_access_token(config):
    """
    boto3 の直接呼び出しを使用して Cognito から OAuth アクセストークンを取得する

    Args:
        config: Gateway 設定 Dict

    Returns:
        str: アクセストークン
    """
    client_info = config["client_info"]
    cognito = boto3.client('cognito-idp', region_name=config["region"])
    
    try:
        response = cognito.initiate_auth(
            ClientId=client_info["client_id"],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': client_info["username"],
                'PASSWORD': client_info["password"]
            }
        )
        return response['AuthenticationResult']['AccessToken']
    except Exception as e:
        raise Exception(f"Failed to get access token: {str(e)}")


def create_mcp_client(gateway_url, access_token):
    """
    OAuth 認証付きの MCP クライアントを作成する

    Args:
        gateway_url: Gateway MCP エンドポイント URL
        access_token: Cognito からの OAuth アクセストークン

    Returns:
        MCPClient: 設定済みの MCP クライアント
    """
    return MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
    )


def get_all_tools(mcp_client):
    """
    ページネーションサポート付きで Gateway からすべてのツールを取得する

    Args:
        mcp_client: MCPClient インスタンス

    Returns:
        list: 利用可能なすべての MCP ツール
    """
    tools = []
    pagination_token = None
    
    while True:
        result = mcp_client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(result)
        
        if result.pagination_token is None:
            break
        pagination_token = result.pagination_token
    
    return tools


# ============================================================================
# SUPERVISOR AGENT FUNCTIONS (inlined from supervisor_agent.py)
# ============================================================================

def create_supervisor_agent(model_id, tools, region="us-west-2"):
    """
    ストリーミング有効の Strands スーパーバイザーエージェントを作成する

    Args:
        model_id: Bedrock モデル識別子または推論プロファイル ARN
        tools: MCP ツールのリスト
        region: AWS リージョン

    Returns:
        Agent: 設定済みの Strands エージェント
    """
    # Use cross-region inference profile for Claude 3.7 Sonnet
    inference_profile = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    
    model = BedrockModel(
        model_id=inference_profile,
        streaming=True,  # Enable streaming
    )
    
    system_prompt = """
        # Supervisor Agent システムプロンプト

あなたは3つの専門サブエージェントをオーケストレーションして、完全なインフラストラクチャトラブルシューティングソリューションを提供するエキスパート SRE Supervisor Agent です。

## サブエージェントツール

### 1. Diagnostic Agent
- AWS インフラストラクチャを分析して根本原因を特定
- 詳細な診断情報を提供
- パフォーマンスボトルネックと設定問題を特定

### 2. Remediation Agent
- インフラストラクチャの修正と修復スクリプトを実行
- 承認ワークフローで是正アクションを実装
- 安全な実行のために AgentCore Code Interpreter を使用

### 3. Prevention Agent
- AWS ベストプラクティスと予防措置を調査
- 予防的な推奨を提供
- リアルタイムドキュメント用に AgentCore Browser を使用

## オーケストレーションワークフロー

各ユーザーリクエストに対して:
1. **診断**: 診断ツールを使用して問題を特定
2. **修復**: 承認された修復手順を実行
3. **予防**: 予防的な推奨を提供
4. 問題が存在しない場合、他の問題を探すことに逸脱しない

## レスポンス構造

常に提供する:
- **概要**: 問題の簡潔な概要
- **診断結果**: 発見された内容
- **修復アクション**: 修正された内容（該当する場合）
- **予防推奨**: 今後の問題を回避する方法

## ツール使用ガイドライン

- 診断ツールを使用して問題を分析・特定
- 修正には修復ツールを使用（承認が必要）
- ベストプラクティスと調査には予防ツールを使用
- 包括的なソリューションのためにエージェント間で連携

## 安全ルール

- 変更を加える前に必ず環境を検証
- 修復アクションには明示的な承認を要求
- 実行されたすべてのアクションについて明確な説明を提供
- 修復手順のリスク評価を含める
"""
    
    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )


# Page configuration
st.set_page_config(
    page_title="SRE AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .status-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .status-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .status-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .status-info {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .thinking-indicator {
        font-style: italic;
        color: #6c757d;
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def initialize_agent():
    """エージェントを初期化してセッション状態に保存する"""
    if 'agent_initialized' not in st.session_state:
        with st.spinner("🔧 Initializing SRE AI Agent..."):
            try:
                # Load configuration
                config = load_gateway_config()
                st.session_state.config = config
                
                # Get OAuth token
                access_token = get_access_token(config)
                st.session_state.access_token = access_token
                
                # Extract email from JWT token
                import base64
                try:
                    # Decode JWT payload (second part)
                    payload = access_token.split('.')[1]
                    # Add padding if needed
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = base64.b64decode(payload)
                    token_data = json.loads(decoded)
                    st.session_state.user_email = token_data.get('email', token_data.get('username', 'Unknown'))
                except Exception as jwt_error:
                    st.session_state.user_email = config['client_info']['username']
                
                # Create MCP client
                try:
                    mcp_client = create_mcp_client(config['gateway_url'], access_token)
                    st.session_state.mcp_client = mcp_client
                    
                    # Initialize MCP client context
                    st.session_state.mcp_client.__enter__()
                    
                    # Get tools
                    tools = get_all_tools(mcp_client)
                    st.session_state.tools = tools
                except Exception as mcp_error:
                    raise Exception(f"MCP client initialization failed: {str(mcp_error)}")
                
                # Create agent
                model_id = "anthropic.claude-3-7-sonnet-20250219-v1:0"
                agent = create_supervisor_agent(model_id, tools, config['region'])
                st.session_state.agent = agent
                
                st.session_state.agent_initialized = True
                st.session_state.initialization_error = None
                
            except FileNotFoundError:
                st.session_state.agent_initialized = False
                st.session_state.initialization_error = "gateway_config.json not found. Please run Section 9.1 in the notebook first."
            except Exception as e:
                st.session_state.agent_initialized = False
                import traceback
                st.session_state.initialization_error = f"{str(e)}\n\nDetails:\n{traceback.format_exc()}"


def stream_agent_response(prompt: str, message_placeholder) -> str:
    """
    コールバックハンドラーを使用してエージェントレスポンスをストリーミングする

    Args:
        prompt: ユーザー入力プロンプト
        message_placeholder: 表示更新用の Streamlit プレースホルダー

    Returns:
        str: 完全なレスポンステキスト
    """
    agent = st.session_state.agent
    response_data = {
        "text": "", 
        "last_update": 0, 
        "tools_shown": set(), 
        "in_tool_construction": False,
        "tool_start_times": {}
    }
    
    def streaming_callback(**kwargs):
        """ストリーミングイベント用コールバックハンドラー - エージェントスレッドで実行"""
        import time
        
        # Handle text streaming
        if "data" in kwargs:
            data = kwargs["data"]
            
            # Detect if we're in tool input construction phase
            if data.strip().startswith('{') or data.strip().startswith('"'):
                response_data["in_tool_construction"] = True
                return  # Skip JSON construction
            elif response_data["in_tool_construction"] and not data.strip().endswith('}'):
                return  # Still in JSON construction
            else:
                response_data["in_tool_construction"] = False
                response_data["text"] += data
                response_data["last_update"] = time.time()
        
        # Handle tool usage - show when tool execution starts (has toolUseId)
        elif "current_tool_use" in kwargs:
            tool_use = kwargs["current_tool_use"]
            tool_id = tool_use.get("toolUseId")
            tool_name = tool_use.get("name")
            
            # Only show when we have both ID and name (tool is starting execution)
            if tool_id and tool_name and tool_id not in response_data["tools_shown"]:
                response_data["tools_shown"].add(tool_id)
                response_data["tool_start_times"][tool_id] = time.time()
                tool_text = f"\n\n🔧 **Using tool:** `{tool_name}`\n\n"
                response_data["text"] += tool_text
                response_data["last_update"] = time.time()
                response_data["in_tool_construction"] = False
        
        # Handle tool completion (when message is created after tool use)
        elif "message" in kwargs:
            message = kwargs["message"]
            if message.get("role") == "user":
                # Check for tool results in the message
                content = message.get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_id = item.get("tool_use_id")
                        if tool_id in response_data["tool_start_times"]:
                            elapsed = time.time() - response_data["tool_start_times"][tool_id]
                            timing_text = f"⏱️ *Completed in {elapsed:.2f}s*\n\n"
                            response_data["text"] += timing_text
                            response_data["last_update"] = time.time()
                            del response_data["tool_start_times"][tool_id]
    
    try:
        import time
        import threading
        
        # Start agent in background thread
        agent_thread = threading.Thread(
            target=lambda: agent(prompt, callback_handler=streaming_callback)
        )
        agent_thread.start()
        
        # Update UI from main thread while agent runs
        while agent_thread.is_alive():
            if response_data["text"]:
                message_placeholder.markdown(response_data["text"] + "▌")
            time.sleep(0.1)
        
        # Wait for thread to complete
        agent_thread.join()
        
        # Display final response without cursor
        final_response = response_data["text"]
        message_placeholder.markdown(final_response)
        return final_response
        
    except Exception as e:
        import traceback
        error_msg = f"\n\n❌ Error: {str(e)}\n```\n{traceback.format_exc()}\n```"
        message_placeholder.markdown(error_msg)
        return error_msg


def main():
    """メインアプリケーション関数"""
    
    # Header
    st.markdown('<div class="main-header">🤖 SRE AI Agent</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Initialize agent
    initialize_agent()
    
    # Sidebar
    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown("""
        **SRE AI Agent** is a Strands-based supervisor agent that orchestrates three specialized agents.
        
        **Features:**
        - 🔍 Diagnostics Agent - Analyzes logs and metrics
        - 🔧 Remediation Agent - Executes fixes with Code Interpreter
        - 🛡️ Prevention Agent - Researches best practices with Browser
        - 🔄 Real-time streaming responses
        - 🔐 OAuth authentication via Cognito
        """)
        
        st.markdown("---")
        
        # Status information
        if st.session_state.get('agent_initialized'):
            st.markdown('<div class="status-box status-success">✅ Agent Ready</div>', unsafe_allow_html=True)
            
            config = st.session_state.config
            st.markdown("**Configuration:**")
            st.text(f"Gateway: {config['gateway_id']}")
            st.text(f"Region: {config['region']}")
            
            # Show logged in user from JWT token
            st.markdown("**Logged in as:**")
            user_email = st.session_state.get('user_email', 'Unknown')
            st.text(f"👤 {user_email}")
            
            if 'tools' in st.session_state:
                st.markdown(f"**Tools Available:** {len(st.session_state.tools)}")
                for tool in st.session_state.tools:
                    st.text(f"  • {tool.tool_name}")
        else:
            error = st.session_state.get('initialization_error', 'Unknown error')
            st.markdown(f'<div class="status-box status-error">❌ Initialization Failed<br/>{error}</div>', unsafe_allow_html=True)
            
            if "gateway_config.json not found" in error:
                st.info("💡 Run `python setup_gateway.py` to create the Gateway infrastructure.")
        
        st.markdown("---")
        
        # Clear chat button
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
    
    # Initialize chat history
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if st.session_state.get('agent_initialized'):
        if prompt := st.chat_input("Ask about your infrastructure (e.g., 'What issues do you see in the CRM application?')..."):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Display assistant response with streaming
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                # Stream the response using callback handler
                with st.spinner("🤔 Thinking..."):
                    full_response = stream_agent_response(prompt, message_placeholder)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": full_response})
    else:
        st.error("⚠️ Agent not initialized. Please check the sidebar for details.")
        st.info("Make sure you have run `python setup_gateway.py` to set up the Gateway infrastructure.")


if __name__ == "__main__":
    main()
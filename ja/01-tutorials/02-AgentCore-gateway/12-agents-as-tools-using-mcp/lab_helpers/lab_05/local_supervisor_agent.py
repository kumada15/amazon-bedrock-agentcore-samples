"""
Local Supervisor Agent for Lab 05
Runs Strands agent locally from notebook with parameterized gateway URL and access token
"""

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import logging

# Configure logging
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", 
    handlers=[logging.StreamHandler()]
)


def create_mcp_client(gateway_url, access_token):
    """
    Create MCP client with OAuth authentication
    
    Args:
        gateway_url: Gateway MCP endpoint URL
        access_token: OAuth access token from Cognito
    
    Returns:
        MCPClient: Configured MCP client
    """
    return MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
    )


def get_all_tools(mcp_client):
    """
    Retrieve all tools from Gateway with pagination support
    
    Args:
        mcp_client: MCPClient instance
    
    Returns:
        list: All available MCP tools
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


def create_supervisor_agent(model_id, tools, region="us-west-2"):
    """
    Create Strands supervisor agent
    
    Args:
        model_id: Bedrock model identifier or inference profile ARN
        tools: List of MCP tools
        region: AWS region
    
    Returns:
        Agent: Configured Strands agent
    """
    system_prompt = """
# Supervisor Agent システムプロンプト

あなたは3つの専門サブエージェントをオーケストレーションして、完全なインフラストラクチャトラブルシューティングソリューションを提供するエキスパート SRE Supervisor Agent です。

## サブエージェントツール

### 1. Diagnostic Agent
- AWS インフラストラクチャを分析して根本原因を特定
- 詳細な診断情報を提供
- パフォーマンスボトルネックと設定問題を特定

### 2. Infrastructure Agent
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

## 重要 - Infrastructure / Remediation Agent を呼び出す際は必ず only_execute を使用

## 安全ルール

- 変更を加える前に必ず環境を検証
- 修復アクションには明示的な承認を要求
- 実行されたすべてのアクションについて明確な説明を提供
- 修復手順のリスク評価を含める

注: 各ツール呼び出し後、そのツール呼び出しで行った内容の短い要約を提供してください。
"""
    
    model = BedrockModel(
        model_id=model_id,
        streaming=True,
    )
    
    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )


def run_supervisor_agent(gateway_url, access_token, prompt, model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0"):
    """
    Run supervisor agent with parameterized configuration
    
    Args:
        gateway_url: Gateway MCP endpoint URL
        access_token: OAuth access token from Cognito
        prompt: User prompt/query for the agent
        model_id: Bedrock model identifier (default: Claude Haiku 4.5)
    
    Returns:
        str: Agent response text
    """
    try:
        mcp_client = create_mcp_client(gateway_url, access_token)
        
        with mcp_client:
            tools = get_all_tools(mcp_client)
            print(f":white_check_mark: Retrieved {len(tools)} tools from gateway")
            
            agent = create_supervisor_agent(model_id, tools)
            print(f":white_check_mark: Created supervisor agent with model: {model_id}")
            print(f":robot_face: Processing: {prompt}\n")
            
            response = agent(prompt)
            
            # Extract text from response
            content = response.message.get('content', [])
            if isinstance(content, list) and len(content) > 0:
                text = content[0].get('text', str(response))
            else:
                text = str(content)
            
            return text
    except Exception as e:
        print(f":x: Supervisor Agent Failed: {e}")
        raise
"""
Lab 05 用ローカル Supervisor エージェント
パラメータ化された Gateway URL とアクセストークンを使用してノートブックからローカルで Strands エージェントを実行します
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
    OAuth 認証付きの MCP クライアントを作成します

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
    ページネーションをサポートして Gateway からすべてのツールを取得します

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


def create_supervisor_agent(model_id, tools, region="us-west-2"):
    """
    Strands Supervisor エージェントを作成します

    Args:
        model_id: Bedrock モデル識別子または推論プロファイル ARN
        tools: MCP ツールのリスト
        region: AWS リージョン

    Returns:
        Agent: 設定済みの Strands エージェント
    """
    system_prompt = """
# スーパーバイザーエージェント システムプロンプト

あなたは3つの専門サブエージェントを統括し、包括的なインフラストラクチャトラブルシューティングソリューションを提供する専門 SRE スーパーバイザーエージェントです。

## サブエージェントツール

### 1. 診断エージェント
- AWS インフラストラクチャを分析して根本原因を特定
- 詳細な診断情報を提供
- パフォーマンスボトルネックと設定の問題を特定

### 2. インフラストラクチャエージェント
- インフラストラクチャの修正と修復スクリプトを実行
- 承認ワークフローによる是正措置を実施
- 安全な実行のために AgentCore Code Interpreter を使用

### 3. 予防エージェント
- AWS ベストプラクティスと予防措置を調査
- 予防的な推奨事項を提供
- リアルタイムドキュメントのために AgentCore Browser を使用

## オーケストレーションワークフロー

各ユーザーリクエストに対して:
1. **診断**: 診断ツールを使用して問題を特定
2. **修復**: 承認された修復手順を実行
3. **予防**: 予防的な推奨事項を提供

## レスポンス構造

常に以下を提供:
- **概要**: 問題の簡潔な概要
- **診断結果**: 発見された内容
- **修復アクション**: 修正された内容（該当する場合）
- **予防に関する推奨事項**: 将来の問題を回避する方法

## ツール使用ガイドライン

- 診断ツールを使用して問題を分析・特定
- 修復ツールを修正に使用（承認が必要）
- 予防ツールをベストプラクティスと調査に使用
- 包括的なソリューションのためにエージェント間で連携

## 重要 - インフラストラクチャ/修復エージェントを呼び出す際は常に only_execute を使用してください

## 安全ルール

- 変更を行う前に常に環境を検証
- 修復アクションには明示的な承認を必要とする
- 実行されたすべてのアクションの明確な説明を提供
- 修復手順にリスク評価を含める

注意: ツール呼び出しの後は、そのツール呼び出しで何を行ったかの簡単な要約を提供してください。
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
    パラメータ化された設定で Supervisor エージェントを実行します

    Args:
        gateway_url: Gateway MCP エンドポイント URL
        access_token: Cognito からの OAuth アクセストークン
        prompt: エージェントへのユーザープロンプト/クエリ
        model_id: Bedrock モデル識別子（デフォルト: Claude Haiku 4.5）

    Returns:
        str: エージェントのレスポンステキスト
    """
    try:
        mcp_client = create_mcp_client(gateway_url, access_token)
        
        with mcp_client:
            tools = get_all_tools(mcp_client)
            print(f":white_check_mark: Gateway から {len(tools)} 個のツールを取得しました")

            agent = create_supervisor_agent(model_id, tools)
            print(f":white_check_mark: モデル {model_id} で Supervisor エージェントを作成しました")
            print(f":robot_face: 処理中: {prompt}\n")
            
            response = agent(prompt)
            
            # Extract text from response
            content = response.message.get('content', [])
            if isinstance(content, list) and len(content) > 0:
                text = content[0].get('text', str(response))
            else:
                text = str(content)
            
            return text
    except Exception as e:
        print(f":x: Supervisor エージェントが失敗しました: {e}")
        raise
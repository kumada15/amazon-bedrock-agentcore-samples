"""
Lab 02: Strands Diagnostics Agent Lambda Handler

診断エージェント用の Lambda ハンドラー関数を提供するモジュール。
AgentCore Gateway と MCP プロトコルとの連携を想定して設計されています。

機能:
- ユーザーコンテキスト伝播のための actor_id と session_id を受け付け
- エージェント状態を介した AgentCore Memory との統合
- 診断ツールの定義（EC2、NGINX、DynamoDB ログ、メトリクス）
- Lambda の同期コンテキスト内での非同期エージェント呼び出しの処理
- MCP 互換の構造化レスポンスを返却

イベント構造（Gateway 経由 MCP から）:
{
    "query": "ユーザーの診断クエリ",
    "actor_id": "JWT からのユーザー識別子",
    "session_id": "関連呼び出しをグループ化するセッション ID"
}
"""

import asyncio
import json
import os


def lambda_handler(event, context):
    """
    AgentCore Gateway が Strands 診断エージェントを呼び出すための Lambda ハンドラー。

    MCP プロトコル経由で Gateway から query、actor_id、session_id を受け取ります。
    メモリフック付きの Strands エージェントを作成し、非同期で呼び出します。
    エージェント出力とリクエストメタデータを含む構造化レスポンスを返します。

    Args:
        event: 以下のキーを持つ辞書:
            - query (string): ユーザーの診断クエリ
            - actor_id (string): JWT トークンからのユーザー識別子
            - session_id (string): 関連呼び出しをグループ化するセッション ID
        context: Lambda コンテキストオブジェクト

    Returns:
        以下の構造を持つレスポンス辞書:
            {
                "status": "success" | "error",
                "request_id": "session-id または aws_request_id",
                "agent_input": "ユーザーのクエリ",
                "response": "エージェントのレスポンステキスト",
                "type": "strands_agent_response"
            }
    """
    try:
        # pip インストールされたパッケージを見つけるために lib/ を Python パスに追加
        import sys
        current_dir = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(current_dir, 'lib')
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)

        from strands import Agent, tool
        from lab_helpers import mock_data

        # 環境変数からモデル ID を取得（Lambda 設定で設定）
        MODEL_ID = os.getenv("MODEL_ID", "global.anthropic.claude-sonnet-4-20250514-v1:0")

        # ===================================================================
        # 診断ツールの定義
        # ===================================================================

        @tool(description="Fetch EC2 application logs to identify application errors and issues")
        def get_ec2_logs(limit: int = 10) -> dict:
            """モックデータから最近の EC2 アプリケーションログを取得"""
            logs = mock_data.get_ec2_logs()
            return {
                "logs": logs[:limit],
                "total": len(logs),
                "errors": [log["message"] for log in logs if "error" in log["message"].lower()][:5]
            }

        @tool(description="Fetch NGINX access/error logs to identify HTTP errors and worker issues")
        def get_nginx_logs(limit: int = 10) -> dict:
            """モックデータから NGINX アクセス/エラーログを取得"""
            logs = mock_data.get_nginx_logs()
            return {
                "logs": logs[:limit],
                "total": len(logs),
                "http_errors": [log["message"] for log in logs if "5" in log["message"]][:5],
                "worker_issues": [log["message"] for log in logs if "worker" in log["message"].lower()][:5]
            }

        @tool(description="Fetch DynamoDB operation logs to detect throttling and service issues")
        def get_dynamodb_logs(limit: int = 10) -> dict:
            """モックデータから DynamoDB 操作ログを取得"""
            logs = mock_data.get_dynamodb_logs()
            return {
                "logs": logs[:limit],
                "total": len(logs),
                "throttling": [log["message"] for log in logs if "throttl" in log["message"].lower()][:5],
                "unavailable": [log["message"] for log in logs if "unavailable" in log["message"].lower()][:5]
            }

        @tool(description="Fetch CloudWatch metrics (CPU, Memory) to analyze resource utilization")
        def get_cloudwatch_metrics(metric_name: str, limit: int = 10) -> dict:
            """モックデータから CloudWatch メトリクスを取得"""
            metrics = mock_data.get_metrics(metric_name)
            high_values = [m for m in metrics if m.get("Maximum", 0) > (80 if metric_name == "MemoryUtilization" else 85)]
            return {
                "metric": metric_name,
                "data_points": len(metrics),
                "high_utilization_periods": len(high_values),
                "peak_value": max([m.get("Maximum", 0) for m in metrics]) if metrics else 0
            }

        # ===================================================================
        # リクエストコンテキストの抽出
        # ===================================================================

        # Gateway イベントからパラメータを抽出
        agent_input = event.get("query", "Analyze system logs for issues")
        actor_id = event.get("actor_id", "unknown-actor")
        session_id = event.get("session_id", "default-session")

        # session_id をリクエスト追跡 ID として使用（ユーザーインタラクションごとに一意）
        request_id = session_id

        # メモリフックがアクセスできるようにエージェント状態に格納
        agent_state = {
            "actor_id": actor_id,
            "session_id": session_id
        }

        # ===================================================================
        # STRANDS エージェントの作成
        # ===================================================================

        diagnostic_agent = Agent(
            name="system_diagnostics_agent",
            model=MODEL_ID,
            tools=[get_ec2_logs, get_nginx_logs, get_dynamodb_logs, get_cloudwatch_metrics],
            system_prompt="""あなたはシステム診断のエキスパートエージェントです。システムログとメトリクスを分析し、問題とその根本原因を特定することが役割です。

システムの問題を診断する際は:
1. まず関連するログ（EC2、NGINX、DynamoDB）を収集する
2. CloudWatch メトリクスを確認してリソース使用率のパターンを把握する
3. 複数のソースからの発見を相関分析する
4. 重要度の明確な評価と推奨アクションを提示する

常に徹底的な調査を行い、証拠に基づいた結論を提示してください。""",
            state=agent_state  # メモリフック用に actor_id と session_id を渡す
        )

        # ===================================================================
        # エージェントを非同期で実行
        # ===================================================================

        # エージェントを実行する非同期関数を作成
        async def run_agent():
            """エージェントを非同期で実行してレスポンスを返す"""
            return await diagnostic_agent.invoke_async(agent_input)

        # 同期 Lambda コンテキスト内で非同期関数を実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent_response = loop.run_until_complete(run_agent())
        finally:
            loop.close()

        # ===================================================================
        # レスポンスを返却
        # ===================================================================

        return {
            "status": "success",
            "request_id": request_id,
            "agent_input": agent_input,
            "actor_id": actor_id,
            "session_id": session_id,
            "response": str(agent_response),
            "type": "strands_agent_response"
        }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "request_id": context.aws_request_id if context else "unknown"
        }

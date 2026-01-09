"""
ビデオゲーム売上データアナリストアシスタント - メインアプリケーション

このアプリケーションは、ビデオゲーム売上分析に特化したインテリジェントなデータアナリストアシスタントを提供します。
自然言語処理には Amazon Bedrock Claude モデル、データストレージには Aurora Serverless PostgreSQL、
会話コンテキスト管理には AgentCore Memory を活用しています。

主な機能:
- 自然言語から SQL クエリへの変換
- ビデオゲーム売上データの分析とインサイト
- 会話メモリとコンテキスト認識
- リアルタイムストリーミングレスポンス
- 包括的なエラーハンドリングとロギング
"""

import logging
import json
import os
from uuid import uuid4

# Bedrock Agent Core imports
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands import Agent, tool
from strands_tools import current_time
from strands.models import BedrockModel

# Custom module imports
from src.tools import get_tables_information, run_sql_query
from src.utils import (
    save_raw_query_result,
    load_file_content,
    load_config,
    get_agentcore_memory_messages,
    MemoryHookProvider,
)

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("personal-agent")


# SSM Parameter Store から設定を読み込み
# 環境変数から PROJECT_ID を取得して SSM パラメータパスを構築
PROJECT_ID = os.environ.get("PROJECT_ID", "agentcore-data-analyst-assistant")

# SSM からすべての設定を読み込み
try:
    config = load_config()
    print("✅ SSM から設定を読み込みました")
    print("-" * 50)
    print(f"🔧 プロジェクト ID: {PROJECT_ID}")
    print(f"📊 データベース: {config.get('DATABASE_NAME')}")
    print("-" * 50)
except Exception as e:
    print("❌ 設定読み込みエラー")
    print("-" * 50)
    print(f"🚨 エラー: {e}")
    print(f"🔧 プロジェクト ID: {PROJECT_ID}")
    print("-" * 50)
    # フォールバックとして空の設定を設定
    config = {}


# AgentCore Memory 設定の初期化
try:
    print("\n" + "=" * 70)
    print("🚀 ビデオゲーム売上アナリストアシスタントを初期化中")
    print("=" * 70)
    print("📋 AWS Systems Manager から設定を読み込み中...")

    # 設定からメモリ ID を取得
    memory_id = config.get("MEMORY_ID")

    # メモリ ID 設定を検証
    if not memory_id or memory_id.strip() == "":
        error_msg = "設定にメモリ ID が見つかりません。先に AgentCore Memory を作成してください。"
        print(f"❌ 設定エラー: {error_msg}")
        logger.error(f"設定エラー: {error_msg}")
        raise ValueError(error_msg)

    print(f"✅ メモリ ID を取得しました: {memory_id}")

    # AgentCore Memory Client を初期化
    print("🧠 AgentCore Memory サービスに接続中...")
    client = MemoryClient()
    print("✅ メモリクライアントの接続に成功しました")
    print("=" * 70 + "\n")

except Exception as e:
    print(f"💥 初期化に失敗しました: {str(e)}")
    print("=" * 70 + "\n")
    logger.error(f"AgentCore Memory の初期化に失敗しました: {e}")
    raise


# Bedrock Agent Core アプリを初期化
app = BedrockAgentCoreApp()


def load_system_prompt():
    """
    ビデオゲーム売上アナリストアシスタント用のシステムプロンプト設定を読み込む。

    このプロンプトは、ビデオゲーム売上データ分析におけるアシスタントの動作、
    機能、専門知識を定義します。instructions.txt ファイルが利用できない場合は
    デフォルトのプロンプトにフォールバックします。

    Returns:
        str: アシスタント用のシステムプロンプト設定
    """
    print("\n" + "=" * 50)
    print("📝 システムプロンプトを読み込み中")
    print("=" * 50)
    print("📂 instructions.txt を読み込み中...")

    fallback_prompt = """あなたはゲーム業界のトレンド、売上パフォーマンス、市場インサイトの分析に専門知識を持つ
                ビデオゲーム売上データアナリストアシスタントです。SQL クエリを実行し、ゲームデータを解釈し、
                ビデオゲーム業界向けの実用的なビジネスインテリジェンスを提供することができます。"""

    try:
        prompt = load_file_content("instructions.txt", default_content=fallback_prompt)
        if prompt == fallback_prompt:
            print("⚠️  フォールバックプロンプトを使用中（instructions.txt が見つかりません）")
        else:
            print("✅ instructions.txt からシステムプロンプトを正常に読み込みました")
            print(f"📊 プロンプト長: {len(prompt)} 文字")
        print("=" * 50 + "\n")
        return prompt
    except Exception as e:
        print(f"❌ システムプロンプトの読み込みエラー: {str(e)}")
        print("⚠️  フォールバックプロンプトを使用中")
        print("=" * 50 + "\n")
        return fallback_prompt


# システムプロンプトを読み込み
DATA_ANALYST_SYSTEM_PROMPT = load_system_prompt()


def create_execute_sql_query_tool(user_prompt: str, prompt_uuid: str):
    """
    ビデオゲーム売上データ分析用の動的 SQL クエリ実行ツールを作成する。

    この関数は、ビデオゲーム売上データを含む Aurora PostgreSQL データベースに対して
    SQL クエリを実行する専用ツールを生成します。クエリ結果は監査証跡と将来の参照のために
    自動的に DynamoDB に保存されます。

    Args:
        user_prompt (str): ビデオゲーム売上データに関する元のユーザー質問
        prompt_uuid (str): この分析プロンプトを追跡するための一意の識別子

    Returns:
        function: ビデオゲーム売上コンテキストを持つ設定済み SQL 実行ツール
    """

    @tool
    def execute_sql_query(sql_query: str, description: str) -> str:
        """
        データ分析のためにビデオゲーム売上データベースに対して SQL クエリを実行する。

        このツールは、ゲームタイトル、プラットフォーム、ジャンル、売上数値、
        地域別パフォーマンス指標を含む包括的なビデオゲーム売上データを格納した
        Aurora PostgreSQL データベースに対して SQL クエリを実行します。

        Args:
            sql_query (str): ビデオゲーム売上データベースに対して実行する SQL クエリ
            description (str): クエリが分析または取得する内容の明確な説明

        Returns:
            str: クエリ結果、メタデータ、またはエラー情報を含む JSON 文字列
        """
        print("\n" + "=" * 60)
        print("🎮 ビデオゲーム売上データクエリ実行")
        print("=" * 60)
        print(f"📝 分析: {description}")
        print(f"🔍 SQL クエリ: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}")
        print(f"🆔 プロンプト UUID: {prompt_uuid}")
        print("-" * 60)

        try:
            print("⏳ RDS Data API 経由でビデオゲーム売上データクエリを実行中...")

            # Execute the SQL query using the RDS Data API function
            response_json = json.loads(run_sql_query(sql_query))

            # エラーがあったかチェック
            if "error" in response_json:
                print(f"❌ クエリ実行に失敗しました: {response_json['error']}")
                print("=" * 60 + "\n")
                return json.dumps(response_json)

            # 結果を抽出
            records_to_return = response_json.get("result", [])
            message = response_json.get("message", "")

            print("✅ ビデオゲーム売上データクエリが正常に実行されました")
            print(f"📊 取得データレコード数: {len(records_to_return)}")
            if message:
                print(f"💬 クエリメッセージ: {message}")

            # 結果オブジェクトを準備
            if message != "":
                result = {"result": records_to_return, "message": message}
            else:
                result = {"result": records_to_return}

            print("-" * 60)
            print("💾 監査証跡用に分析結果を DynamoDB に保存中...")

            # 将来の参照のためにクエリ結果を DynamoDB に保存
            save_result = save_raw_query_result(
                prompt_uuid, user_prompt, sql_query, description, result, message
            )

            if not save_result["success"]:
                print(
                    f"⚠️  分析結果の DynamoDB への保存に失敗しました: {save_result['error']}"
                )
                result["saved"] = False
                result["save_error"] = save_result["error"]
            else:
                print("✅ 分析結果を DynamoDB 監査証跡に正常に保存しました")

            print("=" * 60 + "\n")
            return json.dumps(result)

        except Exception as e:
            error_msg = f"予期しないエラー: {str(e)}"
            print(f"💥 例外: {error_msg}")
            print("=" * 60 + "\n")
            return json.dumps({"error": error_msg})

    return execute_sql_query


@app.entrypoint
async def agent_invocation(payload):
    """ストリーミングレスポンス付きビデオゲーム売上データ分析リクエストのメインエントリーポイント。

    この関数はビデオゲーム売上データに関する自然言語クエリを処理し、
    専用ツールを備えた Claude 搭載エージェントを初期化し、会話コンテキストを
    維持しながらクライアントにインテリジェントな分析をストリーミングで返します。

    期待されるペイロード構造:
    {
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "user_timezone": "US/Pacific",
        "session_id": "optional-conversation-session-id",
        "user_id": "optional-user-identifier",
        "last_turns": "optional-number-of-conversation-turns-to-retrieve"
    }

    Returns:
        AsyncGenerator: 分析結果を含むストリーミングレスポンスチャンクを生成
    """
    try:
        # ペイロードからパラメータを抽出
        user_message = payload.get(
            "prompt",
            "入力にプロンプトが見つかりません。prompt キーを持つ JSON ペイロードを作成するようお客様にご案内ください",
        )
        bedrock_model_id = payload.get(
            "bedrock_model_id", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        )   
        prompt_uuid = payload.get("prompt_uuid", str(uuid4()))
        user_timezone = payload.get("user_timezone", "US/Pacific")
        session_id = payload.get("session_id", str(uuid4()))
        user_id = payload.get("user_id", "guest")
        last_k_turns = int(payload.get("last_k_turns", 20))

        print("\n" + "=" * 80)
        print("🎮 ビデオゲーム売上分析リクエスト")
        print("=" * 80)
        print(
            f"💬 ユーザークエリ: {user_message[:100]}{'...' if len(user_message) > 100 else ''}"
        )
        print(f"🤖 Claude モデル: {bedrock_model_id}")
        print(f"🆔 プロンプト UUID: {prompt_uuid}")
        print(f"🌍 ユーザータイムゾーン: {user_timezone}")
        print(f"🔗 会話 ID: {session_id}")
        print(f"👤 ユーザー ID: {user_id}")
        print(f"🔄 コンテキストターン数: {last_k_turns}")
        print("-" * 80)

        # ビデオゲーム売上分析用に Claude モデルを初期化
        print(f"🧠 分析用 Claude モデルを初期化中: {bedrock_model_id}")
        bedrock_model = BedrockModel(model_id=bedrock_model_id)
        print("✅ Claude モデルがビデオゲーム売上分析の準備完了")

        print("-" * 80)
        print("🧠 AgentCore Memory から会話コンテキストを取得中...")
        agentcore_messages = get_agentcore_memory_messages(
            client, memory_id, user_id, session_id, last_k_turns
        )

        print("📋 会話コンテキストを読み込みました:")
        print("-" * 50)
        if agentcore_messages:
            for i, msg in enumerate(agentcore_messages, 1):
                role = msg.get("role", "unknown")
                role_icon = "🤖" if role == "assistant" else "👤"
                content_text = ""
                if "content" in msg and msg["content"]:
                    for content_item in msg["content"]:
                        if "text" in content_item:
                            content_text = content_item["text"]
                            break
                content_preview = (
                    f"{content_text[:80]}..."
                    if len(content_text) > 80
                    else content_text
                )
                print(f"   {i}. {role_icon} {role.upper()}: {content_preview}")
        else:
            print("   📭 新しい会話を開始します（以前のコンテキストなし）")
        print("-" * 50)

        # ユーザーのタイムゾーンコンテキストでシステムプロンプトを設定
        print("📝 ビデオゲーム売上アナリスト用システムプロンプトを設定中...")
        system_prompt = DATA_ANALYST_SYSTEM_PROMPT.replace("{timezone}", user_timezone)
        print(
            f"✅ ビデオゲーム売上分析用システムプロンプトを設定しました（{len(system_prompt)} 文字）"
        )

        print("-" * 80)
        print("🔧 ビデオゲーム売上アナリストエージェントを初期化中...")

        # ビデオゲーム売上分析機能を持つ専門エージェントを作成
        agent = Agent(
            messages=agentcore_messages,
            model=bedrock_model,
            system_prompt=system_prompt,
            hooks=[
                MemoryHookProvider(client, memory_id, user_id, session_id, last_k_turns)
            ],
            tools=[
                get_tables_information,
                current_time,
                create_execute_sql_query_tool(user_message, prompt_uuid),
            ],
            callback_handler=None,
        )

        print("✅ ビデオゲーム売上アナリストエージェントの準備完了:")
        print(f"   📝 {len(agentcore_messages)} 件の会話コンテキストメッセージ")
        print(
            "   🔧 3 つの専門ツール（データベーススキーマ、時間ユーティリティ、SQL 実行）"
        )
        print("   🧠 会話メモリ管理が有効")

        print("-" * 80)
        print("🚀 ビデオゲーム売上データ分析を開始...")
        print("=" * 80)

        # レスポンスをストリーミング
        tool_active = False

        async for item in agent.stream_async(user_message):
            if "event" in item:
                event = item["event"]

                # Check for tool start
                if "contentBlockStart" in event and "toolUse" in event[
                    "contentBlockStart"
                ].get("start", {}):
                    tool_active = True
                    event_formatted = {"event": event}
                    yield json.dumps(event_formatted) + "\n"

                # Check for tool end
                elif "contentBlockStop" in event and tool_active:
                    tool_active = False

                    event_formatted = {"event": event}
                    yield json.dumps(event_formatted) + "\n"

            elif "start_event_loop" in item:
                yield json.dumps(item) + "\n"
            elif "current_tool_use" in item and tool_active:
                yield json.dumps(item["current_tool_use"]) + "\n"
            elif "data" in item:
                yield json.dumps({"data": item["data"]}) + "\n"

    except Exception as e:
        import traceback

        tb = traceback.extract_tb(e.__traceback__)
        filename, line_number, function_name, text = tb[-1]
        error_message = f"エラー: {str(e)}（{filename} の {line_number} 行目）"
        print("\n" + "=" * 80)
        print("💥 ビデオゲーム売上分析エラー")
        print("=" * 80)
        print(f"❌ エラー: {str(e)}")
        print(f"📍 場所: {filename} の {line_number} 行目")
        print(f"🔧 関数: {function_name}")
        if text:
            print(f"💻 コード: {text}")
        print("=" * 80 + "\n")
        yield f"申し訳ありませんが、ビデオゲーム売上データリクエストの分析中にエラーが発生しました: {error_message}"


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 ビデオゲーム売上データアナリストアシスタントを起動中")
    print("=" * 80)
    print("📡 サーバーをポート 8080 で起動中...")
    print("🌐 ヘルスチェックエンドポイント: /ping")
    print("🎯 分析エンドポイント: /invocations")
    print("📋 ビデオゲーム売上トレンドとインサイトの分析準備完了！")
    print("=" * 80)
    app.run()

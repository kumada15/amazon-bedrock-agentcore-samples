"""
スライドデッキエージェントデモ用 Flask Web アプリケーション - Basic エージェントと Memory 有効エージェントの比較
"""

import logging
import os
import sys
import traceback
from datetime import datetime

from agents.basic_agent import BasicSlideDeckAgent
from agents.memory_agent import MemoryEnabledSlideDeckAgent
from config import (
    DEFAULT_USER_ID,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    FLASK_SECRET_KEY,
    OUTPUT_DIR,
    get_session_id,
)
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_cors import CORS
from memory_setup import setup_slide_deck_memory

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder="../templates", static_folder="../static")

# Security: Require secret key in production


if not FLASK_SECRET_KEY:
    import secrets
    logger.warning("⚠️  FLASK_SECRET_KEY が設定されていません - このセッション用にランダムキーを生成します")
    app.config["SECRET_KEY"] = secrets.token_hex(32)
else:
    app.config["SECRET_KEY"] = FLASK_SECRET_KEY

CORS(app)

# Global variables for demo
basic_agent = None
memory_agent = None
memory_session = None
memory_session_manager = None


def initialize_agents():
    """Basic エージェントと Memory 有効エージェントの両方を初期化する"""
    global basic_agent, memory_agent, memory_session, memory_session_manager

    try:
        # Initialize basic agent
        basic_agent = BasicSlideDeckAgent(OUTPUT_DIR)
        logger.info("✅ Basic エージェントを初期化しました")

        # Initialize memory system and memory-enabled agent
        memory, session_manager, memory_mgr = setup_slide_deck_memory()
        memory_session_manager = session_manager  # Store globally for delete operations
        memory_session = session_manager.create_memory_session(
            actor_id=DEFAULT_USER_ID, session_id=get_session_id()
        )
        memory_agent = MemoryEnabledSlideDeckAgent(memory_session, OUTPUT_DIR)
        logger.info("✅ Memory 有効エージェントを初期化しました")

        return True

    except Exception as e:
        logger.error(f"❌ エージェントの初期化に失敗しました: {e}")
        logger.error(traceback.format_exc())
        return False


@app.route("/")
def index():
    """エージェント比較を表示するメインページ"""
    return render_template("index.html")


@app.route("/create-basic", methods=["GET", "POST"])
def create_basic():
    """Basic エージェント（Memory なし）を使用してプレゼンテーションを作成する"""
    if request.method == "GET":
        return render_template("create_basic.html")

    try:
        data = request.get_json()
        user_request = data.get("request", "")

        if not user_request:
            return jsonify({"error": "プレゼンテーションリクエストを入力してください"}), 400

        # Use basic agent
        logger.info(f"Basic リクエストを処理中: {user_request[:100]}...")
        result = basic_agent.create_presentation(user_request)

        return jsonify(
            {
                "success": True,
                "result": result,
                "agent_type": "Basic Agent (No Memory)",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Basic 作成でエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/create-memory", methods=["GET", "POST"])
def create_memory():
    """Memory 有効エージェントを使用してプレゼンテーションを作成する"""
    if request.method == "GET":
        return render_template("create_memory.html")

    try:
        data = request.get_json()
        user_request = data.get("request", "")

        if not user_request:
            return jsonify({"error": "プレゼンテーションリクエストを入力してください"}), 400

        # Use memory-enabled agent
        logger.info(f"Memory 有効リクエストを処理中: {user_request[:100]}...")
        result = memory_agent.create_presentation(user_request)

        return jsonify(
            {
                "success": True,
                "result": result,
                "agent_type": "Memory-Enabled Agent",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Memory 有効作成でエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/compare")
def compare():
    """サイドバイサイド比較ページ"""
    return render_template("compare.html")


@app.route("/compare-agents", methods=["POST"])
def compare_agents():
    """同じリクエストで両方のエージェントを比較する"""
    try:
        data = request.get_json()
        user_request = data.get("request", "")

        if not user_request:
            return jsonify({"error": "プレゼンテーションリクエストを入力してください"}), 400

        # Process with both agents
        logger.info(f"リクエストに対してエージェントを比較中: {user_request[:100]}...")

        # Basic agent result
        basic_result = basic_agent.create_presentation(user_request)

        # Memory-enabled agent result
        memory_result = memory_agent.create_presentation(user_request)

        return jsonify(
            {
                "success": True,
                "basic_result": {
                    "result": basic_result,
                    "agent_type": "Basic Agent (No Memory)",
                    "description": "Creates presentations using default settings and basic styling options.",
                },
                "memory_result": {
                    "result": memory_result,
                    "agent_type": "Memory-Enabled Agent",
                    "description": "Learns your preferences and creates personalized presentations that improve over time.",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"エージェント比較でエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/get-preferences")
def get_preferences():
    """Memory から現在のユーザー好みを取得する"""
    try:
        if memory_agent:
            # Use the memory agent's preference tool
            preferences = memory_agent.get_user_preferences_tool()
            return jsonify({"success": True, "preferences": preferences})
        else:
            return jsonify({"error": "Memory エージェントが利用できません"}), 500

    except Exception as e:
        logger.error(f"好みの取得でエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/recommend-style", methods=["POST"])
def recommend_style():
    """Memory エージェントからスタイル推奨を取得する"""
    try:
        data = request.get_json()
        topic = data.get("topic", "")
        audience = data.get("audience", "general")
        context = data.get("context", "business")

        if not topic:
            return jsonify({"error": "プレゼンテーショントピックを入力してください"}), 400

        if memory_agent:
            recommendations = memory_agent.recommend_style_tool(
                topic, audience, context
            )
            return jsonify({"success": True, "recommendations": recommendations})
        else:
            return jsonify({"error": "Memory エージェントが利用できません"}), 500

    except Exception as e:
        logger.error(f"推奨の取得でエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/delete-memory", methods=["POST"])
def delete_memory():
    """AgentCore Memory 削除 API を使用して Memory からすべてのユーザー好みを削除する"""
    try:
        if memory_session_manager and memory_agent and memory_session:
            # Get the user namespace for preferences
            user_id = DEFAULT_USER_ID
            namespace = f"slidedecks/user/{user_id}/style_preferences"

            logger.info(f"🗑️ 名前空間のメモリレコードを検索中: {namespace}")

            # First, search for all memory records in the user preference namespace
            # Use a broad query to find all preference records
            preference_memories = memory_session.search_long_term_memories(
                query="style preferences",  # Broad query to find all preferences
                namespace_prefix=namespace,
                top_k=100,  # Get up to 100 records to delete
            )

            if not preference_memories:
                logger.info("削除するメモリレコードが見つかりません")
                return jsonify(
                    {
                        "success": True,
                        "message": "No preference records found to delete. Memory is already clear!",
                        "details": {"deleted": 0, "failed": 0, "namespace": namespace},
                    }
                )

            logger.info(f"削除対象のメモリレコード {len(preference_memories)} 件を発見しました")

            # Delete each memory record individually
            successful_count = 0
            failed_count = 0
            deleted_ids = []

            for memory_record in preference_memories:
                try:
                    # Extract the memory record ID - the correct field name is 'memoryRecordId'
                    record_id = memory_record.get("memoryRecordId")

                    if record_id:
                        # Use the memory session to delete the record
                        # The memory session should have a delete method
                        if hasattr(memory_session, "delete_memory_record"):
                            memory_session.delete_memory_record(record_id)
                        elif hasattr(memory_session_manager, "delete_memory_record"):
                            # Get the memory ID from our setup
                            memory_id = getattr(
                                memory_session,
                                "_memory_id",
                                "SlideDeckAgentMemory-rMV28tDfXu",
                            )
                            memory_session_manager.delete_memory_record(
                                memory_id=memory_id, memory_record_id=record_id
                            )
                        else:
                            logger.warning(
                                f"削除メソッドが見つかりません、レコード ID: {record_id}"
                            )
                            failed_count += 1
                            continue

                        successful_count += 1
                        deleted_ids.append(record_id)
                        logger.info(f"✅ メモリレコードを削除しました: {record_id}")
                    else:
                        logger.warning(
                            f"メモリレコードに有効な ID が見つかりません: {list(memory_record.keys())}"
                        )
                        failed_count += 1

                except Exception as delete_error:
                    logger.error(f"❌ メモリレコードの削除に失敗しました: {delete_error}")
                    failed_count += 1

            logger.info(
                f"✅ ユーザー {user_id} のメモリレコード {successful_count} 件を正常に削除しました"
            )
            if failed_count > 0:
                logger.warning(f"⚠️ {failed_count} 件のレコードの削除に失敗しました")

            return jsonify(
                {
                    "success": True,
                    "message": (
                        f"Successfully deleted {successful_count} preference records! "
                        "The agent will start learning fresh."
                    ),
                    "details": {
                        "deleted": successful_count,
                        "failed": failed_count,
                        "namespace": namespace,
                        "deleted_ids": deleted_ids[
                            :5
                        ],  # Show first 5 IDs for reference
                    },
                }
            )
        else:
            return jsonify({"error": "Memory システムが利用できません"}), 500

    except Exception as e:
        logger.error(f"❌ メモリレコードの削除でエラーが発生しました: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/files")
def list_files():
    """生成されたプレゼンテーションファイルの一覧を取得する"""
    try:
        files = []
        if os.path.exists(OUTPUT_DIR):
            for filename in os.listdir(OUTPUT_DIR):
                if filename.endswith(".html"):  # Only show HTML files
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    file_info = {
                        "name": filename,
                        "size": os.path.getsize(filepath),
                        "modified": datetime.fromtimestamp(
                            os.path.getmtime(filepath)
                        ).isoformat(),
                        "type": "HTML Presentation",
                        "agent_type": (
                            "Memory Agent" if "_Memory" in filename else "Basic Agent"
                        ),
                    }
                    files.append(file_info)

        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["modified"], reverse=True)

        return jsonify({"success": True, "files": files})

    except Exception as e:
        logger.error(f"ファイル一覧の取得でエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download_file(filename):
    """生成されたファイルをダウンロードする"""
    try:
        # Prevent path traversal
        if ".." in filename or filename.startswith("/"):
            return jsonify({"error": "無効なファイル名です"}), 400

        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            flash(f"ファイル {filename} が見つかりません", "error")
            return redirect(url_for("index"))

        return send_file(filepath, as_attachment=True)

    except Exception as e:
        logger.error(f"ファイルのダウンロードでエラーが発生しました: {e}")
        flash(f"ファイルのダウンロードでエラーが発生しました: {str(e)}", "error")
        return redirect(url_for("index"))


@app.route("/preview/<filename>")
def preview_file(filename):
    """HTML プレゼンテーションファイルをプレビューする"""
    try:
        # Prevent path traversal
        if ".." in filename or filename.startswith("/"):
            return jsonify({"error": "無効なファイル名です"}), 400

        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath) or not filename.endswith(".html"):
            return jsonify({"error": f"HTML ファイル {filename} が見つかりません"}), 404

        return send_file(filepath, mimetype="text/html")

    except Exception as e:
        logger.error(f"ファイルのプレビューでエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify(
        {
            "status": "healthy",
            "basic_agent": basic_agent is not None,
            "memory_agent": memory_agent is not None,
            "memory_session": memory_session is not None,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="Page not found", code=404), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", error="Internal server error", code=500), 500


def create_app():
    """アプリケーションファクトリパターン"""
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initialize agents
    if not initialize_agents():
        logger.error("❌ エージェントの初期化に失敗しました - 一部の機能が動作しない可能性があります")

    return app


if __name__ == "__main__":
    # Create and run the app
    app = create_app()
    logger.info(f"🚀 スライドデッキデモサーバーを起動中: {FLASK_HOST}:{FLASK_PORT}")
    logger.info(f"📁 出力ディレクトリ: {OUTPUT_DIR}")
    logger.info("🎯 デモ機能:")
    logger.info("   - Basic エージェント（Memory なし）")
    logger.info("   - Memory 有効エージェント（好みを学習）")
    logger.info("   - サイドバイサイド比較")
    logger.info("   - HTML と PowerPoint 生成")
    logger.info("   - ファイルダウンロードとプレビュー")

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)

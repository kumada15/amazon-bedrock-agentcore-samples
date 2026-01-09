#!/usr/bin/env python3
"""
スライドデッキエージェントのメインデモスクリプト - エージェント Memory の重要性のデモンストレーション

このスクリプトは以下を比較することでエージェント Memory の重要性を実演します:
1. Basic エージェント: Memory なしでスライドを作成（毎回デフォルト設定を使用）
2. Memory エージェント: ユーザー好みを学習してパーソナライズされたプレゼンテーションを作成

Usage:
    python main.py [--mode MODE] [--user-id USER_ID]

Modes:
    web     - Web インターフェースを起動（デフォルト）
    cli     - コマンドラインインタラクティブデモ
    demo    - サンプルインタラクションによる自動デモ
    compare - サンプルリクエストによる直接比較
"""

from web.app import create_app
from memory_setup import setup_slide_deck_memory
from agents.memory_agent import MemoryEnabledSlideDeckAgent
from agents.basic_agent import BasicSlideDeckAgent
from config import ensure_directories, DEFAULT_USER_ID, get_session_id
import os
import sys
import argparse
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_banner():
    """デモバナーを表示する"""
    print("=" * 80)
    print("🧠 SLIDE DECK AGENT デモ - エージェントメモリの重要性")
    print("=" * 80)
    print()
    print(
        "このデモでは、エージェントメモリが AI インタラクションをどのように変革するかを比較して紹介します:"
    )
    print("📊 Basic Agent:       学習やメモリなしでスライドを作成")
    print("🧠 Memory Agent:      好みを学習してパーソナライズされたプレゼンテーションを作成")
    print()


def setup_demo_environment() -> tuple:
    """両方のエージェントでデモ環境をセットアップする。

    Returns:
        basic_agent、memory_agent、user_session のタプル
    """
    print("🚀 デモ環境をセットアップ中...")

    # Ensure directories exist
    ensure_directories()

    # Initialize basic agent
    print("   ⚙️  Basic Agent（メモリなし）を初期化中...")
    basic_agent = BasicSlideDeckAgent()

    # Initialize memory system and memory agent
    print("   🧠 メモリシステムをセットアップ中...")
    memory, session_manager, memory_mgr = setup_slide_deck_memory()

    print("   👤 ユーザーセッションを作成中...")
    user_session = session_manager.create_memory_session(
        actor_id=DEFAULT_USER_ID, session_id=get_session_id()
    )

    print("   🤖 メモリ有効エージェントを初期化中...")
    memory_agent = MemoryEnabledSlideDeckAgent(user_session)

    print("✅ デモ環境の準備完了！")
    print()

    return basic_agent, memory_agent, user_session


def run_cli_demo():
    """インタラクティブ CLI デモを実行する。

    ユーザーがコマンドラインで Basic Agent と Memory Agent をテストできる
    インタラクティブなセッションを開始する。
    """
    print_banner()
    basic_agent, memory_agent, user_session = setup_demo_environment()

    print("🎯 インタラクティブデモモード")
    print("終了するには 'exit'、コマンド一覧は 'help' と入力")
    print()

    while True:
        try:
            print("利用可能なコマンド:")
            print("  1. basic    - Basic Agent をテスト")
            print("  2. memory   - Memory Agent をテスト")
            print("  3. compare  - 両方のエージェントを比較")
            print("  4. prefs    - 学習した好みを表示")
            print("  5. help     - このヘルプを表示")
            print("  6. exit     - デモを終了")
            print()

            choice = input("オプションを選択 (1-6): ").strip()

            if choice in ["exit", "6"]:
                print("👋 Agent Memory デモをお試しいただきありがとうございました！")
                break

            elif choice in ["help", "5"]:
                continue

            elif choice in ["1", "basic"]:
                run_basic_agent_test(basic_agent)

            elif choice in ["2", "memory"]:
                run_memory_agent_test(memory_agent)

            elif choice in ["3", "compare"]:
                run_agent_comparison(basic_agent, memory_agent)

            elif choice in ["4", "prefs"]:
                show_learned_preferences(memory_agent)

            else:
                print("❌ 無効な選択です。1-6 を選択してください。")

            input("\\nEnter キーを押して続行...")
            print("\\n" + "=" * 50 + "\\n")

        except KeyboardInterrupt:
            print("\\n\\n👋 デモが中断されました。さようなら！")
            break
        except Exception as e:
            logger.error(f"デモエラー: {e}")
            print(f"❌ エラー: {e}")


def run_basic_agent_test(basic_agent):
    """Basic エージェントをテストする。

    Args:
        basic_agent: テスト対象の BasicSlideDeckAgent インスタンス
    """
    print("\\n📊 BASIC AGENT テスト（メモリなし）")
    print("-" * 40)

    request = input("プレゼンテーションリクエストを入力（サンプルを使用する場合は Enter）: ").strip()

    if not request:
        request = """Create a presentation about "Introduction to Cloud Computing" for IT professionals.
        Include overview, benefits, service models, deployment types, and security considerations.
        Use professional blue theme with modern fonts."""

        print(f"サンプルリクエストを使用: {request[:100]}...")

    print("\\n⏳ Basic Agent でプレゼンテーションを作成中...")
    try:
        result = basic_agent.create_presentation(request)
        print("\\n✅ Basic Agent の結果:")
        print("-" * 30)
        print(result)
    except Exception as e:
        print(f"❌ エラー: {e}")


def run_memory_agent_test(memory_agent):
    """Memory 有効エージェントをテストする。

    Args:
        memory_agent: テスト対象の MemoryEnabledSlideDeckAgent インスタンス
    """
    print("\\n🧠 MEMORY AGENT テスト（学習あり）")
    print("-" * 40)

    request = input("プレゼンテーションリクエストを入力（サンプルを使用する場合は Enter）: ").strip()

    if not request:
        request = """Create a presentation about "Sustainable Energy Solutions" for environmental conference.
        Include current challenges, renewable technologies, implementation strategies, and future outlook.
        I prefer green color schemes and clean, professional designs for environmental topics."""

        print(f"サンプルリクエストを使用: {request[:100]}...")

    print("\\n⏳ Memory Agent でプレゼンテーションを作成中...")
    try:
        result = memory_agent.create_presentation(request)
        print("\\n✅ Memory Agent の結果:")
        print("-" * 30)
        print(result)
    except Exception as e:
        print(f"❌ エラー: {e}")


def run_agent_comparison(basic_agent, memory_agent):
    """同じリクエストで両方のエージェントを比較する。

    Args:
        basic_agent: BasicSlideDeckAgent インスタンス
        memory_agent: MemoryEnabledSlideDeckAgent インスタンス
    """
    print("\\n⚖️  エージェント比較")
    print("-" * 40)

    request = input(
        "両方のエージェントへのリクエストを入力（サンプルを使用する場合は Enter）: "
    ).strip()

    if not request:
        request = """Create a presentation about "Digital Marketing Trends 2024" for marketing professionals.
        Include current trends, social media evolution, AI in marketing, data analytics, and future predictions.
        Target audience: Marketing managers and digital strategists."""

        print(f"サンプルリクエストを使用: {request[:100]}...")

    print("\\n🔄 同じリクエストで両方のエージェントをテスト中...")

    # Test basic agent
    print("\\n1️⃣ Basic Agent（メモリなし）:")
    print("-" * 25)
    try:
        basic_result = basic_agent.create_presentation(request)
        print("✅", basic_result[:200], "..." if len(basic_result) > 200 else "")
    except Exception as e:
        print(f"❌ Basic Agent エラー: {e}")

    # Test memory agent
    print("\\n2️⃣ Memory Agent（学習あり）:")
    print("-" * 30)
    try:
        memory_result = memory_agent.create_presentation(request)
        print("✅", memory_result[:200], "..." if len(memory_result) > 200 else "")
    except Exception as e:
        print(f"❌ Memory Agent エラー: {e}")

    print("\\n🔍 主な違い:")
    print("• Basic Agent: デフォルト設定を使用、学習なし")
    print("• Memory Agent: 学習した好みを適用、コンテキスト認識")


def show_learned_preferences(memory_agent):
    """現在の学習済み好みを表示する。

    Args:
        memory_agent: 好みを取得する MemoryEnabledSlideDeckAgent インスタンス
    """
    print("\\n🧠 学習した好み")
    print("-" * 30)

    try:
        preferences = memory_agent.get_user_preferences_tool()
        print(preferences)
    except Exception as e:
        print(f"❌ 好みの取得エラー: {e}")


def run_automated_demo():
    """事前定義されたシナリオで自動デモを実行する。

    複数のシナリオを順番に実行し、Basic Agent と Memory Agent の
    動作の違いを自動的にデモンストレーションする。
    """
    print_banner()
    basic_agent, memory_agent, user_session = setup_demo_environment()

    print("🤖 自動デモ - エージェントメモリ学習の旅")
    print()

    scenarios = [
        {
            "name": "Tech Presentation - Learning Blue Preference",
            "request": """Create a presentation about "Cybersecurity Fundamentals" for IT training.
            Include threat landscape, security frameworks, best practices, and incident response.
            I really prefer blue color schemes for technical content as they convey trust and professionalism.""",
        },
        {
            "name": "Business Presentation - Learning Professional Style",
            "request": """Create a presentation about "Digital Transformation Strategy" for executives.
            Include market drivers, technology trends, implementation roadmap, and ROI analysis.
            I like professional, corporate styling with clean fonts for business presentations.""",
        },
        {
            "name": "Adaptive Presentation - Testing Memory",
            "request": """Create a presentation about "AI in Finance" for financial services conference.
            Include applications, risk management, regulatory considerations, and future outlook.
            This is a technical topic for finance professionals.""",
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\\n{i}. {scenario['name']}")
        print("=" * 60)

        # Test with basic agent
        print("\\n📊 Basic Agent の応答:")
        try:
            basic_agent.create_presentation(scenario["request"])
            print("✅ デフォルトスタイリングでプレゼンテーションを作成しました")
        except Exception as e:
            print(f"❌ エラー: {e}")

        # Test with memory agent
        print("\\n🧠 Memory Agent の応答:")
        try:
            memory_agent.create_presentation(scenario["request"])
            print("✅ 学習した好みでプレゼンテーションを作成しました")
        except Exception as e:
            print(f"❌ エラー: {e}")

        if i < len(scenarios):
            input("\\n次のシナリオへ進むには Enter キーを押してください...")

    print("\\n" + "=" * 60)
    print("🎉 デモ完了！")
    print("\\n重要なポイント:")
    print("• Basic Agent: 一貫しているが汎用的な出力")
    print("• Memory Agent: ユーザーの好みを学習して適応")
    print("• 各インタラクションが将来のプレゼンテーションを改善")


def run_web_interface():
    """Web インターフェースを起動する。

    Flask ベースの Web アプリケーションを起動し、ブラウザから
    エージェントをインタラクティブにテストできるようにする。
    """
    print_banner()
    print("🌐 Web インターフェースを起動中...")
    print()
    print("Web インターフェースの機能:")
    print("• Basic と Memory エージェントのインタラクティブ比較")
    print("• リアルタイム好み学習の可視化")
    print("• HTML と PowerPoint ファイルの生成")
    print("• ファイルダウンロードとプレビュー機能")
    print()

    try:
        app = create_app()
        print("✅ Web インターフェースの準備完了！")
        print("🌐 ブラウザでアクセス: http://localhost:5000")
        print("📱 サーバーを停止するには Ctrl+C を押してください")
        print()

        app.run(host="127.0.0.1", port=5000, debug=False)

    except Exception as e:
        logger.error(f"Web インターフェースエラー: {e}")
        print(f"❌ Web インターフェースの起動に失敗しました: {e}")


def main():
    """メインエントリポイント。

    コマンドライン引数を解析し、指定されたモードでデモを実行する。
    """
    parser = argparse.ArgumentParser(
        description="Slide Deck Agent Demo - Memory Importance Demonstration"
    )
    parser.add_argument(
        "--mode",
        choices=["web", "cli", "demo", "compare"],
        default="web",
        help="Demo mode (default: web)",
    )
    parser.add_argument(
        "--user-id", default=DEFAULT_USER_ID, help="User ID for memory session"
    )

    args = parser.parse_args()

    # Update global user ID if provided
    if args.user_id != DEFAULT_USER_ID:
        import config

        config.DEFAULT_USER_ID = args.user_id

    try:
        if args.mode == "web":
            run_web_interface()
        elif args.mode == "cli":
            run_cli_demo()
        elif args.mode == "demo":
            run_automated_demo()
        elif args.mode == "compare":
            print_banner()
            basic_agent, memory_agent, _ = setup_demo_environment()
            run_agent_comparison(basic_agent, memory_agent)

    except KeyboardInterrupt:
        print("\\n\\n👋 デモが中断されました。さようなら！")
    except Exception as e:
        logger.error(f"デモが失敗しました: {e}")
        print(f"\\n❌ デモに失敗しました: {e}")
        print("\\n以下を確認してください:")
        print("• AWS 認証情報が設定されているか")
        print("• 必要な依存関係がインストールされているか")
        print("• AWS サービスへのネットワーク接続があるか")


if __name__ == "__main__":
    main()

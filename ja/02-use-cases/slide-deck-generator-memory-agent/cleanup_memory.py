"""
既存の AgentCore Memory リソースを削除するクリーンアップスクリプト。
新しい設定でメモリを再作成する必要がある場合は、アプリケーション起動前にこれを実行してください。

Usage:
    python cleanup_memory.py
"""

import logging

from memory_setup import SlideMemoryManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """既存のスライドデッキ Memory リソースを削除する"""

    print("\n" + "=" * 60)
    print("  AgentCore Memory クリーンアップユーティリティ")
    print("=" * 60 + "\n")

    print("⚠️  警告: 既存の Memory リソースを削除します。")
    print("    学習したすべてのユーザー好みが失われます。\n")

    try:
        # Create memory manager
        memory_mgr = SlideMemoryManager()

        # Delete existing memory
        deleted = memory_mgr.delete_existing_memory()

        if deleted:
            print("\n" + "=" * 60)
            print("✅ クリーンアップが正常に完了しました！")
            print("=" * 60)
            print("\n新しい Memory でアプリケーションを実行できます:")
            print("  • Web アプリ: python web/app.py")
            print("  • メインデモ: python main.py")
            print()
        else:
            print("\n" + "=" * 60)
            print("ℹ️  クリーンアップ不要 - Memory が存在しません")
            print("=" * 60)
            print("\nアプリケーションを実行できます。")
            print()

    except Exception as e:
        logger.error(f"❌ クリーンアップに失敗しました: {e}")
        print("\n" + "=" * 60)
        print("❌ クリーンアップに失敗しました - 上記のエラーを確認してください")
        print("=" * 60)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

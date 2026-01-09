#!/usr/bin/env python3

import asyncio
import sys


# マルチエージェントシステム用のシンプルな CLI ラッパー
def main():
    """メイン CLI エントリーポイント - デバッグサポート付きでマルチエージェントシステムを実行します。"""
    try:
        # マルチエージェントシステムをインポートして実行
        from .multi_agent_langgraph import main as multi_agent_main

        asyncio.run(multi_agent_main())
    except ImportError as e:
        print(f"マルチエージェントシステムのインポートエラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"マルチエージェントシステムの実行エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

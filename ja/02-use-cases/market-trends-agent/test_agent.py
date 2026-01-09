#!/usr/bin/env python3
"""
Market Trends Agent テストスイート
メモリ、市場分析、基本操作を含むコア機能をテストする
"""

import boto3
import json
import os
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_agent_arn():
    """ファイルからエージェント ARN を読み込む"""
    arn_file = ".agent_arn"
    if not os.path.exists(arn_file):
        print("❌ ARN ファイルが見つかりません。先にエージェントをデプロイしてください。")
        return None

    with open(arn_file, "r") as f:
        return f.read().strip()


def invoke_agent(runtime_arn: str, prompt: str, session_id: str = None) -> str:
    """プロンプトを使用してデプロイ済みエージェントを呼び出す"""
    try:
        client = boto3.client("bedrock-agentcore", region_name="us-east-1")

        # Prepare the payload
        payload = json.dumps({"prompt": prompt}).encode("utf-8")

        # Build the request parameters
        request_params = {"agentRuntimeArn": runtime_arn, "payload": payload}

        # Add session ID if provided
        if session_id:
            request_params["runtimeSessionId"] = session_id

        response = client.invoke_agent_runtime(**request_params)

        # Handle different response types
        if "text/event-stream" in response.get("contentType", ""):
            # Handle streaming response
            content = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                    content.append(line)
            return "\n".join(content)
        elif response.get("contentType") == "application/json":
            # Handle standard JSON response
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode("utf-8"))
            return json.loads("".join(content))
        else:
            # Handle other response types
            if "response" in response:
                return response["response"].read().decode("utf-8")
            else:
                return str(response)

    except Exception as e:
        logger.error(f"エージェント呼び出し中にエラーが発生しました: {e}")
        return f"エラー: {e}"


def run_simple_test(runtime_arn: str):
    """シンプルな接続テストを実行する"""
    print("🧪 シンプルテスト: 基本接続確認")
    print("-" * 40)

    test_message = "Hello, I'm testing the agent. Can you help me?"
    response = invoke_agent(runtime_arn, test_message)

    success = "error" not in response.lower() and len(response) > 50
    print(f"✅ レスポンス: {response[:200]}..." if len(response) > 200 else response)
    print(f"🔍 テスト結果: {'✅ 合格' if success else '❌ 失敗'}")
    print()

    return success


def run_comprehensive_tests(runtime_arn: str):
    """包括的な機能テストを実行する"""
    print("🚀 Market Trends Agent - 包括的テストスイート")
    print("=" * 60)
    print(f"📋 テスト対象 ARN: {runtime_arn}")

    # Create a consistent session ID for all tests to ensure memory persistence (min 33 chars)
    session_id = "test-session-memory-persistence-2025-comprehensive"
    print(f"📋 セッション ID: {session_id}")
    print()

    tests_passed = 0
    total_tests = 4

    # Test 1: Broker Introduction & Memory
    print("📋 テスト 1: ブローカープロファイルとメモリ")
    print("-" * 30)

    broker_intro = "Hi, I'm Sarah Chen from Morgan Stanley. I focus on growth investing and tech stocks for younger clients. Please remember my profile."

    response1 = invoke_agent(runtime_arn, broker_intro, session_id)
    print(
        "✅ レスポンス:", response1[:200] + "..." if len(response1) > 200 else response1
    )

    # Check if profile was acknowledged
    profile_acknowledged = any(
        keyword in response1.lower()
        for keyword in [
            "sarah",
            "morgan stanley",
            "growth",
            "tech",
            "profile",
            "remember",
        ]
    )
    print(f"🔍 プロファイル確認: {'✅ はい' if profile_acknowledged else '❌ いいえ'}")

    if profile_acknowledged:
        tests_passed += 1

    print()
    time.sleep(5)  # Wait to avoid throttling

    # Test 2: Memory Recall
    print("📋 テスト 2: メモリの呼び出し")
    print("-" * 30)

    memory_test = "Hi, I'm Sarah Chen from Morgan Stanley. What do you remember about my investment preferences?"
    response2 = invoke_agent(runtime_arn, memory_test, session_id)
    print(
        "✅ レスポンス:", response2[:200] + "..." if len(response2) > 200 else response2
    )

    # Check if memory was recalled
    memory_recalled = any(
        keyword in response2.lower()
        for keyword in ["sarah", "growth", "tech", "morgan stanley"]
    )
    print(f"🔍 メモリ呼び出し: {'✅ はい' if memory_recalled else '❌ いいえ'}")

    if memory_recalled:
        tests_passed += 1

    print()
    time.sleep(5)  # Wait to avoid throttling

    # Test 3: Market Data Request
    print("📋 テスト 3: 市場データリクエスト")
    print("-" * 30)

    market_request = "Get me the current Apple stock price and recent performance"
    response3 = invoke_agent(runtime_arn, market_request, session_id)
    print(
        "✅ レスポンス:", response3[:200] + "..." if len(response3) > 200 else response3
    )

    # Check if market data was attempted
    market_data_attempted = any(
        keyword in response3.lower()
        for keyword in ["apple", "aapl", "stock", "price", "market"]
    )
    print(f"🔍 市場データ取得: {'✅ はい' if market_data_attempted else '❌ いいえ'}")

    if market_data_attempted:
        tests_passed += 1

    print()
    time.sleep(5)  # Wait to avoid throttling

    # Test 4: News Search
    print("📋 テスト 4: ニュース検索")
    print("-" * 30)

    news_request = "Find recent news about AI and technology stocks"
    response4 = invoke_agent(runtime_arn, news_request, session_id)
    print(
        "✅ レスポンス:", response4[:200] + "..." if len(response4) > 200 else response4
    )

    # Check if news search was attempted
    news_retrieved = any(
        keyword in response4.lower()
        for keyword in ["news", "ai", "technology", "search", "recent"]
    )
    print(f"🔍 ニュース取得: {'✅ はい' if news_retrieved else '❌ いいえ'}")

    if news_retrieved:
        tests_passed += 1

    print()

    # Summary
    print("=" * 60)
    print("📊 テストサマリー")
    print("=" * 60)
    print(f"合格テスト数: {tests_passed}/{total_tests}")
    print(f"成功率: {(tests_passed / total_tests) * 100:.0f}%")

    if tests_passed == total_tests:
        print("🎉 すべてのテストに合格 - エージェントは完全に機能しています！")
    elif tests_passed >= total_tests // 2:
        print("⚠️ 部分的成功 - 一部の機能に注意が必要な場合があります")
    else:
        print("❌ 問題が検出されました - エージェントの確認が必要です")

    return tests_passed == total_tests


def main():
    """メインテスト関数"""
    runtime_arn = load_agent_arn()
    if not runtime_arn:
        return False

    print("テストタイプを選択:")
    print("1. シンプル接続テスト")
    print("2. 包括的機能テスト")

    try:
        choice = input("選択してください (1 または 2, デフォルト=1): ").strip()
        if not choice:
            choice = "1"
    except KeyboardInterrupt:
        print("\nテストがキャンセルされました。")
        return False

    if choice == "2":
        return run_comprehensive_tests(runtime_arn)
    else:
        return run_simple_test(runtime_arn)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

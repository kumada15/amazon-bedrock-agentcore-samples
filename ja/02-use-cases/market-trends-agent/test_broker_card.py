#!/usr/bin/env python3
"""
会話形式の broker card 機能をテストする

Market Trends Agent との正しい対話方法を示します:
1. 構造化フォーマットでブローカープロファイルを送信
2. エージェントがプロファイルをパースしてメモリに保存
3. 今後のすべての対話が保存されたプロファイルに基づいてパーソナライズ
"""

import boto3
import json
from botocore.config import Config


def test_broker_card_conversation():
    """broker card のパースとメモリ機能をテストする"""

    # Load agent ARN
    with open(".agent_arn", "r") as f:
        runtime_arn = f.read().strip()

    client = boto3.client("bedrock-agentcore", region_name="us-east-1")

    # Create consistent session ID for memory persistence across interactions (min 33 chars)
    session_id = "broker-card-test-session-2025-memory-persistence"

    # Test 1: Send broker card format - This is how users should provide their profile
    broker_card_prompt = """Name: Maria Rodriguez
Company: JP Morgan Chase
Role: Senior Investment Advisor
Preferred News Feed: Bloomberg
Industry Interests: cryptocurrency, fintech, gaming
Investment Strategy: growth investing
Risk Tolerance: aggressive
Client Demographics: millennial retail investors
Geographic Focus: Latin America, Asia-Pacific
Recent Interests: blockchain technology, NFTs, metaverse"""

    print("🧪 ブローカーカードのパースをテスト中...")
    print("=" * 50)
    print(f"📋 セッション ID: {session_id}")
    print("📋 構造化フォーマットでブローカープロファイルを送信中:")
    print(broker_card_prompt)
    print("\n" + "=" * 50)

    try:
        # Configure client with longer timeout for complex broker card processing
        config = Config(read_timeout=120)
        client = boto3.client(
            "bedrock-agentcore", region_name="us-east-1", config=config
        )

        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps({"prompt": broker_card_prompt}).encode("utf-8"),
        )

        if "response" in response:
            result = response["response"].read().decode("utf-8")
            print("✅ ブローカーカードへのエージェント応答:")
            print(result)
            print("\n" + "=" * 50)

            # Test 2: Ask for market analysis - Should be personalized based on stored profile
            print("🧪 パーソナライズされた市場分析をテスト中...")
            print(
                "📋 フォローアップ質問: 'It's Maria Rodriguez, What's the latest news on cryptocurrency and fintech stocks?'"
            )
            print("\n" + "=" * 50)

            analysis_prompt = "It's Maria Rodriguez, What's the latest news on cryptocurrency and fintech stocks?"

            response2 = client.invoke_agent_runtime(
                agentRuntimeArn=runtime_arn,
                runtimeSessionId=session_id,
                payload=json.dumps({"prompt": analysis_prompt}).encode("utf-8"),
            )

            if "response" in response2:
                result2 = response2["response"].read().decode("utf-8")
                print("✅ パーソナライズされた市場分析:")
                print(result2)

                # Check if response is personalized
                personalization_indicators = [
                    "maria",
                    "jp morgan",
                    "aggressive",
                    "cryptocurrency",
                    "fintech",
                    "gaming",
                    "growth investing",
                    "millennial",
                    "blockchain",
                    "nft",
                    "metaverse",
                ]
                found_indicators = [
                    indicator
                    for indicator in personalization_indicators
                    if indicator in result2.lower()
                ]

                if found_indicators:
                    print("\n🎯 成功: レスポンスがパーソナライズされています！")
                    print(
                        f"   パーソナライズ指標が見つかりました: {', '.join(found_indicators)}"
                    )
                else:
                    print("\n⚠️  警告: レスポンスが完全にパーソナライズされていない可能性があります")

                print("\n" + "=" * 50)
                print("✅ デモンストレーション完了")
                print(
                    "Market Trends Agent との正しい対話方法を示しています:"
                )
                print("1. 構造化フォーマットでブローカープロファイルを送信（上記参照）")
                print("2. エージェントが自動的にプロファイルをパースして保存")
                print("3. 今後のすべての市場分析がプロファイルに基づいてパーソナライズ")

        else:
            print("❌ レスポンスを受信できませんでした")

    except Exception as e:
        print(f"❌ エラー: {e}")


def show_broker_card_template():
    """ユーザーに期待される broker card フォーマットを表示する"""
    print("\n📋 ブローカーカードテンプレート")
    print("=" * 50)
    print("このテンプレートをコピーして、情報を入力してください:")
    print()
    template = """Name: [Your Full Name]
Company: [Your Company/Firm]
Role: [Your Role/Title]
Preferred News Feed: [Bloomberg, WSJ, Reuters, etc.]
Industry Interests: [technology, healthcare, energy, etc.]
Investment Strategy: [growth, value, dividend, etc.]
Risk Tolerance: [conservative, moderate, aggressive]
Client Demographics: [retail, institutional, high net worth, etc.]
Geographic Focus: [North America, Europe, Asia-Pacific, etc.]
Recent Interests: [specific sectors, trends, or companies]"""

    print(template)
    print("\n" + "=" * 50)


if __name__ == "__main__":
    print("🚀 Market Trends Agent - ブローカーカードデモンストレーション")
    print("=" * 60)

    # Show template first
    show_broker_card_template()

    # Run the test
    test_broker_card_conversation()

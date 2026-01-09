#!/usr/bin/env python3
"""
基本エージェントテストスクリプト

このスクリプトは基本エージェントをシンプルな会話プロンプトでテストします。
基本エージェントは追加ツールなし - コアの Q&A 機能のみです。

使用方法:
    python test_basic_agent.py <agent_arn>

    agent_arn: 基本エージェント Runtime の ARN（必須）

例:
    # 基本エージェントをテスト
    python test_basic_agent.py arn:aws:bedrock-agentcore:<region>:123456789012:runtime/basic-agent-id

    # Terraform 出力から取得
    python test_basic_agent.py $(terraform output -raw agent_runtime_arn)
"""

import boto3
import json
import sys


def extract_region_from_arn(arn):
    """エージェント Runtime ARN から AWS リージョンを抽出

    ARN 形式: arn:aws:bedrock-agentcore:REGION:account:runtime/id

    Args:
        arn: エージェント Runtime ARN 文字列

    Returns:
        str: AWS リージョンコード

    Raises:
        ValueError: ARN 形式が無効またはリージョンを抽出できない場合
    """
    try:
        parts = arn.split(':')
        if len(parts) < 4:
            raise ValueError(
                f"Invalid ARN format: {arn}\n"
                f"Expected format: arn:aws:bedrock-agentcore:REGION:account:runtime/id"
            )
        
        region = parts[3]
        if not region:
            raise ValueError(
                f"Region not found in ARN: {arn}\n"
                f"Expected format: arn:aws:bedrock-agentcore:REGION:account:runtime/id"
            )
        
        return region
        
    except IndexError:
        raise ValueError(
            f"Invalid ARN format: {arn}\n"
            f"Expected format: arn:aws:bedrock-agentcore:REGION:account:runtime/id"
        )


def test_agent(client, agent_arn, test_name, prompt):
    """指定されたプロンプトでエージェントをテスト

    Args:
        client: boto3 bedrock-agentcore クライアント
        agent_arn: エージェント Runtime の ARN
        test_name: 表示用のテスト名
        prompt: エージェントに送信するプロンプト

    Returns:
        bool: テスト成功時は True、失敗時は False
    """
    print(f"\n{'=' * 80}")
    print(f"テスト: {test_name}")
    print(f"{'=' * 80}\n")
    print(f"プロンプト: '{prompt}'")
    print("-" * 80)

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
        )

        print(f"ステータス: {response['ResponseMetadata']['HTTPStatusCode']}")
        print(f"Content Type: {response.get('contentType', 'N/A')}")
        
        # ストリーミングレスポンスボディを読み取り
        response_text = ""
        if 'response' in response:
            response_body = response['response'].read()
            response_text = response_body.decode('utf-8')
        
        if response_text:
            try:
                result = json.loads(response_text)
                response_content = result.get('response', response_text)
                print(f"\n✅ レスポンス:\n{response_content}")
            except json.JSONDecodeError:
                print(f"\n✅ レスポンス:\n{response_text}")
        else:
            print("\n⚠️  レスポンスの内容が受信されませんでした")

        return True

    except Exception as e:
        print(f"\n❌ エラー: {str(e)}")
        return False


def main():
    """メインテスト実行関数"""
    if len(sys.argv) < 2:
        print("エラー: エージェントARN引数が必要です")
        print("\n使用方法:")
        print(f"  {sys.argv[0]} <agent_arn>")
        print("\n例:")
        print(f"  {sys.argv[0]} arn:aws:bedrock-agentcore:<region>:123456789012:runtime/agent-id")
        print("\nTerraformから取得する場合:")
        print(f"  {sys.argv[0]} $(terraform output -raw agent_runtime_arn)")
        sys.exit(1)

    agent_arn = sys.argv[1]

    # ARN からリージョンを抽出
    try:
        region = extract_region_from_arn(agent_arn)
    except ValueError as e:
        print(f"\n❌ エラー: {e}\n")
        sys.exit(1)

    print("=" * 80)
    print("基本エージェントテストスイート")
    print("=" * 80)
    print(f"\nエージェントARN: {agent_arn}")
    print(f"リージョン: {region}\n")

    # 抽出したリージョンで boto3 クライアントを初期化
    client = boto3.client("bedrock-agentcore", region_name=region)

    # 基本エージェント用テストケース（ツールなし、Q&A のみ）
    tests = [
        {
            "name": "簡単な挨拶",
            "prompt": "Hello! Can you introduce yourself?",
        },
        {
            "name": "推論タスク",
            "prompt": "Explain what cloud computing is in simple terms and list three key benefits.",
        },
    ]

    # すべてのテストを実行
    results = []
    for test in tests:
        passed = test_agent(client, agent_arn, test["name"], test["prompt"])
        results.append({"name": test["name"], "passed": passed})

    # サマリーを表示
    print(f"\n{'=' * 80}")
    print("テスト結果サマリー")
    print("=" * 80)

    for result in results:
        status = "✅ 成功" if result["passed"] else "❌ 失敗"
        print(f"{status} - {result['name']}")

    # 全体結果
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print(f"\n{'=' * 80}")
    if passed_count == total_count:
        print("✅ すべてのテストに成功しました")
    else:
        print(f"⚠️  {passed_count}/{total_count}件のテストに成功しました")
    print("=" * 80 + "\n")

    # 適切なコードで終了
    sys.exit(0 if passed_count == total_count else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
マルチエージェントシステムテストスクリプト

このスクリプトは Agent-to-Agent (A2A) 通信を使用するマルチエージェントシステムをテストします。
Terraform、CloudFormation、CDK、手動など、任意の方法でデプロイされたエージェントで動作します。

使用方法:
    python test_multi_agent.py <orchestrator_arn> [specialist_arn]

    orchestrator_arn: オーケストレーターエージェントの ARN（必須）
    specialist_arn: スペシャリストエージェントの ARN（オプション、独立テスト用）

例:
    # A2A 通信でオーケストレーターをテスト
    python test_multi_agent.py arn:aws:bedrock-agentcore:<region>:123456789012:runtime/orchestrator-id

    # 両方のエージェントを独立してテスト
    python test_multi_agent.py \\
        arn:aws:bedrock-agentcore:<region>:123456789012:runtime/orchestrator-id \\
        arn:aws:bedrock-agentcore:<region>:123456789012:runtime/specialist-id
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


def test_agent(client, agent_arn, agent_name, prompt):
    """指定されたプロンプトで単一のエージェントをテスト

    Args:
        client: boto3 bedrock-agentcore クライアント
        agent_arn: エージェント Runtime の ARN
        agent_name: 表示用の名前
        prompt: 送信するテストプロンプト
    """
    print(f"\nプロンプト: '{prompt}'")
    print("-" * 80)
    
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt})
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
                # 読みやすさのため長いレスポンスを省略
                if len(response_content) > 500:
                    print(f"\n✅ レスポンス:\n{response_content[:500]}...")
                    print("\n[表示のためレスポンスを省略しました]")
                else:
                    print(f"\n✅ レスポンス:\n{response_content}")
            except json.JSONDecodeError:
                if len(response_text) > 500:
                    print(f"\n✅ レスポンス:\n{response_text[:500]}...")
                else:
                    print(f"\n✅ レスポンス:\n{response_text}")
        else:
            print("\n⚠️  レスポンスの内容が受信されませんでした")

        return True

    except Exception as e:
        print(f"\n❌ {agent_name}のテストでエラー: {e}")
        return False

def test_multi_agent(orchestrator_arn, specialist_arn=None):
    """マルチエージェントシステムをテスト

    Args:
        orchestrator_arn: オーケストレーターエージェント Runtime ARN（必須）
        specialist_arn: スペシャリストエージェント Runtime ARN（オプション）
    """

    # オーケストレーター ARN からリージョンを抽出
    try:
        region = extract_region_from_arn(orchestrator_arn)
    except ValueError as e:
        print(f"\n❌ エラー: {e}\n")
        sys.exit(1)

    print("\n" + "="*80)
    print("マルチエージェントシステムテスト")
    print("="*80)
    print(f"\nオーケストレーターエージェントARN: {orchestrator_arn}")
    if specialist_arn:
        print(f"スペシャリストエージェントARN: {specialist_arn}")
    else:
        print("スペシャリストエージェント: 指定なし（オーケストレーターのみテスト）")
    print(f"リージョン: {region}")
    
    # 抽出したリージョンで bedrock-agentcore クライアントを作成
    agentcore_client = boto3.client('bedrock-agentcore', region_name=region)
    
    test_results = []
    
    # テスト1: オーケストレーターへの簡単なクエリ
    print("\n" + "="*80)
    print("テスト1: 簡単なクエリ（オーケストレーター）")
    print("="*80)
    result = test_agent(
        agentcore_client,
        orchestrator_arn,
        "オーケストレーター",
        "Hello! Can you introduce yourself and your capabilities?"
    )
    test_results.append(("簡単なクエリ", result))

    # テスト2: A2A 通信をトリガーする複雑なクエリ
    print("\n" + "="*80)
    print("テスト2: A2A通信を使った複雑なクエリ")
    print("="*80)
    result = test_agent(
        agentcore_client,
        orchestrator_arn,
        "オーケストレーター",
        "I need expert analysis. Please coordinate with the specialist agent to provide a comprehensive explanation of cloud computing architectures and best practices."
    )
    test_results.append(("A2A通信テスト", result))

    # サマリー
    print("\n" + "="*80)
    print("テスト結果サマリー")
    print("="*80)

    all_passed = True
    for test_name, passed in test_results:
        status = "✅ 成功" if passed else "❌ 失敗"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print("✅ すべてのテストに成功しました")
    else:
        print("⚠️  一部のテストに失敗しました")
    print("="*80 + "\n")
    
    return all_passed

def main():
    """メインエントリポイント"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ エラー: エージェントランタイムARNが必要です")
        print("\nエージェントARNを取得するには:")
        print("  - Terraform: terraform output orchestrator_runtime_arn")
        print("  - CloudFormation: aws cloudformation describe-stacks --stack-name <stack> --query 'Stacks[0].Outputs'")
        print("  - CDK: cdk deploy --outputs-file outputs.json")
        print("  - コンソール: Bedrock Agent Coreコンソールを確認")
        sys.exit(1)

    orchestrator_arn = sys.argv[1]
    specialist_arn = sys.argv[2] if len(sys.argv) > 2 else None

    # ARN 形式を検証
    if not orchestrator_arn.startswith("arn:aws:bedrock-agentcore:"):
        print(f"\n❌ エラー: オーケストレーターの無効なARN形式です: {orchestrator_arn}")
        print("期待される形式: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id")
        sys.exit(1)

    if specialist_arn and not specialist_arn.startswith("arn:aws:bedrock-agentcore:"):
        print(f"\n❌ エラー: スペシャリストの無効なARN形式です: {specialist_arn}")
        print("期待される形式: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id")
        sys.exit(1)
    
    # テストを実行
    success = test_multi_agent(orchestrator_arn, specialist_arn)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

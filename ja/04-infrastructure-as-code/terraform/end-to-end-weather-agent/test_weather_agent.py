#!/usr/bin/env python3
"""
天気エージェントテストスクリプト

このスクリプトは天気クエリ、コードインタプリタ使用、ブラウザツールの
インタラクションなど様々なプロンプトで天気エージェントをテストします。

使用方法:
    python test_weather_agent.py <agent_arn>

    agent_arn: 天気エージェント Runtime の ARN（必須）

例:
    # 天気エージェントをテスト
    python test_weather_agent.py arn:aws:bedrock-agentcore:<region>:123456789012:runtime/weather-agent-id

    # Terraform 出力から取得
    python test_weather_agent.py $(terraform output -raw agent_runtime_arn)
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
        prompt: 送信するテストプロンプト
    """
    print(f"\nテスト: {test_name}")
    print(f"プロンプト: '{prompt}'")
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
        print(f"\n❌ エラー: {e}")
        return False

def test_weather_agent(agent_arn):
    """様々なシナリオで天気エージェントをテスト

    Args:
        agent_arn: 天気エージェント Runtime ARN
    """

    # ARN からリージョンを抽出
    try:
        region = extract_region_from_arn(agent_arn)
    except ValueError as e:
        print(f"\n❌ エラー: {e}\n")
        sys.exit(1)

    print("\n" + "="*80)
    print("天気エージェントテストスイート")
    print("="*80)
    print(f"\nエージェントARN: {agent_arn}")
    print(f"リージョン: {region}")
    
    # 抽出したリージョンで bedrock-agentcore クライアントを作成
    agentcore_client = boto3.client('bedrock-agentcore', region_name=region)
    
    test_results = []
    
    # テスト1: 簡単な天気クエリ
    print("\n" + "="*80)
    print("テスト1: 簡単な天気クエリ")
    print("="*80)
    result = test_agent(
        agentcore_client,
        agent_arn,
        "基本的な天気",
        "What's the weather like in San Francisco today?"
    )
    test_results.append(("簡単な天気クエリ", result))

    # テスト2: ツールを使った複雑なクエリ（ブラウザ + コードインタプリタ + メモリ）
    print("\n" + "="*80)
    print("テスト2: ツールを使った複雑なクエリ")
    print("="*80)
    result = test_agent(
        agentcore_client,
        agent_arn,
        "ツールを使った天気分析",
        "Look up current weather conditions for Seattle, create a visualization of the temperature trend, and suggest outdoor activities based on the forecast."
    )
    test_results.append(("ツールを使った複雑なクエリ", result))

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
        print("  - Terraform: terraform output agent_runtime_arn")
        print("  - CloudFormation: aws cloudformation describe-stacks --stack-name <stack> --query 'Stacks[0].Outputs'")
        print("  - CDK: cdk deploy --outputs-file outputs.json")
        print("  - コンソール: Bedrock Agent Coreコンソールを確認")
        sys.exit(1)

    agent_arn = sys.argv[1]

    # ARN 形式を検証
    if not agent_arn.startswith("arn:aws:bedrock-agentcore:"):
        print(f"\n❌ エラー: 無効なARN形式です: {agent_arn}")
        print("期待される形式: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id")
        sys.exit(1)
    
    # テストを実行
    success = test_weather_agent(agent_arn)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

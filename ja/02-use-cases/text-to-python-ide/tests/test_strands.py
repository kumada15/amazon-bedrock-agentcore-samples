#!/usr/bin/env python3
"""
strands-agents フレームワークを検証するテストスクリプト
"""

import os
import sys
from dotenv import load_dotenv

def test_strands_import():
    """strands-agents フレームワークのインポートをテストする"""
    print("Strands-Agents のインポートをテスト中")
    print("=" * 40)
    
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel
        print("✓ strands-agents フレームワークのインポートに成功しました")
        return True
    except ImportError as e:
        print(f"✗ strands-agents フレームワークのインポートに失敗しました: {e}")
        print("実行: pip install strands-agents")
        return False

def test_bedrock_model():
    """BedrockModel の作成をテストする"""
    print("\nBedrockModel の作成をテスト中")
    print("=" * 40)
    
    load_dotenv()
    
    try:
        from strands.models import BedrockModel
        
        model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            aws_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        print("✓ BedrockModel の作成に成功しました")
        return True
    except Exception as e:
        print(f"✗ BedrockModel の作成に失敗しました: {e}")
        return False

def test_agent_creation():
    """Agent の作成をテストする"""
    print("\nエージェントの作成をテスト中")
    print("=" * 40)
    
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel
        
        # Create a simple tool
        @tool
        def test_tool(message: str) -> str:
            """シンプルなテストツール"""
            return f"Tool received: {message}"
        
        model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            aws_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        agent = Agent(
            model=model,
            tools=[test_tool],
            system_prompt="あなたはテストエージェントです。"
        )
        
        print("✓ ツール付きエージェントの作成に成功しました")
        return True
    except Exception as e:
        print(f"✗ エージェントの作成に失敗しました: {e}")
        return False

def main():
    """すべての strands-agents テストを実行する"""
    print("Strands-Agents フレームワークテスト")
    print("=" * 50)
    
    load_dotenv()
    
    tests = [
        test_strands_import,
        test_bedrock_model,
        test_agent_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 例外でテストに失敗しました: {e}")
        print()

    print("=" * 50)
    print(f"テスト成功: {passed}/{total}")

    if passed == total:
        print("🎉 Strands-Agents フレームワークは正しく動作しています！")
        return 0
    else:
        print("❌ 一部の strands-agents テストに失敗しました")
        return 1

if __name__ == "__main__":
    sys.exit(main())

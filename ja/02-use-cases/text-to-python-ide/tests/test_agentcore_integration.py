#!/usr/bin/env python3
"""
公式サンプルに従った正しい AgentCore 統合を検証するテストスクリプト
"""

import os
import sys
from dotenv import load_dotenv

def test_agentcore_code_session():
    """AgentCore code_session 機能をテストする"""
    print("AgentCore Code Session をテスト中")
    print("=" * 40)
    
    load_dotenv()
    
    try:
        from bedrock_agentcore.tools.code_interpreter_client import code_session
        print("✓ code_session のインポートに成功しました")

        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        print(f"使用リージョン: {aws_region}")
        
        # Test code execution following the sample pattern
        test_code = "print('Hello from AgentCore!')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')"
        
        try:
            with code_session(aws_region) as code_client:
                print("✓ Code セッションの作成に成功しました")

                response = code_client.invoke("executeCode", {
                    "code": test_code,
                    "language": "python",
                    "clearContext": True
                })

                print("✓ コード実行リクエストを送信しました")

                # Process response stream following the sample pattern
                for event in response["stream"]:
                    result = event.get("result", {})
                    if result.get("isError", False):
                        print(f"✗ 実行エラー: {result}")
                        return False
                    else:
                        structured_content = result.get("structuredContent", {})
                        stdout = structured_content.get("stdout", "")
                        if stdout:
                            print(f"✓ 実行出力: {stdout.strip()}")

                print("✓ AgentCore コード実行に成功しました！")
                return True
                
        except Exception as e:
            print(f"⚠ AgentCore 実行に失敗しました: {e}")
            print("  これは bedrock-agentcore の権限がない場合に予期される動作です")
            return False

    except ImportError as e:
        print(f"✗ インポートに失敗しました: {e}")
        return False

def test_strands_with_agentcore_tool():
    """サンプルパターンに従った AgentCore ツール付き Strands-Agents エージェントをテストする"""
    print("\nStrands-Agents + AgentCore 統合をテスト中")
    print("=" * 40)
    
    try:
        from strands import Agent, tool
        from strands.models import BedrockModel
        from bedrock_agentcore.tools.code_interpreter_client import code_session
        import json
        print("✓ すべてのインポートに成功しました")
        
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Create the execute_python tool following the exact sample pattern
        @tool
        def execute_python(code: str, description: str = "") -> str:
            """sandbox で Python コードを実行する - 公式サンプルパターンに準拠"""
            
            if description:
                code = f"# {description}\n{code}"
            
            print(f"\n 生成されたコード: {code}")
            
            try:
                with code_session(aws_region) as code_client:
                    response = code_client.invoke("executeCode", {
                        "code": code,
                        "language": "python",
                        "clearContext": False
                    })
                
                # Process response following the sample pattern
                for event in response["stream"]:
                    return json.dumps(event["result"])
                        
            except Exception as e:
                return f"Execution failed: {str(e)}"
        
        print("✓ サンプルパターンに従って AgentCore ツールを作成しました")

        # Create Bedrock model
        bedrock_model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            aws_region=aws_region
        )
        print("✓ Bedrock モデルを作成しました")
        
        # Create Strands agent with AgentCore tool following the sample system prompt
        SYSTEM_PROMPT = """あなたはコード実行を通じてすべての回答を検証する AI アシスタントです。

検証の原則:
1. コード、アルゴリズム、または計算について主張する場合 - それらを検証するコードを書く
2. execute_python を使用して数学的計算、アルゴリズム、ロジックをテストする
3. 回答を提供する前に、理解を検証するテストスクリプトを作成する
4. 常に実際のコード実行で作業を示す
5. 不確かな場合は、制限を明示的に述べ、可能なものを検証する

アプローチ:
- プログラミングの概念について質問された場合、デモンストレーションのためにコードで実装する
- 計算を求められた場合、プログラムで計算し、コードも表示する
- アルゴリズムを実装する場合、正確性を証明するテストケースを含める
- 透明性のために検証プロセスを文書化する
- サンドボックスは実行間で状態を維持するため、以前の結果を参照できる

利用可能なツール:
- execute_python: Python コードを実行して出力を確認

応答フォーマット: execute_python ツールは以下を含む JSON 応答を返します:
- sessionId: サンドボックスセッション ID
- id: リクエスト ID
- isError: エラーがあったかどうかを示すブール値
- content: タイプとテキスト/データを含むコンテンツオブジェクトの配列
- structuredContent: コード実行の場合、stdout、stderr、exitCode、executionTime を含む"""
        
        agent = Agent(
            tools=[execute_python],
            system_prompt=SYSTEM_PROMPT,
            model=bedrock_model
        )
        print("✓ サンプルパターンに従って AgentCore ツール付き Strands-Agents エージェントを作成しました")

        # Test the integration with a simple query
        test_query = "Calculate 5 factorial using Python code"
        print(f"\nクエリでテスト中: {test_query}")
        
        try:
            response = agent(test_query)
            print("✓ エージェント応答を受信しました")
            print(f"応答プレビュー: {str(response)[:200]}...")
            return True

        except Exception as e:
            print(f"⚠ エージェント実行に失敗しました: {e}")
            return False

    except Exception as e:
        print(f"✗ 統合テストに失敗しました: {e}")
        return False

def main():
    """公式サンプルに従ったすべての AgentCore 統合テストを実行する"""
    print("AgentCore 統合テスト（公式サンプルに準拠）")
    print("=" * 60)
    
    load_dotenv()
    
    tests = [
        test_agentcore_code_session,
        test_strands_with_agentcore_tool
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

    print("=" * 60)
    print(f"テスト成功: {passed}/{total}")

    if passed == total:
        print("🎉 すべての AgentCore 統合テストに成功しました！")
        print("\n利用可能な AgentCore 機能:")
        print("✓ サンドボックス環境でのリアルコード実行")
        print("✓ AgentCore ツール付き Strands-Agents")
        print("✓ 公式サンプルパターンに準拠")
        return 0
    elif passed > 0:
        print("⚠ 部分的成功 - 一部の AgentCore 機能が利用可能")
        print("アプリケーションは利用可能な機能で動作します")
        return 0
    else:
        print("❌ AgentCore 統合は利用できません")
        print("アプリケーションは代わりに Strands シミュレーションを使用します")
        return 1

if __name__ == "__main__":
    sys.exit(main())

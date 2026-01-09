#!/usr/bin/env python3
"""
AgentCore Code Interpreter の総合テストスイート
"""

import os
import sys
import subprocess
import time
import requests
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'backend'))

class TestRunner:
    def __init__(self):
        self.backend_pid = None
        self.frontend_pid = None
        self.passed_tests = 0
        self.total_tests = 0
        
    def start_backend(self):
        """バックエンドサーバーを起動する"""
        print("🚀 バックエンドサーバーを起動中...")
        
        # Kill existing backend
        os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
        time.sleep(2)
        
        # Start backend
        backend_process = subprocess.Popen(
            [sys.executable, "backend/main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.backend_pid = backend_process.pid
        
        # Wait for backend to start
        for i in range(30):
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print("✅ バックエンドの起動に成功しました")
                    return True
            except:
                time.sleep(1)

        print("❌ バックエンドの起動に失敗しました")
        return False
    
    def stop_backend(self):
        """バックエンドサーバーを停止する"""
        if self.backend_pid:
            try:
                os.kill(self.backend_pid, 9)
                print("✅ バックエンドを停止しました")
            except:
                pass
        os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
    
    def run_test(self, test_name, test_func):
        """単一のテストを実行する"""
        print(f"\n📋 {test_name} を実行中...")
        print("-" * 50)

        self.total_tests += 1
        try:
            if test_func():
                print(f"✅ {test_name} 成功")
                self.passed_tests += 1
                return True
            else:
                print(f"❌ {test_name} 失敗")
                return False
        except Exception as e:
            print(f"❌ {test_name} エラー: {e}")
            return False
    
    def test_environment_setup(self):
        """環境と依存関係をテストする"""
        print("🔍 環境セットアップをテスト中")

        # Check virtual environment
        if not os.path.exists(project_root / "venv"):
            print("❌ 仮想環境が見つかりません")
            return False

        # Check AWS credentials
        try:
            from main import setup_aws_credentials
            aws_session, aws_region = setup_aws_credentials()
            if aws_session and aws_region:
                print("✅ AWS 認証情報が設定されています")
            else:
                print("❌ AWS 認証情報が設定されていません")
                return False
        except Exception as e:
            print(f"❌ AWS セットアップに失敗しました: {e}")
            return False

        # Check dependencies
        try:
            import strands
            import bedrock_agentcore
            print("✅ コア依存関係が利用可能です")
        except ImportError as e:
            print(f"❌ 依存関係が不足しています: {e}")
            return False

        return True
    
    def test_model_initialization(self):
        """モデル初期化とフォールバックをテストする"""
        print("🤖 モデル初期化をテスト中")

        try:
            from main import create_bedrock_model_with_fallback

            model, model_id = create_bedrock_model_with_fallback('us-east-1')

            print(f"✅ モデルを初期化しました: {model_id}")

            if model_id.startswith('us.'):
                print("✅ 推論プロファイルを使用中")
            else:
                print("⚠️  標準モデルを使用中")

            return True
        except Exception as e:
            print(f"❌ モデル初期化に失敗しました: {e}")
            return False
    
    def test_agent_initialization(self):
        """エージェント初期化をテストする"""
        print("🤖 エージェント初期化をテスト中")

        try:
            from main import setup_aws_credentials, initialize_agents
            import main

            # Setup AWS
            aws_session, aws_region = setup_aws_credentials()
            main.aws_session = aws_session
            main.aws_region = aws_region

            # Initialize agents
            initialize_agents()

            if hasattr(main, 'code_generator_agent') and main.code_generator_agent:
                print("✅ コード生成エージェントを初期化しました")
            else:
                print("❌ コード生成エージェントが初期化されていません")
                return False

            if hasattr(main, 'code_executor_agent'):
                print("✅ コード実行エージェントを初期化しました")
            else:
                print("❌ コード実行エージェントが初期化されていません")
                return False

            return True
        except Exception as e:
            print(f"❌ エージェント初期化に失敗しました: {e}")
            return False
    
    def test_code_generation_api(self):
        """コード生成 API をテストする"""
        print("🔧 コード生成 API をテスト中")

        try:
            response = requests.post(
                "http://localhost:8000/api/generate-code",
                json={"prompt": "Create a function to calculate factorial"},
                timeout=30
            )

            if response.status_code != 200:
                print(f"❌ API がステータス {response.status_code} を返しました")
                return False

            data = response.json()
            code = data.get("code", "")

            if not isinstance(code, str):
                print(f"❌ コードが文字列ではありません: {type(code)}")
                return False

            if len(code.strip()) == 0:
                print("❌ 生成されたコードが空です")
                return False

            print(f"✅ {len(code)} 文字のコードを生成しました")
            return True

        except Exception as e:
            print(f"❌ コード生成テストに失敗しました: {e}")
            return False
    
    def test_code_execution_api(self):
        """コード実行 API をテストする"""
        print("⚡ コード実行 API をテスト中")

        test_code = """
print("Hello, World!")
result = 2 + 2
print(f"2 + 2 = {result}")
"""

        try:
            response = requests.post(
                "http://localhost:8000/api/execute-code",
                json={"code": test_code.strip()},
                timeout=30
            )

            if response.status_code != 200:
                print(f"❌ API がステータス {response.status_code} を返しました")
                return False

            data = response.json()
            result = data.get("result", "")

            if not isinstance(result, str):
                print(f"❌ 結果が文字列ではありません: {type(result)}")
                return False

            if len(result.strip()) == 0:
                print("❌ 実行結果が空です")
                return False

            print(f"✅ {len(result)} 文字の出力で実行が完了しました")
            return True

        except Exception as e:
            print(f"❌ コード実行テストに失敗しました: {e}")
            return False
    
    def test_health_endpoint(self):
        """ヘルスエンドポイントをテストする"""
        print("🏥 ヘルスエンドポイントをテスト中")

        try:
            response = requests.get("http://localhost:8000/health", timeout=5)

            if response.status_code != 200:
                print(f"❌ ヘルスチェックがステータス {response.status_code} を返しました")
                return False

            data = response.json()

            if data.get("status") != "healthy":
                print(f"❌ システムが正常ではありません: {data.get('status')}")
                return False

            print(f"✅ システムは正常、モデル: {data.get('current_model', '不明')}")
            return True

        except Exception as e:
            print(f"❌ ヘルスチェックに失敗しました: {e}")
            return False
    
    def test_agentcore_integration(self):
        """AgentCore 統合をテストする"""
        print("🔗 AgentCore 統合をテスト中")

        try:
            from bedrock_agentcore.tools.code_interpreter_client import code_session

            with code_session('us-east-1') as code_client:
                response = code_client.invoke('executeCode', {
                    'code': 'print("AgentCore test successful")',
                    'language': 'python',
                    'clearContext': True
                })

                print("✅ AgentCore 統合が動作しています")
                return True

        except Exception as e:
            print(f"❌ AgentCore 統合に失敗しました: {e}")
            return False
    
    def run_all_tests(self):
        """すべてのテストを実行する"""
        print("🎯 AgentCore Code Interpreter - 総合テストスイート")
        print("=" * 70)

        # Environment tests (don't need backend)
        tests_no_backend = [
            ("環境セットアップ", self.test_environment_setup),
            ("モデル初期化", self.test_model_initialization),
            ("エージェント初期化", self.test_agent_initialization),
            ("AgentCore 統合", self.test_agentcore_integration)
        ]

        for test_name, test_func in tests_no_backend:
            self.run_test(test_name, test_func)

        # Start backend for API tests
        if not self.start_backend():
            print("❌ バックエンドなしで API テストを実行できません")
            return self.passed_tests, self.total_tests

        # API tests (need backend)
        tests_with_backend = [
            ("ヘルスエンドポイント", self.test_health_endpoint),
            ("コード生成 API", self.test_code_generation_api),
            ("コード実行 API", self.test_code_execution_api)
        ]

        for test_name, test_func in tests_with_backend:
            self.run_test(test_name, test_func)

        return self.passed_tests, self.total_tests

    def cleanup(self):
        """リソースをクリーンアップする"""
        print("\n🧹 クリーンアップ中...")
        self.stop_backend()

def main():
    """メインテストランナー"""
    runner = TestRunner()

    try:
        passed, total = runner.run_all_tests()

        print("\n" + "=" * 70)
        print(f"🎯 テスト結果: {passed}/{total} テスト成功")

        if passed == total:
            print("🎉 すべてのテストに成功しました！アプリケーションは使用準備完了です。")
            return 0
        else:
            print("❌ 一部のテストに失敗しました。上記の出力を確認してください。")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️  ユーザーによりテストが中断されました")
        return 1
    except Exception as e:
        print(f"\n❌ テストスイートエラー: {e}")
        return 1
    finally:
        runner.cleanup()

if __name__ == "__main__":
    sys.exit(main())

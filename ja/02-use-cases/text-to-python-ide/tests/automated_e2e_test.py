#!/usr/bin/env python3
"""
AgentCore Code Interpreter の自動エンドツーエンドテストスイート
ユーザー入力なしで完全に自動実行
"""

import os
import sys
import subprocess
import time
import requests
import json
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'backend'))

class AutomatedE2ETest:
    def __init__(self):
        self.backend_process = None
        self.frontend_process = None
        self.test_results = []
        self.start_time = time.time()
        
    def log_result(self, test_name, passed, details=""):
        """テスト結果をログ出力する"""
        status = "✅ PASS" if passed else "❌ FAIL"
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:.1f}s] {status} {test_name}")
        if details and not passed:
            print(f"    Details: {details}")
        
        self.test_results.append({
            'name': test_name,
            'passed': passed,
            'details': details,
            'elapsed': elapsed
        })
        return passed
    
    def start_backend(self):
        """バックエンドサーバーを起動する"""
        print("🚀 バックエンドサーバーを起動中...")
        
        # Kill existing processes
        os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
        time.sleep(2)
        
        # Start backend
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root)
        
        self.backend_process = subprocess.Popen(
            [sys.executable, "backend/main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Wait for backend to start
        for i in range(30):
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    return self.log_result("バックエンド起動", True)
            except:
                time.sleep(1)
        
        return self.log_result("バックエンド起動", False, "30 秒以内にバックエンドが起動しませんでした")
    
    def test_health_endpoint(self):
        """ヘルスエンドポイントをテストする"""
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return self.log_result("ヘルスエンドポイント",
                                     data.get("status") == "healthy",
                                     f"ステータス: {data.get('status')}")
            else:
                return self.log_result("ヘルスエンドポイント", False, f"ステータスコード: {response.status_code}")
        except Exception as e:
            return self.log_result("ヘルスエンドポイント", False, str(e))
    
    def test_agents_status(self):
        """エージェントステータスエンドポイントをテストする"""
        try:
            response = requests.get("http://localhost:8000/api/agents/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self.log_result("エージェントステータス",
                                     data.get("agents_initialized", False),
                                     f"モデル: {data.get('current_model', 'Unknown')}")
            else:
                return self.log_result("エージェントステータス", False, f"ステータスコード: {response.status_code}")
        except Exception as e:
            return self.log_result("エージェントステータス", False, str(e))
    
    def test_code_generation(self):
        """コード生成 API をテストする"""
        try:
            test_prompt = "Create a function to calculate the factorial of a number using recursion"
            response = requests.post(
                "http://localhost:8000/api/generate-code",
                json={"prompt": test_prompt},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                code = data.get("code", "")

                # Validate response
                if not isinstance(code, str):
                    return self.log_result("コード生成", False, f"コードが文字列ではありません: {type(code)}")

                if len(code.strip()) == 0:
                    return self.log_result("コード生成", False, "生成されたコードが空です")

                # Check if code contains expected elements
                code_lower = code.lower()
                has_function = "def " in code_lower
                has_factorial = "factorial" in code_lower

                if has_function and has_factorial:
                    return self.log_result("コード生成", True, f"{len(code)} 文字を生成")
                else:
                    return self.log_result("コード生成", False, "コードに期待される要素が含まれていません")
            else:
                return self.log_result("コード生成", False, f"ステータスコード: {response.status_code}")
                
        except Exception as e:
            return self.log_result("コード生成", False, str(e))
    
    def test_code_execution(self):
        """コード実行 API をテストする"""
        try:
            test_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Test the function
result = fibonacci(10)
print(f"Fibonacci(10) = {result}")
"""
            
            response = requests.post(
                "http://localhost:8000/api/execute-code",
                json={"code": test_code.strip()},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", "")

                # Validate response
                if not isinstance(result, str):
                    return self.log_result("コード実行", False, f"結果が文字列ではありません: {type(result)}")

                if len(result.strip()) == 0:
                    return self.log_result("コード実行", False, "実行結果が空です")

                # Check if result contains expected output
                if "55" in result or "Fibonacci" in result:
                    return self.log_result("コード実行", True, f"結果: {result[:50]}...")
                else:
                    return self.log_result("コード実行", False, f"予期しない結果: {result[:100]}")
            else:
                return self.log_result("コード実行", False, f"ステータスコード: {response.status_code}")
                
        except Exception as e:
            return self.log_result("コード実行", False, str(e))
    
    def test_performance_metrics(self):
        """並行リクエストでパフォーマンスをテストする"""
        try:
            def make_request():
                start = time.time()
                response = requests.post(
                    "http://localhost:8000/api/generate-code",
                    json={"prompt": "Create a simple hello world function"},
                    timeout=15
                )
                elapsed = time.time() - start
                return response.status_code == 200, elapsed
            
            # Test concurrent requests
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(make_request) for _ in range(3)]
                results = [future.result() for future in as_completed(futures)]

            successful = sum(1 for success, _ in results if success)
            avg_time = sum(elapsed for _, elapsed in results) / len(results)

            if successful >= 2 and avg_time < 20:  # At least 2/3 successful, under 20s average
                return self.log_result("パフォーマンステスト", True,
                                     f"{successful}/3 成功、平均 {avg_time:.1f} 秒")
            else:
                return self.log_result("パフォーマンステスト", False,
                                     f"{successful}/3 成功、平均 {avg_time:.1f} 秒")
                
        except Exception as e:
            return self.log_result("パフォーマンステスト", False, str(e))
    
    def test_error_handling(self):
        """エラーハンドリングをテストする"""
        try:
            # Test invalid code execution
            response = requests.post(
                "http://localhost:8000/api/execute-code",
                json={"code": "invalid_function_call()"},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", "")

                # Should contain error information
                if "error" in result.lower() or "exception" in result.lower():
                    return self.log_result("エラーハンドリング", True, "実行エラーを適切に処理しました")
                else:
                    return self.log_result("エラーハンドリング", False, "エラーが適切に報告されていません")
            else:
                return self.log_result("エラーハンドリング", False, f"ステータスコード: {response.status_code}")
                
        except Exception as e:
            return self.log_result("エラーハンドリング", False, str(e))
    
    def cleanup(self):
        """プロセスをクリーンアップする"""
        print("\n🧹 クリーンアップ中...")
        
        if self.backend_process:
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
            except:
                try:
                    self.backend_process.kill()
                except:
                    pass
        
        # Kill any remaining processes
        os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
        os.system("lsof -ti:3000 | xargs kill -9 2>/dev/null || true")
    
    def run_all_tests(self):
        """すべての自動テストを実行する"""
        print("🎯 AgentCore Code Interpreter - 自動 E2E テストスイート")
        print("=" * 70)
        
        try:
            # Start backend
            if not self.start_backend():
                print("❌ バックエンドなしでは続行できません")
                return False

            # Run tests in sequence
            tests = [
                ("ヘルスチェック", self.test_health_endpoint),
                ("エージェントステータス", self.test_agents_status),
                ("コード生成", self.test_code_generation),
                ("コード実行", self.test_code_execution),
                ("エラーハンドリング", self.test_error_handling),
                ("パフォーマンス", self.test_performance_metrics)
            ]

            for test_name, test_func in tests:
                print(f"\n📋 {test_name} を実行中...")
                test_func()
            
            # Calculate results
            passed = sum(1 for result in self.test_results if result['passed'])
            total = len(self.test_results)
            total_time = time.time() - self.start_time

            print("\n" + "=" * 70)
            print(f"🎯 テスト結果: {passed}/{total} テスト成功（{total_time:.1f} 秒）")

            if passed == total:
                print("🎉 すべてのテストが成功しました！アプリケーションは正常に動作しています。")
                return True
            else:
                print("❌ 一部のテストが失敗しました。上記の出力を確認してください。")
                failed_tests = [r['name'] for r in self.test_results if not r['passed']]
                print(f"失敗したテスト: {', '.join(failed_tests)}")
                return False

        except KeyboardInterrupt:
            print("\n⚠️  ユーザーによりテストが中断されました")
            return False
        except Exception as e:
            print(f"\n❌ テストスイートエラー: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """メインテストランナー"""
    test_runner = AutomatedE2ETest()
    success = test_runner.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

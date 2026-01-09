#!/usr/bin/env python3
"""
アプリケーションが正しくセットアップされているかを確認するクイック検証スクリプト
"""

import os
import sys
import subprocess
from pathlib import Path

def check_files():
    """必須ファイルが存在するかを確認する"""
    print("📁 必須ファイルを確認中...")
    
    project_root = Path(__file__).parent.parent
    required_files = [
        "backend/main.py",
        "frontend/package.json",
        "frontend/src/App.js",
        ".env",
        "start.sh",
        "setup.sh"
    ]
    
    missing = []
    for file_path in required_files:
        if not (project_root / file_path).exists():
            missing.append(file_path)
    
    if missing:
        print(f"❌ 不足しているファイル: {', '.join(missing)}")
        return False
    else:
        print("✅ すべての必須ファイルが存在します")
        return True

def check_environment():
    """Python 環境を確認する"""
    print("\n🐍 Python 環境を確認中...")
    
    project_root = Path(__file__).parent.parent
    venv_path = project_root / "venv"
    
    if not venv_path.exists():
        print("❌ 仮想環境が見つかりません")
        return False

    # Check if we're in the virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ 仮想環境がアクティブです")
    else:
        print("⚠️  仮想環境がアクティブではありません")
    
    return True

def check_dependencies():
    """Python 依存関係を確認する"""
    print("\n📦 依存関係を確認中...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'boto3',
        'strands',
        'bedrock-agentcore'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ 不足しているパッケージ: {', '.join(missing)}")
        return False
    else:
        print("✅ すべての依存関係がインストール済みです")
        return True

def check_aws_config():
    """AWS 設定を確認する"""
    print("\n☁️  AWS 設定を確認中...")
    
    # Check .env file
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print("❌ .env ファイルが見つかりません")
        return False
    
    # Check for AWS configuration
    env_content = env_file.read_text()
    has_profile = "AWS_PROFILE" in env_content
    has_keys = "AWS_ACCESS_KEY_ID" in env_content and "AWS_SECRET_ACCESS_KEY" in env_content
    
    if has_profile:
        print("✅ AWS プロファイル設定が見つかりました")
        return True
    elif has_keys:
        print("✅ AWS アクセスキー設定が見つかりました")
        return True
    else:
        print("❌ .env に AWS 設定が見つかりません")
        return False

def check_frontend():
    """フロントエンドのセットアップを確認する"""
    print("\n🌐 フロントエンドのセットアップを確認中...")
    
    project_root = Path(__file__).parent.parent
    frontend_path = project_root / "frontend"
    
    if not (frontend_path / "node_modules").exists():
        print("❌ フロントエンドの依存関係がインストールされていません")
        return False

    print("✅ フロントエンドの依存関係がインストール済みです")
    return True

def main():
    """すべての検証チェックを実行する"""
    print("🔍 AgentCore Code Interpreter - セットアップ検証")
    print("=" * 60)
    
    checks = [
        ("ファイル", check_files),
        ("環境", check_environment),
        ("依存関係", check_dependencies),
        ("AWS 設定", check_aws_config),
        ("フロントエンド", check_frontend)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                passed += 1
        except Exception as e:
            print(f"❌ {check_name} チェックに失敗: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 検証結果: {passed}/{total} チェック成功")

    if passed == total:
        print("🎉 セットアップ検証に成功しました！アプリケーションを実行する準備ができています。")
        print("\n🚀 次のステップ:")
        print("   1. 実行: ./start.sh")
        print("   2. 開く: http://localhost:3000")
        return 0
    else:
        print("❌ セットアップ検証に失敗しました。上記の問題を修正してください。")
        print("\n🔧 一般的な修正方法:")
        print("   1. 実行: ./setup.sh")
        print("   2. .env で AWS 認証情報を設定")
        print("   3. フロントエンドをインストール: cd frontend && npm install")
        return 1

if __name__ == "__main__":
    sys.exit(main())

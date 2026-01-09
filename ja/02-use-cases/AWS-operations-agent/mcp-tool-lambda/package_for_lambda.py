#!/usr/bin/env python3
"""
mcp-tool-lambda ディレクトリから Lambda 関数をデプロイ用にパッケージ化
SAM テンプレートの期待に合致
"""
import os
import zipfile
from pathlib import Path

def create_lambda_package():
    """SAM テンプレートに合致する Lambda デプロイ用 ZIP パッケージを作成する"""
    current_dir = Path.cwd()
    packaging_dir = current_dir / "packaging"
    lambda_dir = current_dir / "lambda"
    
    # Ensure packaging directory exists
    packaging_dir.mkdir(exist_ok=True)
    
    # SAM template expects this specific filename
    lambda_deployment_zip = packaging_dir / "mcp-tool-lambda.zip"
    
    print(f"Lambda関数をパッケージ化中: {lambda_dir}")
    print(f"パッケージを作成中: {lambda_deployment_zip}")
    
    # Check if lambda directory exists
    if not lambda_dir.exists():
        print(f"❌ Lambdaディレクトリが見つかりません: {lambda_dir}")
        return False

    # Check if dependencies are packaged in current directory
    deps_packaging_dir = current_dir / "packaging"
    if not deps_packaging_dir.exists():
        print(f"❌ 依存関係パッケージディレクトリが見つかりません: {deps_packaging_dir}")
        print("   依存関係を先にインストールしてください！")
        return False
    
    # Create the Lambda deployment ZIP
    print("📦 mcp-tool-lambda.zipを作成中...")
    with zipfile.ZipFile(lambda_deployment_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        # Add handler files from lambda directory
        handler_files = [
            "mcp-tool-handler.py",
            "optimized_mcp_system_prompt.py"
        ]
        
        for file_name in handler_files:
            file_path = lambda_dir / file_name
            if file_path.exists():
                zipf.write(file_path, file_name)
                print(f"  ✅ 追加しました: {file_name}")
            else:
                print(f"  ⚠️  見つかりません: {file_name}")
        
        # Add dependencies directly to the root of the ZIP (not in python/ subdirectory)
        deps_dir = deps_packaging_dir / "python"
        if deps_dir.exists():
            print("  📦 依存関係をルートレベルに追加中...")
            dep_count = 0
            for root, _, files in os.walk(deps_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Put dependencies at root level, not in python/ subdirectory
                    arcname = os.path.relpath(file_path, deps_dir)
                    zipf.write(file_path, arcname)
                    dep_count += 1
            print(f"  ✅ {dep_count}個の依存ファイルをルートレベルに追加しました")
        else:
            print(f"  ❌ 依存関係が見つかりません: {deps_dir}")
            return False
    
    # Show package size
    if lambda_deployment_zip.exists():
        size_mb = lambda_deployment_zip.stat().st_size / (1024 * 1024)
        print(f"✅ パッケージを作成しました: {size_mb:.2f} MB")
        print(f"📍 場所: {lambda_deployment_zip}")
        return True
    else:
        print("❌ パッケージの作成に失敗しました")
        return False

if __name__ == "__main__":
    success = create_lambda_package()
    if not success:
        exit(1)
    print("🎉 Lambdaパッケージングが正常に完了しました！")

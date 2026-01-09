#!/bin/bash
# agentcore-runtime-gw-mcp-toolkit のビルドスクリプト

echo "パッケージをビルド中..."
python -m build

echo "パッケージのビルドが完了しました！"
echo "ローカルにインストール: pip install dist/agentcore_runtime_gw_mcp_toolkit-0.1.0-py3-none-any.whl"
echo "PyPI にアップロード: twine upload dist/*"

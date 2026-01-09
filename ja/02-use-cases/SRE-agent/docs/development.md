# 開発

## テストの実行

SRE エージェントには信頼性を確保するための包括的なテストカバレッジが含まれています：

```bash
# すべてのテストを実行
pytest

# カバレッジレポート付きでテストを実行
pytest --cov=sre_agent --cov-report=html
open htmlcov/index.html  # カバレッジレポートを表示

# 特定のテストカテゴリを実行
pytest tests/unit/          # 高速なユニットテスト
pytest tests/integration/   # モック API を使用した統合テスト
pytest tests/e2e/          # デモバックエンドを使用したエンドツーエンドテスト

# 高速化のためにテストを並列実行
pytest -n auto

# デバッグ用の詳細出力で実行
pytest -vv -s
```

## コード品質

自動化ツールを使用してコード品質を維持：

```bash
# mypy で型ヒントをチェック
mypy sre_agent/

# ruff でコードをリント
ruff check sre_agent/

# すべての品質チェックを実行
make quality
```

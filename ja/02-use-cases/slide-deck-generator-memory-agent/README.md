# Slide Deck Agent デモ - エージェントメモリの重要性

この包括的なデモでは、2つのスライドデッキ生成システムを比較することで、**エージェントメモリ**の変革的な力を紹介します：

- **Basic Agent**: 学習やメモリなしでプレゼンテーションを作成
- **Memory-Enhanced Agent**: ユーザーの好みを学習し、ますますパーソナライズされたプレゼンテーションを作成

## 主なデモンストレーションポイント

| 機能                   | Basic Agent                            | Memory-Enhanced Agent                                   |
| ------------------------- | -------------------------------------- | ------------------------------------------------------- |
| **スタイル学習**        | 学習なし                         | 色、フォント、テーマの好みを記憶             |
| **コンテキスト認識**     | 一般的な応答                   | プレゼンテーションタイプ（技術/ビジネス/学術）に適応 |
| **パーソナライズ**       | 全員に同じ出力            | 個々のユーザーの好みに合わせて調整              |
| **効率性**            | 手動でのスタイル指定が必要 | 学習した好みの自動適用         |
| **時間経過による改善** | 静的な機能                 | インタラクションごとに向上                    |

## アーキテクチャ概要

![Architecture](./workflow_diagram.png)

エンドツーエンドの技術ワークフローをここに説明します。

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Basic Agent   │    │  Memory-Enhanced │    │   AgentCore     │
│   (No Memory)   │    │     Agent        │◄──►│    Memory       │
│                 │    │                  │    │   (User Prefs)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         │                        │                       │
         ▼                        ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ HTML Generator  │    │  CSS Generator   │    │  PPT Converter  │
│ (Basic Themes)  │    │ (Advanced Style) │    │ (Multi-format)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         └────────────────────────┼───────────────────────┘
                                  ▼
                        ┌─────────────────┐
                        │   Web Interface │
                        │ (Comparison UI) │
                        └─────────────────┘
```

## 前提条件

### 必要なソフトウェア

- **Python 3.10+**
- **AWS CLI**（認証情報設定済み）
- **Bedrock AgentCore Memory** 権限

### 必要な AWS 権限

AWS 認証情報には以下の権限が必要です：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:*",
        "bedrock:InvokeModel",
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}
```

## クイックスタート

### 1. インストール

```bash
# デモディレクトリにクローンまたは移動
cd slide-deck-memory-demo

# Python 依存関係をインストール
pip install -r requirements.txt

# AWS 設定を確認
aws sts get-caller-identity
```

### 2. デモの実行

```bash
# Web インターフェースを起動（推奨）
python main.py

# または特定のモードを選択
python main.py --mode web      # Web インターフェース
python main.py --mode cli      # コマンドラインデモ
python main.py --mode demo     # 自動デモ
python main.py --mode compare  # 直接比較
```

### 3. デモへのアクセス

- **Web インターフェース**: `http://localhost:5000` を開く
- **CLI モード**: インタラクティブなプロンプトに従う
- **自動**: 学習の進行を観察

## デモモードの説明

### Web インターフェースモード（デフォルト）

```bash
python main.py
```

- **最適な用途**: インタラクティブな探索とプレゼンテーション
- **機能**: 美しい UI、サイドバイサイド比較、ファイルダウンロード
- **URL**: `http://localhost:5000`

### CLI インタラクティブモード

```bash
python main.py --mode cli
```

- **最適な用途**: 技術ユーザーとデバッグ
- **機能**: コマンドラインインターフェース、直接エージェントテスト
- **オプション**: 個別エージェントテストまたはサイドバイサイド比較

### 自動デモモード

```bash
python main.py --mode demo
```

- **最適な用途**: プレゼンテーションとクイックデモンストレーション
- **機能**: 学習の進行を示すスクリプト化されたシナリオ
- **フロー**: エージェントが時間とともに好みを学習する様子を観察

### 直接比較モード

```bash
python main.py --mode compare
```

- **最適な用途**: クイック A/B テスト
- **機能**: 両方のエージェントで単一リクエストをテスト
- **出力**: サイドバイサイドの結果比較

## 使用例

### 例1: 色の好みの学習

```
リクエスト1: "AI についての技術プレゼンテーションを作成してください。技術コンテンツにはブルーテーマを好みます。"
結果: Memory エージェントが技術トピックのブルー好みを学習

リクエスト2: "機械学習についての別の技術プレゼンテーションを作成してください。"
結果: Memory エージェントは自動的にブルーテーマを適用、Basic エージェントはデフォルトを使用
```

### 例2: コンテキストアウェアスタイリング

```
ビジネスリクエスト: "四半期結果についてのエグゼクティブプレゼンテーションを作成"
Memory Agent: 学習したプロフェッショナルで企業的なスタイリングを適用

クリエイティブリクエスト: "デザインショーケースプレゼンテーションを作成"
Memory Agent: ユーザーの色の好みを維持しながらクリエイティブで大胆なスタイリングに適応
```

## 設定

### 環境変数

```bash
# オプション: デフォルト設定を上書き
export AWS_REGION=us-east-1
export DEMO_USER_ID=your-user-id
export OUTPUT_DIR=./custom-output

# セキュリティ: 本番環境用にセキュアなシークレットキーを設定
export FLASK_SECRET_KEY=your-random-secret-key-here
```

### 設定ファイル (`config.py`)

```python
# AWS 設定
AWS_REGION = "us-east-1"
BEDROCK_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

# メモリ設定
MEMORY_NAME = "SlideDeckAgentMemory"
MEMORY_EXPIRY_DAYS = 30

# Web UI 設定
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
```

## プロジェクト構成

```
slide-deck-memory-demo/
├── config.py                    # 設定（AWS リージョン、モデル ID、パス）
├── memory_setup.py              # メモリ初期化（AgentCore Memory セットアップ）
├── main.py                      # CLI デモ（Web UI の代替オプション）
├── requirements.txt             # Python 依存関係
├── README.md                    # このドキュメント
│
├── web/                        # Flask Web アプリケーション（メインデモインターフェース）
│   └── app.py                     # Web サーバー、API エンドポイント、ルートハンドラー
│
├── agents/                      # 基本およびメモリ対応エージェント
│   ├── basic_agent.py             # メモリ機能なしのエージェント
│   └── memory_agent.py            # メモリ対応エージェント（ユーザーの好みを学習）
│
├── generators/                  # HTML および CSS ジェネレーター
│   ├── html_generator.py          # HTML スライド生成（Markdown 解析）
│   └── css_generator.py           # CSS 生成（好みに基づく動的スタイリング）
│
├── memory_hooks/                # メモリ統合フック
│   └── slide_hooks.py             # 自動好み学習とメモリイベント処理
│
├── templates/                   # Web UI 用 HTML テンプレート
│   ├── base.html                  # 共通スタイリング付きベーステンプレート
│   ├── index.html                 # ランディングページ
│   ├── create_basic.html          # Basic Agent インターフェース
│   ├── create_memory.html         # Memory Agent インターフェース
│   ├── compare.html               # サイドバイサイド比較インターフェース
│   └── error.html                 # エラー処理テンプレート
│
├── static/                     # Web UI 用 CSS/JS
│   └── (CSS, JavaScript, images)
│
├── converters/                  # フォーマット変換ユーティリティ（オプション）
│   └── ppt_converter.py           # HTML から PowerPoint への変換
│
└── output/                     # 生成されたプレゼンテーション（HTML ファイル）
```

## 主なデモンストレーション機能

### メモリ学習機能

- **スタイルの好み**: 色、テーマ、フォント、間隔
- **コンテキスト認識**: プレゼンテーションタイプ（技術、ビジネス、学術、クリエイティブ）
- **オーディエンス適応**: プロフェッショナル、技術的、クリエイティブなスタイリング
- **継続的改善**: インタラクションごとにより良い結果

### 高度なスタイリング機能

- **動的 CSS 生成**: 学習したユーザーの好みに基づく
- **プレゼンテーションタイプ**: 適切なスタイリングを持つ技術、ビジネス、学術、クリエイティブ
- **フォントシステム**: モダン、クラシック、テクニカル、クリエイティブなフォントの組み合わせ
- **レスポンシブデザイン**: さまざまな画面サイズで動作
- **インタラクティブナビゲーション**: キーボードショートカットとスムーズなトランジション

### 出力フォーマット

- **HTML プレゼンテーション**: インタラクティブでウェブ対応のスライドデッキ
- **PowerPoint ファイル**: 共有用のプロフェッショナルな PPTX フォーマット
- **プレビュー機能**: ブラウザ内でのプレゼンテーション表示
- **ダウンロード管理**: 簡単なファイルアクセスと整理

## トラブルシューティング

### よくある問題

#### AWS 認証情報エラー

```
Error: Unable to locate credentials
```

**解決策**: AWS 認証情報を設定

```bash
aws configure
# または環境変数を設定:
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1
```

#### メモリ作成失敗

```
Error: Memory creation failed: Access denied
```

**解決策**: Bedrock AgentCore Memory の IAM 権限を確認

- 上記の AWS 権限セクションを確認
- Bedrock サービスへのアカウントアクセスを確認

#### モジュールインポートエラー

```
ModuleNotFoundError: No module named 'strands'
```

**解決策**: 依存関係をインストール

```bash
pip install -r requirements.txt
```

#### Web インターフェースが起動しない

```
Error: Address already in use
```

**解決策**: ポートを変更するか既存のプロセスを終了

```bash
# 別のポートを使用
python main.py --mode web --port 5001

# または既存のプロセスを終了
lsof -ti:5000 | xargs kill -9
```

### デバッグモード

トラブルシューティング用の詳細ログを有効化：

```python
# config.py 内
import logging
logging.basicConfig(level=logging.DEBUG)
```

## デモのテスト

### クイック機能テスト

```bash
# 基本コンポーネントをテスト
python -c "from agents.basic_agent import BasicSlideDeckAgent; print('✅ Basic agent OK')"
python -c "from memory_setup import setup_slide_deck_memory; print('✅ Memory setup OK')"
```

### メモリ学習テスト

1. **初回インタラクション**: 明示的に色の好みを指定
2. **2回目のインタラクション**: 色の好みを省略し、エージェントが記憶しているか確認
3. **学習した好みを確認**: 好み表示ツールを使用

### 比較テスト

両方のエージェントで同一のリクエストを使用して違いを確認：

```
リクエスト: "アナリスト向けのデータサイエンスプレゼンテーションを作成"
Basic Agent: デフォルトのブルーテーマを使用
Memory Agent: 学習した好み + コンテキスト認識を適用
```

## 学習目標

このデモを完了すると、以下を理解できます：

1. **AI インタラクションにおけるメモリの影響**

   - メモリが汎用 AI をパーソナライズされたアシスタントに変換する方法
   - ステートレス AI エージェントとステートフル AI エージェントの違い

2. **ユーザーエクスペリエンスの向上**

   - 繰り返しの好み指定の必要性を削減
   - 時間とともに関連性とパーソナライズが向上

3. **技術的実装**

   - Strands エージェントとの AgentCore Memory 統合
   - 自動学習と取得のためのメモリフック
   - ユーザー好み戦略と統合

4. **ビジネス価値**
   - パーソナライズによるユーザー満足度の向上
   - 手動設定の削減による効率性の向上
   - 適応型エクスペリエンスによるユーザーエンゲージメントの強化

## サポート

問題や質問がある場合：

1. 上記のトラブルシューティングセクションを確認
2. AWS 認証情報と権限を確認
3. すべての依存関係が正しくインストールされていることを確認
4. 詳細なエラー情報については出力ログを確認

## バージョン情報

- **デモバージョン**: 1.0
- **AgentCore Memory**: 最新互換バージョン
- **Strands Framework**: 最新互換バージョン
- **Python**: 3.10+ 必須

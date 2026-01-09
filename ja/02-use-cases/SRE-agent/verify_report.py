#!/usr/bin/env python3
"""
SRE レポート検証ツール

このツールは、SRE 調査レポートをグラウンドトゥルースデータと比較して、
ハルシネーションを特定し、レポート内の主張の正確性を検証します。
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(Path(__file__).parent / "sre_agent" / ".env")


def _get_anthropic_api_key() -> str:
    """環境変数から Anthropic API キーを取得します。"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required for verification"
        )
    return api_key


def _read_file(file_path: str) -> str:
    """ファイルからコンテンツを読み取ります。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"ファイルが見つかりません: {file_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ファイル読み取りエラー {file_path}: {e}")
        sys.exit(1)


def _create_verification_prompt(report_content: str, ground_truth_content: str) -> str:
    """Claude 用の検証プロンプトを作成します。"""
    return f"""<task>
あなたは専門の SRE データ検証スペシャリストです。SRE 調査レポートの正確性を、グラウンドトゥルースデータと比較して検証することがあなたのタスクです。

<report>
{report_content}
</report>

<ground_truth_data>
{ground_truth_content}
</ground_truth_data>
</task>

<critical_context>
重要: グラウンドトゥルースデータには、インフラストラクチャの完全な状態を表す包括的なデータセットが含まれています:
- 複数のサービス（正常なものと問題があるものの両方）
- 異なる期間にわたる履歴データ
- 様々な Pod の状態（running、failed、crashed など）
- 混在したパフォーマンスメトリクス（良好なものと悪いもの）
- 異なるログパターンとエラー条件

レポート内のすべてのエンティティがグラウンドトゥルースで問題を持つことを期待しないでください。グラウンドトゥルースは完全な状況を示しているため:
- 一部のサービスは正常で、他のサービスには問題がある場合があります
- 一部の Pod は正常に実行されており、他の Pod は失敗している場合があります
- パフォーマンスメトリクスは良好なパターンと悪いパターンの両方を示す場合があります
- レポート内の特定の主張がデータの実際の内容と一致するかどうかのみを検証してください

システム全体が正常か異常かではなく、レポート内の特定の主張の正確性に焦点を当ててください。
</critical_context>

<instructions>
SRE 調査レポートを注意深く分析し、すべての特定の主張をグラウンドトゥルースデータと比較してください。以下の検証に焦点を当ててください:

1. **Pod 名** - 言及されているすべての Pod 名（例: api-service-xyz、database-pod-abc）
2. **アプリケーション名** - 参照されているサービス名
3. **タイムスタンプ** - ログやメトリクスで言及されている特定の時刻
4. **ログエントリ** - 引用された正確なログメッセージ
5. **メトリクス値** - パフォーマンス数値、応答時間、エラー率
6. **リソース使用量** - CPU、メモリのパーセンテージ
7. **エラー数** - エラーや発生の回数
8. **ステータス情報** - Pod の状態、サービスの健全性

レポートで言及されている各エンティティについて:
- グラウンドトゥルースデータに存在するか確認
- 詳細（タイムスタンプ、値、ステータス）が正確に一致するか検証
- 捏造されたまたはハルシネーションされた情報を特定
- 注意: グラウンドトゥルースにサービスの問題がないことは、レポートがそのサービスに問題があると具体的に主張していない限り、レポートを無効にしません

<output_format>
ハルシネーションが見つかった場合は、以下の形式で応答:

# ハルシネーション検出

## 捏造された主張:
- **[エンティティタイプ]**: [具体的な主張]
  - **レポートの主張**: [レポートが述べていること]
  - **グラウンドトゥルース**: [データが実際に示していることまたは「見つからず」]
  - **検証結果**: 捏造/不正確

## 追加の問題:
[発見されたその他の正確性の問題]

---

ハルシネーションが見つからなかった場合は、以下の形式で応答:

# レポートの正確性を確認

## 確認された重要なエンティティ:
- **[エンティティタイプ]**: [エンティティ名/値]
  - **グラウンドトゥルース参照**: 行 [X]: "[グラウンドトゥルースからの正確なテキスト]"
  - **レポートのコンテキスト**: [レポートでの使用方法]

## 検証サマリー:
レポート内のすべての主張がグラウンドトゥルースデータと照合検証されました。捏造された情報は検出されませんでした。
</output_format>

非常に徹底的かつ正確に行ってください。SRE 操作には絶対的な正確性が必要です - タイムスタンプ、Pod 名、またはメトリクス値のわずかな不一致でも特定することが重要です。
</instructions>"""


def _verify_report_with_claude(
    report_content: str, ground_truth_content: str, api_key: str
) -> str:
    """Claude を使用してレポートをグラウンドトゥルースデータと照合検証します。"""
    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = _create_verification_prompt(report_content, ground_truth_content)

        logger.info("Claude 4 Sonnet に検証リクエストを送信中...")

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            temperature=0.1,  # Low temperature for consistent, accurate analysis
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    except Exception as e:
        logger.error(f"Claude API 呼び出しエラー: {e}")
        sys.exit(1)


def main():
    """レポート検証のメイン関数。"""
    parser = argparse.ArgumentParser(
        description="Verify SRE investigation reports against ground truth data"
    )
    parser.add_argument(
        "report_path", help="Path to the SRE investigation report (markdown file)"
    )
    parser.add_argument(
        "--data-path",
        default="backend/data/all_data_dump.txt",
        help="Path to the ground truth data file (default: backend/data/all_data_dump.txt)",
    )
    parser.add_argument(
        "--output", help="Optional output file to save verification results"
    )

    args = parser.parse_args()

    # Validate input files
    if not os.path.exists(args.report_path):
        logger.error(f"レポートファイルが見つかりません: {args.report_path}")
        sys.exit(1)

    if not os.path.exists(args.data_path):
        logger.error(f"グラウンドトゥルースデータファイルが見つかりません: {args.data_path}")
        sys.exit(1)

    # Get API key
    try:
        api_key = _get_anthropic_api_key()
    except ValueError as e:
        logger.error(f"API キーエラー: {e}")
        sys.exit(1)

    # Read files
    logger.info(f"レポートを読み込み中: {args.report_path}")
    report_content = _read_file(args.report_path)

    logger.info(f"グラウンドトゥルースデータを読み込み中: {args.data_path}")
    ground_truth_content = _read_file(args.data_path)

    # Verify report
    logger.info("検証プロセスを開始中...")
    verification_result = _verify_report_with_claude(
        report_content, ground_truth_content, api_key
    )

    # Output results
    print("\n" + "=" * 80)
    print("SRE REPORT VERIFICATION RESULTS")
    print("=" * 80)
    print(verification_result)
    print("=" * 80)

    # Save to output file if specified
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write("# SRE Report Verification Results\n\n")
                f.write(f"**Report**: {args.report_path}\n")
                f.write(f"**Ground Truth**: {args.data_path}\n")
                f.write(f"**Verified on**: {Path().cwd()}\n\n")
                f.write("---\n\n")
                f.write(verification_result)
            logger.info(f"検証結果を保存しました: {args.output}")
        except Exception as e:
            logger.error(f"出力ファイルの保存エラー: {e}")

    logger.info("検証が完了しました！")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Factuality チェックモジュール

このモジュールは GitHub ワークフローから Factuality スコアチェックロジックを抽出し、
Factuality 結果を検証するための再利用可能な関数を提供します。
"""

import sys
import json
from typing import Dict, Any


def load_factuality_results(results_file: str = 'factuality_results.json') -> Dict[str, Any]:
    """
    JSON ファイルから Factuality 結果を読み込みます。

    Args:
        results_file: Factuality 結果の JSON ファイルへのパス

    Returns:
        Factuality 結果を含む辞書

    Raises:
        FileNotFoundError: 結果ファイルが存在しない場合
        json.JSONDecodeError: ファイルに無効な JSON が含まれている場合
    """
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
        return results
    except FileNotFoundError:
        print(f'✗ エラー: {results_file} が見つかりません')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'✗ エラー: {results_file} に無効な JSON が含まれています: {e}')
        sys.exit(1)


def print_factuality_summary(results: Dict[str, Any]) -> None:
    """
    Factuality 結果のフォーマット済みサマリーを出力します。

    Args:
        results: Factuality 結果を含む辞書
    """
    # メトリクスを抽出
    avg_factuality = results['average_factuality_score']
    total_items = results['total_items']
    experiment_name = results['experiment_name']
    
    print(f'実験名: {experiment_name}')
    print(f'評価アイテム数: {total_items}')
    print(f'平均 Factuality スコア: {avg_factuality:.3f} ({avg_factuality*100:.1f}%)')

    # 個別スコアを出力
    print('\n個別スコア:')
    for i, score_data in enumerate(results['scores']):
        print(f"  アイテム {i+1}: {score_data['value']:.3f} ({score_data.get('name', '不明')})")
        if score_data.get('comment'):
            print(f"    コメント: {score_data['comment']}")


def check_factuality_threshold(results: Dict[str, Any], threshold: float = 0.5) -> bool:
    """
    平均 Factuality スコアが閾値要件を満たしているかチェックします。

    Args:
        results: Factuality 結果を含む辞書
        threshold: 許容可能な最小 Factuality スコア（デフォルト：0.5）

    Returns:
        スコアが閾値を満たす場合は True、それ以外は False
    """
    avg_factuality = results['average_factuality_score']
    
    print(f'\n閾値: {threshold*100:.0f}%')

    if avg_factuality >= threshold:
        print(f'✓ 合格: Factuality スコア {avg_factuality*100:.1f}% は閾値 {threshold*100:.0f}% を超えています')
        return True
    else:
        print(f'✗ 不合格: Factuality スコア {avg_factuality*100:.1f}% は閾値 {threshold*100:.0f}% を下回っています')
        return False


def main(results_file: str = 'factuality_results.json', threshold: float = 0.5) -> int:
    """
    Factuality 結果をチェックするメイン関数。

    Args:
        results_file: Factuality 結果の JSON ファイルへのパス
        threshold: 許容可能な最小 Factuality スコア

    Returns:
        終了コード：成功の場合 0、失敗の場合 1
    """
    # ファイルから結果を読み込み
    results = load_factuality_results(results_file)
    
    # サマリーを出力
    print_factuality_summary(results)
    
    # 閾値をチェック
    passed = check_factuality_threshold(results, threshold)
    
    return 0 if passed else 1


if __name__ == '__main__':
    # コマンドライン引数をパース
    import argparse
    
    parser = argparse.ArgumentParser(description='Check factuality results from evaluation')
    parser.add_argument('--results-file', '-f', 
                       default='factuality_results.json',
                       help='Path to factuality results JSON file (default: factuality_results.json)')
    parser.add_argument('--threshold', '-t', 
                       type=float, 
                       default=0.5,
                       help='Minimum acceptable factuality score (default: 0.5)')
    
    args = parser.parse_args()
    
    # チェックを実行
    exit_code = main(args.results_file, args.threshold)
    sys.exit(exit_code)

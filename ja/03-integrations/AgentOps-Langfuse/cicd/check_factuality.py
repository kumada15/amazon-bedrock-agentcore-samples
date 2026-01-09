#!/usr/bin/env python3
"""
事実性チェックモジュール

このモジュールは GitHub ワークフローから事実性スコアのチェックロジックを抽出し、
事実性結果を検証するための再利用可能な関数を提供します。
"""

import sys
import json
from typing import Dict, Any


def load_factuality_results(results_file: str = 'factuality_results.json') -> Dict[str, Any]:
    """
    JSON ファイルから事実性結果を読み込みます。

    Args:
        results_file: 事実性結果 JSON ファイルのパス

    Returns:
        事実性結果を含む辞書

    Raises:
        FileNotFoundError: 結果ファイルが存在しない場合
        json.JSONDecodeError: ファイルに無効な JSON が含まれている場合
    """
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
        return results
    except FileNotFoundError:
        print(f'✗ エラー: {results_file}が見つかりません')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'✗ エラー: {results_file}に無効なJSONがあります: {e}')
        sys.exit(1)


def print_factuality_summary(results: Dict[str, Any]) -> None:
    """
    事実性結果のフォーマットされたサマリーを出力します。

    Args:
        results: 事実性結果を含む辞書
    """
    # Extract metrics
    avg_factuality = results['average_factuality_score']
    total_items = results['total_items']
    experiment_name = results['experiment_name']
    
    print(f'実験: {experiment_name}')
    print(f'評価されたアイテム総数: {total_items}')
    print(f'平均Factualityスコア: {avg_factuality:.3f} ({avg_factuality*100:.1f}%)')
    
    # Print individual scores
    print('\n個別スコア:')
    for i, score_data in enumerate(results['scores']):
        print(f"  アイテム {i+1}: {score_data['value']:.3f} ({score_data.get('name', 'Unknown')})")
        if score_data.get('comment'):
            print(f"    コメント: {score_data['comment']}")


def check_factuality_threshold(results: Dict[str, Any], threshold: float = 0.5) -> bool:
    """
    平均事実性スコアがしきい値要件を満たしているかチェックします。

    Args:
        results: 事実性結果を含む辞書
        threshold: 許容可能な最小事実性スコア（デフォルト: 0.5）

    Returns:
        スコアがしきい値を満たす場合は True、そうでない場合は False
    """
    avg_factuality = results['average_factuality_score']
    
    print(f'\nしきい値: {threshold*100:.0f}%')
    
    if avg_factuality >= threshold:
        print(f'✓ 合格: Factualityスコア{avg_factuality*100:.1f}%がしきい値{threshold*100:.0f}%を上回っています')
        return True
    else:
        print(f'✗ 不合格: Factualityスコア{avg_factuality*100:.1f}%がしきい値{threshold*100:.0f}%を下回っています')
        return False


def main(results_file: str = 'factuality_results.json', threshold: float = 0.5) -> int:
    """
    事実性結果をチェックするメイン関数。

    Args:
        results_file: 事実性結果 JSON ファイルのパス
        threshold: 許容可能な最小事実性スコア

    Returns:
        終了コード: 成功の場合は 0、失敗の場合は 1
    """
    # Load results from file
    results = load_factuality_results(results_file)
    
    # Print summary
    print_factuality_summary(results)
    
    # Check threshold
    passed = check_factuality_threshold(results, threshold)
    
    return 0 if passed else 1


if __name__ == '__main__':
    # Parse command line arguments
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
    
    # Run the check
    exit_code = main(args.results_file, args.threshold)
    sys.exit(exit_code)

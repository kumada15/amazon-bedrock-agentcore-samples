"""
ビデオゲーム売上データアナリストアシスタント用ユーティリティ関数

このモジュールは、DynamoDB からビデオゲーム売上分析データを保存・取得するための
ユーティリティ関数を提供します。SQL クエリ結果と分析データのフォーマットおよび
保存・取得処理を行います。

このモジュールは以下の SSM パラメータを使用します:
- QUESTION_ANSWERS_TABLE: クエリ結果と分析データを保存する DynamoDB テーブル
"""

import boto3
import json
from datetime import datetime
from .ssm_utils import load_config

# SSM パラメータから設定を読み込み
try:
    CONFIG = load_config()
except Exception as e:
    print("\n" + "=" * 70)
    print("❌ 設定読み込みエラー")
    print("=" * 70)
    print(f"💥 SSM からの設定読み込みエラー: {e}")
    print("=" * 70 + "\n")
    CONFIG = {}


def save_raw_query_result(
    user_prompt_uuid, user_prompt, sql_query, sql_query_description, result, message
):
    """
    監査証跡と将来の参照のために、ビデオゲーム売上分析クエリ結果を DynamoDB に保存する。

    この関数は、各 SQL クエリ実行に関する包括的な情報（元のユーザー質問、生成された SQL クエリ、
    結果、および追跡・監査目的のメタデータ）を保存します。

    Args:
        user_prompt_uuid (str): ユーザープロンプト/分析セッションの一意識別子
        user_prompt (str): ビデオゲーム売上データに関する元のユーザー質問
        sql_query (str): ビデオゲーム売上データベースに対して実行された SQL クエリ
        sql_query_description (str): クエリが分析する内容の人間が読める説明
        result (dict): クエリ結果とメタデータ
        message (str): 結果に関する追加情報（例：切り詰め通知）

    Returns:
        dict: 成功ステータスと DynamoDB レスポンスまたはエラー詳細を含むレスポンス
    """
    try:
        # テーブル名が利用可能か確認
        question_answers_table = CONFIG.get("QUESTION_ANSWERS_TABLE")
        if not question_answers_table:
            return {"success": False, "error": "QUESTION_ANSWERS_TABLE が設定されていません"}

        dynamodb_client = boto3.client("dynamodb")

        response = dynamodb_client.put_item(
            TableName=question_answers_table,
            Item={
                "id": {"S": user_prompt_uuid},
                "my_timestamp": {"N": str(int(datetime.now().timestamp()))},
                "datetime": {"S": str(datetime.now())},
                "user_prompt": {"S": user_prompt},
                "sql_query": {"S": sql_query},
                "sql_query_description": {"S": sql_query_description},
                "data": {"S": json.dumps(result)},
                "message_result": {"S": message},
            },
        )

        print("\n" + "=" * 70)
        print("✅ ビデオゲーム売上分析データを DynamoDB に保存しました")
        print("=" * 70)
        print(f"🆔 セッション ID: {user_prompt_uuid}")
        print(f"📊 DynamoDB テーブル: {question_answers_table}")
        print("=" * 70 + "\n")
        return {"success": True, "response": response}

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ ビデオゲーム売上分析データ保存エラー")
        print("=" * 70)
        print(f"📊 DynamoDB テーブル: {question_answers_table}")
        print(f"💥 エラー: {str(e)}")
        print("=" * 70 + "\n")
        return {"success": False, "error": str(e)}

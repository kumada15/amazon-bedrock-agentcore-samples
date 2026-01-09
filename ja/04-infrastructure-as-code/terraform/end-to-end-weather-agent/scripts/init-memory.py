#!/usr/bin/env python3
"""
天気エージェント用メモリ初期化スクリプト

このスクリプトは天気エージェントが推奨に使用するアクティビティ設定で
AgentCore Memory を初期化します。

使用方法:
    python init-memory.py

環境変数:
    MEMORY_ID（必須）: 初期化する AgentCore Memory の ID
    AWS_REGION（必須）: メモリが存在する AWS リージョン
"""

import boto3
import json
import os
import sys
from datetime import datetime


def main():
    """アクティビティ設定でメモリを初期化"""

    # 必須環境変数を取得
    memory_id = os.environ.get('MEMORY_ID')
    region = os.environ.get('AWS_REGION')
    
    if not memory_id:
        print("❌ エラー: MEMORY_ID環境変数が必要です")
        sys.exit(1)

    if not region:
        print("❌ エラー: AWS_REGION環境変数が必要です")
        sys.exit(1)

    print(f"🎯 メモリを初期化中: {memory_id}")
    print(f"📍 リージョン: {region}")
    
    # アクティビティ設定データ構造
    activity_preferences = {
        "good_weather": [
            "hiking",
            "beach volleyball",
            "outdoor picnic",
            "farmers market",
            "gardening",
            "photography",
            "bird watching"
        ],
        "ok_weather": [
            "walking tours",
            "outdoor dining",
            "park visits",
            "museums"
        ],
        "poor_weather": [
            "indoor museums",
            "shopping",
            "restaurants",
            "movies"
        ]
    }
    
    # 保存用に JSON 文字列に変換
    activity_preferences_json = json.dumps(activity_preferences)
    
    try:
        # bedrock-agentcore クライアントを初期化
        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # タイムスタンプを作成
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        print("📝 アクティビティの設定でメモリイベントを作成中...")
        
        # メモリイベントを作成
        response = client.create_event(
            memoryId=memory_id,
            actorId="user123",
            sessionId="session456",
            eventTimestamp=timestamp,
            payload=[
                {
                    'blob': activity_preferences_json
                }
            ]
        )
        
        print("✅ メモリの初期化に成功しました！")
        print(f"📊 イベントID: {response.get('eventId', 'N/A')}")
        print(f"📦 保存された設定: {len(activity_preferences)}カテゴリ")
        print(f"   - 良い天気: {len(activity_preferences['good_weather'])}件のアクティビティ")
        print(f"   - まあまあの天気: {len(activity_preferences['ok_weather'])}件のアクティビティ")
        print(f"   - 悪い天気: {len(activity_preferences['poor_weather'])}件のアクティビティ")
        
        return 0
        
    except Exception as e:
        print(f"❌ エラー: メモリの初期化に失敗しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

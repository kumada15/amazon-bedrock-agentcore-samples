#!/usr/bin/env python3
"""
BedrockAgentCore リソース用のシンプルなクリーンアップスクリプト。
AWS リソースをクリーンアップしてコストを回避するために定期的に実行してください。
"""

import boto3
import sys
from datetime import datetime, timedelta

def cleanup_browsers(region='us-west-2'):
    """課金を停止するためにすべての BedrockAgentCore ブラウザを削除する。"""
    print("🧹 ブラウザをクリーンアップ中...")
    
    try:
        # This is a placeholder - the actual API endpoint might differ
        # You need to use the correct BedrockAgentCore control plane API
        from bedrock_agentcore._utils.endpoints import get_control_plane_endpoint
        
        control_client = boto3.client(
            "bedrock-agentcore-control",
            region_name=region,
            endpoint_url=get_control_plane_endpoint(region)
        )
        
        response = control_client.list_browsers()
        browsers = response.get('browsers', [])
        
        for browser in browsers:
            try:
                control_client.delete_browser(browserId=browser['browserId'])
                print(f"  ✅ ブラウザを削除しました: {browser['browserId']}")
            except Exception as e:
                print(f"  ❌ {browser['browserId']} の削除に失敗しました: {e}")
                
        if not browsers:
            print("  ✓ クリーンアップするブラウザはありません")
            
    except Exception as e:
        print(f"  ⚠️  ブラウザの一覧を取得できませんでした: {e}")
        print("  注意: ブラウザが存在しないか、API が変更された可能性があります")

def cleanup_old_s3_recordings(bucket_name, days_to_keep=7):
    """指定した日数より古い S3 録画を削除する。"""
    print(f"🧹 {days_to_keep} 日以上前の S3 レコーディングをクリーンアップ中...")
    
    if not bucket_name:
        print("  ⚠️  S3 バケットが指定されていません")
        return
        
    try:
        s3 = boto3.client('s3')
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix='competitive_intel/'
        )
        
        if 'Contents' not in response:
            print("  ✓ レコーディングが見つかりません")
            return
            
        old_objects = []
        for obj in response['Contents']:
            if obj['LastModified'].replace(tzinfo=None) < cutoff:
                old_objects.append({'Key': obj['Key']})
        
        if old_objects:
            s3.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': old_objects[:1000]}  # Max 1000 at a time
            )
            print(f"  ✅ {len(old_objects)} 件の古いレコーディングを削除しました")
        else:
            print("  ✓ 削除する古いレコーディングはありません")
            
    except Exception as e:
        print(f"  ❌ エラー: {e}")

if __name__ == "__main__":
    import os
    
    print("=" * 50)
    print("BedrockAgentCore リソースのクリーンアップ")
    print("=" * 50)
    
    # Get config from environment
    region = os.environ.get('AWS_REGION', 'us-west-2')
    bucket = os.environ.get('S3_RECORDING_BUCKET', '')
    
    # Clean browsers (main cost driver)
    cleanup_browsers(region)
    
    # Clean old S3 recordings
    if '--delete-old-recordings' in sys.argv:
        cleanup_old_s3_recordings(bucket)
    else:
        print("\n💡 ヒント: S3 もクリーンアップするには --delete-old-recordings を追加してください")

    print("\n✅ クリーンアップ完了")
    print("=" * 50)
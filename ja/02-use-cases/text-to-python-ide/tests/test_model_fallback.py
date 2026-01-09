#!/usr/bin/env python3
"""
モデルフォールバックロジックを検証するテストスクリプト
"""

import os
import sys
from dotenv import load_dotenv

def test_model_availability():
    """現在のリージョンで利用可能なモデルをテストする"""
    print("🔍 モデルの利用可能性をテスト中")
    print("=" * 50)
    
    load_dotenv()
    
    import boto3
    
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    print(f"リージョン: {aws_region}")
    
    try:
        session = boto3.Session()
        bedrock_client = session.client('bedrock', region_name=aws_region)
        
        response = bedrock_client.list_foundation_models()
        available_models = [model['modelId'] for model in response.get('modelSummaries', [])]
        
        # Test models in priority order
        test_models = [
            ("Claude Haiku 4.5", "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
            ("Nova Premier", "us.amazon.nova-premier-v1:0"),
            ("Claude 3.5 Sonnet", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        ]
        
        print(f"\n{aws_region} で {len(available_models)} 個のモデルが見つかりました")
        print("\n優先モデルをテスト中:")
        
        for name, model_id in test_models:
            if model_id in available_models:
                print(f"✅ {name}: {model_id} - 利用可能")
            else:
                print(f"❌ {name}: {model_id} - 利用不可")
        
        return available_models
        
    except Exception as e:
        print(f"❌ モデル一覧の取得に失敗: {e}")
        return []

def test_model_fallback_logic():
    """モデルフォールバックロジックをテストする"""
    print("\n🧪 モデルフォールバックロジックをテスト中")
    print("=" * 50)
    
    try:
        sys.path.append('backend')
        from main import create_bedrock_model_with_fallback
        
        load_dotenv()
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        model, model_id = create_bedrock_model_with_fallback(aws_region)

        print(f"✅ 選択されたモデル: {model_id}")
        print(f"✅ モデルオブジェクトの作成に成功")
        
        return model, model_id
        
    except Exception as e:
        print(f"❌ モデルフォールバックテストに失敗: {e}")
        return None, None

def test_agent_initialization():
    """フォールバックモデルを使用したエージェント初期化をテストする"""
    print("\n🤖 エージェント初期化をテスト中")
    print("=" * 50)
    
    try:
        sys.path.append('backend')
        from main import setup_aws_credentials, initialize_agents
        
        # Setup AWS
        aws_session, aws_region = setup_aws_credentials()
        
        # Initialize agents
        import main
        main.aws_session = aws_session
        main.aws_region = aws_region
        initialize_agents()
        
        current_model = getattr(main, 'current_model_id', 'Unknown')
        print(f"✅ モデル {current_model} でエージェントを初期化しました")
        
        return True
        
    except Exception as e:
        print(f"❌ エージェント初期化に失敗: {e}")
        return False

def main():
    """すべてのモデルフォールバックテストを実行する"""
    print("🎯 モデルフォールバックテスト")
    print("=" * 60)
    
    # Test 1: Check model availability
    available_models = test_model_availability()
    
    # Test 2: Test fallback logic
    model, model_id = test_model_fallback_logic()
    
    # Test 3: Test agent initialization
    agent_success = test_agent_initialization()

    print("\n🎯 サマリー")
    print("=" * 30)

    if model_id:
        print(f"✅ 選択されたモデル: {model_id}")

        if "claude-3-7-sonnet" in model_id:
            print("🎉 プライマリモデルを使用中: Claude Haiku 4.5")
        elif "nova-premier" in model_id:
            print("⚠️  フォールバックモデルを使用中: Nova Premier")
        elif "claude-3-5-sonnet" in model_id:
            print("⚠️  最終手段モデルを使用中: Claude 3.5 Sonnet")
        else:
            print(f"❓ 不明なモデルを使用中: {model_id}")

    if agent_success:
        print("✅ エージェントの初期化に成功しました")
    else:
        print("❌ エージェントの初期化に失敗しました")

    print(f"\n📊 リージョンで利用可能なモデル数: {len(available_models)}")
    
    return 0 if model_id and agent_success else 1

if __name__ == "__main__":
    sys.exit(main())

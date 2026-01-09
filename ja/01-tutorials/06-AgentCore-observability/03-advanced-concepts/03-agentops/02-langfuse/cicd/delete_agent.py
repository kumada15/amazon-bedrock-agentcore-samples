#!/usr/bin/env python3
"""
CI/CD パイプラインクリーンアップ用のエージェント削除スクリプト。
このスクリプトは utils.agent の delete_agent 関数を使用してデプロイ済みエージェントを削除します。
"""

import json
import sys
from pathlib import Path

# utils をインポートするために親ディレクトリを Python パスに追加
sys.path.append(str(Path(__file__).parent.parent))

from utils.agent import delete_agent


def load_hp_config(config_path="cicd/hp_config.json"):
    """設定ファイルからハイパーパラメータを読み込みます。"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"エラー: 設定ファイル {config_path} が見つかりません。")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"エラー: {config_path} の JSON が無効です: {e}")
        sys.exit(1)


def get_agent_info_from_deploy_result():
    """
    デプロイ結果からエージェント情報を取得します。
    実際の CI/CD シナリオでは、デプロイステップで設定されたファイルまたは環境変数から読み取ります。
    """
    # 現時点では、設定からエージェント名を構築して検索を試みます
    # 本番シナリオでは、エージェント情報をファイルに保存するか、
    # ワークフローステップ間で環境変数として渡すことを検討してください
    
    config = load_hp_config()
    model = config["model"]
    system_prompt = config["system_prompt"]
    environment = "TST"
    
    agent_name = f'strands_{model["name"]}_{system_prompt["name"]}_{environment}'
    
    # boto3 をインポートしてエージェントを検索
    import boto3
    from boto3.session import Session
    
    boto_session = Session()
    region = boto_session.region_name
    
    try:
        agentcore_control_client = boto3.client(
            'bedrock-agentcore-control',
            region_name=region
        )
        
        # 対象のエージェントを見つけるためにすべてのエージェント Runtime をリスト
        list_response = agentcore_control_client.list_agent_runtimes()
        existing_agents = list_response.get('agentRuntimes', [])
        
        # 対象の名前を持つエージェントを検索
        target_agent = None
        for agent_summary in existing_agents:
            if agent_summary.get('agentRuntimeName') == agent_name:
                target_agent = agent_summary
                break
        
        if not target_agent:
            print(f"警告: Agent '{agent_name}' が見つかりません。既に削除されている可能性があります。")
            return None
        
        # ECR URI を抽出するために完全なエージェント Runtime 詳細を取得
        agent_runtime_id = target_agent.get('agentRuntimeId')

        print(f"Agent ランタイム ID: {agent_runtime_id}")
        
        try:
            get_response = agentcore_control_client.get_agent_runtime(
                agentRuntimeId=agent_runtime_id
            )

            print(f"取得レスポンス: {get_response}")

            ecr_uri = get_response['agentRuntimeArtifact']['containerConfiguration']['containerUri']

            print(f"ECR URI: {ecr_uri}")
        except Exception as e:
            print(f"警告: ECR URI を取得できませんでした: {str(e)}")
            ecr_uri = ''
        
        return {
            'agent_runtime_id': agent_runtime_id,
            'ecr_uri': ecr_uri,
            'agent_name': agent_name
        }
        
    except Exception as e:
        print(f"Agent の検索中にエラーが発生しました: {str(e)}")
        return None


def main():
    """エージェントを削除するメイン関数。"""
    print("デプロイ済みの Agent を検索中...")
    agent_info = get_agent_info_from_deploy_result()
    
    if not agent_info:
        print("削除する Agent が見つかりません。終了します。")
        return
    
    print("Agent を削除中:")
    print(f"  Agent 名: {agent_info['agent_name']}")
    print(f"  Agent ランタイム ID: {agent_info['agent_runtime_id']}")
    print(f"  ECR URI: {agent_info['ecr_uri']}")
    
    try:
        # エージェントを削除
        result = delete_agent(
            agent_runtime_id=agent_info['agent_runtime_id'],
            ecr_uri=agent_info['ecr_uri']
        )
        
        if result['status'] == 'success':
            print("Agent の削除に成功しました!")
            print(f"ランタイム削除レスポンス: {result.get('runtime_delete_response', {})}")
            print(f"ECR 削除レスポンス: {result.get('ecr_delete_response', {})}")
        else:
            print(f"Agent の削除に失敗しました: {result.get('error', '不明なエラー')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Agent の削除中にエラーが発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

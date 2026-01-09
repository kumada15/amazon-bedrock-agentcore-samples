#!/usr/bin/env python3
"""
CI/CD パイプライン用のエージェントデプロイスクリプト。
このスクリプトは hp_config.json からエージェントのハイパーパラメータを読み取り、
指定された環境（TST または PRD）で utils.agent の deploy_agent 関数を使用してエージェントをデプロイします。
"""

import json
import sys
import argparse
from pathlib import Path

# utils をインポートするために親ディレクトリを Python パスに追加
sys.path.append(str(Path(__file__).parent.parent))

from utils.agent import deploy_agent


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


def main():
    """エージェントをデプロイするメイン関数。"""
    # コマンドライン引数をパース
    parser = argparse.ArgumentParser(description='Deploy agent to specified environment')
    parser.add_argument('--environment', choices=['TST', 'PRD'], 
                       help='Environment to deploy to (TST or PRD)', default='TST')
    args = parser.parse_args()
    
    environment = args.environment
    
    print("Agent のハイパーパラメータを読み込み中...")
    config = load_hp_config()
    
    # 設定からモデルとシステムプロンプトを抽出
    if not config.get("model") or not config.get("system_prompt"):
        print("エラー: 設定には 'model' と 'system_prompt' オブジェクトが必要です。")
        sys.exit(1)
    
    model = config["model"]
    system_prompt = config["system_prompt"]
    
    print("以下の設定で Agent をデプロイ中:")
    print(f"  モデル: {model['name']} ({model['model_id']})")
    print(f"  システムプロンプト: {system_prompt['name']}")
    print(f"  環境: {environment}")
    
    try:
        # 指定された環境でエージェントをデプロイ
        result = deploy_agent(
            model=model,
            system_prompt=system_prompt,
            force_redeploy=False,
            environment=environment
        )
        
        print("Agent のデプロイに成功しました!")
        print(f"Agent 名: {result['agent_name']}")
        print(f"Agent ARN: {result['launch_result'].agent_arn}")
        print(f"Agent ID: {result['launch_result'].agent_id}")
        
        # 後続のパイプラインステップで使用するために既存の hp_config.json にエージェント ARN を追加
        # TST と PRD のデプロイ間の競合を避けるために環境固有のキーを使用
        # 環境キーが存在しない場合は作成
        if environment.lower() not in config:
            config[environment.lower()] = {}
        
        config[environment.lower()]['agent_arn'] = result['launch_result'].agent_arn
        config[environment.lower()]['agent_name'] = result['agent_name']
        config[environment.lower()]['agent_id'] = result['launch_result'].agent_id
        
        with open("cicd/hp_config.json", 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Agent ARN を hp_config.json に {environment} 環境キーで追加しました")
        
        # エージェントの準備完了を待機
        print("Agent の準備が完了するまで待機中...")
        import time
        time.sleep(60)        
        # status_response = result['launch_result'].status()
        # status = status_response.endpoint['status']
        # end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        # while status not in end_status:
        #     time.sleep(10)
        #     status_response = result['launch_result'].status()
        #     status = status_response.endpoint['status']
        #     print(f"Agent status: {status}")
        
        # if status == 'READY':
        #     print("Agent is ready!")
        # else:
        #     print(f"Agent deployment failed with status: {status}")
        #     sys.exit(1)
        
        return result
        
    except Exception as e:
        print(f"Agent のデプロイ中にエラーが発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

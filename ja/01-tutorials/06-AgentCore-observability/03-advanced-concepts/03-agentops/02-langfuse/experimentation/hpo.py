import json
import argparse
import os
import sys
import time

# 上位ディレクトリの utils からインポートするためにパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.agent import deploy_agent, delete_agent
from utils.langfuse import run_experiment


def _parse_bool(value):
    value_str = str(value).strip().lower()
    if value_str in {"true", "t", "1", "yes", "y"}:
        return True
    if value_str in {"false", "f", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean value (True/False)")


def main():
    # 設定ファイルを読み込み
    config_path = os.path.join(os.path.dirname(__file__), 'hpo_config.json')

    parser = argparse.ArgumentParser(description="Hyperparameter optimization runner")
    parser.add_argument(
        "--force-redeploy",
        dest="force_redeploy",
        type=_parse_bool,
        default=True,
        metavar="True/False",
        help="Force agent re-deployment before running experiments (default: True)",
    )
    args = parser.parse_args()

    force_redeploy = args.force_redeploy
    environment = "DEV"
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    models = config['models']
    system_prompts = config['system_prompts']
    
    # 結果を格納する辞書
    results = {}
    deployed_agents = []
    
    # フェーズ 1: すべてのエージェントをデプロイ
    print(f"\n{'='*80}")
    print("PHASE 1: DEPLOYING AGENTS")
    print(f"{'='*80}\n")
    
    for model in models:
        for prompt in system_prompts:
            combination_key = f"{model['name']}__{prompt['name']}"
            
            print(f"\n{'='*80}")
            print(f"組み合わせをデプロイ中: {combination_key}")
            print(f"モデル: {model['name']} ({model['model_id']})")
            print(f"プロンプト: {prompt['name']}")
            print(f"{'='*80}\n")
            
            try:
                # deploy_agent 関数を実行
                result = deploy_agent(model, prompt, force_redeploy, environment)
                
                # 結果から agent_name, agent_arn, agent_id, ecr_uri を抽出
                agent_name = result['agent_name']
                launch_result = result['launch_result']
                # launch_result にはエージェント Runtime ARN が含まれているはず
                agent_arn = launch_result.agent_arn
                agent_id = launch_result.agent_id
                ecr_uri = launch_result.ecr_uri
                
                results[combination_key] = {
                    'status': 'deployed',
                    'model': model['name'],
                    'prompt': prompt['name'],
                    'deployment_result': result
                }
                deployed_agents.append({
                    'combination_key': combination_key,
                    'agent_name': agent_name,
                    'agent_arn': agent_arn,
                    'agent_id': agent_id,
                    'ecr_uri': ecr_uri,
                    'model_id': model['model_id'],
                    'system_prompt_id': prompt['name']
                })
                print(f"✓ デプロイに成功しました: {combination_key}\n")
                
            except Exception as e:
                results[combination_key] = {
                    'status': 'error',
                    'model': model['name'],
                    'prompt': prompt['name'],
                    'error': str(e)
                }
                print(f"✗ デプロイエラー {combination_key}: {str(e)}\n")
    
    # フェーズ 2: すべてのデプロイ済みエージェントで実験を実行
    print(f"\n{'='*80}")
    print("PHASE 2: RUNNING EXPERIMENTS")
    print(f"{'='*80}\n")
    
    for agent_info in deployed_agents:
        combination_key = agent_info['combination_key']
        agent_name = agent_info['agent_name']
        agent_arn = agent_info['agent_arn']
        model_id = agent_info['model_id']
        system_prompt_id = agent_info['system_prompt_id']
        
        print(f"\n{'='*80}")
        print(f"エージェントの実験を実行中: {combination_key}")
        print(f"Agent ARN: {agent_arn}")
        print(f"{'='*80}\n")
        
        try:
            # Langfuse データセットを使用して実験を実行
            experiment_result = run_experiment(
                agent_arn=agent_arn,
                experiment_name=f"hpo_experiment_{combination_key}",
                experiment_description=f"Hyperparameter optimization experiment for {combination_key}",
                metadata={
                    'model_id': model_id,
                    'system_prompt_id': system_prompt_id
                }
            )
            
            # 結果を実験データで更新
            results[combination_key]['experiment_result'] = str(experiment_result)
            results[combination_key]['status'] = 'success'
            print(f"✓ 実験を正常に実行しました: {combination_key}\n")
            
        except Exception as e:
            results[combination_key]['experiment_error'] = str(e)
            results[combination_key]['status'] = 'experiment_error'
            print(f"✗ 実験実行エラー {combination_key}: {str(e)}\n")

    # Langfuse での評価が完了するまで 2 分間待機
    time.sleep(120)
    
    # # フェーズ 3: すべてのデプロイ済みエージェントを削除
    print(f"\n{'='*80}")
    print("PHASE 3: DELETING AGENTS")
    print(f"{'='*80}\n")
    
    for agent_info in deployed_agents:
        combination_key = agent_info['combination_key']
        agent_name = agent_info['agent_name']
        agent_id = agent_info['agent_id']
        ecr_uri = agent_info['ecr_uri']
        
        print(f"\n{'='*80}")
        print(f"エージェントを削除中: {combination_key}")
        print(f"エージェント名: {agent_name}")
        print(f"エージェント ID: {agent_id}")
        print(f"{'='*80}\n")
        
        try:
            deletion_result = delete_agent(agent_id, ecr_uri)
            
            # 結果を削除データで更新
            results[combination_key]['deletion_result'] = deletion_result
            print(f"✓ 削除に成功しました: {combination_key}\n")
            
        except Exception as e:
            results[combination_key]['deletion_error'] = str(e)
            print(f"✗ 削除エラー {combination_key}: {str(e)}\n")
    
    # 最終結果サマリーを出力
    print(f"\n{'='*80}")
    print("FINAL RESULTS SUMMARY")
    print(f"{'='*80}\n")
    
    print(json.dumps(results, indent=2, default=str))
    
    # 統計情報を出力
    successful = sum(1 for r in results.values() if r['status'] == 'success')
    failed = sum(1 for r in results.values() if r['status'] == 'error')
    
    print(f"\n{'='*80}")
    print(f"合計組み合わせ数: {len(results)}")
    print(f"成功: {successful}")
    print(f"失敗: {failed}")
    print(f"{'='*80}\n")
    
    return results


if __name__ == "__main__":
    main()


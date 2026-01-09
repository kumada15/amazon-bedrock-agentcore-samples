import json
import os
import sys

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.agent import invoke_agent

# Configuration
AGENT_ARN = "arn:aws:bedrock-agentcore:us-west-2:308819823671:runtime/strands_claude45sonnet_prompt1_PRD-86HGVK6oub"  # Replace with your actual agent ARN
CONFIG_FILE = "load_config.json"


def load_config(config_file):
    """
    プロンプトを含む設定ファイルを読み込みます。

    Parameters:
    - config_file (str): 設定 JSON ファイルのパス

    Returns:
    - dict: 読み込まれた設定
    """
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config


def simulate_user_interactions(agent_arn, prompts):
    """
    各プロンプトでエージェントを呼び出してユーザーインタラクションをシミュレートします。

    Parameters:
    - agent_arn (str): デプロイされたエージェントランタイムの ARN
    - prompts (list): 'name' と 'prompt' キーを持つプロンプト辞書のリスト

    Returns:
    - list: 各エージェント呼び出しの結果リスト
    """
    results = []
    
    for idx, prompt_item in enumerate(prompts):
        prompt_name = prompt_item.get('name', f'prompt_{idx}')
        prompt = prompt_item.get('prompt', '')
        
        print(f"\n{'='*80}")
        print(f"処理中: {prompt_name}")
        print(f"プロンプト: {prompt}")
        print(f"{'='*80}")
        
        # Invoke the agent
        result = invoke_agent(agent_arn, prompt)
        
        # Check for errors
        if 'error' in result:
            print(f"❌ エージェント呼び出しエラー: {result['error']}")
            results.append({
                'prompt_name': prompt_name,
                'prompt': prompt,
                'status': 'error',
                'error': result['error']
            })
            continue
        
        # Extract the response based on content type
        if result.get('content_type') == 'application/json':
            response = result['response']
        else:
            response = result.get('response', '')
        
        print("\n✅ 応答を受信しました:")
        print(f"{response}\n")
        
        results.append({
            'prompt_name': prompt_name,
            'prompt': prompt,
            'status': 'success',
            'response': response,
            'session_id': result.get('session_id'),
            'content_type': result.get('content_type')
        })
    
    return results


def main():
    """
    設定を読み込み、ユーザーインタラクションをシミュレートするメイン関数。
    """
    print(f"{CONFIG_FILE}から設定を読み込み中...")
    
    try:
        config = load_config(CONFIG_FILE)
        prompts = config.get('prompts', [])
        
        if not prompts:
            print("⚠️  設定ファイルにプロンプトが見つかりません。")
            return
        
        print(f"{len(prompts)}個のプロンプトを処理します。")
        print(f"Agent ARNを使用中: {AGENT_ARN}")
        
        # Simulate user interactions
        results = simulate_user_interactions(AGENT_ARN, prompts)
        
        # Print summary
        print(f"\n{'='*80}")
        print("シミュレーションサマリー")
        print(f"{'='*80}")
        print(f"処理されたプロンプト総数: {len(results)}")
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = sum(1 for r in results if r['status'] == 'error')
        print(f"✅ 成功: {success_count}")
        print(f"❌ 失敗: {error_count}")
        print(f"{'='*80}\n")
        
    except FileNotFoundError:
        print(f"❌ エラー: 設定ファイル'{CONFIG_FILE}'が見つかりません。")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON設定ファイルの解析エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

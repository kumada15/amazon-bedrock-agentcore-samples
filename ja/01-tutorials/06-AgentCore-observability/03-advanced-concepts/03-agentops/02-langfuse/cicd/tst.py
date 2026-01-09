import sys
import os
import json
import langfuse

from langfuse.experiment import create_evaluator_from_autoevals
from autoevals.llm import Factuality
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.langfuse import get_langfuse_client
from utils.agent import invoke_agent
from utils.aws import get_ssm_parameter

# スクリプトの先頭に追加
#logging.basicConfig(level=logging.DEBUG)
#logger = logging.getLogger("autoevals")
#logger.setLevel(logging.DEBUG)




# hp_config.json からハイパーパラメータとエージェント設定を読み込み
def load_hp_config(config_path="cicd/hp_config.json"):
    """JSON ファイルからハイパーパラメータとエージェント設定を読み込みます。"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config["tst"]
    except FileNotFoundError:
        print(f"エラー: 設定ファイル {config_path} が見つかりません。")
        print("まずデプロイ手順を実行してください。")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"エラー: {config_path} の JSON が無効です: {e}")
        sys.exit(1)

# 設定を読み込み
print("hp_config.json から Agent 設定を読み込み中...")
config = load_hp_config()

# 設定に agent_arn が存在するかチェック
if not config.get("agent_arn"):
    print("エラー: hp_config.json に agent_arn が見つかりません。")
    print("まずデプロイ手順を実行してください。")
    sys.exit(1)

agent_arn = config["agent_arn"]
print(f"デプロイからの Agent ARN を使用: {agent_arn}")
print(f"Agent 名: {config.get('agent_name', 'N/A')}")
print(f"Agent ID: {config.get('agent_id', 'N/A')}")

    # Langfuse クライアントを初期化
langfuse_client = get_langfuse_client() 

# Bedrock モデルを LLMaaJ モデルとして定義
# Bedrock を指す環境変数を設定
os.environ["OPENAI_API_KEY"] = get_ssm_parameter("/autoevals/OPENAI_API_KEY")
os.environ["OPENAI_BASE_URL"] = get_ssm_parameter("/autoevals/OPENAI_BASE_URL")


# データセットを取得
dataset_name="strands-ai-mcp-agent-evaluation"
dataset = langfuse_client.get_dataset(dataset_name)

# オリジナルデータセットの最初の 3 件を出力
print(f"\n{'='*80}\nデータセット '{dataset_name}' から最初の 3 件のオリジナルアイテム:\n{'='*80}")
for i, item in enumerate(dataset.items[:3]):
    print(f"\nアイテム {i+1}:")
    print(f"  ID: {item.id}")
    print(f"  入力: {item.input}")
    print(f"  期待される出力: {item.expected_output}")
    print(f"  メタデータ: {item.metadata}")
print(f"{'='*80}\n")

# データセットアイテムを変換：response_facts を個別のアイテムに展開
expanded_items = []
for item in dataset.items:
    # expected_output から response_facts を抽出
    response_facts = item.expected_output.get('response_facts', [])
    
    # 各 response_fact に対して新しいアイテムを作成
    for idx, fact in enumerate(response_facts):
        # 変換されたデータで辞書を作成
        # 入力辞書から質問文字列を抽出
        expanded_item = {
            'input': item.input['question'],
            'expected_output': fact
        }
        expanded_items.append(expanded_item)

# 変換されたデータセットの最初の 3 件を出力
print(f"\n{'='*80}\nデータセット '{dataset_name}' から最初の 3 件の展開アイテム:\n{'='*80}")
for i, item in enumerate(expanded_items[:3]):
    print(f"\nアイテム {i+1}:")
    print(f"  入力: {item['input']}")
    print(f"  期待される出力: {item['expected_output']}")
print(f"{'='*80}\n")

# invoke_agent をラップするタスク関数を定義
def agent_task(*, item, **kwargs):
    """
    データセットアイテムの入力でエージェントを呼び出すタスク関数。

    Parameters:
    - item: 'input' と 'expected_output' を含む辞書

    Returns:
    - str: エージェントのレスポンス
    """
    # データセットアイテムからプロンプトを抽出
    # item は辞書で、input には質問が直接含まれる
    prompt = item['input']
    
    # エージェントを呼び出し
    result = invoke_agent(agent_arn, prompt)

    # エラーをチェック
    if 'error' in result:
        raise Exception(f"Agent invocation error: {result['error']}")
    
    # コンテンツタイプに基づいてレスポンスを抽出
    if result.get('content_type') == 'application/json':
        response = result['response']
    else:
        response = result.get('response', '')
    
    return response


# autoevals 評価器を定義
evaluator = create_evaluator_from_autoevals(Factuality(
    client=OpenAI(), 
    model="qwen.qwen3-235b-a22b-2507-v1:0")
    )
 
result = langfuse_client.run_experiment(
    name="Autoevals Integration Test",
    data=expanded_items,
    task=agent_task,
    evaluators=[evaluator]
)
 
print(result.format(include_item_results=True))

# Factuality スコアを抽出してファイルに保存

factuality_scores = []
# 実験結果からアイテム結果にアクセス
for item_result in result.item_results:
    for evaluation in item_result.evaluations:
        if evaluation.name == 'Factuality':
            evaluation_dict = {
                "name": evaluation.name,
                "value": evaluation.value,
                "comment": evaluation.comment
            }
            factuality_scores.append(evaluation_dict)
            print(evaluation_dict)

# 平均を計算
avg_score = sum(s['value'] for s in factuality_scores) / len(factuality_scores) if factuality_scores else 0

# 結果を保存
results = {
    'experiment_name': result.name,
    'total_items': len(factuality_scores),
    'average_factuality_score': avg_score,
    'scores': factuality_scores
}

with open('factuality_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*80}")
print("Factuality 結果サマリー:")
print(f"  平均スコア: {avg_score:.3f} ({avg_score*100:.1f}%)")
print(f"  合計アイテム数: {len(factuality_scores)}")
print("  結果を保存しました: factuality_results.json")
print(f"{'='*80}\n")
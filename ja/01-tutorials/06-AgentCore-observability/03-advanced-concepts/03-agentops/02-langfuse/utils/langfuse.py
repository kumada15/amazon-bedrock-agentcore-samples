import os
from datetime import datetime
from langfuse import get_client
from utils.agent import invoke_agent
from utils.aws import get_ssm_parameter


def get_langfuse_client():
    """
    適切な設定で Langfuse クライアントを初期化して返します。

    Returns:
    - Langfuse クライアントインスタンス
    """

    os.environ["LANGFUSE_HOST"] = get_ssm_parameter("/langfuse/LANGFUSE_HOST")
    os.environ["LANGFUSE_SECRET_KEY"] = get_ssm_parameter("/langfuse/LANGFUSE_SECRET_KEY")
    os.environ["LANGFUSE_PUBLIC_KEY"] = get_ssm_parameter("/langfuse/LANGFUSE_PUBLIC_KEY")
    os.environ["LANGFUSE_PROJECT_NAME"] = get_ssm_parameter("/langfuse/LANGFUSE_PROJECT_NAME")
    # Langfuse クライアントを初期化
    client = get_client()
    
    return client


def run_experiment(
    agent_arn,
    dataset_name="strands-ai-mcp-agent-evaluation",
    experiment_name=None,
    experiment_description=None,
    evaluators=None,
    run_evaluators=None,
    max_concurrency=1,
    metadata=None
):
    """
    invoke_agent をタスク関数として使用し、Langfuse データセットで実験を実行します。

    Parameters:
    - agent_arn (str): デプロイされたエージェント Runtime の ARN
    - dataset_name (str): Langfuse のデータセット名（デフォルト：'strands-ai-mcp-agent-evaluation'）
    - experiment_name (str): この実験実行の名前（デフォルト：'{timestamp}_strands_langfuse_mcp_experimentation'）
    - experiment_description (str, optional): 実験の説明
    - evaluators (list, optional): アイテムレベル評価用の評価関数のリスト
    - run_evaluators (list, optional): 実行レベル評価用の評価関数のリスト
    - max_concurrency (int): 同時タスク実行の最大数（デフォルト：1）

    Returns:
    - dict: トレース、スコア、メタデータを含む実験結果
    """
    
    # 実験名にタイムスタンプを追加
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_name_ts = f"{timestamp}_{experiment_name}"
    
    # Langfuse クライアントを初期化
    langfuse = get_langfuse_client()

    # データセットを取得
    dataset = langfuse.get_dataset(dataset_name)
    
    # invoke_agent をラップするタスク関数を定義
    def agent_task(*, item, **kwargs):
        """
        データセットアイテムの入力でエージェントを呼び出すタスク関数。

        Parameters:
        - item: input と、オプションで expected_output を含む DatasetItemClient オブジェクト

        Returns:
        - str: エージェントのレスポンス
        """
        # データセットアイテムからプロンプトを抽出
        # ドット記法を使用して DatasetItemClient プロパティにアクセス
        prompt = item.input['question']

        # エージェントを呼び出し
        result = invoke_agent(agent_arn, prompt, environment="DEV")

        # エラーをチェック
        if 'error' in result:
            raise Exception(f"エージェント呼び出しエラー: {result['error']}")

        # コンテンツタイプに基づいてレスポンスを抽出
        if result.get('content_type') == 'application/json':
            response = result['response']
        else:
            response = result.get('response', '')

        return response
    
    # データセットで実験を実行
    result = dataset.run_experiment(
        name=experiment_name_ts,
        description=experiment_description or f"エージェント {agent_arn} の評価",
        task=agent_task,
        metadata=metadata
        #evaluators=evaluators or [],
        #run_evaluators=run_evaluators or [],
        #max_concurrency=max_concurrency
    )
    
    # フォーマットされた結果を出力
    print("\n" + "="*80)
    print("EXPERIMENT RESULTS")
    print("="*80)
    print(result.format())
    print("="*80 + "\n")
    
    return result


def run_experiment_with_evaluators(
    agent_arn,
    dataset_name="strands-ai-mcp-agent-evaluation",
    experiment_name="Agent Evaluation with Scoring",
    experiment_description=None,
    max_concurrency=1
):
    """
    レスポンス品質評価用のサンプル評価器を使用して実験を実行します。

    Parameters:
    - agent_arn (str): デプロイされたエージェント Runtime の ARN
    - dataset_name (str): Langfuse のデータセット名
    - experiment_name (str): この実験実行の名前
    - experiment_description (str, optional): 実験の説明
    - max_concurrency (int): 同時タスク実行の最大数

    Returns:
    - dict: 評価を含む実験結果
    """
    from langfuse import Evaluation
    
    # アイテムレベル評価器を定義
    def response_length_evaluator(*, input, output, expected_output, metadata, **kwargs):
        """
        レスポンスが妥当な長さ（短すぎない）かどうかを評価します。
        """
        if isinstance(output, str):
            response_text = output
        else:
            response_text = str(output)
        
        # レスポンスが少なくとも 10 文字あるかチェック
        is_adequate = len(response_text) >= 10
        
        return Evaluation(
            name="response_length",
            value=1.0 if is_adequate else 0.0,
            comment=f"レスポンス長: {len(response_text)} 文字"
        )
    
    def response_quality_evaluator(*, input, output, expected_output, metadata, **kwargs):
        """
        基本的な品質チェック - レスポンスにエラー指標が含まれていないことを確認します。
        """
        if isinstance(output, str):
            response_text = output.lower()
        else:
            response_text = str(output).lower()
        
        # 一般的なエラーパターンをチェック
        error_indicators = ['error', 'failed', 'unable', 'cannot', 'invalid']
        has_errors = any(indicator in response_text for indicator in error_indicators)
        
        return Evaluation(
            name="response_quality",
            value=0.0 if has_errors else 1.0,
            comment="レスポンスにエラー指標が含まれています" if has_errors else "レスポンスは有効です"
        )
    
    # 実行レベル評価器を定義
    def average_score_evaluator(*, run_evaluations, **kwargs):
        """
        すべてのアイテム評価の平均スコアを計算します。
        """
        if not run_evaluations:
            return Evaluation(name="avg_score", value=0.0, comment="平均化する評価がありません")
        
        # response_quality スコアの平均を計算
        quality_scores = [
            eval.value for eval in run_evaluations 
            if eval.name == "response_quality"
        ]
        
        if quality_scores:
            avg = sum(quality_scores) / len(quality_scores)
            return Evaluation(
                name="avg_response_quality",
                value=avg,
                comment=f"平均レスポンス品質: {avg:.2%}"
            )
        
        return Evaluation(name="avg_response_quality", value=0.0, comment="品質スコアが見つかりません")
    
    # 評価器を使用して実験を実行
    return run_experiment(
        agent_arn=agent_arn,
        dataset_name=dataset_name,
        experiment_name=experiment_name,
        experiment_description=experiment_description,
        evaluators=[response_length_evaluator, response_quality_evaluator],
        run_evaluators=[average_score_evaluator],
        max_concurrency=max_concurrency
    )

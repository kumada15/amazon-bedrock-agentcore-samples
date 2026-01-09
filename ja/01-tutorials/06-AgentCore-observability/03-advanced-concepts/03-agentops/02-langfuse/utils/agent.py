import base64
import boto3
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
from langfuse import get_client
from utils.aws import get_ssm_parameter

boto_session = Session()
region = boto_session.region_name

agentcore_runtime = Runtime()


class ExistingAgentLaunchResult:
    """API 互換性を維持するための、既にデプロイされたエージェント用のモック起動結果オブジェクト。"""
    def __init__(self, agent_arn, agent_id, ecr_uri=None, status='ACTIVE'):
        self.agent_arn = agent_arn
        self.agent_id = agent_id
        self.ecr_uri = ecr_uri
        self.status = status
        self.already_deployed = True


LANGFUSE_PROJECT_NAME = get_ssm_parameter("/langfuse/LANGFUSE_PROJECT_NAME")
LANGFUSE_SECRET_KEY = get_ssm_parameter("/langfuse/LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = get_ssm_parameter("/langfuse/LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = get_ssm_parameter("/langfuse/LANGFUSE_HOST")

    # Langfuse 設定
otel_endpoint = f'{LANGFUSE_HOST}/api/public/otel'
langfuse_project_name = LANGFUSE_PROJECT_NAME
langfuse_secret_key = LANGFUSE_SECRET_KEY
langfuse_public_key = LANGFUSE_PUBLIC_KEY
langfuse_auth_token = base64.b64encode(f"{langfuse_public_key}:{langfuse_secret_key}".encode()).decode()
otel_auth_header = f"Authorization=Basic {langfuse_auth_token}"




def deploy_agent(model, system_prompt, force_redeploy=False, environment="DEV"):
    """
    指定された設定で Amazon Bedrock AgentCore Runtime エージェントをデプロイします。

    Parameters:
    - model (dict): モデル名と model_id を含む辞書
    - system_prompt (dict): プロンプト名とプロンプトテキストを含む辞書
    - force_redeploy (bool): True の場合、既に存在していてもエージェントを再デプロイ（デフォルト：False）

    Returns:
    - dict: AgentCore Runtime からの起動結果、または既にデプロイされている場合は既存のエージェント情報
    """
    agent_name = f'strands_{model["name"]}_{system_prompt["name"]}_{environment}'
    
    # エージェントが既に存在するかチェック
    try:
        agentcore_control_client = boto3.client(
            'bedrock-agentcore-control',
            region_name=region
        )
        
        # このエージェントが既に存在するかどうかを確認するため、すべてのエージェント Runtime をリスト
        list_response = agentcore_control_client.list_agent_runtimes()
        existing_agents = list_response.get('agentRuntimes', [])        
        # この名前のエージェントが既に存在するかチェック
        existing_agent = None
        for agent_summary in existing_agents:
            if agent_summary.get('agentRuntimeName') == agent_name:
                existing_agent = agent_summary
                break
        
        # エージェントが存在し、force_redeploy が False の場合、既存のエージェント情報を返す
        if existing_agent and not force_redeploy:
            print(f"エージェント '{agent_name}' は既に存在します。デプロイをスキップします。")
            print(f"Agent Runtime ARN: {existing_agent.get('agentRuntimeArn')}")
            print(f"ステータス: {existing_agent.get('status')}")
            
            # ECR URI を抽出するために完全なエージェント Runtime 詳細を取得
            agent_runtime_id = existing_agent.get('agentRuntimeId')
            agent_runtime_arn = existing_agent.get('agentRuntimeArn')
            
            try:
                get_response = agentcore_control_client.get_agent_runtime(
                    agentRuntimeId=agent_runtime_id
                )
                ecr_uri = get_response.get('ecrUri', '')
            except Exception as e:
                print(f"警告: ECR URI を取得できませんでした: {str(e)}")
                ecr_uri = ''
            
            # 互換性のある起動結果オブジェクトを作成
            launch_result = ExistingAgentLaunchResult(
                agent_arn=agent_runtime_arn,
                agent_id=agent_runtime_id,
                ecr_uri=ecr_uri,
                status=existing_agent.get('status', 'ACTIVE')
            )
            
            return {
                'agent_name': agent_name,
                'launch_result': launch_result,
                'model_id': model["model_id"],
                'system_prompt_id': system_prompt["name"]
            }
        
        # エージェントが存在し、force_redeploy が True の場合、ユーザーに通知
        if existing_agent and force_redeploy:
            print(f"エージェント '{agent_name}' は既に存在します。強制的に再デプロイします...")

    except Exception as e:
        print(f"既存エージェント確認中にエラー: {str(e)}")
        print("デプロイを続行します...")
    
    # デプロイを実行
    response = agentcore_runtime.configure(
        entrypoint="./agents/strands_claude.py",
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="./agents/requirements.txt",
        region=region,
        agent_name=agent_name,
        disable_otel=True,
       memory_mode='NO_MEMORY'
    )

    print(response)


    # エージェント設定
    bedrock_model_id = model["model_id"]
    system_prompt_value = system_prompt["prompt"]

    launch_result = agentcore_runtime.launch(
        env_vars={
            "BEDROCK_MODEL_ID": bedrock_model_id,
            "LANGFUSE_PROJECT_NAME": langfuse_project_name,
            "LANGFUSE_TRACING_ENVIRONMENT": environment,
            "OTEL_EXPORTER_OTLP_ENDPOINT": otel_endpoint,  # Langfuse OTEL エンドポイントを使用
            "OTEL_EXPORTER_OTLP_HEADERS": otel_auth_header,  # Langfuse OTEL 認証ヘッダーを追加
            "DISABLE_ADOT_OBSERVABILITY": "true",
            "SYSTEM_PROMPT": system_prompt_value
        }
    )

    print(launch_result)

    return {
        'agent_name': agent_name,
        'launch_result': launch_result,
        'model_id': model["model_id"],
        'system_prompt_id': system_prompt["name"]
    }


def invoke_agent(agent_arn, prompt, session_id=None, environment=None):
    """
    指定されたプロンプトで Amazon Bedrock AgentCore Runtime エージェントを呼び出します。

    Parameters:
    - agent_arn (str): デプロイされたエージェント Runtime の ARN
    - prompt (str): エージェントへの入力プロンプト
    - session_id (str, optional): セッションの一意識別子

    Returns:
    - dict: エージェントのレスポンス
    """
    import json
    import uuid
    
    try:
        # Bedrock AgentCore クライアントを初期化
        agent_core_client = boto3.client('bedrock-agentcore', region_name=region)
        
        if environment == "DEV":
            trace_id = get_client().get_current_trace_id()
            obs_id = get_client().get_current_observation_id()

            payload = json.dumps({"prompt": prompt, 
                                    "trace_id": trace_id, 
                                    "parent_obs_id": obs_id
                                    }).encode()
        else:
            payload = json.dumps({"prompt": prompt}).encode()
        
        # 指定されていない場合は session_id を生成
        if session_id is None:
            session_id = str(uuid.uuid4())
        



        # エージェントを呼び出し
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        # コンテンツタイプに基づいてレスポンスを処理
        content_type = response.get("contentType", "")
        
        if "text/event-stream" in content_type:
            # ストリーミングレスポンスを処理
            content = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                        content.append(line)
            
            return {
                'response': "\n".join(content),
                'session_id': session_id,
                'content_type': content_type
            }
        
        elif content_type == "application/json":
            # 標準 JSON レスポンスを処理
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8'))
            
            return {
                'response': json.loads(''.join(content)),
                'session_id': session_id,
                'content_type': content_type
            }
        
        else:
            # その他のコンテンツタイプの場合は生のレスポンスを返す
            return {
                'response': response,
                'session_id': session_id,
                'content_type': content_type
            }
            
    except Exception as e:
        return {
            'error': str(e),
            'agent_arn': agent_arn
        }


def delete_agent(agent_runtime_id, ecr_uri):
    """
    Amazon Bedrock AgentCore Runtime エージェントとその ECR リポジトリを削除します。

    Parameters:
    - agent_runtime_id (str): 削除するエージェント Runtime ID
    - ecr_uri (str): エージェントのコンテナリポジトリの ECR URI

    Returns:
    - dict: 削除操作のステータス
    """
    try:
        # Bedrock AgentCore Control クライアントを初期化
        agentcore_control_client = boto3.client(
            'bedrock-agentcore-control',
            region_name=region
        )
        
        # ECR クライアントを初期化
        ecr_client = boto3.client(
            'ecr',
            region_name=region
        )
        
        # エージェント Runtime を削除
        runtime_delete_response = agentcore_control_client.delete_agent_runtime(
            agentRuntimeId=agent_runtime_id,
        )

        print(f'ECR リポジトリ: {ecr_uri}')
        
        # ECR リポジトリを削除
        repository_name_tmp = ecr_uri.split('/')[1] if '/' in ecr_uri else ecr_uri

        print(f'リポジトリ名 1: {repository_name_tmp}')

        repository_name = repository_name_tmp.split(':')[0] if ':' in repository_name_tmp else repository_name_tmp

        print(f'リポジトリ名 2: {repository_name}')

        print(f"ECR リポジトリを削除中: {repository_name}")

        ecr_delete_response = ecr_client.delete_repository(
            repositoryName=repository_name,
            force=True
        )
        
        return {
            'status': 'success',
            'agent_runtime_id': agent_runtime_id,
            'runtime_delete_response': runtime_delete_response,
            'ecr_delete_response': ecr_delete_response
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'agent_runtime_id': agent_runtime_id,
            'error': str(e)
        }


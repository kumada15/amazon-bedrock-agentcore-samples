"""
AWS Operations Agent Gateway Lambda ハンドラー - 最適化バージョン
Strands Agent 統合を介して AWS リソース検査ツールを処理する
更新: 2025-08-02 - python_repl と shell ツールを使用した最適化されたシステムプロンプトを追加
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Import Strands components at module level
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import use_aws, shell, calculator, think, current_time, stop, handoff_to_user
STRANDS_AVAILABLE = True
logging.info("Strands modules imported successfully with shell tool")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Service Tool Configurations
SERVICE_QUERIES = {
    # Core AWS Services
    'ec2_read_operations': "List and describe EC2 resources including instances, security groups, VPCs, subnets, and key pairs. Include instance states, types, and network configurations.",
    's3_read_operations': "List and describe S3 resources including buckets, bucket policies, lifecycle configurations, and access settings. Include bucket regions and creation dates.",
    'lambda_read_operations': "List and describe Lambda resources including functions, layers, aliases, and event source mappings. Include runtime, memory, timeout, and last modified information.",
    'cloudformation_read_operations': "List and describe CloudFormation resources including stacks, stack resources, stack events, and templates. Include stack status and creation times.",
    'iam_read_operations': "List and describe IAM resources including users, roles, policies, and groups. Include policy attachments and permissions (read-only operations only).",
    'rds_read_operations': "List and describe RDS and database resources including DB instances, clusters, snapshots, and parameter groups. Include engine types, versions, and status.",
    'cloudwatch_read_operations': "List and describe CloudWatch resources including metrics, alarms, log groups, and dashboards. Include alarm states and metric statistics.",
    'cost_explorer_read_operations': "Retrieve cost and billing information including cost breakdowns, usage reports, and budget information. Include cost trends and service-wise spending.",
    
    # Additional AWS Services
    'ecs_read_operations': "List and describe ECS resources including clusters, services, tasks, and task definitions. Include service status and task counts.",
    'eks_read_operations': "List and describe EKS resources including clusters, node groups, and add-ons. Include cluster status, versions, and configurations.",
    'sns_read_operations': "List and describe SNS resources including topics, subscriptions, and platform applications. Include topic ARNs and subscription counts.",
    'sqs_read_operations': "List and describe SQS resources including queues, queue attributes, and message statistics. Include queue types and visibility timeouts.",
    'dynamodb_read_operations': "List and describe DynamoDB resources including tables, indexes, and backups. Include table status, item counts, and throughput settings.",
    'route53_read_operations': "List and describe Route53 resources including hosted zones, record sets, and health checks. Include DNS configurations and routing policies.",
    'apigateway_read_operations': "List and describe API Gateway resources including REST APIs, resources, methods, and deployments. Include API stages and endpoint configurations.",
    'ses_read_operations': "List and describe SES resources including verified identities, configuration sets, and sending statistics. Include reputation metrics and quotas.",
    'bedrock_read_operations': "List and describe Bedrock resources including foundation models, model customization jobs, and inference profiles. Include model capabilities and availability.",
    'sagemaker_read_operations': "List and describe SageMaker resources including endpoints, models, training jobs, and notebook instances. Include status and configurations."
}

BASIC_TOOLS = ['hello_world', 'get_time']
AWS_SERVICE_TOOLS = list(SERVICE_QUERIES.keys())
ALL_TOOLS = BASIC_TOOLS + AWS_SERVICE_TOOLS


def extract_tool_name(context, event: Dict[str, Any]) -> Optional[str]:
    """Gateway コンテキストまたはイベントからツール名を抽出する。"""
    
    # Try Gateway context first
    if hasattr(context, 'client_context') and context.client_context:
        if hasattr(context.client_context, 'custom') and context.client_context.custom:
            tool_name = context.client_context.custom.get('bedrockAgentCoreToolName')
            if tool_name and '___' in tool_name:
                # Remove namespace prefix (e.g., "aws-tools___hello_world" -> "hello_world")
                return tool_name.split('___', 1)[1]
            elif tool_name:
                return tool_name
    
    # Fallback to event-based extraction
    for field in ['tool_name', 'toolName', 'name', 'method', 'action', 'function']:
        if field in event:
            return event[field]
    
    # Infer from event structure
    if isinstance(event, dict):
        if 'name' in event and len(event) == 1:
            return 'hello_world'  # Typical hello_world structure
        elif len(event) == 0:
            return 'get_time'  # Empty args typically means get_time
    
    return None

def handle_hello_world(event: Dict[str, Any]) -> Dict[str, Any]:
    """hello_world ツールを処理する。"""
    name = event.get('name', 'World')
    message = f"こんにちは、{name}！このメッセージは AWS Operations Agent Gateway 経由で Lambda 関数から送信されています。"
    
    return {
        'success': True,
        'result': message,
        'tool': 'hello_world',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

def handle_get_time(event: Dict[str, Any]) -> Dict[str, Any]:
    """get_time ツールを処理する。"""
    current_time = datetime.utcnow().isoformat() + 'Z'

    return {
        'success': True,
        'result': f"現在の UTC 時刻: {current_time}",
        'tool': 'get_time',
        'timestamp': current_time
    }

def handle_aws_service_tool(tool_name: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Strands Agent を使用して AWS サービスツールを処理する。"""
    
    # Check if Strands is available
    if not STRANDS_AVAILABLE:
        return {
            'success': False,
            'error': f"Strands modules not available for {tool_name}. Please check Lambda dependencies.",
            'tool': tool_name,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    
    try:
        # Get the natural language query from the simplified schema
        user_query = event.get('query', '')
        if not user_query:
            return {
                'success': False,
                'error': f"Missing required 'query' parameter for {tool_name}",
                'tool': tool_name,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        
        logger.info(f"Strands Agent を初期化中: {tool_name}")
        
        # Initialize Bedrock model
        bedrock_model = BedrockModel(
            region_name='us-east-1',
            model_id='global.anthropic.claude-haiku-4-5-20251001-v1:0',
            temperature=0.1
        )
        
        # Import loop control tools
        from strands_tools import stop, handoff_to_user
        
        # Create Strands Agent with loop control tools
        agent = Agent(
            model=bedrock_model,
            tools=[use_aws, stop, handoff_to_user, current_time],
            system_prompt="""
            あなたは AWS アシスタントです。重要なループ制御ルール:

            1. 実行した AWS 操作の回数を追跡してください
            2. 15 回以上の AWS ツール呼び出しを行った場合は、すぐに 'stop' ツールを使用してください
            3. 繰り返し操作が発生した場合は、'handoff_to_user' を使用してガイダンスを求めてください
            4. ループにはまった場合は、説明を付けて 'stop' を呼び出してください
            5. 'stop' を呼び出す前に必ず要約を提供してください

            ループ制御用の利用可能なツール:
            - stop: 完了時または制限に達した時に正常に終了
            - handoff_to_user: 不確かな場合に人間のガイダンスを取得
            - use_aws: メインの AWS 操作ツール

            重要: 日付関連のクエリでは、日付範囲を計算する前に必ず current_time ツールを使用して現在の日付を取得してください。
            """
        )

        # Build query
        # Get the natural language query from the simplified schema
        if not user_query:
            return {
                'success': False,
                'error': f"Missing required 'query' parameter for {tool_name}",
                'tool': tool_name,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        
        # Build a simple, direct query (removed complex service context to prevent over-execution)
        #service_name = tool_name.replace('_read_operations', '').upper()
        #final_query = f"AWS {service_name}: {user_query}\n\nExecute this single operation directly and return results."
        
        #logger.info(f"Executing simplified query for {tool_name}: {user_query}")
        
        # Execute query
        #response = agent(final_query)
        response = agent(user_query)
        logger.info("##################################")
        print(str(response))
        logger.info("##################################")
        # Extract response text
        response_text = ""
        if hasattr(response, 'message') and 'content' in response.message:
            for content_block in response.message['content']:
                if content_block.get('type') == 'text' or 'text' in content_block:
                    response_text += content_block.get('text', '')
        else:
            response_text = str(response)
        
        logger.info(f"レスポンス長: {len(response_text)} 文字")
        
        return response_text
        # return {
        #     'success': True,
        #     'result': response_text,
        #     'tool': tool_name,
        #     'service': tool_name.replace('_read_operations', '').replace('_', '-'),
        #     'user_query': user_query,
        #     'timestamp': datetime.utcnow().isoformat() + 'Z'
        # }
        
    except Exception as e:
        logger.error(f"AWS サービスツールエラー: {str(e)}")
        return {
            'success': False,
            'error': f"AWS Service Tool Error: {str(e)}",
            'tool': tool_name,
            'service': tool_name.replace('_read_operations', '').replace('_', '-'),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

def lambda_handler(event, context):
    """
    AWS Operations Agent Gateway Lambda ハンドラー - 最適化バージョン

    基本ツール (hello_world、get_time) と AWS サービスツールを
    Strands Agent 統合と包括的なエラーハンドリングで処理する。
    """
    logger.info("AWS Operations Agent Gateway Lambda ハンドラー - 開始")
    logger.info(f"Event: {json.dumps(event, default=str)}")
    
    try:
        # Extract tool name
        tool_name = extract_tool_name(context, event)
        logger.info(f"Tool: {tool_name}")
        
        if not tool_name:
            return {
                'success': False,
                'error': 'Unable to determine tool name from context or event',
                'available_tools': ALL_TOOLS,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        
        # Route to appropriate handler
        if tool_name == 'hello_world':
            return handle_hello_world(event)
        
        elif tool_name == 'get_time':
            return handle_get_time(event)
        
        elif tool_name in AWS_SERVICE_TOOLS:
            return handle_aws_service_tool(tool_name, event)
        
        else:
            # Unknown tool
            return {
                'success': False,
                'error': f"Unknown tool: {tool_name}",
                'available_tools': ALL_TOOLS,
                'total_tools': len(ALL_TOOLS),
                'categories': {
                    'basic': BASIC_TOOLS,
                    'aws_services': AWS_SERVICE_TOOLS
                },
                'tool': tool_name,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
    
    except Exception as e:
        logger.error(f"ハンドラーエラー: {str(e)}")
        return {
            'success': False,
            'error': f"Internal error: {str(e)}",
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    
    finally:
        logger.info("AWS Operations Agent Gateway Lambda ハンドラー - 終了")

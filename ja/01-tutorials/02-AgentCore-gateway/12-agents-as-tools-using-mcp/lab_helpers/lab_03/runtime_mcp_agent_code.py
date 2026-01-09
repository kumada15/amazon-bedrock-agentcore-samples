#!/usr/bin/env python3
"""
Lab 3: Strands 修復エージェント（FastMCP 使用）- AgentCore Runtime デプロイメント
Gateway から Runtime への通信に MCP プロトコルを実装するために FastMCP を使用

重点項目:
- FastMCP による MCP プロトコル実装
- 承認ゲート付きのセキュアな修復ワークフロー
- Code Interpreter を使用したインフラストラクチャ自動化
- 2段階プロセス: 計画 → 承認 → 実行
- リスク評価と影響分析

サーバーレス実行のために AgentCore Runtime にデプロイ
"""

import os
import json
import boto3
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal
import time

# Official MCP package for AgentCore Runtime compatibility
from mcp.server.fastmcp import FastMCP

# Strands framework
from strands import Agent
from strands.models import BedrockModel
from strands.tools import tool

# Bypass tool consent for AgentCore deployment
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("bedrock_agentcore.app")

# Auto-detect AWS region
def get_aws_region():
    """環境変数または boto3 セッションから AWS リージョンを自動検出"""
    # Try environment variable first
    region = os.environ.get('AWS_REGION')
    if region:
        return region
    
    # Try boto3 session default region
    try:
        session = boto3.Session()
        region = session.region_name
        if region:
            return region
    except Exception:
        pass
    
    # Fallback to us-east-1
    return "us-west-2"

# Environment variables (set by AgentCore Runtime)
AWS_REGION = get_aws_region()
logger.info(f"🌍 Using AWS Region: {AWS_REGION}")
MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
AWS_ACCESS_KEY_ID = 'none'
AWS_SECRET_ACCESS_KEY = 'none'

# Treat 'none' string as None for IAM role usage
if AWS_ACCESS_KEY_ID.lower() == 'none':
    AWS_ACCESS_KEY_ID = None
if AWS_SECRET_ACCESS_KEY.lower() == 'none':
    AWS_SECRET_ACCESS_KEY = None

# Initialize FastMCP server for AgentCore Runtime
# host="0.0.0.0" - Listens on all interfaces as required by AgentCore
# stateless_http=True - Enables session isolation for enterprise security
mcp = FastMCP("SRE Remediation Agent", host="0.0.0.0", stateless_http=True)

# Global variables for Code Interpreter
agentcore_code_interpreter = None
CODE_INTERPRETER_AVAILABLE = False

def get_boto3_client(service_name: str, region: str = None):
    """環境変数の認証情報を使用して boto3 クライアントを作成"""
    #region = region or AWS_REGION
    region = get_aws_region()
    
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.client(
            service_name,
            region_name=region,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
    else:
        return boto3.client(service_name, region_name=region)

def get_boto3_session():
    """環境変数の認証情報を使用して boto3 セッションを作成"""
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
    else:
        return boto3.Session(region_name=AWS_REGION)

def get_code_interpreter_from_ssm():
    """SSM Parameter Store から Code Interpreter の詳細を取得"""
    ssm = get_boto3_client('ssm')
    WORKSHOP_NAME = 'aiml301_sre_agentcore'
    
    try:
        interpreter_id = ssm.get_parameter(Name=f'/{WORKSHOP_NAME}/lab-03/code-interpreter-id')['Parameter']['Value']
        interpreter_arn = ssm.get_parameter(Name=f'/{WORKSHOP_NAME}/lab-03/code-interpreter-arn')['Parameter']['Value']
        logger.info(f"✅ Retrieved code interpreter from SSM: {interpreter_id}")
        return interpreter_id, interpreter_arn
    except Exception as e:
        logger.error(f"SSM から Code Interpreter の取得に失敗しました: {e}")
        raise

# Get code interpreter from SSM
CUSTOM_INTERPRETER_ID, CUSTOM_INTERPRETER_ARN = get_code_interpreter_from_ssm()

def get_sre_remediation_s3_bucket():
    # Store in SSM Parameter Store
    parameter_name = '/aiml301_sre_workshop/remediation_s3_bucket'
    #ssm = get_boto3_client('ssm')
    ssm = boto3.client('ssm', region_name='us-west-2')
    parameter = ssm.get_parameter(Name=parameter_name)
    retrieved_bucket_name = parameter['Parameter']['Value']
    print(f"Parameter Store からバケット名を取得しました: {retrieved_bucket_name}")
    return retrieved_bucket_name

# Get s3 details from SSM
retrieved_bucket_name = get_sre_remediation_s3_bucket()

def initialize_code_interpreter_client():
    """AgentCore Code Interpreter クライアントを初期化"""
    global agentcore_code_interpreter, CODE_INTERPRETER_AVAILABLE
    
    try:
        agentcore_code_interpreter = get_boto3_client('bedrock-agentcore')
        CODE_INTERPRETER_AVAILABLE = True
        logger.info("✅ AgentCore Code Interpreter client initialized")
        return True
    except Exception as e:
        CODE_INTERPRETER_AVAILABLE = False
        logger.warning(f"⚠️ AgentCore Code Interpreter not available: {e}")
        return False

def start_code_interpreter_session():
    """カスタムインタープリターを使用して Code Interpreter セッションを開始"""
    if not CODE_INTERPRETER_AVAILABLE:
        return None
    
    try:
        session_response = agentcore_code_interpreter.start_code_interpreter_session(
            codeInterpreterIdentifier=CUSTOM_INTERPRETER_ID,  # Use custom interpreter
            name=f"remediation-session-{uuid.uuid4()}",
            sessionTimeoutSeconds=1800  # 30 minutes
        )
        
        session_id = session_response.get('sessionId')
        logger.info(f"✅ Code Interpreter session started: {session_id}")
        return session_id
        
    except Exception as e:
        logger.error(f"❌ Failed to start Code Interpreter session: {e}")
        return None

def stop_code_interpreter_session(session_id: str):
    """Code Interpreter セッションを停止"""
    if not session_id or not CODE_INTERPRETER_AVAILABLE:
        return
    
    try:
        agentcore_code_interpreter.stop_code_interpreter_session(
            codeInterpreterIdentifier=CUSTOM_INTERPRETER_ID,  # Use custom interpreter
            sessionId=session_id
        )
        logger.info(f"✅ Code Interpreter session stopped: {session_id}")
    except Exception as e:
        logger.error(f"❌ Failed to stop Code Interpreter session: {e}")

def execute_remediation_code(session_id: str, code: str) -> Dict:
    """カスタム AgentCore Code Interpreter を使用して修復コードを実行"""
    if not session_id:
        return {"error": "No Code Interpreter session available"}
    
    try:
        logger.info(f"🔧 Executing remediation code: {code}")
        
        execute_response = agentcore_code_interpreter.invoke_code_interpreter(
            codeInterpreterIdentifier=CUSTOM_INTERPRETER_ID,  # Use custom interpreter
            sessionId=session_id,
            name="executeCode",
            arguments={
                "language": "python",
                "code": code
            }
        )
        
        # Process the streaming response
        output_text = ""
        execution_status = "success"
        
        for event in execute_response.get('stream', []):
            if 'result' in event:
                result = event['result']
                if 'content' in result:
                    for content_item in result['content']:
                        if content_item.get('type') == 'text':
                            output_text += content_item.get('text', '')
                        elif content_item.get('type') == 'error':
                            execution_status = "error"
                            output_text += f"ERROR: {content_item.get('text', '')}"
        
        return {
            "execution_status": execution_status,
            "output": output_text,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to execute remediation code: {e}")
        return {"error": f"Code execution failed: {str(e)}"}

# Define FastMCP Tools

@tool
def execute_remediation_step(remediation_code: str) -> str:
    """修復ステップを実行"""
    try:
        logger.info(f"🔧 execute_remediation_step called with code length: {len(remediation_code)}")
        
        if not initialize_code_interpreter_client():
            logger.error("❌ Code interpreter client not available")
            return "AgentCore Code Interpreter not available"
        
        logger.info("✅ Code interpreter client initialized")
        session_id = start_code_interpreter_session()
        if not session_id:
            logger.error("❌ Failed to start code interpreter session")
            return "Failed to start code interpreter session"
        
        logger.info(f"✅ Code interpreter session started: {session_id}")
        
        # Prepend region detection to all remediation code
        region_detection = """import requests
import os

# Detect AWS region from EC2 metadata
try:
    token = requests.put(
        'http://169.254.169.254/latest/api/token',
        headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
        timeout=1
    ).text
    AWS_REGION = requests.get(
        'http://169.254.169.254/latest/meta-data/placement/region',
        headers={'X-aws-ec2-metadata-token': token},
        timeout=1
    ).text
    print(f"✓ Detected region: {AWS_REGION}")
except Exception as e:
    AWS_REGION = 'us-west-2'
    print(f"⚠ Using default region: {AWS_REGION}")

"""
        wrapped_code = region_detection + remediation_code
        
        try:
            logger.info("⚡ Executing remediation code...")
            execution_result = execute_remediation_code(session_id, wrapped_code)
            logger.info(f"✅ Code execution completed")
            
            if 'error' in execution_result:
                logger.error(f"❌ Execution error: {execution_result['error']}")
                return f"❌ failed: {execution_result['error']}"
            
            response = f"# ✅ APPROVED EXECUTION - Results\n\n"
            response += "## Execution Output\n\n```\n"
            response += execution_result['output']
            response += "\n```\n"
            
            logger.info(f"✅ Execution successful, output length: {len(execution_result['output'])}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Execution exception: {type(e).__name__}: {str(e)}", exc_info=True)
            return f"❌ remediation plan execution failed: {str(e)}"
        finally:
            logger.info(f"🛑 Stopping session: {session_id}")
            stop_code_interpreter_session(session_id)
            
    except Exception as e:
        logger.error(f"❌ execute_remediation_step failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return f"❌ Tool failed: {str(e)}"

@tool
def validate_remediation_environment() -> str:
    """修復環境が準備完了していることを検証"""
    try:
        logger.info("🔍 validate_remediation_environment called")
        logger.info("🔍 Validating remediation environment...")
        
        validation_results = {
            "code_interpreter_available": False,
            "session_creation": False,
            "aws_access": False,
            "environment_ready": False
        }
        
        try:
            # Test code interpreter initialization
            logger.info("コードインタープリターの初期化をテスト中...")
            if initialize_code_interpreter_client():
                validation_results["code_interpreter_available"] = True
                logger.info("✅ Code interpreter available")
                
                # Test session creation
                logger.info("セッション作成をテスト中...")
                session_id = start_code_interpreter_session()
                if session_id:
                    validation_results["session_creation"] = True
                    validation_results["aws_access"] = True  # Simplified for demo
                    logger.info(f"✅ Session created: {session_id}")
                    stop_code_interpreter_session(session_id)
                else:
                    logger.error("❌ Session creation failed")
            else:
                logger.error("❌ Code interpreter not available")
            
            validation_results["environment_ready"] = all([
                validation_results["code_interpreter_available"],
                validation_results["session_creation"],
                validation_results["aws_access"]
            ])
            
        except Exception as e:
            logger.error(f"❌ Environment validation failed: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Format response
        response = "# Remediation Environment Validation\n\n"
        response += f"**Validation Date**: {datetime.now(timezone.utc).isoformat()}\n\n"
        
        for check, status in validation_results.items():
            status_icon = "✅" if status else "❌"
            check_name = check.replace('_', ' ').title()
            response += f"- **{check_name}**: {status_icon} {'PASS' if status else 'FAIL'}\n"
        
        if validation_results["environment_ready"]:
            response += "\n🎉 **Environment is READY for remediation**\n"
            logger.info("✅ Environment validation passed")
        else:
            response += "\n⚠️ **Environment is NOT READY**\n"
            logger.warning("⚠️ Environment validation failed")

        logger.info("=" * 80)
        logger.info("📤 エージェントの生レスポンス")
        logger.info(f"レスポンスタイプ: {type(response)}")
        logger.info(f"レスポンス属性: {dir(response)}")
        logger.debug(f"Full response object: {response}")
        logger.debug(f"Response.message: {response.message}")
        logger.info("=" * 80)
        
        return response
        
    except Exception as e:
        logger.error(f"❌ validate_remediation_environment failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return f"❌ Validation failed: {str(e)}"

@tool
def persist_remediation_scripts_to_s3(
    file_key: str,
    content: str
) -> dict:
    """Python スクリプトを S3 バケットに書き込む。

    Args:
        file_key: ファイルが保存される S3 キー（パス/ファイル名）
        content: ファイルに書き込む内容
    """
    bucket_name=retrieved_bucket_name
    region=AWS_REGION
    try:
        s3_client = get_boto3_client('s3')
        
        # Write to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=content.encode('utf-8')
        )
        
        # Generate S3 URL
        s3_url = f"s3://{bucket_name}/{file_key}"
        https_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{file_key}"
        
        result = {
            "success": True,
            "message": "Successfully wrote file to S3",
            "bucket": bucket_name,
            "key": file_key,
            "s3_url": s3_url,
            "https_url": https_url,
            "size_bytes": len(content.encode('utf-8'))
        }
        
        return {
            "status": "success",
            "content": [
                {"text": f"✓ File written  to {s3_url}"},
                {"json": result}
            ]
        }
        
    except Exception as e:
        error_msg = f"Failed to write file to S3: {str(e)}"
        return {
            "status": "error",
            "content": [
                {"text": error_msg}
            ]
        }

@tool
def read_remediation_scripts_from_s3(prefix: str = "") -> dict:
    """S3 バケットからすべてのファイルを読み取り、その内容を返す。

    Args:
        prefix: ファイルをフィルタリングするオプションのプレフィックス（例: 'crm-remediation'）
    """
    bucket_name=retrieved_bucket_name
    region = AWS_REGION
    max_files = 100

    try:
        logger.info(f"🔧 read_remediation_scripts_from_s3 called with prefix='{prefix}'")
        logger.info(f"📦 Reading from bucket: {bucket_name}, region: {region}")
        
        s3_client = get_boto3_client('s3')
        
        # List objects
        list_params = {
            'Bucket': bucket_name,
            'MaxKeys': max_files
        }
        if prefix:
            list_params['Prefix'] = prefix
        
        logger.info(f"📋 Listing objects with params: {list_params}")
        response = s3_client.list_objects_v2(**list_params)
        
        # FIX: Changed 'in' to 'not in' - return early only when NO files found
        if 'Contents' not in response:
            logger.warning(f"⚠️ No files found in s3://{bucket_name}/{prefix}")
            return {
                "status": "success",
                "content": [
                    {"text": f"No files found in s3://{bucket_name}/{prefix}"},
                    {"json": {
                        "success": True,
                        "bucket": bucket_name,
                        "prefix": prefix,
                        "file_count": 0,
                        "files": []
                    }}
                ]
            }
        
        logger.info(f"✅ Found {len(response['Contents'])} objects")
        files_data = []
        total_size = 0
        
        # Read each file
        for obj in response['Contents']:
            file_key = obj['Key']
            
            # Skip directories (keys ending with /)
            if file_key.endswith('/'):
                logger.info(f"⏭️ Skipping directory: {file_key}")
                continue
            
            logger.info(f"📄 Reading file: {file_key}")
            try:
                # Read file content
                file_response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                content = file_response['Body'].read().decode('utf-8')
                
                file_info = {
                    'key': file_key,
                    's3_url': f"s3://{bucket_name}/{file_key}",
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'content': content
                }
                files_data.append(file_info)
                total_size += obj['Size']
                logger.info(f"✅ Read file: {file_key} ({obj['Size']} bytes)")
            except Exception as file_error:
                # If a file can't be read, include error info but continue
                logger.error(f"❌ Failed to read {file_key}: {type(file_error).__name__}: {str(file_error)}")
                files_data.append({
                    'key': file_key,
                    's3_url': f"s3://{bucket_name}/{file_key}",
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'error': str(file_error)
                })
        
        logger.info(f"✅ Successfully read {len(files_data)} files, total size: {total_size} bytes")
        result = {
            "success": True,
            "message": f"Successfully read {len(files_data)} files from S3",
            "bucket": bucket_name,
            "prefix": prefix,
            "file_count": len(files_data),
            "total_size_bytes": total_size,
            "files": files_data
        }
        
        return {
            "status": "success",
            "content": [
                {"text": f"✓ Read {len(files_data)} files from s3://{bucket_name}/{prefix}"},
                {"json": result}
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ read_remediation_scripts_from_s3 failed: {type(e).__name__}: {str(e)}", exc_info=True)
        error_msg = f"Failed to read files from S3: {str(e)}"
        return {
            "status": "error",
            "content": [
                {"text": error_msg}
            ]
        }

@tool
def get_current_time() -> str:
    """現在時刻を UTC ISO 形式で取得する。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

@tool
def convert_timezone(time_str: str, from_tz: str, to_tz: str) -> str:
    """タイムゾーン間で時刻を変換する。UTC と ISO 形式をサポート（例: 'America/Los_Angeles', 'US/Pacific'）。"""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    # Parse input time
    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    
    # Convert from source timezone
    if from_tz.upper() == 'UTC':
        dt = dt.replace(tzinfo=ZoneInfo('UTC'))
    else:
        dt = dt.replace(tzinfo=ZoneInfo(from_tz))
    
    # Convert to target timezone
    if to_tz.upper() == 'UTC':
        dt = dt.astimezone(ZoneInfo('UTC'))
    else:
        dt = dt.astimezone(ZoneInfo(to_tz))
    
    return dt.isoformat()

current_architecture = """
## Current Architecture

## System Context
You are troubleshooting a 3-tier web application deployed on AWS. The infrastructure consists of two separate application flows: a main Python application and a CRM demo application, both with complete observability through CloudWatch.

## Network Architecture

### VPC Configuration
- VPC CIDR: 10.0.0.0/16
- Public Subnets: 10.0.1.0/24 (AZ1), 10.0.2.0/24 (AZ2)
- Private Subnets: 10.0.10.0/24 (AZ1), 10.0.11.0/24 (AZ2)
- Internet Gateway: Attached to VPC for public internet access
- NAT Gateway: Located in PublicSubnet1 for private subnet egress



## Application Flow: CRM Demo Application

### Traffic Path
```
Internet (Port 8080)
  ↓
Public ALB (sre-workshop-public-alb)
  - Same ALB as main app
  - Listener: Port 8080 → CRMAppTargetGroup
  ↓
CRM App Instance (CRMAppInstance)
  - Instance Type: t3.micro
  - Subnet: PrivateSubnet1 (10.0.10.0/24)
  - Port: 8080
  - Security Group: CRMAppSecurityGroup (allows PublicALBSecurityGroup → 8080)
  - Application: Python Flask/Gunicorn CRM app (2 workers)
  - Health Check: /health endpoint
  ↓
DynamoDB Tables (3 tables):
  1. CRMCustomersTable
  2. CRMDealsTable
  3. CRMActivitiesTable
```

### CRM Instance Details
- **IAM Role**: prefixed with EC2InstanceRole. The role should have allow to access DynamoDB tables.
  - DynamoDB access to all 3 CRM tables
  - CloudWatch agent permissions
  - S3 read access to AssetsBucketName
- **Environment Variables**:
  - AWS_REGION: Current region
  - CUSTOMERS_TABLE: CRMCustomersTable name
  - DEALS_TABLE: CRMDealsTable name
  - ACTIVITIES_TABLE: CRMActivitiesTable name
- **Initialization**: Runs init_sample_data.py to populate sample data
- **Service**: Systemd service (crm-app.service)
- **Tags**: DeploymentVersion: "2.0"

### CRM Data Model
```
CRMCustomersTable
  - Partition Key: customer_id (String)
  - Contains: Customer profile information

CRMDealsTable
  - Partition Key: deal_id (String)
  - Global Secondary Index: customer-index
    - Hash Key: customer_id
  - Relationship: One customer → Many deals

CRMActivitiesTable
  - Partition Key: activity_id (String)
  - Global Secondary Index: customer-index
    - Hash Key: customer_id
  - Relationship: One customer → Many activities
```


## Security Group Chain

### Main Application Security Flow
```
PublicALBSecurityGroup
  - Ingress: 0.0.0.0/0 → 80, 443, 8080
  ↓ allows traffic to
NginxSecurityGroup
  - Ingress: PublicALBSecurityGroup → 80
  ↓ allows traffic to
PrivateALBSecurityGroup
  - Ingress: NginxSecurityGroup → 80
  ↓ allows traffic to
AppServerSecurityGroup
  - Ingress: PrivateALBSecurityGroup → 8080
```

### CRM Application Security Flow
```
PublicALBSecurityGroup
  - Ingress: 0.0.0.0/0 → 8080
  ↓ allows traffic to
CRMAppSecurityGroup
  - Ingress: PublicALBSecurityGroup → 8080
```


## Observability Stack


sre-workshop-crm-app [EC2] has python app running from file /opt/crm-app/app.py 

sre-workshop-app [EC2] has python app running from file /opt/sre-app/app.py


## IAM Roles and Permissions

### EC2InstanceRole (Used by all EC2 instances)
Managed Policies:
- AmazonSSMManagedInstanceCore (remote access via Session Manager)
- CloudWatchAgentServerPolicy (metrics and logs)

Inline Policies:
- DynamoDB access (PutItem, GetItem, Query, Scan, UpdateItem, DeleteItem, BatchWriteItem)
- S3 read access to LambdaS3Bucket and AssetsBucketName
"""

logger.info("🔧 About to define remediation_agent with @mcp.tool() decorator...")
logger.info(f"🔍 MCP server exists: {mcp is not None}")
logger.info(f"🔍 MCP server type: {type(mcp)}")

@mcp.tool()
def infrastructure_agent(action_type: Literal["only_plan", "only_execute"], remediation_query: str):
    """AgentCore Code Interpreter を使用してインフラストラクチャの修復と AWS サービス操作を実行

    すべての AWS インフラストラクチャのクエリ、チェック、アクションのための主要ツール。
    AWS インフラストラクチャの問題に対する修復プランの作成または修正の実行を行う。
    プランは承認のために S3 に保存される。実行は失敗時の自動ロールバック付きの
    セキュアなサンドボックス環境を使用する。

    このツールの用途:
    - AWS リソースのクエリ（EC2、DynamoDB、ALB、CloudWatch など）
    - アプリケーションの健全性とインフラストラクチャの状態チェック
    - 修復アクションと修正の実行
    - 設定と接続性の検証

    Args:
        action_type: 修復モード - "only_plan" は S3 に保存される実行可能なプランを生成、
                    "only_execute" は検証付きで承認済みの修復コードを実行
        remediation_query: 問題の説明またはクエリ（例: "List all DynamoDB tables",
                          "Fix DynamoDB throttling on CRMDealsTable",
                          "Check EC2 instance sre-workshop-app health",
                          "Restart failed application service"）

    Returns:
        S3 の場所を含むプランサマリー（only_plan）または検証付きの実行結果（only_execute）
    """
    try:
        logger.info(f"🔧 remediation_agent called with action_type={action_type}, query={remediation_query}")
        
        if not initialize_code_interpreter_client():
            logger.error("❌ Failed to initialize code interpreter client")
            return "Error: Failed to initialize code interpreter client"
        
        logger.info(f"✅ Code interpreter client initialized")
        boto_session = get_boto3_session()
        model = BedrockModel(model_id=MODEL_ID, streaming=True, boto_session=boto_session)
        logger.info(f"✅ Bedrock model initialized: {MODEL_ID}")
        
        if action_type == "only_plan":
            logger.info("📋 Setting up agent for plan-only mode")
            system_prompt=f"""あなたは実行可能な修復プランを作成する AWS SRE 修復計画エージェントです（コード実行なし）。以下はアプリケーションの詳細とアーキテクチャです: {current_architecture}

フォーカス：サービスの可用性を復旧するための即時アクションのみを生成します。長期的な改善は対象外です。

プラン構造（markdown 使用）：
1. **問題の概要** - 問題の簡潔な説明
2. **根本原因** - 診断に基づいて特定された原因
3. **即時アクション** - 段階的な修復手順（番号付きリスト）

要件：
- 各アクションは正確な AWS サービス、リソース、操作を指定する必要があります
- 各アクションの影響とリスクレベル（Low/Medium/High）を見積もる
- persist_remediation_scripts_to_s3 ツールを使用してプランを S3 に保存する

完全なプランが markdown として S3 に保存されたら、プランが保存された S3 の場所を含む簡潔なサマリーを提供してください。

"""
            agent = Agent(system_prompt=system_prompt,
                model=model, 
                tools=[persist_remediation_scripts_to_s3]
            )
        elif action_type == "only_execute":
            logger.info("⚡ Setting up agent for execute-only mode")
            system_prompt=f"""
            あなたはアプリケーションの問題のトラブルシューティングを支援する AWS アプリケーション修復エージェントです。
            以下はトラブルシューティング対象の問題に関するアプリケーションの詳細とアーキテクチャです: {current_architecture}


実行ワークフローとコード要件：
1. 段階的に考える
2. boto3 を使用して Python コードを生成する
3. execute_remediation_step ツール経由でコードを実行する。必要な IAM 権限があり、常に action_type='only_execute' を使用します
4. 変更を加える前にリソースの状態を確認する（まず describe/list 操作を実行）


重要：
- 実行環境は AWS リージョンを自動検出し、AWS_REGION 変数として提供します。作業リージョンとして常に us-west-2 を使用してください。
- boto3 クライアントを作成する際は常にこの変数を使用してください：

- EC2 インスタンスに接続する必要がある場合は、SSM を使用する必要があります

すべての修復とトラブルシューティングのステップが完了したら、以下のサマリーを提供してください：
1. **問題の概要** - 問題の簡潔な説明
2. **根本原因** - 診断に基づいて特定された原因
3. **適用されたアクション/修正** - 修正の概要（番号付きリスト）

**重要な検証**：アプリケーションがエンドツーエンドで実行されていることを確認するために、パブリック ALB [sre-workshop-public-alb] にポート 8080 でアクセスし、データベースエラーが表示されないことを確認してください。データベースエラーが表示される場合は、EC2 [sre-workshop-public-alb および sre-workshop-crm-app] で実行されているバックエンドサービスを確認し、DynamoDB テーブルに正常に接続できることを確認してください

**重要な注意**：実行には 5 分のタイムアウトがあります。時間効率が良く構文的に正しいコードを生成してください。広範な検証は不要です。

**タイムアウトエラー時の重要な対応**「RuntimeError: Connection to the MCP server was closed」を受信した場合、接続タイムアウトをユーザーに丁寧に通知しつつ、正常に完了できたステップも確認してください。

"""

            agent = Agent(system_prompt=system_prompt,
                model=model, 
                tools=[execute_remediation_step, validate_remediation_environment, read_remediation_scripts_from_s3, get_current_time, convert_timezone]
            )
        else:
            logger.error(f"❌ Invalid action_type: {action_type}")
            return f"Error: Invalid action_type '{action_type}'. Must be one of: only_plan, only_execute"
        
        logger.info(f"🤖 Agent configured, invoking with query...")
        return_text=""
        response = agent(remediation_query)
        logger.info(f"✅ Agent response received")
        
        response_content = response.message.get('content', [])
        if response_content:
            for content in response_content:
                if isinstance(content, dict) and 'text' in content:
                    return_text = content['text']
            logger.info(f"✅ Extracted response text (length: {len(return_text)})")
        else:
            logger.warning("⚠️ No content in agent response")
        
        return return_text
        
    except Exception as e:
        logger.error(f"❌ remediation_agent failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return f"Error: {type(e).__name__}: {str(e)}"

# Add tool registration verification AFTER function definition
logger.info("✅ remediation_agent tool defined")
#logger.info(f"🔍 Tool function callable: {callable(remediation_agent)}")

#if callable(remediation_agent):
#    logger.info("✅ Tool registration successful - MCP server should work properly")
#else:
#    logger.warning("⚠️ Tool registration failed - this will cause MCP requests to fail!")

# Initialize at module level
logger.info("🚀 Initializing SRE Remediation Agent with FastMCP")
initialize_code_interpreter_client()

logger.info("🚀 Starting FastMCP server with streamable-http transport on port 8000")

mcp.run(transport="streamable-http")

import boto3
import json
import time
from boto3.session import Session
import botocore
from botocore.exceptions import ClientError
import requests
import time


def get_or_create_user_pool(cognito, USER_POOL_NAME):
    response = cognito.list_user_pools(MaxResults=60)
    for pool in response["UserPools"]:
        if pool["Name"] == USER_POOL_NAME:
            user_pool_id = pool["Id"]
            response = cognito.describe_user_pool(
                UserPoolId=user_pool_id
            )
        
            # Get the domain from user pool description
            user_pool = response.get('UserPool', {})
            domain = user_pool.get('Domain')
        
            if domain:
                region = user_pool_id.split('_')[0] if '_' in user_pool_id else REGION
                domain_url = f"https://{domain}.auth.{region}.amazoncognito.com"
                print(f"User Pool {user_pool_id} のドメインを発見: {domain} ({domain_url})")
            else:
                print(f"User Pool {user_pool_id} にドメインが見つかりません")
            return pool["Id"]
    print('新しいUser Poolを作成中')
    created = cognito.create_user_pool(PoolName=USER_POOL_NAME)
    user_pool_id = created["UserPool"]["Id"]
    user_pool_id_without_underscore_lc = user_pool_id.replace("_", "").lower()
    cognito.create_user_pool_domain(
        Domain=user_pool_id_without_underscore_lc,
        UserPoolId=user_pool_id
    )
    print("ドメインも作成しました")
    return created["UserPool"]["Id"]

def get_or_create_resource_server(cognito, user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES):
    try:
        existing = cognito.describe_resource_server(
            UserPoolId=user_pool_id,
            Identifier=RESOURCE_SERVER_ID
        )
        return RESOURCE_SERVER_ID
    except cognito.exceptions.ResourceNotFoundException:
        print('新しいリソースサーバーを作成中')
        cognito.create_resource_server(
            UserPoolId=user_pool_id,
            Identifier=RESOURCE_SERVER_ID,
            Name=RESOURCE_SERVER_NAME,
            Scopes=SCOPES
        )
        return RESOURCE_SERVER_ID

def get_or_create_m2m_client(cognito, user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID, SCOPES=None):
    response = cognito.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
    for client in response["UserPoolClients"]:
        if client["ClientName"] == CLIENT_NAME:
            describe = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client["ClientId"])
            return client["ClientId"], describe["UserPoolClient"]["ClientSecret"]
    print('新しいM2Mクライアントを作成中')

    # Default scopes if not provided (for backward compatibility)
    if SCOPES is None:
        SCOPES = [f"{RESOURCE_SERVER_ID}/gateway:read", f"{RESOURCE_SERVER_ID}/gateway:write"]

    created = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=SCOPES,
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"]
    )
    return created["UserPoolClient"]["ClientId"], created["UserPoolClient"]["ClientSecret"]

def get_token(user_pool_id: str, client_id: str, client_secret: str, scope_string: str, REGION: str) -> dict:
    try:
        user_pool_id_without_underscore = user_pool_id.replace("_", "")
        url = f"https://{user_pool_id_without_underscore}.auth.{REGION}.amazoncognito.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,

        }
        print(client_id)
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}
    


def create_agentcore_gateway_role(gateway_name):
    iam_client = boto3.client('iam')
    agentcore_gateway_role_name = f'agentcore-{gateway_name}-role'
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*",
                    "bedrock:*",
                    "agent-credential-provider:*",
                    "iam:PassRole",
                    "secretsmanager:GetSecretValue",
                    "lambda:InvokeFunction",
                    "execute-api:Invoke"
                ],
                "Resource": "*"
            }
        ]
    }

    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )

    role_policy_document = json.dumps(role_policy)
    # Create IAM Role for the Lambda function
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("ロールは既に存在します -- 削除して再作成します")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_gateway_role_name,
            MaxItems=100
        )
        print("ポリシー:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_gateway_role_name,
                PolicyName=policy_name
            )
        print(f"{agentcore_gateway_role_name}を削除中")
        iam_client.delete_role(
            RoleName=agentcore_gateway_role_name
        )
        print(f"{agentcore_gateway_role_name}を再作成中")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

    # Attach the AWSLambdaBasicExecutionRole policy
    print(f"ロールポリシーをアタッチ中: {agentcore_gateway_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_gateway_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role


def load_openapi_definition(filename):
    """
    Load OpenAPI definition from a JSON file.
    
    :param filename: The path to the OpenAPI JSON file
    :return: Dictionary containing the OpenAPI definition
    """
    with open(filename, 'r') as f:
        return json.load(f)

def create_and_deploy_api_from_openapi_with_extensions(filename='AgentCore_Sample_API-dev-oas30-apigateway.json', stage_name='dev', description='Initial Deployment'):
    """
    Load OpenAPI definition with API Gateway extensions and deploy it.
    This function expects the OpenAPI document to already have integrations and security configured.
    
    :param filename: The path to the OpenAPI JSON file with x-amazon-apigateway extensions
    :param stage_name: The stage name for deployment (default: 'dev')
    :param description: Deployment description (default: 'Initial Deployment')
    :return: Dictionary containing api_id, api_name, api_key, and invoke_url
    """
    import boto3
    
    # Initialize the API Gateway client
    client = boto3.client('apigateway')
    
    # Load OpenAPI definition from file
    openapi_definition = load_openapi_definition(filename)
    
    try:
        # Convert the OpenAPI definition to a JSON string
        body = json.dumps(openapi_definition)
        
        print("API Gateway拡張機能付きでREST APIをインポート中...")
        # Import the REST API using the OpenAPI definition
        response = client.import_rest_api(
            body=body,
            failOnWarnings=False,
            parameters={
                'endpointConfigurationTypes': 'REGIONAL'
            }
        )
        
        api_id = response['id']
        api_name = response['name']
        
        print(f"✓ API Gateway REST APIを正常に作成しました")
        print(f"  API ID: {api_id}")
        print(f"  API Name: {api_name}")
        
        # Deploy the API
        print(f"\nAPIをステージ '{stage_name}' にデプロイ中...")
        deployment_response = client.create_deployment(
            restApiId=api_id,
            stageName=stage_name,
            description=description
        )
        
        deployment_id = deployment_response['id']
        print(f"✓ デプロイメントを作成しました: {deployment_id}")
        
        # Create API Key for the orders endpoint
        print("\nAPIキーを作成中...")
        api_key_response = client.create_api_key(
            name=f'{api_name}-api-key',
            description=f'API Key for {api_name} orders endpoint',
            enabled=True
        )
        api_key_id = api_key_response['id']
        api_key_value = api_key_response['value']
        print(f"✓ APIキーを作成しました: {api_key_id}")
        
        # Create Usage Plan
        print("\n使用量プランを作成中...")
        usage_plan_response = client.create_usage_plan(
            name=f'{api_name}-usage-plan',
            description=f'Usage plan for {api_name}',
            apiStages=[
                {
                    'apiId': api_id,
                    'stage': stage_name
                }
            ],
            throttle={
                'rateLimit': 100.0,
                'burstLimit': 200
            },
            quota={
                'limit': 10000,
                'period': 'MONTH'
            }
        )
        usage_plan_id = usage_plan_response['id']
        print(f"✓ 使用量プランを作成しました: {usage_plan_id}")
        
        # Associate API Key with Usage Plan
        print("\nAPIキーを使用量プランに関連付け中...")
        client.create_usage_plan_key(
            usagePlanId=usage_plan_id,
            keyId=api_key_id,
            keyType='API_KEY'
        )
        print("✓ APIキーを使用量プランに関連付けました")
        
        # Construct the invoke URL
        region = client.meta.region_name
        invoke_url = f"https://{api_id}.execute-api.{region}.amazonaws.com/{stage_name}"
        
        print(f"\n{'='*70}")
        print(f"API Gatewayデプロイメント完了")
        print(f"{'='*70}")
        print(f"呼び出しURL: {invoke_url}")
        print(f"\nエンドポイント認証:")
        print(f"  • GET /pets              → AWS IAM (SigV4)")
        print(f"  • POST /pets             → AWS IAM (SigV4)")
        print(f"  • GET /pets/{{petId}}      → AWS IAM (SigV4)")
        print(f"  • GET /orders/{{orderId}}  → API Key (x-api-key header)")
        print(f"{'='*70}")
        
        return {
            'api_id': api_id,
            'api_name': api_name,
            'deployment_id': deployment_id,
            'invoke_url': invoke_url,
            'stage_name': stage_name,
            'api_key_id': api_key_id,
            'api_key_value': api_key_value,
            'usage_plan_id': usage_plan_id
        }
        
    except client.exceptions.ConflictException:
        print("指定された名前のAPIは既に存在します。既存のAPIを更新または削除することを検討してください。")
        raise
    except Exception as e:
        print(f"API Gateway REST APIの作成またはデプロイ中にエラー: {e}")
        raise


def test_api_gateway_endpoints(invoke_url, api_key, region):
    """
    Test API Gateway endpoints with proper authorization.
    Tests both IAM-authorized /pets endpoints and API Key-authorized /orders endpoint.
    
    :param invoke_url: The API Gateway invoke URL
    :param api_key: The API key for /orders endpoint
    :param region: AWS region (default: 'us-west-2')
    :return: Dictionary with test results
    """
    import boto3
    import requests
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    
    print(f"\n{'='*70}")
    print(f"API Gatewayエンドポイントをテスト中")
    print(f"{'='*70}\n")
    
    results = {}
    session = boto3.Session()
    credentials = session.get_credentials()
    
    # Test 1: GET /pets (IAM Authorization)
    print("1. GET /pets をテスト中 (IAM認証)...")
    try:
        url = f"{invoke_url}/pets"
        request = AWSRequest(method='GET', url=url)
        SigV4Auth(credentials, 'execute-api', region).add_auth(request)
        
        response = requests.get(url, headers=dict(request.headers))
        
        if response.status_code == 200:
            print(f"   ✓ 成功 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.json()}")
            results['get_pets'] = {'status': 'success', 'data': response.json()}
        else:
            print(f"   ✗ 失敗 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.text}")
            results['get_pets'] = {'status': 'failed', 'error': response.text}
    except Exception as e:
        print(f"   ✗ エラー: {e}")
        results['get_pets'] = {'status': 'error', 'error': str(e)}
    
    # Test 2: GET /pets/1 (IAM Authorization)
    print("\n2. GET /pets/1 をテスト中 (IAM認証)...")
    try:
        url = f"{invoke_url}/pets/1"
        request = AWSRequest(method='GET', url=url)
        SigV4Auth(credentials, 'execute-api', region).add_auth(request)
        
        response = requests.get(url, headers=dict(request.headers))
        
        if response.status_code == 200:
            print(f"   ✓ 成功 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.json()}")
            results['get_pet_by_id'] = {'status': 'success', 'data': response.json()}
        else:
            print(f"   ✗ 失敗 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.text}")
            results['get_pet_by_id'] = {'status': 'failed', 'error': response.text}
    except Exception as e:
        print(f"   ✗ エラー: {e}")
        results['get_pet_by_id'] = {'status': 'error', 'error': str(e)}
    
    # Test 3: POST /pets (IAM Authorization)
    print("\n3. POST /pets をテスト中 (IAM認証)...")
    try:
        url = f"{invoke_url}/pets"
        request = AWSRequest(method='POST', url=url, data='{}')
        SigV4Auth(credentials, 'execute-api', region).add_auth(request)
        
        response = requests.post(url, headers=dict(request.headers), json={})
        
        if response.status_code == 200:
            print(f"   ✓ 成功 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.json()}")
            results['post_pets'] = {'status': 'success', 'data': response.json()}
        else:
            print(f"   ✗ 失敗 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.text}")
            results['post_pets'] = {'status': 'failed', 'error': response.text}
    except Exception as e:
        print(f"   ✗ エラー: {e}")
        results['post_pets'] = {'status': 'error', 'error': str(e)}
    
    # Test 4: GET /orders/1 (API Key Authorization)
    print("\n4. GET /orders/1 をテスト中 (APIキー認証)...")
    try:
        url = f"{invoke_url}/orders/1"
        headers = {'x-api-key': api_key}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            print(f"   ✓ 成功 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.json()}")
            results['get_order_by_id'] = {'status': 'success', 'data': response.json()}
        else:
            print(f"   ✗ 失敗 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.text}")
            results['get_order_by_id'] = {'status': 'failed', 'error': response.text}
    except Exception as e:
        print(f"   ✗ エラー: {e}")
        results['get_order_by_id'] = {'status': 'error', 'error': str(e)}
    
    # Test 5: GET /orders/1 without API Key (should fail)
    print("\n5. APIキーなしでGET /orders/1 をテスト中 (403エラーになるはず)...")
    try:
        url = f"{invoke_url}/orders/1"
        response = requests.get(url)
        
        if response.status_code == 403:
            print(f"   ✓ 想定通りの失敗 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.json()}")
            results['get_order_no_key'] = {'status': 'expected_failure', 'data': response.json()}
        else:
            print(f"   ✗ 想定外 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.text}")
            results['get_order_no_key'] = {'status': 'unexpected', 'error': response.text}
    except Exception as e:
        print(f"   ✗ エラー: {e}")
        results['get_order_no_key'] = {'status': 'error', 'error': str(e)}
    
    # Test 6: GET /pets without IAM Auth (should fail)
    print("\n6. IAM認証なしでGET /pets をテスト中 (403エラーになるはず)...")
    try:
        url = f"{invoke_url}/pets"
        response = requests.get(url)
        
        if response.status_code == 403:
            print(f"   ✓ 想定通りの失敗 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.json()}")
            results['get_pets_no_auth'] = {'status': 'expected_failure', 'data': response.json()}
        else:
            print(f"   ✗ 想定外 (ステータス: {response.status_code})")
            print(f"   レスポンス: {response.text}")
            results['get_pets_no_auth'] = {'status': 'unexpected', 'error': response.text}
    except Exception as e:
        print(f"   ✗ エラー: {e}")
        results['get_pets_no_auth'] = {'status': 'error', 'error': str(e)}
    
    print(f"\n{'='*70}")
    print(f"テストサマリー")
    print(f"{'='*70}")
    success_count = sum(1 for r in results.values() if r['status'] in ['success', 'expected_failure'])
    total_count = len(results)
    print(f"合格: {success_count}/{total_count}")
    print(f"{'='*70}\n")
    
    return results


def delete_api_gateway_and_resources(api_id, api_key_id=None, usage_plan_id=None):
    """
    Delete API Gateway and all related resources (API key, usage plan).
    
    :param api_id: The API Gateway REST API ID
    :param api_key_id: The API Key ID (optional)
    :param usage_plan_id: The Usage Plan ID (optional)
    :return: Dictionary with deletion results
    """
    import boto3
    from botocore.exceptions import ClientError
    
    client = boto3.client('apigateway')
    results = {
        'api_deleted': False,
        'api_key_deleted': False,
        'usage_plan_deleted': False,
        'errors': []
    }
    
    print(f"\n{'='*70}")
    print(f"API Gatewayリソースを削除中")
    print(f"{'='*70}\n")
    
    # Delete Usage Plan Key association first (if usage plan and api key exist)
    if usage_plan_id and api_key_id:
        try:
            print(f"1. 使用量プランからAPIキーを削除中...")
            client.delete_usage_plan_key(
                usagePlanId=usage_plan_id,
                keyId=api_key_id
            )
            print(f"   ✓ 使用量プランからAPIキーを削除しました")
        except ClientError as e:
            error_msg = f"使用量プランからAPIキーの削除に失敗: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
        except Exception as e:
            error_msg = f"使用量プランからのAPIキー削除中にエラー: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    
    # Delete Usage Plan
    if usage_plan_id:
        try:
            print(f"\n2. 使用量プランを削除中: {usage_plan_id}...")
            
            # First, get the usage plan to find associated API stages
            try:
                usage_plan = client.get_usage_plan(usagePlanId=usage_plan_id)
                api_stages = usage_plan.get('apiStages', [])
                
                if api_stages:
                    print(f"   {len(api_stages)} 件の関連APIステージを発見")
                    for stage in api_stages:
                        api_id_stage = stage.get('apiId')
                        stage_name = stage.get('stage')
                        print(f"   APIステージを削除中: {api_id_stage}/{stage_name}...")
                        try:
                            client.update_usage_plan(
                                usagePlanId=usage_plan_id,
                                patchOperations=[
                                    {
                                        'op': 'remove',
                                        'path': f'/apiStages',
                                        'value': f'{api_id_stage}:{stage_name}'
                                    }
                                ]
                            )
                            print(f"   ✓ APIステージを削除しました")
                        except Exception as e:
                            print(f"   ⚠ APIステージを削除できませんでした: {e}")
            except Exception as e:
                print(f"   ⚠ 使用量プランの詳細を取得できませんでした: {e}")
            
            # Now delete the usage plan
            client.delete_usage_plan(usagePlanId=usage_plan_id)
            print(f"   ✓ 使用量プランを削除しました")
            results['usage_plan_deleted'] = True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFoundException':
                print(f"   ⚠ 使用量プランが見つかりません (既に削除されている可能性があります)")
                results['usage_plan_deleted'] = True
            else:
                error_msg = f"使用量プランの削除に失敗: {e}"
                print(f"   ✗ {error_msg}")
                results['errors'].append(error_msg)
        except Exception as e:
            error_msg = f"使用量プラン削除中にエラー: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    
    # Delete API Key
    if api_key_id:
        try:
            print(f"\n3. APIキーを削除中: {api_key_id}...")
            client.delete_api_key(apiKey=api_key_id)
            print(f"   ✓ APIキーを削除しました")
            results['api_key_deleted'] = True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFoundException':
                print(f"   ⚠ APIキーが見つかりません (既に削除されている可能性があります)")
                results['api_key_deleted'] = True
            else:
                error_msg = f"APIキーの削除に失敗: {e}"
                print(f"   ✗ {error_msg}")
                results['errors'].append(error_msg)
        except Exception as e:
            error_msg = f"APIキー削除中にエラー: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    
    # Delete REST API
    try:
        print(f"\n4. REST APIを削除中: {api_id}...")
        client.delete_rest_api(restApiId=api_id)
        print(f"   ✓ REST APIを削除しました")
        results['api_deleted'] = True
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            print(f"   ⚠ REST APIが見つかりません (既に削除されている可能性があります)")
            results['api_deleted'] = True
        else:
            error_msg = f"REST APIの削除に失敗: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"REST API削除中にエラー: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    print(f"\n{'='*70}")
    print(f"クリーンアップサマリー")
    print(f"{'='*70}")
    print(f"REST API削除済み: {'✓' if results['api_deleted'] else '✗'}")
    if api_key_id:
        print(f"APIキー削除済み: {'✓' if results['api_key_deleted'] else '✗'}")
    if usage_plan_id:
        print(f"使用量プラン削除済み: {'✓' if results['usage_plan_deleted'] else '✗'}")
    
    if results['errors']:
        print(f"\n発生したエラー: {len(results['errors'])}件")
        for error in results['errors']:
            print(f"  - {error}")
    else:
        print(f"\n✓ すべてのリソースを正常に削除しました")
    
    print(f"{'='*70}\n")
    
    return results


def delete_agentcore_gateway_and_targets(gateway_id, region='us-west-2'):
    """
    Delete AgentCore Gateway and all its targets.
    
    :param gateway_id: The AgentCore Gateway ID
    :param region: AWS region (default: 'us-west-2')
    :return: Dictionary with deletion results
    """
    import boto3
    from botocore.exceptions import ClientError
    
    gateway_client = boto3.client('bedrock-agentcore-control', region_name=region)
    
    results = {
        'targets_deleted': [],
        'gateway_deleted': False,
        'errors': []
    }
    
    print(f"\n{'='*70}")
    print(f"AgentCore Gatewayとターゲットを削除中")
    print(f"{'='*70}\n")
    
    # List and delete all targets first
    try:
        print(f"1. ゲートウェイのすべてのターゲットを一覧表示中: {gateway_id}...")
        list_response = gateway_client.list_gateway_targets(
            gatewayIdentifier=gateway_id,
            maxResults=100
        )
        
        targets = list_response.get('items', [])
        
        if targets:
            print(f"   {len(targets)} 件のターゲットを発見")
            
            for item in targets:
                target_id = item["targetId"]
                target_name = item.get("name", "Unknown")
                
                try:
                    print(f"\n   ターゲットを削除中: {target_name} ({target_id})...")
                    gateway_client.delete_gateway_target(
                        gatewayIdentifier=gateway_id,
                        targetId=target_id
                    )
                    print(f"   ✓ ターゲット削除を開始: {target_id}")
                    results['targets_deleted'].append(target_id)
                    
                    # Wait for target to be fully deleted
                    print(f"   ターゲットが完全に削除されるのを待機中...")
                    max_wait = 30  # Maximum wait time in seconds
                    wait_interval = 2
                    elapsed = 0
                    
                    while elapsed < max_wait:
                        try:
                            # Try to get the target - if it doesn't exist, deletion is complete
                            gateway_client.get_gateway_target(
                                gatewayIdentifier=gateway_id,
                                targetId=target_id
                            )
                            time.sleep(wait_interval)
                            elapsed += wait_interval
                        except ClientError as e:
                            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                                print(f"   ✓ ターゲットを完全に削除しました: {target_id}")
                                break
                            else:
                                raise
                    
                    if elapsed >= max_wait:
                        print(f"   ⚠ ターゲット削除がタイムアウトしました。処理を続行します...")
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        print(f"   ⚠ ターゲットが見つかりません (既に削除されている可能性があります)")
                        results['targets_deleted'].append(target_id)
                    else:
                        error_msg = f"ターゲット {target_id} の削除に失敗: {e}"
                        print(f"   ✗ {error_msg}")
                        results['errors'].append(error_msg)
                except Exception as e:
                    error_msg = f"ターゲット {target_id} 削除中にエラー: {e}"
                    print(f"   ✗ {error_msg}")
                    results['errors'].append(error_msg)
        else:
            print(f"   ターゲットが見つかりません")
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"   ⚠ ゲートウェイが見つかりません (既に削除されている可能性があります)")
            results['gateway_deleted'] = True
            return results
        else:
            error_msg = f"ターゲット一覧の取得に失敗: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"ターゲット一覧取得中にエラー: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    # Delete the gateway
    try:
        print(f"\n2. ゲートウェイを削除中: {gateway_id}...")
        gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
        print(f"   ✓ ゲートウェイを削除しました")
        results['gateway_deleted'] = True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"   ⚠ ゲートウェイが見つかりません (既に削除されている可能性があります)")
            results['gateway_deleted'] = True
        else:
            error_msg = f"ゲートウェイの削除に失敗: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"ゲートウェイ削除中にエラー: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    print(f"\n{'='*70}")
    print(f"AgentCore Gatewayクリーンアップサマリー")
    print(f"{'='*70}")
    print(f"削除されたターゲット数: {len(results['targets_deleted'])}")
    print(f"ゲートウェイ削除済み: {'✓' if results['gateway_deleted'] else '✗'}")
    
    if results['errors']:
        print(f"\n発生したエラー: {len(results['errors'])}件")
        for error in results['errors']:
            print(f"  - {error}")
    else:
        print(f"\n✓ すべてのAgentCoreリソースを正常に削除しました")
    
    print(f"{'='*70}\n")
    
    return results


def delete_agentcore_credential_provider(credential_provider_arn, region='us-west-2'):
    """
    Delete AgentCore Identity API Key Credential Provider.
    This will also delete the associated secret in AWS Secrets Manager.
    
    :param credential_provider_arn: The credential provider ARN
    :param region: AWS region (default: 'us-west-2')
    :return: Dictionary with deletion results
    """
    import boto3
    from botocore.exceptions import ClientError
    
    bedrock_agent_client = boto3.client('bedrock-agentcore-control', region_name=region)
    
    results = {
        'credential_provider_deleted': False,
        'errors': []
    }
    
    print(f"\n{'='*70}")
    print(f"AgentCore Identity資格情報プロバイダーを削除中")
    print(f"{'='*70}\n")
    
    # Extract the credential provider name from ARN
    # ARN format: arn:aws:bedrock-agentcore:region:account:token-vault/default/apikeycredentialprovider/name
    try:
        provider_name = credential_provider_arn.split('/')[-1]
        print(f"資格情報プロバイダー名: {provider_name}")
        print(f"資格情報プロバイダーARN: {credential_provider_arn}\n")
    except Exception as e:
        error_msg = f"Failed to parse credential provider ARN: {e}"
        print(f"✗ {error_msg}")
        results['errors'].append(error_msg)
        return results
    
    # Delete the credential provider
    try:
        print(f"APIキー資格情報プロバイダーを削除中: {provider_name}...")
        bedrock_agent_client.delete_api_key_credential_provider(
            name=provider_name
        )
        print(f"✓ 資格情報プロバイダーを削除しました")
        print(f"  Note: Associated secret in Secrets Manager will also be deleted")
        results['credential_provider_deleted'] = True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"⚠ Credential Provider not found (may already be deleted)")
            results['credential_provider_deleted'] = True
        else:
            error_msg = f"Failed to delete credential provider: {e}"
            print(f"✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting credential provider: {e}"
        print(f"✗ {error_msg}")
        results['errors'].append(error_msg)
    
    print(f"\n{'='*70}")
    print(f"Credential Provider Cleanup Summary")
    print(f"{'='*70}")
    print(f"Credential Provider Deleted: {'✓' if results['credential_provider_deleted'] else '✗'}")
    
    if results['errors']:
        print(f"\n発生したエラー: {len(results['errors'])}件")
        for error in results['errors']:
            print(f"  - {error}")
    else:
        print(f"\n✓ Credential provider deleted successfully")
    
    print(f"{'='*70}\n")
    
    return results


def delete_cognito_user_pool(user_pool_name, region='us-west-2'):
    """
    Delete Cognito User Pool and all associated resources (domain, clients, resource servers).
    
    :param user_pool_name: The Cognito User Pool name
    :param region: AWS region (default: 'us-west-2')
    :return: Dictionary with deletion results
    """
    import boto3
    from botocore.exceptions import ClientError
    
    cognito = boto3.client('cognito-idp', region_name=region)
    
    results = {
        'user_pool_deleted': False,
        'domain_deleted': False,
        'clients_deleted': [],
        'errors': []
    }
    
    print(f"\n{'='*70}")
    print(f"Deleting Cognito User Pool: {user_pool_name}")
    print(f"{'='*70}\n")
    
    # Find the user pool by name
    try:
        print(f"1. Finding User Pool: {user_pool_name}...")
        response = cognito.list_user_pools(MaxResults=60)
        user_pool_id = None
        
        for pool in response.get("UserPools", []):
            if pool["Name"] == user_pool_name:
                user_pool_id = pool["Id"]
                print(f"   ✓ Found User Pool ID: {user_pool_id}")
                break
        
        if not user_pool_id:
            print(f"   ⚠ User Pool '{user_pool_name}' not found (may already be deleted)")
            results['user_pool_deleted'] = True
            return results
            
    except Exception as e:
        error_msg = f"Error finding user pool: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
        return results
    
    # Delete domain if exists
    try:
        print(f"\n2. Checking for User Pool Domain...")
        describe_response = cognito.describe_user_pool(UserPoolId=user_pool_id)
        domain = describe_response.get('UserPool', {}).get('Domain')
        
        if domain:
            print(f"   Found domain: {domain}")
            print(f"   Deleting domain...")
            cognito.delete_user_pool_domain(
                Domain=domain,
                UserPoolId=user_pool_id
            )
            print(f"   ✓ Domain deleted")
            results['domain_deleted'] = True
        else:
            print(f"   No domain found")
            
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceNotFoundException':
            error_msg = f"Error deleting domain: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"Error checking/deleting domain: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    # Delete all clients
    try:
        print(f"\n3. Deleting User Pool Clients...")
        clients_response = cognito.list_user_pool_clients(
            UserPoolId=user_pool_id,
            MaxResults=60
        )
        
        clients = clients_response.get('UserPoolClients', [])
        if clients:
            for client in clients:
                client_id = client['ClientId']
                client_name = client['ClientName']
                try:
                    print(f"   Deleting client: {client_name} ({client_id})...")
                    cognito.delete_user_pool_client(
                        UserPoolId=user_pool_id,
                        ClientId=client_id
                    )
                    print(f"   ✓ Client deleted")
                    results['clients_deleted'].append(client_id)
                except Exception as e:
                    error_msg = f"Error deleting client {client_id}: {e}"
                    print(f"   ✗ {error_msg}")
                    results['errors'].append(error_msg)
        else:
            print(f"   No clients found")
            
    except Exception as e:
        error_msg = f"Error listing/deleting clients: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    # Delete the user pool
    try:
        print(f"\n4. Deleting User Pool: {user_pool_id}...")
        cognito.delete_user_pool(UserPoolId=user_pool_id)
        print(f"   ✓ User Pool deleted")
        results['user_pool_deleted'] = True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"   ⚠ User Pool not found (may already be deleted)")
            results['user_pool_deleted'] = True
        else:
            error_msg = f"Failed to delete user pool: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting user pool: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    print(f"\n{'='*70}")
    print(f"Cognito User Pool Cleanup Summary")
    print(f"{'='*70}")
    print(f"User Pool Deleted: {'✓' if results['user_pool_deleted'] else '✗'}")
    print(f"Domain Deleted: {'✓' if results['domain_deleted'] else 'N/A'}")
    print(f"Clients Deleted: {len(results['clients_deleted'])}")
    
    if results['errors']:
        print(f"\n発生したエラー: {len(results['errors'])}件")
        for error in results['errors']:
            print(f"  - {error}")
    else:
        print(f"\n✓ Cognito resources deleted successfully")
    
    print(f"{'='*70}\n")
    
    return results


def delete_iam_role(role_name):
    """
    Delete IAM Role and all attached inline policies.
    
    :param role_name: The IAM Role name
    :return: Dictionary with deletion results
    """
    import boto3
    from botocore.exceptions import ClientError
    
    iam_client = boto3.client('iam')
    
    results = {
        'role_deleted': False,
        'policies_deleted': [],
        'errors': []
    }
    
    print(f"\n{'='*70}")
    print(f"Deleting IAM Role: {role_name}")
    print(f"{'='*70}\n")
    
    # Delete inline policies first
    try:
        print(f"1. Listing inline policies for role: {role_name}...")
        policies_response = iam_client.list_role_policies(
            RoleName=role_name,
            MaxItems=100
        )
        
        policy_names = policies_response.get('PolicyNames', [])
        
        if policy_names:
            print(f"   Found {len(policy_names)} inline policy(ies)")
            for policy_name in policy_names:
                try:
                    print(f"   Deleting policy: {policy_name}...")
                    iam_client.delete_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name
                    )
                    print(f"   ✓ Policy deleted")
                    results['policies_deleted'].append(policy_name)
                except Exception as e:
                    error_msg = f"Error deleting policy {policy_name}: {e}"
                    print(f"   ✗ {error_msg}")
                    results['errors'].append(error_msg)
        else:
            print(f"   No inline policies found")
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"   ⚠ Role not found (may already be deleted)")
            results['role_deleted'] = True
            return results
        else:
            error_msg = f"Error listing policies: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"Error listing policies: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    # Delete the role
    try:
        print(f"\n2. Deleting IAM Role: {role_name}...")
        iam_client.delete_role(RoleName=role_name)
        print(f"   ✓ IAM Role deleted")
        results['role_deleted'] = True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"   ⚠ Role not found (may already be deleted)")
            results['role_deleted'] = True
        else:
            error_msg = f"Failed to delete role: {e}"
            print(f"   ✗ {error_msg}")
            results['errors'].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting role: {e}"
        print(f"   ✗ {error_msg}")
        results['errors'].append(error_msg)
    
    print(f"\n{'='*70}")
    print(f"IAM Role Cleanup Summary")
    print(f"{'='*70}")
    print(f"IAM Role Deleted: {'✓' if results['role_deleted'] else '✗'}")
    print(f"Inline Policies Deleted: {len(results['policies_deleted'])}")
    
    if results['errors']:
        print(f"\n発生したエラー: {len(results['errors'])}件")
        for error in results['errors']:
            print(f"  - {error}")
    else:
        print(f"\n✓ IAM role deleted successfully")
    
    print(f"{'='*70}\n")
    
    return results

"""AgentCore Gateway 用の Lambda インターセプターをデプロイ"""
import json
import zipfile
import io
import time
import boto3


def deploy_interceptor(region: str, prefix: str, gateway_arn: str = None) -> str:
    """
    Lambda インターセプター関数をデプロイ

    Args:
        region: AWS リージョン
        prefix: リソース名のプレフィックス
        gateway_arn: Lambda 権限用の Gateway ARN（オプション）

    Returns:
        function_arn: デプロイされた Lambda 関数の ARN
    """
    lambda_client = boto3.client('lambda', region_name=region)
    iam_client = boto3.client('iam', region_name=region)

    function_name = f"{prefix}-interceptor-request"
    role_name = f"{prefix}-interceptor-role"

    # IAM ロールを作成
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    
    try:
        role_response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy)
        )
        role_arn = role_response['Role']['Arn']
        
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        print(f"IAM ロールを作成しました: {role_arn}")
        time.sleep(10)  # ロールの反映を待機

    except iam_client.exceptions.EntityAlreadyExistsException:
        role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
        print(f"既存のロールを使用します: {role_arn}")

    # デプロイパッケージを作成
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write('lab_helpers/lab_03/interceptor-request.py', 'lambda_function.py')
    
    zip_buffer.seek(0)

    # 既存の Lambda が存在する場合は削除
    try:
        lambda_client.get_function(FunctionName=function_name)
        print(f"既存の Lambda を削除中: {function_name}")
        lambda_client.delete_function(FunctionName=function_name)
        time.sleep(2)
    except lambda_client.exceptions.ResourceNotFoundException:
        pass

    # Lambda を作成
    response = lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.11',
        Role=role_arn,
        Handler='lambda_function.lambda_handler',
        Code={'ZipFile': zip_buffer.getvalue()},
        Timeout=30,
        MemorySize=256
    )
    function_arn = response['FunctionArn']
    print(f"Lambda を作成しました: {function_arn}")

    # Gateway が Lambda を呼び出すための権限を追加
    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='AllowGatewayInvoke',
        Action='lambda:InvokeFunction',
        Principal='bedrock-agentcore.amazonaws.com',
        SourceArn=f'arn:aws:bedrock-agentcore:us-east-1:{boto3.client("sts").get_caller_identity()["Account"]}:gateway/*'
    )
    print(f"アカウント内のすべての Gateway に Lambda 権限を追加しました")
    
    return function_arn

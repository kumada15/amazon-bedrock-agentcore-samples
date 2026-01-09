"""
このプログラムは他のプログラムで使用する環境変数を設定します。
CloudFormation の出力と OAuth discovery endpoint から値を取得します。
"""
import boto3
import os
import argparse
from urllib.parse import urlparse
import requests

# パラメータ設定
parser = argparse.ArgumentParser(
                    prog='setup_env_variables',
                    description='FHIR ツール用の環境変数をセットアップ',
                    epilog='入力パラメータ')

parser.add_argument('--cfn_name', help = "CloudFormation テンプレート名")
parser.add_argument('--region', default="us-east-1", help = "使用する AWS リージョン")
parser.add_argument('--openapi_spec_file', default="./temp-fhir-openapi-spec.yaml", help = "OpenAPI spec ファイルのパス")
parser.add_argument('--profile', help = "AWS 認証情報プロファイル名（オプション）")

def main():
    apigateway_endpoint = ""
    apigateway_cognito_lambda = ""

    env_vars = {
        "aws_default_region": args.region,
        "gateway_iam_role": "",
        "cognito_discovery_url":"",
        "cognito_issuer":"",
        "cognito_auth_endpoint":"",
        "cognito_token_url":"",
        "cognito_user_pool_id":"",
        "cognito_client_id":"",
        "cognito_auth_scope":"",
        "healthlake_endpoint":"",
        "openapi_spec_file":args.openapi_spec_file
    }

    # boto3 セッションとクライアントの作成
    if args.profile is None:
        session = boto3.Session()  # デフォルトプロファイルを使用
    else:
        session = boto3.Session(profile_name=args.profile)
        env_vars['awscred_profile_name'] = args.profile

    print(f"CloudFormation スタック名から出力変数を取得中: {args.cfn_name}")
    cfn_client = session.client("cloudformation", region_name=args.region)

    next_token = "start"
    while next_token != "end":
        if next_token == "start":
            response = cfn_client.describe_stacks(
                StackName=args.cfn_name
            )
        else:
             response = cfn_client.describe_stacks(
                StackName=args.cfn_name,
                NextToken=next_token
            )
        
        next_token = "end" if 'NextToken' not in response else response['NextToken']

        for stack in response['Stacks']:
            if stack['StackName'] == args.cfn_name:
                cfn_output = stack['Outputs']

    for output in cfn_output:
        if output['OutputKey'] == 'IAMRolePrimitivesArn':
            env_vars['gateway_iam_role'] = output['OutputValue']
        elif output['OutputKey'] == 'oAuthDiscoveryURL':
            env_vars['cognito_discovery_url'] = output['OutputValue']
        elif output['OutputKey'] == 'oAuthIssuer':
            env_vars['cognito_issuer'] = output['OutputValue']
        elif output['OutputKey'] == 'oAuthEndpoint':
            env_vars['cognito_auth_endpoint'] = output['OutputValue']
        elif output['OutputKey'] == 'oAuthTokenURL':
            env_vars['cognito_token_url'] = output['OutputValue']
        elif output['OutputKey'] == 'APIClientId':
            env_vars['cognito_client_id'] = output['OutputValue']
        elif output['OutputKey'] == 'oAuthScope':
            env_vars['cognito_auth_scope'] = output['OutputValue']
        elif output['OutputKey'] == 'HealthLakeEndpoint':
            env_vars['healthlake_endpoint'] = output['OutputValue']
        elif output['OutputKey'] == 'UserPoolId':
            env_vars['cognito_user_pool_id'] = output['OutputValue']
        elif output['OutputKey'] == 'ApiUrl':
            apigateway_endpoint = output['OutputValue']
        elif output['OutputKey'] == 'APIGWCognitoLambdaName':
            apigateway_cognito_lambda = output['OutputValue']
            
    #print(env_vars)

    print(f"OpenID ディスカバリエンドポイントから oAuth issuer と auth エンドポイントを取得中: {env_vars['cognito_discovery_url']}")
    response = requests.get(env_vars['cognito_discovery_url'])
    response_json = response.json()

    if 'authorization_endpoint' in response_json:
        env_vars['cognito_auth_endpoint'] = response_json['authorization_endpoint']

    if 'issuer' in response_json:
        env_vars['cognito_issuer'] = response_json['issuer']

    print(".env ファイルを作成中")
    # .env ファイルを書き込みモードで開く
    with open(".env", "w") as f:
        # 各キーと値のペアを新しい行に書き込む
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print(".env ファイルが正常に作成/更新されました。")
    print(f"APIEndpoint をメモしておいてください: {apigateway_endpoint}（OpenAPI spec を適切に更新してください）")
    print(f"APIGWCognitoLambdaName をメモしておいてください: {apigateway_cognito_lambda}（後続のステップで必要になります）")

def validate_url(url_string):
    try:
        result = urlparse(url_string)
        if all([result.scheme, result.netloc]):
            return (url_string, 0)
        else:
            return (f"Invalid URL format: '{url_string}'", 0)
    except ValueError:
        return (f"Invalid URL format: '{url_string}'", 0)
        
if __name__ == "__main__":
    args = parser.parse_args()

    # バリデーション
    if args.cfn_name is None:
        raise Exception("CloudFormation テンプレート名は必須です")

    if args.region is None:
        raise Exception("AWS リージョンは必須です")
    elif args.region!= "us-east-1" and args.region!= "us-west-2":
        raise Exception("現時点では us-east-1 と us-west-2 リージョンのみサポートされています")

    if args.openapi_spec_file is None:
        raise Exception("OpenAPI spec ファイルパスは必須です")
    else:
        if not os.path.exists(args.openapi_spec_file):
            raise Exception("OpenAPI spec ファイルパスが無効です")

    main()

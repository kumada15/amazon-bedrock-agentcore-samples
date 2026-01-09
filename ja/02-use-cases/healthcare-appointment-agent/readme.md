# Healthcare Appointment Agent

## 概要
**Model Context Protocol (MCP)** を使用してツールを公開する **Amazon Bedrock AgentCore Gateway** で構築された、予防接種関連の医療予約用 AI エージェントです。この AI エージェントは、現在の予防接種状況/スケジュールの照会、予約枠の確認、予約の予約をサポートします。また、ログインしているユーザー（成人）とその子供を認識することでパーソナライズされた体験を提供し、**FHIR R4**（Fast Healthcare Interoperability Resources）データベースとして **AWS Healthlake** を使用します。

### ユースケースの詳細
| 情報         | 詳細                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| ユースケースタイプ       | 会話型                                                                                                                      |
| エージェントタイプ          | シングルエージェント                                                                                                                        |
| ユースケースコンポーネント | Amazon Bedrock AgentCore 関連コンポーネント: Gateway と Identity                                                                   |
|  					  | その他のコンポーネント: Amazon Cognito、AWS Healthlake、Amazon API Gateway、AWS Lambda                                                 |
|  					  | MCP ツール: MCP ツールは OpenAPI 仕様を使用して Bedrock AgentCore Gateway に公開                                          |
| ユースケース業種   | ヘルスケア                                                                                                                          |
| 例の複雑さ  | 中級                                                                                                                        |
| 使用 SDK            | Amazon Bedrock AgentCore SDK と boto3								                                                                |


### ユースケースアーキテクチャ
![Image1](static/healthcare_gateway_flow.png)

### ユースケースの主な機能

## 前提条件
**注意: これらの手順は us-east-1 と us-west-2 リージョンで動作するように設計されています。**

### 必要な IAM ポリシー
必要な IAM 権限を確認してください。Admin ロールからこのサンプルを実行している場合は無視してください。

このサンプルで使用される CloudFormation スタックには、AWS Healthlake、Cognito、S3、IAM ロール、API Gateway、Lambda 関数関連のリソースがあります。

クイックスタートとして、このコードサンプルのデプロイとセットアップで問題を回避するために、AWS マネージド IAM ポリシーとインラインポリシーの組み合わせを使用できます。ただし、本番環境では最小権限の原則に従うことを推奨します。

**AWS マネージド IAM ポリシー：**
* AmazonAPIGatewayAdministrator
* AmazonCognitoPowerUser
* AmazonHealthLakeFullAccess
* AmazonS3FullAccess
* AWSCloudFormationFullAccess
* AWSKeyManagementServicePowerUser
* AWSLakeFormationDataAdmin
* AWSLambda_FullAccess
* AWSResourceAccessManagerFullAccess
* CloudWatchFullAccessV2
* AmazonBedrockFullAccess

**インラインポリシー：**
```
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Effect": "Allow",
			"Action": [
				"s3:GetObject",
				"s3:PutObject"
			],
			"Resource": [
				"arn:aws:s3:::amzn-s3-demo-source-bucket/*",
				"arn:aws:s3:::amzn-s3-demo-logging-bucket/*"
			]
		},
		{
			"Effect": "Allow",
			"Action": [
				"ram:GetResourceShareInvitations",
				"ram:AcceptResourceShareInvitation",
				"glue:CreateDatabase",
				"glue:DeleteDatabase"
			],
			"Resource": "*"
		},
		{
			"Effect": "Allow",
			"Action": [
				"bedrock-agentcore:*",
				"agent-credential-provider:*"
			],
			"Resource": "*"
		}
	]
}
```
### その他
* Python 3.12
* GIT
* AWS CLI 2.x
* Amazon Bedrock で Claude 3.5 Sonnet モデルが有効。セットアップについては、この[ガイド](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html)に従ってください。

## ユースケースのセットアップ
GIT リポジトリをクローンし、Healthcare-Appointment-Agent ディレクトリに移動します。

```
git clone <repository-url>
cd ./02-use-cases/05-Healthcare-Appointment-Agent/
```

### インフラストラクチャのセットアップ
S3 バケットを作成（**既存のバケットを使用する場合は無視**）

```
aws s3api create-bucket --bucket <globally unique bucket name here>
```

Lambda zip パッケージを S3 バケットにプッシュ
```
aws s3 cp "./cloudformation/fhir-openapi-searchpatient.zip" s3://<bucket name here>/lambda_code/fhir-openapi-searchpatient.zip
```

以下の手順で CloudFormation テンプレートをデプロイします。スタックには約10分かかります。この[ガイド](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/monitor-stack-progress.html)に従ってスタックの進行状況を監視できます。
```
aws cloudformation create-stack \
  --stack-name healthcare-cfn-stack \
  --template-body file://cloudformation/healthcare-cfn.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region <us-east-1 or us-west-2> \
  --parameters ParameterKey=LambdaS3Bucket,ParameterValue="<bucket name here>" \
               ParameterKey=LambdaS3Key,ParameterValue="lambda_code/fhir-openapi-searchpatient.zip"
```

### Python 依存関係のインストールと環境の初期化
この[ガイド](https://docs.astral.sh/uv/getting-started/installation/)に従って UV をインストール

仮想環境を作成してアクティベート

```
uv venv --python 3.12
source ./.venv/bin/activate
```

依存関係をインストール

```
uv pip install -r requirements.txt
```

以下のコマンドを実行して環境を初期化します。これにより、環境変数に使用される **.env** ファイルが作成されます。上記の CloudFormation テンプレートで使用したのと同じリージョン名を使用してください。出力で返される **APIEndpoint** と **APIGWCognitoLambdaName** をメモしてください。

```
python init_env.py \
--cfn_name healthcare-cfn-stack \
--openapi_spec_file ./fhir-openapi-spec.yaml \
--region <us-east-1 or us-west-2>
```

名前付き認証プロファイルを使用する必要がある場合は、以下で実現できます。

```
python init_env.py \
--cfn_name healthcare-cfn-stack \
--region <us-east-1 or us-west-2> \
--openapi_spec_file ./fhir-openapi-spec.yaml \
--profile <profile-name here>>
```

**.env** ファイルは以下のようになります。
![EnvImage1](static/env_screenshot1.png)


**API Gateway で Cognito 認証を有効化**
```
aws lambda invoke \
--function-name <input APIGWCognitoLambdaName as noted earlier> \
response.json \
--payload '{ "RequestType": "Create" }' \
--cli-binary-format raw-in-base64-out \
--region <us-east-1 or us-west-2>
```

### AWS Healthlake でテストデータを作成
以下の Python プログラムを実行して、**test_data** フォルダにあるテストデータを取り込みます。完了まで約5分かかる場合があります。
```
python create_test_data.py
```

## 実行手順
### Bedrock AgentCore Gateway と Gateway Target の作成
OpenAPI 仕様ファイル **fhir-openapi-spec.yaml** を開き、**<your API endpoint here>** を先ほどメモした **APIEndpoint** に置き換えます。

**fhir-openapi-spec.yaml** ファイル内の OpenAPI 仕様に基づいて Bedrock AgentCore Gateway と Gateway Target をセットアップします。後の手順で必要になるため、出力から Gateway ID をメモしてください。

```
python setup_fhir_mcp.py --op_type Create --gateway_name <gateway_name_here>
```

### Strands Agent の実行
以下の手順で Strands Agent を実行します。

```
python strands_agent.py --gateway_id <gateway_id_here>
```

### Langgraph Agent の実行
以下の手順で Langgraph Agent を実行します。

```
python langgraph_agent.py --gateway_id <gateway_id_here>
```

### エージェントと対話するサンプルプロンプト：
* どのようなお手伝いができますか？
* まず予防接種スケジュールを確認しましょう
* 予定日前後で MMR ワクチンの空き枠を見つけてください

![Image1](static/appointment_agent_demo.gif)


## クリーンアップ手順
API Gateway で Cognito 認証を無効化

```
aws lambda invoke \
--function-name <input APIGWCognitoLambdaName as noted earlier> \
response.json \
--payload '{ "RequestType": "Delete" }' \
--cli-binary-format raw-in-base64-out \
--region <us-east-1 or us-west-2>
```

Gateway と Gateway Target を削除します。複数の Gateway を作成した場合は、すべての Gateway に対してこの手順を繰り返してください。

```
python setup_fhir_mcp.py --op_type Delete --gateway_id <gateway_id_here>
```

CloudFormation スタックを削除します。

```
aws cloudformation delete-stack \
  --stack-name healthcare-cfn-stack \
  --region <us-east-1 or us-west-2>
```

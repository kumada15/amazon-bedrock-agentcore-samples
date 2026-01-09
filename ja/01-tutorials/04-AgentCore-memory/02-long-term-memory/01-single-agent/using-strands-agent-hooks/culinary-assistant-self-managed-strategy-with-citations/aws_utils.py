import boto3
import json
import time
import uuid
import zipfile
import os
import io
from botocore.exceptions import ClientError


class AWSUtils:
    """AgentCore 自己管理メモリに必要な AWS リソースをセットアップするためのユーティリティクラス"""

    def __init__(self, region_name='us-east-1'):
        """使用する AWS リージョンで初期化します"""
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.sns_client = boto3.client('sns', region_name=region_name)
        self.sqs_client = boto3.client('sqs', region_name=region_name)
        self.lambda_client = boto3.client('lambda', region_name=region_name)
        self.iam_client = boto3.client('iam', region_name=region_name)
        self.agentcore_client = boto3.client('bedrock-agentcore', region_name=region_name)
        self.agentcore_client_control = boto3.client('bedrock-agentcore-control', region_name=region_name)
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=region_name)
        self.account_id = boto3.client('sts').get_caller_identity().get('Account')
        self.created_resources = {
            's3_buckets': [],
            'sns_topics': [],
            'sqs_queues': [],
            'lambda_functions': [],
            'iam_roles': [],
            'memories': []
        }

    # S3 Bucket Methods
    def create_s3_bucket(self, bucket_name_prefix):
        """AgentCore ペイロード用の S3 バケットを作成します"""
        bucket_name = f"{bucket_name_prefix}-{self.account_id}-{int(time.time())}"

        try:
            if self.region_name == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region_name}
                )

            # Add lifecycle policy to delete objects after 7 days
            lifecycle_config = {
                'Rules': [
                    {
                        'Status': 'Enabled',
                        'Prefix': '',
                        'Expiration': {'Days': 7},
                        'ID': 'DeleteAfter7Days'
                    }
                ]
            }
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_config
            )

            print(f"S3バケットを作成しました: {bucket_name}")
            self.created_resources['s3_buckets'].append(bucket_name)
            return bucket_name

        except ClientError as e:
            print(f"S3バケット作成エラー: {e}")
            raise

    # SNS Topic Methods
    def create_sns_topic(self, topic_name):
        """メモリジョブ通知用の SNS トピックを作成します"""
        try:
            response = self.sns_client.create_topic(Name=topic_name)
            topic_arn = response['TopicArn']
            print(f"SNSトピックを作成しました: {topic_arn}")
            self.created_resources['sns_topics'].append(topic_arn)
            return topic_arn

        except ClientError as e:
            print(f"SNSトピック作成エラー: {e}")
            raise

    # SQS Queue Methods
    def create_sqs_queue_with_sns_subscription(self, queue_name, sns_topic_arn):
        """SQS キューを作成し、SNS トピックにサブスクライブします"""
        try:
            # Create SQS queue with visibility timeout higher than Lambda timeout (60 seconds)
            queue_response = self.sqs_client.create_queue(
                QueueName=queue_name,
                Attributes={
                    'VisibilityTimeout': '120'  # 120 seconds, double the Lambda timeout
                }
            )
            queue_url = queue_response['QueueUrl']

            # Get queue ARN
            queue_attrs = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['QueueArn']
            )
            queue_arn = queue_attrs['Attributes']['QueueArn']

            # Set queue policy to allow SNS
            policy = {
                'Version': '2012-10-17',
                'Statement': [{
                    'Effect': 'Allow',
                    'Principal': {'Service': 'sns.amazonaws.com'},
                    'Action': 'sqs:SendMessage',
                    'Resource': queue_arn,
                    'Condition': {'ArnEquals': {'aws:SourceArn': sns_topic_arn}}
                }]
            }

            self.sqs_client.set_queue_attributes(
                QueueUrl=queue_url,
                Attributes={'Policy': json.dumps(policy)}
            )

            # Subscribe queue to SNS topic
            self.sns_client.subscribe(
                TopicArn=sns_topic_arn,
                Protocol='sqs',
                Endpoint=queue_arn
            )

            print(f"SQSキューを作成しSNSトピックにサブスクライブしました: {queue_url}")
            self.created_resources['sqs_queues'].append(queue_url)
            return queue_url, queue_arn

        except ClientError as e:
            print(f"SQSキューのセットアップエラー: {e}")
            raise

    # IAM Role Methods
    def create_iam_role_for_agentcore(self, role_name, s3_bucket_name, sns_topic_arn):
        """AgentCore が S3 と SNS にアクセスするための IAM ロールを作成します"""
        try:
            # Trust policy for AgentCore
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "bedrock-agentcore.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }

            # Create role
            create_role_response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )

            role_arn = create_role_response['Role']['Arn']

            # Create policy for S3 and SNS access
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "S3PayloadDelivery",
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetBucketLocation",
                            "s3:PutObject"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{s3_bucket_name}",
                            f"arn:aws:s3:::{s3_bucket_name}/*"
                        ]
                    },
                    {
                        "Sid": "SNSNotifications",
                        "Effect": "Allow",
                        "Action": [
                            "sns:GetTopicAttributes",
                            "sns:Publish"
                        ],
                        "Resource": sns_topic_arn
                    }
                ]
            }

            # Attach inline policy to role
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-policy",
                PolicyDocument=json.dumps(policy_document)
            )

            # Wait for IAM role to propagate
            print(f"IAMロールを作成しました: {role_arn}、伝播のため10秒待機中...")
            time.sleep(10)

            self.created_resources['iam_roles'].append(role_name)
            return role_arn

        except ClientError as e:
            print(f"IAMロール作成エラー: {e}")
            raise

    def create_iam_role_for_lambda(self, role_name, s3_bucket_name, sqs_queue_arn):
        """Lambda 関数用の IAM ロールを作成します"""
        try:
            # Trust policy for Lambda
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }

            # Create role
            create_role_response = self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy)
            )

            role_arn = create_role_response['Role']['Arn']

            # Attach AWSLambdaBasicExecutionRole for CloudWatch logs
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
            )

            # Create policy for S3, SQS, and AgentCore access
            policy_document = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{s3_bucket_name}/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "sqs:ReceiveMessage",
                            "sqs:DeleteMessage",
                            "sqs:GetQueueAttributes"
                        ],
                        "Resource": sqs_queue_arn
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock-agentcore:BatchCreateMemoryRecords",
                            "bedrock:InvokeModel"
                        ],
                        "Resource": "*"
                    }
                ]
            }

            # Attach inline policy to role
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{role_name}-policy",
                PolicyDocument=json.dumps(policy_document)
            )

            # Wait for IAM role to propagate
            print(f"Lambda用IAMロールを作成しました: {role_arn}、伝播のため10秒待機中...")
            time.sleep(10)

            self.created_resources['iam_roles'].append(role_name)
            return role_arn

        except ClientError as e:
            print(f"Lambda用IAMロール作成エラー: {e}")
            raise

    # Lambda Layer Method
    def create_boto3_layer(self, layer_name):
        """最新の boto3 を含む Lambda レイヤーを作成します"""
        try:
            # Create a temp directory for boto3 package
            import tempfile
            import subprocess
            import shutil

            # Create a temporary directory
            temp_dir = tempfile.mkdtemp()
            python_dir = os.path.join(temp_dir, 'python')
            os.makedirs(python_dir)

            # Install boto3 to the temp directory
            subprocess.check_call([
                'pip', 'install', 'boto3', '--target', python_dir
            ])

            # Create a zip file in memory
            layer_zip = os.path.join(temp_dir, 'boto3_layer.zip')

            with zipfile.ZipFile(layer_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add all files from the python directory
                for root, _, files in os.walk(python_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zip_file.write(
                            file_path,
                            os.path.relpath(file_path, temp_dir)
                        )

            # Upload the layer
            with open(layer_zip, 'rb') as zip_file:
                response = self.lambda_client.publish_layer_version(
                    LayerName=layer_name,
                    Description='Layer with latest boto3 for AgentCore',
                    Content={
                        'ZipFile': zip_file.read()
                    },
                    CompatibleRuntimes=['python3.9'],
                )

            # Clean up
            shutil.rmtree(temp_dir)

            layer_version_arn = response['LayerVersionArn']
            print(f"Lambdaレイヤーを作成しました: {layer_version_arn}")
            return layer_version_arn

        except Exception as e:
            print(f"boto3レイヤー作成エラー: {e}")
            raise

    # Lambda Function Methods
    def create_lambda_function(self, function_name, role_arn, handler_code, timeout=60, use_latest_boto3=True):
        """メモリイベント処理用の Lambda 関数を作成します"""
        try:
            # Create boto3 layer if requested
            layer_arn = None
            if use_latest_boto3:
                layer_name = f"boto3-layer-{int(time.time())}"
                layer_arn = self.create_boto3_layer(layer_name)

            # Create zip file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr('lambda_function.py', handler_code)

            zip_buffer.seek(0)

            # Prepare function parameters
            function_params = {
                'FunctionName': function_name,
                'Runtime': 'python3.9',
                'Role': role_arn,
                'Handler': 'lambda_function.lambda_handler',
                'Code': {
                    'ZipFile': zip_buffer.read()
                },
                'Timeout': timeout,
                'MemorySize': 256
            }

            # Add layer if created
            if layer_arn:
                function_params['Layers'] = [layer_arn]

            # Create Lambda function
            response = self.lambda_client.create_function(**function_params)

            function_arn = response['FunctionArn']
            print(f"Lambda関数を作成しました: {function_arn}")
            self.created_resources['lambda_functions'].append(function_name)
            return function_arn

        except ClientError as e:
            print(f"Lambda関数作成エラー: {e}")
            raise

    def add_sqs_trigger_to_lambda(self, function_name, sqs_queue_arn):
        """Lambda 関数のイベントソースとして SQS を追加します"""
        try:
            response = self.lambda_client.create_event_source_mapping(
                EventSourceArn=sqs_queue_arn,
                FunctionName=function_name,
                Enabled=True,
                BatchSize=1
            )

            print(f"Lambda関数にSQSトリガーを追加しました: {function_name}")
            return response['UUID']

        except ClientError as e:
            print(f"LambdaへのSQSトリガー追加エラー: {e}")
            raise

    # AgentCore Memory Methods
    def create_memory_with_self_managed_strategy(
        self,
        memory_name,
        memory_description,
        role_arn,
        sns_topic_arn,
        s3_bucket_name,
        strategy_name="SelfManagedMemory",
        message_trigger_count=5,
        token_trigger_count=1000,
        idle_timeout=900,  # 15 minutes
        historical_window_size=10
    ):
        """自己管理戦略でメモリを作成します"""
        try:
            client_token = str(uuid.uuid4())

            response = self.agentcore_client_control.create_memory(
                clientToken=client_token,
                name=memory_name,
                description=memory_description,
                memoryExecutionRoleArn=role_arn,
                eventExpiryDuration=7,  # 7 days
                memoryStrategies=[
                    {
                        'customMemoryStrategy': {
                            'name': strategy_name,
                            'description': 'Custom self-managed memory strategy',
                            # 'namespaces': ['/interests/actor/{actorId}/session/{sessionId}'],
                            'configuration': {
                                'selfManagedConfiguration': {
                                    'triggerConditions': [
                                        {
                                            'messageBasedTrigger': {
                                                'messageCount': message_trigger_count
                                            }
                                        },
                                        {
                                            'tokenBasedTrigger': {
                                                'tokenCount': token_trigger_count
                                            }
                                        },
                                        {
                                            'timeBasedTrigger': {
                                                'idleSessionTimeout': idle_timeout
                                            }
                                        }
                                    ],
                                    'invocationConfiguration': {
                                        'topicArn': sns_topic_arn,
                                        'payloadDeliveryBucketName': s3_bucket_name
                                    },
                                    'historicalContextWindowSize': historical_window_size
                                }
                            }
                        }
                    }
                ]
            )

            memory_id = response['memory']['id']
            # strategy_id = response['memory']['memoryStrategies'][0]['id']
            print(f"メモリを作成しました、ID: {memory_id}")

            self.created_resources['memories'].append(memory_id)
            return memory_id

        except ClientError as e:
            print(f"メモリ作成エラー: {e}")
            raise

    # Event Creation Method for Testing
    def create_test_events(self, memory_id, actor_id="test-user", num_events=6):
        """自己管理メモリパイプラインをトリガーするテストイベントを作成します"""
        session_id = str(uuid.uuid4())

        print(f"メモリ {memory_id} 用に {num_events} 件のテストイベントを作成中")

        for i in range(num_events):
            try:
                event_payload = [
                    {
                        'conversational': {
                            'content': {
                                'text': f"I like to eat {['pizza', 'sushi', 'tacos', 'pasta', 'burgers'][i % 5]} for dinner."
                            },
                            'role': 'USER'
                        }
                    },
                    {
                        'conversational': {
                            'content': {
                                'text': f"I understand you like {['pizza', 'sushi', 'tacos', 'pasta', 'burgers'][i % 5]}. That's a great choice!"
                            },
                            'role': 'ASSISTANT'
                        }
                    }
                ]

                self.agentcore_client.create_event(
                    memoryId=memory_id,
                    actorId=actor_id,
                    sessionId=session_id,
                    eventTimestamp=int(time.time()),
                    payload=event_payload,
                    clientToken=str(uuid.uuid4())
                )

                print(f"イベント {i+1}/{num_events} を作成しました")

                # Small sleep to space out events
                time.sleep(1)

            except ClientError as e:
                print(f"テストイベント作成エラー: {e}")
                raise

        return session_id

    # Cleanup Method
    def cleanup_resources(self, prefix=None, discover_resources=True):
        """このユーティリティで作成されたすべてのリソースをクリーンアップします

        Args:
            prefix (str, optional): リソースをフィルタリングするためのプレフィックス（例：'agentcore-memory'）
            discover_resources (bool, optional): 追跡されているリソースがない場合にリソースの検出を試みるかどうか
        """
        print("リソースのクリーンアップを開始中...")

        # Track deleted resources
        deleted_resources = 0
        total_resources = 0

        # Build resources to delete from tracked resources and/or discovery
        resources_to_delete = {k: list(v) for k, v in self.created_resources.items()}

        # If no tracked resources or discovery requested, try to find resources
        if discover_resources and sum(len(resources) for resources in self.created_resources.values()) == 0:
            print("追跡されたリソースが見つかりません。リソースの検出を試行中...")

            try:
                # Discover memories with name prefix 'SelfManageMemory'
                memory_prefix = 'SelfManageMemory' if prefix is None else prefix
                memories = self.agentcore_client_control.list_memories(
                    filters=[{'key': 'name', 'value': memory_prefix, 'operator': 'CONTAINS'}]
                ).get('memorySummaries', [])

                for memory in memories:
                    if memory['id'] not in resources_to_delete['memories']:
                        resources_to_delete['memories'].append(memory['id'])
                        print(f"メモリを検出しました: {memory['id']}")
            except Exception as e:
                print(f"メモリ検出エラー: {e}")

            try:
                # Discover Lambda functions
                lambda_prefix = 'agentcore-memory-processor' if prefix is None else prefix
                functions = self.lambda_client.list_functions().get('Functions', [])
                for function in functions:
                    if lambda_prefix in function['FunctionName'] and function['FunctionName'] not in resources_to_delete['lambda_functions']:
                        resources_to_delete['lambda_functions'].append(function['FunctionName'])
                        print(f"Lambda関数を検出しました: {function['FunctionName']}")
            except Exception as e:
                print(f"Lambda関数検出エラー: {e}")

            try:
                # Discover SNS topics
                sns_prefix = 'agentcore-memory-notifications' if prefix is None else prefix
                topics = self.sns_client.list_topics().get('Topics', [])
                for topic in topics:
                    if sns_prefix in topic['TopicArn'] and topic['TopicArn'] not in resources_to_delete['sns_topics']:
                        resources_to_delete['sns_topics'].append(topic['TopicArn'])
                        print(f"SNSトピックを検出しました: {topic['TopicArn']}")
            except Exception as e:
                print(f"SNSトピック検出エラー: {e}")

            try:
                # Discover SQS queues
                sqs_prefix = 'agentcore-memory-queue' if prefix is None else prefix
                queues = self.sqs_client.list_queues(QueueNamePrefix=sqs_prefix).get('QueueUrls', [])
                for queue in queues:
                    if queue not in resources_to_delete['sqs_queues']:
                        resources_to_delete['sqs_queues'].append(queue)
                        print(f"SQSキューを検出しました: {queue}")
            except Exception as e:
                print(f"SQSキュー検出エラー: {e}")

            try:
                # Discover IAM roles
                iam_prefixes = ['AgentCoreMemoryExecutionRole', 'LambdaMemoryProcessingRole']
                if prefix is not None:
                    iam_prefixes = [prefix]

                roles = self.iam_client.list_roles().get('Roles', [])
                for role in roles:
                    role_name = role['RoleName']
                    if any(prefix in role_name for prefix in iam_prefixes) and role_name not in resources_to_delete['iam_roles']:
                        resources_to_delete['iam_roles'].append(role_name)
                        print(f"IAMロールを検出しました: {role_name}")
            except Exception as e:
                print(f"IAMロール検出エラー: {e}")

            try:
                # Discover S3 buckets
                s3_prefix = 'agentcore-memory-payloads' if prefix is None else prefix
                buckets = self.s3_client.list_buckets().get('Buckets', [])
                for bucket in buckets:
                    bucket_name = bucket['Name']
                    if s3_prefix in bucket_name and bucket_name not in resources_to_delete['s3_buckets']:
                        resources_to_delete['s3_buckets'].append(bucket_name)
                        print(f"S3バケットを検出しました: {bucket_name}")
            except Exception as e:
                print(f"S3バケット検出エラー: {e}")

        # Check if there are any resources to clean up
        total_resources = sum(len(resources) for resources in resources_to_delete.values())
        if total_resources == 0:
            print("クリーンアップするリソースがありません。まずリソースを作成してください。")
            return

        # Delete memories
        for memory_id in resources_to_delete['memories']:
            try:
                print(f"メモリを削除中: {memory_id}")
                self.agentcore_client_control.delete_memory(memoryId=memory_id)
                print(f"メモリを正常に削除しました: {memory_id}")
                if memory_id in self.created_resources['memories']:
                    self.created_resources['memories'].remove(memory_id)
                deleted_resources += 1
            except Exception as e:
                print(f"メモリ {memory_id} の削除エラー: {e}")

        # Delete Lambda functions
        for function_name in resources_to_delete['lambda_functions']:
            try:
                print(f"Lambda関数を削除中: {function_name}")
                self.lambda_client.delete_function(FunctionName=function_name)
                print(f"Lambda関数を正常に削除しました: {function_name}")
                if function_name in self.created_resources['lambda_functions']:
                    self.created_resources['lambda_functions'].remove(function_name)
                deleted_resources += 1
            except Exception as e:
                print(f"Lambda関数 {function_name} の削除エラー: {e}")

        # Delete SQS queues
        for queue_url in resources_to_delete['sqs_queues']:
            try:
                print(f"SQSキューを削除中: {queue_url}")
                self.sqs_client.delete_queue(QueueUrl=queue_url)
                print(f"SQSキューを正常に削除しました: {queue_url}")
                if queue_url in self.created_resources['sqs_queues']:
                    self.created_resources['sqs_queues'].remove(queue_url)
                deleted_resources += 1
            except Exception as e:
                print(f"SQSキュー {queue_url} の削除エラー: {e}")

        # Delete SNS topics
        for topic_arn in resources_to_delete['sns_topics']:
            try:
                print(f"SNSトピックを削除中: {topic_arn}")
                self.sns_client.delete_topic(TopicArn=topic_arn)
                print(f"SNSトピックを正常に削除しました: {topic_arn}")
                if topic_arn in self.created_resources['sns_topics']:
                    self.created_resources['sns_topics'].remove(topic_arn)
                deleted_resources += 1
            except Exception as e:
                print(f"SNSトピック {topic_arn} の削除エラー: {e}")

        # Delete IAM roles
        for role_name in resources_to_delete['iam_roles']:
            try:
                print(f"IAMロールを削除中: {role_name}")
                # Detach all managed policies
                attached_policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
                for policy in attached_policies.get('AttachedPolicies', []):
                    self.iam_client.detach_role_policy(
                        RoleName=role_name,
                        PolicyArn=policy['PolicyArn']
                    )
                    print(f"ロール {role_name} からポリシー {policy['PolicyArn']} をデタッチしました")

                # Delete inline policies
                inline_policies = self.iam_client.list_role_policies(RoleName=role_name)
                for policy_name in inline_policies.get('PolicyNames', []):
                    self.iam_client.delete_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name
                    )
                    print(f"ロール {role_name} からインラインポリシー {policy_name} を削除しました")

                # Delete role
                self.iam_client.delete_role(RoleName=role_name)
                print(f"IAMロールを正常に削除しました: {role_name}")
                if role_name in self.created_resources['iam_roles']:
                    self.created_resources['iam_roles'].remove(role_name)
                deleted_resources += 1
            except Exception as e:
                print(f"IAMロール {role_name} の削除エラー: {e}")

        # Delete S3 buckets - need to delete all objects first
        for bucket_name in resources_to_delete['s3_buckets']:
            try:
                print(f"S3バケットとその内容を削除中: {bucket_name}")
                # List and delete all objects
                objects = self.s3_client.list_objects_v2(Bucket=bucket_name)
                if 'Contents' in objects:
                    for obj in objects['Contents']:
                        self.s3_client.delete_object(
                            Bucket=bucket_name,
                            Key=obj['Key']
                        )
                        print(f"バケット {bucket_name} からオブジェクト {obj['Key']} を削除しました")

                # Delete bucket
                self.s3_client.delete_bucket(Bucket=bucket_name)
                print(f"S3バケットを正常に削除しました: {bucket_name}")
                if bucket_name in self.created_resources['s3_buckets']:
                    self.created_resources['s3_buckets'].remove(bucket_name)
                deleted_resources += 1
            except Exception as e:
                print(f"S3バケット {bucket_name} の削除エラー: {e}")

        print(f"クリーンアップ完了。{total_resources} 件中 {deleted_resources} 件のリソースを削除しました。")
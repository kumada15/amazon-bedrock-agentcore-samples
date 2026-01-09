import json
import boto3
import os
import traceback
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    Lambda function to invoke AgentCore Runtime agent.

    Expected event format:
    {
        "prompt": "Your question here",
        "sessionId": "optional-session-id"
    }
    """

    # boto3 クライアントを初期化
    bedrock_agentcore_client = boto3.client("bedrock-agentcore")

    try:
        # 環境変数を取得
        runtime_arn = os.environ.get("RUNTIME_ARN")

        print("Lambda 関数を開始しました")
        print(f"Runtime ARN: {runtime_arn}")

        if not runtime_arn:
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "error": "Configuration Error",
                        "message": "Missing RUNTIME_ARN environment variable",
                    }
                ),
            }

        # 入力をパース
        if isinstance(event, str):
            event = json.loads(event)

        prompt = event.get("prompt", "")
        session_id = event.get("sessionId", context.aws_request_id)

        if not prompt:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Bad Request", "message": "Missing prompt in request"}
                ),
            }

        print(f"プロンプトを処理中: {prompt}")
        print(f"セッション ID: {session_id}")

        # AgentCore 用のペイロードを準備
        payload = json.dumps({"prompt": prompt})

        # AgentCore Runtime を呼び出し
        print("AgentCore Runtime を呼び出し中...")
        response = bedrock_agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn, runtimeSessionId=session_id, payload=payload
        )

        print("AgentCore からレスポンスを受信しました")

        # レスポンスをパース - StreamingBody を処理
        agent_response = None

        if "response" in response:
            response_body = response["response"]

            # StreamingBody を処理
            if hasattr(response_body, "read"):
                raw_data = response_body.read()
                if isinstance(raw_data, bytes):
                    agent_response = raw_data.decode("utf-8")
                else:
                    agent_response = str(raw_data)
            elif isinstance(response_body, list) and len(response_body) > 0:
                if isinstance(response_body[0], bytes):
                    agent_response = response_body[0].decode("utf-8")
                else:
                    agent_response = str(response_body[0])
            elif isinstance(response_body, bytes):
                agent_response = response_body.decode("utf-8")
            elif isinstance(response_body, str):
                agent_response = response_body
            else:
                agent_response = str(response_body)

        if not agent_response:
            agent_response = "No response from agent"
            print("警告: AgentCore からレスポンスが抽出されませんでした")

        print(f"Agent レスポンスを受信しました (長さ: {len(agent_response)} 文字)")

        return {
            "statusCode": 200,
            "body": json.dumps({"response": agent_response, "sessionId": session_id}),
            "headers": {"Content-Type": "application/json"},
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        print(f"AWS クライアントエラー: {error_code}")
        print(f"エラーメッセージ: {error_message}")
        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_code, "message": error_message}),
        }

    except Exception as e:
        print(f"予期せぬエラー: {str(e)}")
        print(f"エラータイプ: {type(e).__name__}")
        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "InternalError", "message": str(e), "type": type(e).__name__}
            ),
        }

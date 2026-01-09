"""
OAuth2 クレデンシャルプロバイダー管理用カスタムリソース Lambda

この Lambda は AgentCore Gateway 用の OAuth2 クレデンシャルプロバイダーを作成・管理します。
CDK がまだ CfnOAuthProvider をサポートしていないため、boto3 API を直接使用しています。

Version: 1.1 - OAuth プロバイダー設定を修正
"""

import json
import logging
import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

agentcore_client = boto3.client("bedrock-agentcore-control")


def handler(event, context):
    """CloudFormation カスタムリソースイベントを処理する"""
    logger.info(f"イベントを受信しました: {json.dumps(event)}")

    request_type = event["RequestType"]
    props = event["ResourceProperties"]

    try:
        if request_type == "Create":
            return create_oauth_provider(event, props)
        elif request_type == "Update":
            return update_oauth_provider(event, props)
        elif request_type == "Delete":
            return delete_oauth_provider(event)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
    except Exception as e:
        logger.error(f"{request_type} の処理中にエラーが発生しました: {str(e)}")
        return send_response(event, "FAILED", str(e))


def create_oauth_provider(event, props):
    """OAuth2 クレデンシャルプロバイダーを作成する"""
    logger.info("OAuth2 クレデンシャルプロバイダーを作成中...")

    provider_name = props["ProviderName"]
    user_pool_id = props["UserPoolId"]
    client_id = props["ClientId"]
    discovery_url = props["DiscoveryUrl"]

    # Cognito からクライアントシークレットを取得
    cognito_client = boto3.client("cognito-idp")
    try:
        response = cognito_client.describe_user_pool_client(
            UserPoolId=user_pool_id, ClientId=client_id
        )
        client_secret = response["UserPoolClient"]["ClientSecret"]
        logger.info(f"クライアント {client_id} のクライアントシークレットを取得しました")
    except Exception as e:
        logger.error(f"クライアントシークレットの取得に失敗しました: {e}")
        raise

    # プロバイダーが既に存在するか確認
    try:
        providers = agentcore_client.list_oauth2_credential_providers()
        for provider in providers.get("items", []):
            if provider["name"] == provider_name:
                logger.info(
                    f"プロバイダーは既に存在します: {provider['credentialProviderArn']}"
                )
                return send_response(
                    event,
                    "SUCCESS",
                    data={"ProviderArn": provider["credentialProviderArn"]},
                    physical_resource_id=provider_name,
                )
    except Exception as e:
        logger.warning(f"既存プロバイダーの確認中にエラーが発生しました: {e}")

    # CustomOauth2 と discovery URL を使用して新しいプロバイダーを作成（Tutorial 05 と一致）
    response = agentcore_client.create_oauth2_credential_provider(
        name=provider_name,
        credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput={
            "customOauth2ProviderConfig": {
                "oauthDiscovery": {"discoveryUrl": discovery_url},
                "clientId": client_id,
                "clientSecret": client_secret,
            }
        },
    )

    provider_arn = response["credentialProviderArn"]
    logger.info(f"OAuth プロバイダーを作成しました: {provider_arn}")

    return send_response(
        event,
        "SUCCESS",
        data={"ProviderArn": provider_arn},
        physical_resource_id=provider_name,
    )


def update_oauth_provider(event, props):
    """OAuth2 クレデンシャルプロバイダーを更新する"""
    provider_name = event["PhysicalResourceId"]
    old_props = event.get("OldResourceProperties", {})

    # 名前が変更された場合、古いものを削除して新しいものを作成
    if old_props.get("ProviderName") != props.get("ProviderName"):
        logger.info("プロバイダー名が変更されました、再作成中...")
        delete_oauth_provider(event)
        return create_oauth_provider(event, props)

    # 現時点では、OAuth プロバイダーは更新をサポートしていない
    # 既存のプロバイダー ARN を返す
    try:
        providers = agentcore_client.list_oauth2_credential_providers()
        for provider in providers.get("items", []):
            if provider["name"] == provider_name:
                return send_response(
                    event,
                    "SUCCESS",
                    data={"ProviderArn": provider["credentialProviderArn"]},
                    physical_resource_id=provider_name,
                )
    except Exception as e:
        logger.error(f"プロバイダーの検索中にエラーが発生しました: {e}")

    return send_response(event, "FAILED", "Provider not found")


def delete_oauth_provider(event):
    """OAuth2 クレデンシャルプロバイダーを削除する"""
    provider_name = event["PhysicalResourceId"]

    try:
        agentcore_client.delete_oauth2_credential_provider(name=provider_name)
        logger.info(f"OAuth プロバイダーを削除しました: {provider_name}")
    except Exception as e:
        logger.warning(f"プロバイダーの削除中にエラーが発生しました: {e}")

    return send_response(event, "SUCCESS", physical_resource_id=provider_name)


def send_response(event, status, reason=None, data=None, physical_resource_id=None):
    """CloudFormation にレスポンスを送信する"""
    response_body = {
        "Status": status,
        "Reason": reason or f"{status}: See CloudWatch logs",
        "PhysicalResourceId": physical_resource_id
        or event.get("PhysicalResourceId", "NONE"),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    }

    logger.info(f"レスポンスを送信中: {json.dumps(response_body)}")

    http = urllib3.PoolManager()
    http.request(
        "PUT",
        event["ResponseURL"],
        body=json.dumps(response_body).encode("utf-8"),
        headers={"Content-Type": ""},
    )

    return response_body

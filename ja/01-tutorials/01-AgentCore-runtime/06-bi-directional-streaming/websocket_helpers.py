#!/usr/bin/env python3
"""
AWS Bedrock AgentCore 用 WebSocket ヘルパー関数

このモジュールは、様々な認証方式（SigV4 ヘッダー、SigV4 クエリパラメータ、OAuth）を使用して
AWS Bedrock AgentCore への WebSocket 接続を作成するためのユーティリティを提供します。
"""
import secrets
import string
import os
from urllib.parse import urlparse
import boto3
from botocore.auth import SigV4Auth, SigV4QueryAuth
from botocore.awsrequest import AWSRequest


def create_signed_headers(url, region=None, service='bedrock-agentcore'):
    """WebSocket 接続用の AWS SigV4 署名付きヘッダーを作成する"""
    if region is None:
        region = os.getenv('AWS_REGION', 'us-west-2')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    parsed_url = urlparse(url)
    request = AWSRequest(
        method='GET',
        url=url,
        headers={'Host': parsed_url.netloc}
    )
    SigV4Auth(credentials, service, region).add_auth(request)
    return dict(request.headers)


def create_presigned_url(url, region=None, service='bedrock-agentcore', expires=300):
    """WebSocket 接続用の AWS SigV4 署名付き URL を作成する"""
    if region is None:
        region = os.getenv('AWS_REGION', 'us-west-2')
    session = boto3.Session()
    credentials = session.get_credentials()
    
    https_url = url.replace("wss://", "https://")
    parsed_url = urlparse(https_url)
    
    request = AWSRequest(
        method='GET',
        url=https_url,
        headers={'Host': parsed_url.netloc}
    )
    SigV4QueryAuth(credentials, service, region, expires=expires).add_auth(request)
    
    return request.url.replace("https://", "wss://")


def create_websocket_headers(session_id):
    """WebSocket 固有のヘッダーを作成する"""
    return {
        'Connection': 'Upgrade',
        'Upgrade': 'websocket',
        'Sec-WebSocket-Version': '13',
        'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
        'User-Agent': 'AWS-SigV4-WebSocket-Client/1.0',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
    }


def prepare_connection(runtime_arn, auth_type='headers', session_id=None):
    """接続用の WebSocket URI とヘッダーを準備する"""
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    if session_id is None:
        session_id = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
    
    uri = f"wss://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime_arn}/ws?qualifier=DEFAULT"
    
    if auth_type == 'query':
        uri = create_presigned_url(uri)
        headers = create_websocket_headers(session_id)
    elif auth_type == 'oauth':
        token = os.getenv('BEARER_TOKEN')
        if not token:
            raise ValueError("BEARER_TOKEN environment variable required for OAuth")
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id,
            'Connection': 'Upgrade',
            'Upgrade': 'websocket',
            'Sec-WebSocket-Version': '13',
            'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
            'User-Agent': 'OAuth-WebSocket-Client/1.0'
        }
    else:
        signed_headers = create_signed_headers(uri)
        ws_headers = create_websocket_headers(session_id)
        headers = {**signed_headers, **ws_headers}
    
    return uri, headers

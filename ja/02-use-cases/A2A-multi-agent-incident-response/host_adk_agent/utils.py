import boto3
from boto3.session import Session
import sys


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """AWS Systems Manager Parameter Store からパラメータを取得する。"""
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]


def get_aws_info():
    """boto3 セッションから AWS アカウント ID とリージョンを取得する。"""
    try:
        boto_session = Session()

        # リージョンを取得
        region = boto_session.region_name
        if not region:
            # デフォルトセッションから取得を試みる
            region = (
                boto3.DEFAULT_SESSION.region_name if boto3.DEFAULT_SESSION else None
            )
            if not region:
                raise ValueError(
                    "AWS region not configured. Please set AWS_DEFAULT_REGION or configure AWS CLI."
                )

        # STS を使用してアカウント ID を取得
        sts = boto_session.client("sts")
        account_id = sts.get_caller_identity()["Account"]

        return account_id, region

    except Exception as e:
        print(f"AWS 情報の取得エラー: {e}")
        print(
            "AWS 認証情報が設定されていることを確認してください（aws configure または環境変数）"
        )
        sys.exit(1)

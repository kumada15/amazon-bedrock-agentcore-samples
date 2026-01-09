"""
AWS サービスおよびその他の共通操作用のユーティリティ関数。
"""

import boto3
import json
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError


def get_ssm_parameter(
    parameter_name: str,
    decrypt: bool = True,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None
) -> Optional[str]:
    """
    AWS Systems Manager Parameter Store からパラメータ値を取得します。

    Args:
        parameter_name (str): 取得するパラメータの名前
        decrypt (bool): SecureString パラメータを復号化するかどうか（デフォルト: True）
        region_name (str, optional): AWS リージョン名
        aws_access_key_id (str, optional): AWS アクセスキー ID
        aws_secret_access_key (str, optional): AWS シークレットアクセスキー
        aws_session_token (str, optional): AWS セッショントークン

    Returns:
        str: パラメータ値、または見つからないかエラーの場合は None

    Raises:
        NoCredentialsError: AWS 認証情報が設定されていない場合
        ClientError: AWS サービスエラーが発生した場合
    """
    try:
        # Create SSM client with optional credentials
        session_kwargs = {}
        if region_name:
            session_kwargs['region_name'] = region_name
        if aws_access_key_id:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        if aws_session_token:
            session_kwargs['aws_session_token'] = aws_session_token
            
        ssm_client = boto3.client('ssm', **session_kwargs)
        
        # Get parameter
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=decrypt
        )
        
        return response['Parameter']['Value']
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ParameterNotFound':
            print(f"パラメータ'{parameter_name}'が見つかりません")
            return None
        else:
            print(f"パラメータ'{parameter_name}'の取得中にAWSエラーが発生しました: {e}")
            raise
    except NoCredentialsError:
        print("AWS認証情報が見つかりません。認証情報を設定してください。")
        raise
    except Exception as e:
        print(f"パラメータ'{parameter_name}'の取得中に予期しないエラーが発生しました: {e}")
        return None


def get_ssm_parameters_by_path(
    parameter_path: str,
    recursive: bool = True,
    decrypt: bool = True,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None
) -> Dict[str, str]:
    """
    パスを指定して AWS Systems Manager Parameter Store から複数のパラメータを取得します。

    Args:
        parameter_path (str): 取得するパラメータのパスプレフィックス
        recursive (bool): パラメータを再帰的に取得するかどうか（デフォルト: True）
        decrypt (bool): SecureString パラメータを復号化するかどうか（デフォルト: True）
        region_name (str, optional): AWS リージョン名
        aws_access_key_id (str, optional): AWS アクセスキー ID
        aws_secret_access_key (str, optional): AWS シークレットアクセスキー
        aws_session_token (str, optional): AWS セッショントークン

    Returns:
        Dict[str, str]: パラメータ名から値へのマッピング辞書

    Raises:
        NoCredentialsError: AWS 認証情報が設定されていない場合
        ClientError: AWS サービスエラーが発生した場合
    """
    try:
        # Create SSM client with optional credentials
        session_kwargs = {}
        if region_name:
            session_kwargs['region_name'] = region_name
        if aws_access_key_id:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        if aws_session_token:
            session_kwargs['aws_session_token'] = aws_session_token
            
        ssm_client = boto3.client('ssm', **session_kwargs)
        
        parameters = {}
        paginator = ssm_client.get_paginator('get_parameters_by_path')
        
        # Paginate through all parameters
        for page in paginator.paginate(
            Path=parameter_path,
            Recursive=recursive,
            WithDecryption=decrypt
        ):
            for param in page['Parameters']:
                parameters[param['Name']] = param['Value']
        
        return parameters
        
    except ClientError as e:
        print(f"パス'{parameter_path}'からのパラメータ取得中にAWSエラーが発生しました: {e}")
        raise
    except NoCredentialsError:
        print("AWS認証情報が見つかりません。認証情報を設定してください。")
        raise
    except Exception as e:
        print(f"パス'{parameter_path}'からのパラメータ取得中に予期しないエラーが発生しました: {e}")
        return {}


def get_ssm_parameter_as_json(
    parameter_name: str,
    decrypt: bool = True,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    AWS Systems Manager Parameter Store からパラメータ値を取得し、JSON としてパースします。

    Args:
        parameter_name (str): 取得するパラメータの名前
        decrypt (bool): SecureString パラメータを復号化するかどうか（デフォルト: True）
        region_name (str, optional): AWS リージョン名
        aws_access_key_id (str, optional): AWS アクセスキー ID
        aws_secret_access_key (str, optional): AWS シークレットアクセスキー
        aws_session_token (str, optional): AWS セッショントークン

    Returns:
        Dict[str, Any]: パースされた JSON 値、または見つからないかエラーの場合は None

    Raises:
        NoCredentialsError: AWS 認証情報が設定されていない場合
        ClientError: AWS サービスエラーが発生した場合
        json.JSONDecodeError: パラメータ値が有効な JSON でない場合
    """
    try:
        parameter_value = get_ssm_parameter(
            parameter_name=parameter_name,
            decrypt=decrypt,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token
        )
        
        if parameter_value is None:
            return None
            
        return json.loads(parameter_value)
        
    except json.JSONDecodeError as e:
        print(f"パラメータ'{parameter_name}'からのJSONパース中にエラーが発生しました: {e}")
        return None
    except Exception as e:
        print(f"JSONパラメータ'{parameter_name}'の取得中に予期しないエラーが発生しました: {e}")
        return None


# Example usage:
if __name__ == "__main__":
    # Example 1: Get a single parameter
    api_key = get_ssm_parameter("/myapp/api-key")
    
    # Example 2: Get multiple parameters by path
    config_params = get_ssm_parameters_by_path("/myapp/config/")
    
    # Example 3: Get a JSON parameter
    db_config = get_ssm_parameter_as_json("/myapp/database-config")
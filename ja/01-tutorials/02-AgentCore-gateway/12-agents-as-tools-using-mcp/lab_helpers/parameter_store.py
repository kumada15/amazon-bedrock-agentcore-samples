"""
AWS Systems Manager Parameter Store 抽象化レイヤー
ワークショップパラメータのすべての読み取り/書き込み操作を処理します

複数の AWS アカウントとリージョンにわたってデプロイ値を保存・取得するための
クリーンなインターフェースを提供します。
"""

import boto3
import json
from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.config import AWS_REGION as DEFAULT_AWS_REGION

# Initialize SSM client (region will be specified per call if needed)
def get_ssm_client(region_name=None):
    """指定されたリージョンの SSM クライアントを取得、config の AWS_REGION がデフォルト"""
    if region_name:
        return boto3.client('ssm', region_name=region_name)
    return boto3.client('ssm', region_name=DEFAULT_AWS_REGION)


def put_parameter(key, value, description="", region_name=None, overwrite=True):
    """
    Store a parameter in Parameter Store

    Args:
        key: Parameter path (e.g., "/aiml301/lab-02/ecr-repository-uri")
        value: Parameter value (string)
        description: Human-readable description
        region_name: AWS region (defaults to AWS_REGION from config.py if None)
        overwrite: Replace existing parameter (default: True)

    Returns:
        Parameter version
    """
    try:
        ssm = get_ssm_client(region_name)

        # Determine if this is a sensitive parameter
        sensitive_keywords = ['password', 'secret', 'token', 'key', 'credential']
        is_sensitive = any(keyword in key.lower() for keyword in sensitive_keywords)
        
        # DEBUG: Log parameter write attempt
        effective_region = region_name if region_name else DEFAULT_AWS_REGION
        print(f"🔍 DEBUG: put_parameter() called")
        print(f"   Key: {key}")
        if is_sensitive:
            print(f"   Value: ****")
        else:
            print(f"   Value length: {len(str(value))} chars")
        print(f"   Region: {effective_region}")
        print(f"   Overwrite: {overwrite}")

        # Check if parameter already exists
        parameter_exists = False
        try:
            existing = ssm.get_parameter(Name=key)
            parameter_exists = True
            existing_value = existing['Parameter']['Value']
            if is_sensitive:
                print(f"   Existing value: ****")
            else:
                print(f"   Existing value found: {len(existing_value)} chars")
        except ssm.exceptions.ParameterNotFound:
            parameter_exists = False
            print(f"   Existing value: None")
        except Exception as e:
            # If error checking, proceed with put_parameter (will fail if appropriate)
            print(f"   Error checking existence: {e}")
            pass

        # Determine action and provide feedback
        if parameter_exists:
            if str(value) == existing_value:
                print(f"   → Action: SKIP (same value)")
                print(f"✓ Parameter already exists with same value: {key}")
                return existing['Parameter']['Version']
            elif not overwrite:
                print(f"   → Action: SKIP (overwrite=False)")
                print(f"⚠ Parameter exists but overwrite=False: {key}")
                return existing['Parameter']['Version']
            else:
                action = "UPDATED"
                print(f"   → Action: UPDATED")
        else:
            action = "CREATED"
            print(f"   → Action: CREATED")

        # Store parameter
        print(f"   🔄 Calling ssm.put_parameter()...")
        response = ssm.put_parameter(
            Name=key,
            Value=str(value),
            Description=description,
            Type='String',
            Overwrite=overwrite
        )
        version = response['Version']
        print(f"   ✅ put_parameter() succeeded")
        print(f"   Version: {version}")
        print(f"✓ Parameter {action}: {key}")
        return version
    except Exception as e:
        print(f"❌ Error storing parameter {key}: {e}")
        import traceback
        print(f"Traceback:")
        traceback.print_exc()
        raise


def get_parameter(key, default=None, region_name=None):
    """
    Retrieve a parameter from Parameter Store

    Args:
        key: Parameter path
        default: Default value if parameter not found
        region_name: AWS region (defaults to AWS_REGION from config.py if None)

    Returns:
        Parameter value or default
    """
    try:
        ssm = get_ssm_client(region_name)
        response = ssm.get_parameter(Name=key, WithDecryption=True)
        return response['Parameter']['Value']
    except ssm.exceptions.ParameterNotFound:
        if default is not None:
            print(f"⚠ Parameter not found: {key}, using default")
            return default
        else:
            effective_region = region_name if region_name else DEFAULT_AWS_REGION
            print(f"❌ Parameter not found: {key}")
            print(f"   Region: {effective_region}")
            print(f"   Check:")
            print(f"     • Is this parameter stored in Parameter Store?")
            print(f"     • Was the prerequisite lab (Lab-01) run first?")
            print(f"     • Is it in a different region?")
            raise
    except Exception as e:
        effective_region = region_name if region_name else DEFAULT_AWS_REGION
        print(f"❌ Error retrieving parameter {key}: {e}")
        print(f"   Region: {effective_region}")
        raise


def delete_parameter(key, region_name=None):
    """
    Delete a parameter from Parameter Store

    Args:
        key: Parameter path
        region_name: AWS region (uses default if None)
    """
    try:
        ssm = get_ssm_client(region_name)
        ssm.delete_parameter(Name=key)
        print(f"✓ Deleted parameter: {key}")
    except ssm.exceptions.ParameterNotFound:
        print(f"⚠ Parameter not found: {key}")
    except Exception as e:
        print(f"❌ Error deleting parameter {key}: {e}")
        raise


def get_parameters_by_path(path_prefix, region_name=None, recursive=True):
    """
    Retrieve all parameters under a path prefix

    Args:
        path_prefix: Parameter path prefix (e.g., "/aiml301/lab-02")
        region_name: AWS region (uses default if None)
        recursive: Include all subpaths

    Returns:
        Dictionary of {parameter_name: value}
    """
    try:
        ssm = get_ssm_client(region_name)
        parameters = {}
        paginator = ssm.get_paginator('get_parameters_by_path')

        for page in paginator.paginate(
            Path=path_prefix,
            Recursive=recursive,
            WithDecryption=True
        ):
            for param in page.get('Parameters', []):
                param_name = param['Name'].split('/')[-1]  # Get last part of path
                parameters[param_name] = param['Value']

        return parameters
    except Exception as e:
        print(f"❌ Error retrieving parameters from {path_prefix}: {e}")
        raise


def delete_parameters_by_path(path_prefix, region_name=None, recursive=True):
    """
    Delete all parameters under a path prefix (cleanup)

    Args:
        path_prefix: Parameter path prefix
        region_name: AWS region (uses default if None)
        recursive: Include all subpaths
    """
    try:
        ssm = get_ssm_client(region_name)
        params = get_parameters_by_path(path_prefix, region_name, recursive)

        for param_name in params.keys():
            full_path = f"{path_prefix}/{param_name}".replace('//', '/')
            delete_parameter(full_path, region_name)

        print(f"✓ Cleaned up {len(params)} parameters under {path_prefix}")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        raise


# Convenience functions for common operations

def store_workshop_metadata(account_id, region, region_name=None):
    """ワークショップレベルのメタデータを保存"""
    put_parameter(
        PARAMETER_PATHS["workshop"]["account_id"],
        account_id,
        description="AWS Account ID for this workshop deployment",
        region_name=region_name
    )
    put_parameter(
        PARAMETER_PATHS["workshop"]["region"],
        region,
        description="AWS Region for this workshop deployment",
        region_name=region_name
    )


def get_lab_02_config(region_name=None):
    """Parameter Store から Lab 02 のすべての設定を取得"""
    return get_parameters_by_path(
        "/aiml301/lab-02",
        region_name=region_name,
        recursive=False
    )


def get_lab_03_config(region_name=None):
    """Parameter Store から Lab 03 のすべての設定を取得"""
    return get_parameters_by_path(
        "/aiml301/lab-03",
        region_name=region_name,
        recursive=False
    )


def get_all_workshop_parameters(region_name=None):
    """すべてのワークショップパラメータを取得"""
    return get_parameters_by_path(
        "/aiml301",
        region_name=region_name,
        recursive=True
    )


def check_lab_prerequisites(lab_number, region_name=None):
    """
    Check if prerequisites for a lab are available

    Args:
        lab_number: Lab number (1, 2, 3, etc.)
        region_name: AWS region (defaults to AWS_REGION from config.py if None)

    Returns:
        Dict with 'ready' (bool) and 'missing' (list of missing parameters)
    """
    prerequisites = {
        1: [],  # Lab-01 has no prerequisites
        2: [PARAMETER_PATHS['cognito']['user_pool_id']],  # Lab-02 needs Cognito from Lab-01
        3: [  # Lab-03 needs Cognito from Lab-01 AND optionally Lab-02
            PARAMETER_PATHS['cognito']['user_pool_id'],
            PARAMETER_PATHS['cognito']['m2m_client_id'],
            PARAMETER_PATHS['cognito']['user_auth_client_id'],
        ],
        4: [PARAMETER_PATHS['cognito']['user_pool_id']],  # Lab-04 needs Cognito
    }

    required_params = prerequisites.get(lab_number, [])
    missing = []

    for param_path in required_params:
        try:
            get_parameter(param_path, region_name=region_name)
        except Exception:
            missing.append(param_path)

    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "lab": lab_number,
        "required": required_params
    }

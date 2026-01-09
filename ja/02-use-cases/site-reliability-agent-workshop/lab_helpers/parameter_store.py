"""
AWS Systems Manager Parameter Store 抽象化レイヤー
ワークショップパラメータのすべての読み書き操作を処理

複数の AWS アカウントとリージョンにわたるデプロイ値の保存と取得のための
クリーンなインターフェースを提供します。
"""

import boto3
from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.config import AWS_REGION as DEFAULT_AWS_REGION

# SSM クライアントの初期化（必要に応じて呼び出しごとにリージョンを指定）
def get_ssm_client(region_name=None):
    """指定されたリージョン用の SSM クライアントを取得、デフォルトは config の AWS_REGION"""
    if region_name:
        return boto3.client('ssm', region_name=region_name)
    return boto3.client('ssm', region_name=DEFAULT_AWS_REGION)


def put_parameter(key, value, description="", region_name=None, overwrite=True):
    """
    Parameter Store にパラメータを保存

    Args:
        key: パラメータパス（例: "/aiml301/lab-02/ecr-repository-uri"）
        value: パラメータ値（文字列）
        description: 人間が読める説明
        region_name: AWS リージョン（None の場合は config.py の AWS_REGION をデフォルトとして使用）
        overwrite: 既存のパラメータを置き換え（デフォルト: True）

    Returns:
        パラメータのバージョン
    """
    try:
        ssm = get_ssm_client(region_name)

        # 機密パラメータかどうかを判定
        sensitive_keywords = ['password', 'secret', 'token', 'key', 'credential']
        is_sensitive = any(keyword in key.lower() for keyword in sensitive_keywords)
        
        # デバッグ: パラメータ書き込み試行をログ出力
        effective_region = region_name if region_name else DEFAULT_AWS_REGION
        print(f"🔍 デバッグ: put_parameter() 呼び出し")
        if is_sensitive:
            print("   値: ****")
        else:
            print(f"   値の長さ: {len(str(value))} 文字")
        print(f"   リージョン: {effective_region}")
        print(f"   上書き: {overwrite}")

        # パラメータが既に存在するか確認
        parameter_exists = False
        try:
            existing = ssm.get_parameter(Name=key)
            parameter_exists = True
            existing_value = existing['Parameter']['Value']
            if is_sensitive:
                print("   既存の値: ****")
            else:
                print(f"   既存の値が見つかりました: {len(existing_value)} 文字")
        except ssm.exceptions.ParameterNotFound:
            parameter_exists = False
            print("   既存の値: なし")
        except Exception as e:
            # 確認中のエラーの場合、put_parameter を続行（必要に応じて失敗）
            print(f"   存在確認中にエラー: {e}")
            pass

        # アクションを決定してフィードバックを提供
        if parameter_exists:
            if str(value) == existing_value:
                print("   → アクション: スキップ (同じ値)")
                print("✓ パラメータは同じ値で既に存在します。")
                return existing['Parameter']['Version']
            elif not overwrite:
                print("   → アクション: スキップ (overwrite=False)")
                print("⚠ パラメータは存在しますが overwrite=False です")
                return existing['Parameter']['Version']
            else:
                print("   → アクション: 更新")
        else:
            print("   → アクション: 作成")

        # パラメータを保存
        print("   🔄 ssm.put_parameter() を呼び出し中...")
        response = ssm.put_parameter(
            Name=key,
            Value=str(value),
            Description=description,
            Type='String',
            Overwrite=overwrite
        )
        version = response['Version']
        print("   ✅ put_parameter() が成功しました")
        print(f"   バージョン: {version}")
        return version
    except Exception as e:
        print(f"❌ パラメータの保存中にエラー: {e}")
        import traceback
        print("トレースバック:")
        traceback.print_exc()
        raise


def get_parameter(key, default=None, region_name=None):
    """
    Parameter Store からパラメータを取得

    Args:
        key: パラメータパス
        default: パラメータが見つからない場合のデフォルト値
        region_name: AWS リージョン（None の場合は config.py の AWS_REGION をデフォルトとして使用）

    Returns:
        パラメータ値またはデフォルト
    """
    try:
        ssm = get_ssm_client(region_name)
        response = ssm.get_parameter(Name=key, WithDecryption=True)
        return response['Parameter']['Value']
    except ssm.exceptions.ParameterNotFound:
        if default is not None:
            print("⚠ パラメータが見つかりません。デフォルト値を使用します")
            return default
        else:
            effective_region = region_name if region_name else DEFAULT_AWS_REGION
            print("❌ パラメータが見つかりません。")
            print(f"   リージョン: {effective_region}")
            print("   確認事項:")
            print("     • このパラメータは Parameter Store に保存されていますか?")
            print("     • 前提となるラボ (Lab-01) は先に実行されましたか?")
            print("     • 別のリージョンにありますか?")
            raise
    except Exception as e:
        effective_region = region_name if region_name else DEFAULT_AWS_REGION
        print(f"❌ パラメータの取得中にエラー: {e}")
        print(f"   リージョン: {effective_region}")
        raise


def delete_parameter(key, region_name=None):
    """
    Parameter Store からパラメータを削除

    Args:
        key: パラメータパス
        region_name: AWS リージョン（None の場合はデフォルトを使用）
    """
    try:
        ssm = get_ssm_client(region_name)
        ssm.delete_parameter(Name=key)
        print(f"✓ パラメータを削除しました: {key}")
    except ssm.exceptions.ParameterNotFound:
        print(f"⚠ パラメータが見つかりません: {key}")
    except Exception as e:
        print(f"❌ パラメータ {key} の削除中にエラー: {e}")
        raise


def get_parameters_by_path(path_prefix, region_name=None, recursive=True):
    """
    パスプレフィックス配下のすべてのパラメータを取得

    Args:
        path_prefix: パラメータパスのプレフィックス（例: "/aiml301/lab-02"）
        region_name: AWS リージョン（None の場合はデフォルトを使用）
        recursive: すべてのサブパスを含める

    Returns:
        {パラメータ名: 値} の辞書
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
        print(f"❌ {path_prefix} からのパラメータ取得中にエラー: {e}")
        raise


def delete_parameters_by_path(path_prefix, region_name=None, recursive=True):
    """
    パスプレフィックス配下のすべてのパラメータを削除（クリーンアップ）

    Args:
        path_prefix: パラメータパスのプレフィックス
        region_name: AWS リージョン（None の場合はデフォルトを使用）
        recursive: すべてのサブパスを含める
    """
    try:
        ssm = get_ssm_client(region_name)
        params = get_parameters_by_path(path_prefix, region_name, recursive)

        for param_name in params.keys():
            full_path = f"{path_prefix}/{param_name}".replace('//', '/')
            delete_parameter(full_path, region_name)

        print(f"✓ {path_prefix} 配下の {len(params)} 件のパラメータをクリーンアップしました")
    except Exception as e:
        print(f"❌ クリーンアップ中にエラー: {e}")
        raise


# よく使う操作のための便利関数

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
    ラボの前提条件が利用可能かどうかを確認

    Args:
        lab_number: ラボ番号（1、2、3 など）
        region_name: AWS リージョン（None の場合は config.py の AWS_REGION をデフォルトとして使用）

    Returns:
        'ready'（bool）と 'missing'（不足しているパラメータのリスト）を含む辞書
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

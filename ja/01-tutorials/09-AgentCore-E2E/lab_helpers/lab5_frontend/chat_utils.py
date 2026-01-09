import json
import os
import re
from typing import Any, Dict

import boto3
import yaml


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
    ssm = boto3.client("ssm")

    put_params = {
        "Name": name,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": True,
    }

    if with_encryption:
        put_params["Type"] = "SecureString"

    ssm.put_parameter(**put_params)


def delete_ssm_parameter(name: str) -> None:
    ssm = boto3.client("ssm")
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        pass


def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def get_aws_region() -> str:
    session = boto3.session.Session()
    return session.region_name


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_cognito_client_secret() -> str:
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/customersupport/agentcore/pool_id"),
        ClientId=get_ssm_parameter("/app/customersupport/agentcore/client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def read_config(file_path: str) -> Dict[str, Any]:
    """
    ファイルパスから設定を読み込みます。JSON、YAML、YML フォーマットをサポートします。

    Args:
        file_path (str): 設定ファイルへのパス

    Returns:
        Dict[str, Any]: 辞書としての設定データ

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: ファイルフォーマットがサポートされていないか無効な場合
        yaml.YAMLError: YAML パースに失敗した場合
        json.JSONDecodeError: JSON パースに失敗した場合
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # ファイル拡張子を取得してフォーマットを判定
    _, ext = os.path.splitext(file_path.lower())

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if ext == ".json":
                return json.load(file)
            elif ext in [".yaml", ".yml"]:
                return yaml.safe_load(file)
            else:
                # JSON を先に試し、次に YAML を試してフォーマットを自動検出
                content = file.read()
                file.seek(0)

                # JSON を先に試す
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # YAML を試す
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        raise ValueError(
                            f"Unsupported configuration file format: {ext}. "
                            f"Supported formats: .json, .yaml, .yml"
                        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")


def make_urls_clickable(text):
    """テキスト内の URL をクリック可能な HTML リンクに変換"""
    url_pattern = r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?"

    def replace_url(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank" style="color:#4fc3f7;text-decoration:underline;">{url}</a>'

    return re.sub(url_pattern, replace_url, text)


def create_safe_markdown_text(text, message_placeholder):
    """適切なエンコーディングと改行処理でセーフな Markdown テキストを作成"""
    # まず安全のためにエンコード/デコード
    safe_text = text.encode("utf-16", "surrogatepass").decode("utf-16")

    # 適切なレンダリングのために改行を HTML break に変換
    # これは実際の改行とエスケープされた改行の両方を処理
    safe_text = safe_text.replace("\n", "<br>")
    safe_text = safe_text.replace("\\n", "<br>")

    message_placeholder.markdown(safe_text, unsafe_allow_html=True)

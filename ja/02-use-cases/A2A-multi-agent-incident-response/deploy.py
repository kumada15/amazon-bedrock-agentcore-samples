#!/usr/bin/env python3
"""
A2A マルチエージェント インシデント対応システムの対話式デプロイスクリプト。
このスクリプトは必要なすべてのパラメータを収集し、.a2a.config に保存します。
"""

import sys
import uuid
import yaml
import subprocess
import json
import time
import re
import getpass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


class Colors:
    """ターミナル出力用の ANSI カラーコード"""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


# Thread-safe print lock for parallel deployments
print_lock = Lock()


def print_header(text: str, thread_safe: bool = False):
    """フォーマットされたヘッダーを表示"""
    output = f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}\n"
    output += f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.END}\n"
    output += f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}\n"

    if thread_safe:
        with print_lock:
            print(output, end="")
    else:
        print(output, end="")


def print_info(text: str, thread_safe: bool = False):
    """情報メッセージを表示"""
    output = f"{Colors.CYAN}ℹ {text}{Colors.END}"
    if thread_safe:
        with print_lock:
            print(output)
    else:
        print(output)


def print_success(text: str, thread_safe: bool = False):
    """成功メッセージを表示"""
    output = f"{Colors.GREEN}✓ {text}{Colors.END}"
    if thread_safe:
        with print_lock:
            print(output)
    else:
        print(output)


def print_warning(text: str, thread_safe: bool = False):
    """警告メッセージを表示"""
    output = f"{Colors.YELLOW}⚠ {text}{Colors.END}"
    if thread_safe:
        with print_lock:
            print(output)
    else:
        print(output)


def print_error(text: str, thread_safe: bool = False):
    """エラーメッセージを表示"""
    output = f"{Colors.RED}✗ {text}{Colors.END}"
    if thread_safe:
        with print_lock:
            print(output)
    else:
        print(output)


def get_input(prompt: str, default: Optional[str] = None, required: bool = True) -> str:
    """オプションのデフォルト値を持つユーザー入力を取得"""
    if default:
        display_prompt = f"{Colors.BLUE}{prompt} [{Colors.GREEN}{default}{Colors.BLUE}]: {Colors.END}"
    else:
        display_prompt = f"{Colors.BLUE}{prompt}: {Colors.END}"

    while True:
        value = input(display_prompt).strip()

        if value:
            return value
        elif default:
            return default
        elif not required:
            return ""
        else:
            print_error("この項目は必須です。値を入力してください。")


def get_secret(prompt: str, required: bool = True) -> str:
    """機密情報（API キーなど）を取得"""
    display_prompt = f"{Colors.BLUE}{prompt}: {Colors.END}"

    while True:
        value = getpass.getpass(display_prompt).strip()

        if value:
            return value
        elif not required:
            return ""
        else:
            print_error("この項目は必須です。値を入力してください。")


def generate_bucket_name(account_id: str = None) -> str:
    """一意の S3 バケット名を生成"""
    unique_id = str(uuid.uuid4())[:8]
    # Include account ID for better uniqueness if available
    if account_id:
        return f"a2a-smithy-models-{account_id}-{unique_id}"
    return f"a2a-smithy-models-{unique_id}"


def generate_cognito_domain_name(account_id: str = None) -> str:
    """一意の Cognito ドメイン名を生成"""
    unique_id = str(uuid.uuid4())[:8]
    # Include account ID for better uniqueness if available
    if account_id:
        return f"agentcore-m2m-{account_id}-{unique_id}"
    return f"agentcore-m2m-{unique_id}"


def validate_bucket_name(bucket_name: str) -> Tuple[bool, str]:
    """AWS ルールに従って S3 バケット名を検証"""
    if not bucket_name:
        return (False, "Bucket name cannot be empty")

    if len(bucket_name) < 3 or len(bucket_name) > 63:
        return (False, "Bucket name must be between 3 and 63 characters")

    if not bucket_name[0].isalnum() or not bucket_name[-1].isalnum():
        return (False, "Bucket name must begin and end with a letter or number")

    # Check for invalid characters and patterns
    if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", bucket_name):
        return (
            False,
            "Bucket name must contain only lowercase letters, numbers, and hyphens",
        )

    if ".." in bucket_name or ".-" in bucket_name or "-." in bucket_name:
        return (
            False,
            "Bucket name cannot contain consecutive periods or period-hyphen combinations",
        )

    return (True, "Valid bucket name")


def check_s3_bucket_exists(bucket_name: str, region: str) -> bool:
    """S3 バケットが既に存在するか確認"""
    success, output = run_command(
        ["aws", "s3api", "head-bucket", "--bucket", bucket_name, "--region", region]
    )
    return success


def validate_cognito_domain_name(domain_name: str) -> Tuple[bool, str]:
    """Cognito ユーザープールのドメイン名を検証"""
    if not domain_name:
        return (False, "Domain name cannot be empty")

    if len(domain_name) < 1 or len(domain_name) > 63:
        return (False, "Domain name must be between 1 and 63 characters")

    if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", domain_name):
        return (
            False,
            "Domain name must contain only lowercase letters, numbers, and hyphens, and must start and end with alphanumeric",
        )

    return (True, "Valid domain name")


def validate_stack_name(stack_name: str) -> Tuple[bool, str]:
    """CloudFormation スタック名を検証"""
    if not stack_name:
        return (False, "Stack name cannot be empty")

    if len(stack_name) > 128:
        return (False, "Stack name must be 128 characters or fewer")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9\-]*$", stack_name):
        return (
            False,
            "Stack name must start with a letter and contain only alphanumeric characters and hyphens",
        )

    return (True, "Valid stack name")


def load_existing_config(config_path: Path) -> Dict[str, Any]:
    """既存の設定が存在する場合は読み込む"""
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(config: Dict[str, Any], config_path: Path):
    """設定を YAML ファイルに保存"""
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print_success(f"Configuration saved to {config_path}")


def run_command(
    cmd: list, capture_output: bool = True, timeout: int = 10
) -> Tuple[bool, str]:
    """シェルコマンドを実行し、(成功, 出力) を返す"""
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, timeout=timeout, check=False
        )
        return (result.returncode == 0, result.stdout.strip() if capture_output else "")
    except subprocess.TimeoutExpired:
        return (False, f"Command timed out after {timeout} seconds")
    except FileNotFoundError:
        return (False, f"Command not found: {cmd[0]}")
    except Exception as e:
        return (False, str(e))


def check_aws_cli() -> bool:
    """AWS CLI がインストールされているか確認"""
    success, output = run_command(["aws", "--version"])
    if success:
        print_success(f"AWS CLI がインストールされています: {output.split()[0]}")
        return True
    else:
        print_error("AWS CLI がインストールされていません")
        print_info(
            "AWS CLI のインストール: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        )
        return False


def check_aws_credentials() -> bool:
    """AWS 認証情報が設定され有効か確認"""
    success, output = run_command(["aws", "sts", "get-caller-identity"])
    if success:
        try:
            identity = json.loads(output)
            print_success("AWS 認証情報は有効です")
            print_info(f"  アカウント: {identity.get('Account', 'N/A')}")
            print_info(f"  ユーザー/ロール: {identity.get('Arn', 'N/A').split('/')[-1]}")
            return True
        except json.JSONDecodeError:
            print_error("AWS ID の解析に失敗しました")
            return False
    else:
        print_error("AWS 認証情報が設定されていないか無効です")
        print_info("AWS CLI を設定: aws configure")
        return False


def check_aws_region() -> Tuple[bool, Optional[str]]:
    """AWS リージョンが設定され us-west-2 であるか確認"""
    success, output = run_command(["aws", "configure", "get", "region"])
    if success and output:
        region = output.strip()
        if region == "us-west-2":
            print_success("AWS リージョンは us-west-2 に正しく設定されています")
            return (True, region)
        else:
            print_error(f"AWS リージョンが '{region}' に設定されていますが、'us-west-2' である必要があります")
            print_info("このソリューションは us-west-2 でのみサポートされています")
            print_info("リージョンを変更: aws configure set region us-west-2")
            return (False, region)
    else:
        print_error("AWS リージョンが設定されていません")
        print_info("リージョンを設定: aws configure set region us-west-2")
        return (False, None)


def check_bedrock_model_access() -> bool:
    """Bedrock モデルへのアクセスが有効か確認"""
    print_info("Bedrock モデルアクセスを確認中...")
    success, output = run_command(
        ["aws", "bedrock", "list-foundation-models", "--region", "us-west-2"]
    )
    if success:
        print_success("Bedrock API にアクセス可能です")
        return True
    else:
        print_warning(
            "Bedrock へのアクセスを確認できませんでした（権限の問題の可能性があります）"
        )
        return True  # Don't fail on this check, just warn


def run_pre_checks() -> Tuple[bool, Optional[str]]:
    """すべてのデプロイ前チェックを実行し、(成功, account_id) を返す"""
    print_header("デプロイ前チェック")
    print_info("前提条件を確認中...\n")

    checks_passed = True
    account_id = None

    # Check AWS CLI
    if not check_aws_cli():
        checks_passed = False

    print()

    # Check AWS credentials and get account ID
    success, output = run_command(["aws", "sts", "get-caller-identity"])
    if success:
        try:
            identity = json.loads(output)
            account_id = identity.get("Account")
            print_success("AWS 認証情報は有効です")
            print_info(f"  アカウント: {account_id or 'N/A'}")
            print_info(f"  ユーザー/ロール: {identity.get('Arn', 'N/A').split('/')[-1]}")
        except json.JSONDecodeError:
            print_error("AWS ID の解析に失敗しました")
            checks_passed = False
    else:
        print_error("AWS 認証情報が設定されていないか無効です")
        print_info("AWS CLI を設定: aws configure")
        checks_passed = False

    print()

    # Check AWS region
    region_ok, region = check_aws_region()
    if not region_ok:
        checks_passed = False

    print()

    # Check Bedrock access (warning only)
    check_bedrock_model_access()

    print()

    if not checks_passed:
        print_error(
            "デプロイ前チェックに失敗しました。続行する前に上記の問題を修正してください。"
        )
        return (False, None)

    print_success("すべてのデプロイ前チェックに合格しました！")
    return (True, account_id)


def collect_deployment_parameters(account_id: str = None) -> Dict[str, Any]:
    """対話形式ですべてのデプロイパラメータを収集"""

    config_path = Path(".a2a.config")
    existing_config = load_existing_config(config_path)

    print_header("A2A マルチエージェント インシデント対応 - デプロイ設定")

    print_info("このスクリプトはデプロイに必要なすべてのパラメータの設定をサポートします。")
    print_info("Enter キーを押すとデフォルト値（緑色の括弧内に表示）が適用されます。\n")

    # Check if config exists
    if existing_config:
        print_warning(f"{config_path} に既存の設定が見つかりました")
        use_existing = get_input(
            "Do you want to use existing values as defaults? (yes/no)",
            default="yes",
            required=True,
        ).lower() in ["yes", "y"]
        print()
    else:
        use_existing = False

    config = {}

    # AWS Configuration (region is fixed to us-west-2)
    print_header("AWS 設定")
    config["aws"] = {
        "region": "us-west-2",  # Fixed to us-west-2 as verified in pre-checks
        "bedrock_model_id": get_input(
            "Bedrock Model ID",
            default=(
                existing_config.get("aws", {}).get(
                    "bedrock_model_id",
                    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                )
                if use_existing
                else "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
            ),
            required=True,
        ),
    }
    print_info("リージョンは us-west-2 に固定されています（デプロイ前チェックで確認済み）")

    # Stack Names with validation
    print_header("CloudFormation スタック名")
    config["stacks"] = {}

    stack_names = {
        "cognito": ("Cognito Stack Name", "cognito-stack-a2a"),
        "monitoring_agent": ("Monitoring Agent Stack Name", "monitor-agent-a2a"),
        "web_search_agent": ("Web Search Agent Stack Name", "web-search-agent-a2a"),
        "host_agent": ("Host Agent Stack Name", "host-agent-a2a"),
    }

    for key, (prompt, default_name) in stack_names.items():
        while True:
            stack_name = get_input(
                prompt,
                default=(
                    existing_config.get("stacks", {}).get(key, default_name)
                    if use_existing
                    else default_name
                ),
                required=True,
            )
            is_valid, message = validate_stack_name(stack_name)
            if is_valid:
                config["stacks"][key] = stack_name
                break
            else:
                print_error(f"無効なスタック名: {message}")

    # Cognito Domain Name with validation
    print_header("Cognito 設定")
    default_cognito_domain = (
        existing_config.get("cognito", {}).get("domain_name")
        if use_existing
        else generate_cognito_domain_name(account_id)
    )

    while True:
        domain_name = get_input(
            "Cognito User Pool Domain Name",
            default=default_cognito_domain,
            required=True,
        )
        is_valid, message = validate_cognito_domain_name(domain_name)
        if is_valid:
            config["cognito"] = {"domain_name": domain_name}
            print_info(
                "This unique domain prevents conflicts with existing Cognito User Pools"
            )
            break
        else:
            print_error(f"無効なドメイン名: {message}")

    # Admin User Configuration
    print()
    print_info("Cognito ユーザープールの管理者ユーザー設定")
    print_info("このユーザーはユーザープールに自動的に作成されます")
    print()

    admin_email = get_input(
        "Admin User Email",
        default=(
            existing_config.get("cognito", {}).get("admin_email")
            if use_existing
            else ""
        ),
        required=True,
    )

    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    while not re.match(email_pattern, admin_email):
        print_error("メール形式が無効です。有効なメールアドレスを入力してください。")
        admin_email = get_input("Admin User Email", required=True)

    config["cognito"]["admin_email"] = admin_email

    print_info("管理者パスワード（オプション - 空欄の場合は一時パスワードが自動生成されます）")
    admin_password = get_secret(
        "Admin User Password (press Enter to skip)",
        required=False,
    )

    config["cognito"]["admin_password"] = admin_password if admin_password else ""

    # S3 Bucket for Smithy Models with validation
    print_header("S3 設定")
    default_bucket = (
        existing_config.get("s3", {}).get("smithy_models_bucket")
        if use_existing
        else generate_bucket_name(account_id)
    )

    while True:
        bucket_name = get_input(
            "S3 Bucket Name for Smithy Models", default=default_bucket, required=True
        )
        is_valid, message = validate_bucket_name(bucket_name)
        if is_valid:
            # Check if bucket already exists
            if check_s3_bucket_exists(bucket_name, "us-west-2"):
                print_warning(
                    f"バケット '{bucket_name}' は既に存在します。所有している場合は使用できます。"
                )
                use_existing_bucket = get_input(
                    "Use this existing bucket? (yes/no)", default="yes", required=True
                ).lower() in ["yes", "y"]
                if use_existing_bucket:
                    config["s3"] = {"smithy_models_bucket": bucket_name}
                    break
                else:
                    continue
            else:
                config["s3"] = {"smithy_models_bucket": bucket_name}
                break
        else:
            print_error(f"無効なバケット名: {message}")

    # GitHub Configuration
    print_header("GitHub 設定")
    config["github"] = {
        "url": get_input(
            "GitHub Repository URL",
            default=(
                existing_config.get("github", {}).get(
                    "url",
                    "https://github.com/awslabs/amazon-bedrock-agentcore-samples.git",
                )
                if use_existing
                else "https://github.com/awslabs/amazon-bedrock-agentcore-samples.git"
            ),
            required=True,
        ),
        # Agent directories are taken from CloudFormation defaults - not configurable
        "monitoring_agent_directory": "monitoring_agent",
        "web_search_agent_directory": "web_search_openai_agents",
        "host_agent_directory": "host_adk_agent",
    }
    print_info(
        "エージェントディレクトリは CloudFormation のデフォルト値を使用します（monitoring_agent, web_search_openai_agents, host_adk_agent）"
    )

    # API Keys
    print_header("API キー設定")
    print_warning("API キーは .a2a.config に保存されます - このファイルは安全に管理してください！")
    print_info("入力はセキュリティのため非表示になります。キーを貼り付けて Enter を押してください。\n")

    # Check if we should ask for API keys
    ask_for_keys = True
    if use_existing and existing_config.get("api_keys"):
        print_info("既存の API キーが設定に見つかりました。")
        update_keys = get_input(
            "Do you want to update API keys? (yes/no)", default="no", required=True
        ).lower() in ["yes", "y"]
        ask_for_keys = update_keys
        print()

    if ask_for_keys:
        config["api_keys"] = {
            "openai": get_secret("OpenAI API Key", required=True),
            "openai_model": get_input(
                "OpenAI Model ID",
                default=(
                    existing_config.get("api_keys", {}).get(
                        "openai_model", "gpt-4o-2024-08-06"
                    )
                    if use_existing
                    else "gpt-4o-2024-08-06"
                ),
                required=True,
            ),
            "tavily": get_secret("Tavily API Key", required=True),
            "google": get_secret("Google API Key (for ADK)", required=True),
            "google_model": get_input(
                "Google Model ID",
                default=(
                    existing_config.get("api_keys", {}).get(
                        "google_model", "gemini-2.5-flash"
                    )
                    if use_existing
                    else "gemini-2.5-flash"
                ),
                required=True,
            ),
        }
    else:
        config["api_keys"] = existing_config.get("api_keys", {})

    return config


def display_configuration(config: Dict[str, Any]):
    """収集した設定を表示"""
    print_header("設定サマリー")

    print(f"{Colors.BOLD}AWS 設定:{Colors.END}")
    print(f"  リージョン: {config['aws']['region']}")
    print(f"  Bedrock モデル ID: {config['aws']['bedrock_model_id']}")

    print(f"\n{Colors.BOLD}CloudFormation スタック:{Colors.END}")
    print(f"  Cognito: {config['stacks']['cognito']}")
    print(f"  監視エージェント: {config['stacks']['monitoring_agent']}")
    print(f"  Web 検索エージェント: {config['stacks']['web_search_agent']}")
    print(f"  ホストエージェント: {config['stacks']['host_agent']}")

    print(f"\n{Colors.BOLD}Cognito 設定:{Colors.END}")
    print(f"  ユーザープールドメイン: {config['cognito']['domain_name']}")
    print(f"  管理者ユーザーメール: {config['cognito']['admin_email']}")
    if config['cognito'].get('admin_password'):
        print(f"  管理者ユーザーパスワード: {'*' * 20} (設定済み)")
    else:
        print("  管理者ユーザーパスワード: (自動生成された一時パスワードがメールで送信されます)")

    print(f"\n{Colors.BOLD}S3 設定:{Colors.END}")
    print(f"  Smithy モデルバケット: {config['s3']['smithy_models_bucket']}")

    print(f"\n{Colors.BOLD}GitHub 設定:{Colors.END}")
    print(f"  リポジトリ URL: {config['github']['url']}")
    print(f"  監視エージェントディレクトリ: {config['github']['monitoring_agent_directory']}")
    print(f"  Web 検索エージェントディレクトリ: {config['github']['web_search_agent_directory']}")
    print(f"  ホストエージェントディレクトリ: {config['github']['host_agent_directory']}")

    print(f"\n{Colors.BOLD}API キー:{Colors.END}")
    print(f"  OpenAI API キー: {'*' * 20} (設定済み)")
    print(f"  Tavily API キー: {'*' * 20} (設定済み)")
    print(f"  Google API キー: {'*' * 20} (設定済み)")

    print()


def wait_for_stack(
    stack_name: str, region: str, operation: str = "create", thread_safe: bool = False
) -> bool:
    """CloudFormation スタック操作の完了を待機"""
    print_info(
        f"スタック '{stack_name}' の {operation} 完了を待機中...",
        thread_safe=thread_safe,
    )

    max_wait_time = 1800  # 30 minutes
    wait_interval = 15  # 15 seconds
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        success, output = run_command(
            [
                "aws",
                "cloudformation",
                "describe-stacks",
                "--stack-name",
                stack_name,
                "--region",
                region,
                "--query",
                "Stacks[0].StackStatus",
                "--output",
                "text",
            ]
        )

        if success:
            status = output.strip()

            # Check for completion statuses
            if operation == "create" and status == "CREATE_COMPLETE":
                print_success(
                    f"スタック '{stack_name}' が正常に作成されました！",
                    thread_safe=thread_safe,
                )
                return True
            elif operation == "create" and status == "CREATE_FAILED":
                print_error(
                    f"スタック '{stack_name}' の作成に失敗しました！", thread_safe=thread_safe
                )
                return False
            elif operation == "create" and status == "ROLLBACK_COMPLETE":
                print_error(
                    f"スタック '{stack_name}' の作成に失敗しロールバックされました！",
                    thread_safe=thread_safe,
                )
                return False
            elif operation == "create" and status == "ROLLBACK_IN_PROGRESS":
                print_warning(
                    f"スタック '{stack_name}' がロールバック中... ステータス: {status}",
                    thread_safe=thread_safe,
                )
            else:
                print_info(
                    f"[{stack_name}] ステータス: {status} (待機中...)",
                    thread_safe=thread_safe,
                )

        time.sleep(wait_interval)
        elapsed_time += wait_interval

    print_error(
        f"スタック '{stack_name}' の待機がタイムアウトしました（{max_wait_time}秒待機）",
        thread_safe=thread_safe,
    )
    return False


def create_s3_bucket_and_upload(config: Dict[str, Any]) -> bool:
    """S3 バケットを作成し Smithy モデルをアップロード"""
    print_header("ステップ 0: S3 バケットの作成と Smithy モデルのアップロード")

    bucket_name = config["s3"]["smithy_models_bucket"]
    region = config["aws"]["region"]

    # Check if bucket already exists
    if check_s3_bucket_exists(bucket_name, region):
        print_info(f"バケット '{bucket_name}' は既に存在するため、作成をスキップします")
    else:
        print_info(f"S3 バケットを作成中: {bucket_name}")
        success, output = run_command(
            ["aws", "s3", "mb", f"s3://{bucket_name}", "--region", region]
        )

        if success:
            print_success(f"S3 バケット '{bucket_name}' が正常に作成されました！")
        else:
            print_error(f"S3 バケットの作成に失敗しました: {output}")
            return False

    # Upload Smithy model
    smithy_model_path = "cloudformation/smithy-models/monitoring-service.json"
    s3_key = "smithy-models/monitoring-service.json"

    if not Path(smithy_model_path).exists():
        print_error(f"Smithy モデルファイルが見つかりません: {smithy_model_path}")
        return False

    print_info(f"Smithy モデルをアップロード中: s3://{bucket_name}/{s3_key}")
    success, output = run_command(
        [
            "aws",
            "s3",
            "cp",
            smithy_model_path,
            f"s3://{bucket_name}/{s3_key}",
            "--region",
            region,
        ]
    )

    if success:
        print_success("Smithy モデルが正常にアップロードされました！")
        return True
    else:
        print_error(f"Smithy モデルのアップロードに失敗しました: {output}")
        return False


def upload_template_to_s3(
    template_file: str, bucket_name: str, region: str, thread_safe: bool = False
) -> Optional[str]:
    """CloudFormation テンプレートを S3 にアップロードし、S3 URL を返す"""
    template_name = Path(template_file).name
    s3_key = f"cloudformation-templates/{template_name}"
    s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"

    print_info(f"テンプレート {template_name} を S3 にアップロード中...", thread_safe=thread_safe)

    success, output = run_command(
        [
            "aws",
            "s3",
            "cp",
            template_file,
            f"s3://{bucket_name}/{s3_key}",
            "--region",
            region,
        ]
    )

    if success:
        print_success(f"テンプレートを S3 にアップロードしました: {s3_key}", thread_safe=thread_safe)
        return s3_url
    else:
        print_error(
            f"テンプレートの S3 へのアップロードに失敗しました: {output}", thread_safe=thread_safe
        )
        return None


def deploy_stack(
    stack_name: str,
    template_file: str,
    parameters: list,
    region: str,
    bucket_name: Optional[str] = None,
    description: str = "",
    thread_safe: bool = False,
) -> bool:
    """CloudFormation スタックをデプロイする汎用関数（常に S3 経由）"""
    if description:
        print_info(description, thread_safe=thread_safe)

    print_info(f"CloudFormation スタックを作成中: {stack_name}", thread_safe=thread_safe)

    # Always use S3 for consistency and to avoid size limits
    if not bucket_name:
        print_error(
            "スタックのデプロイには S3 バケットが必要ですが、指定されていません。",
            thread_safe=thread_safe,
        )
        return False

    print_info("デプロイ前にテンプレートを S3 にアップロード中", thread_safe=thread_safe)
    s3_url = upload_template_to_s3(template_file, bucket_name, region, thread_safe)
    if not s3_url:
        return False

    cmd = (
        [
            "aws",
            "cloudformation",
            "create-stack",
            "--stack-name",
            stack_name,
            "--template-url",
            s3_url,
            "--parameters",
        ]
        + parameters
        + [
            "--capabilities",
            "CAPABILITY_IAM",
            "--region",
            region,
        ]
    )

    success, output = run_command(cmd)

    if success:
        print_success(
            f"スタックの作成を開始しました: {stack_name}", thread_safe=thread_safe
        )
        return wait_for_stack(stack_name, region, "create", thread_safe=thread_safe)
    else:
        if "AlreadyExistsException" in output:
            print_warning(
                f"スタック '{stack_name}' は既に存在します", thread_safe=thread_safe
            )
            return True
        print_error(f"スタックの作成に失敗しました: {output}", thread_safe=thread_safe)
        return False


def deploy_cognito_stack(config: Dict[str, Any]) -> bool:
    """Cognito CloudFormation スタックをデプロイ"""
    print_header("ステップ 1: Cognito スタックのデプロイ")

    parameters = [
        f"ParameterKey=DomainName,ParameterValue={config['cognito']['domain_name']}",
        f"ParameterKey=AdminUserEmail,ParameterValue={config['cognito']['admin_email']}",
    ]

    # Only add AdminUserPassword if provided
    if config['cognito'].get('admin_password'):
        parameters.append(
            f"ParameterKey=AdminUserPassword,ParameterValue={config['cognito']['admin_password']}"
        )

    return deploy_stack(
        stack_name=config["stacks"]["cognito"],
        template_file="cloudformation/cognito.yaml",
        parameters=parameters,
        region=config["aws"]["region"],
        bucket_name=config["s3"]["smithy_models_bucket"],
        description=f"Using Cognito domain: {config['cognito']['domain_name']}, Admin user: {config['cognito']['admin_email']}",
    )


def deploy_monitoring_agent(config: Dict[str, Any]) -> bool:
    """Monitoring Agent CloudFormation スタックをデプロイ"""
    print_header("ステップ 2: 監視エージェントのデプロイ")

    return deploy_stack(
        stack_name=config["stacks"]["monitoring_agent"],
        template_file="cloudformation/monitoring_agent.yaml",
        parameters=[
            f"ParameterKey=GitHubURL,ParameterValue={config['github']['url']}",
            f"ParameterKey=CognitoStackName,ParameterValue={config['stacks']['cognito']}",
            f"ParameterKey=SmithyModelS3Bucket,ParameterValue={config['s3']['smithy_models_bucket']}",
            f"ParameterKey=BedrockModelId,ParameterValue={config['aws']['bedrock_model_id']}",
        ],
        region=config["aws"]["region"],
        bucket_name=config["s3"]["smithy_models_bucket"],
    )


def deploy_web_search_agent(config: Dict[str, Any]) -> bool:
    """Web Search Agent CloudFormation スタックをデプロイ"""
    print_header("ステップ 3: Web 検索エージェントのデプロイ")

    return deploy_stack(
        stack_name=config["stacks"]["web_search_agent"],
        template_file="cloudformation/web_search_agent.yaml",
        parameters=[
            f"ParameterKey=OpenAIKey,ParameterValue={config['api_keys']['openai']}",
            f"ParameterKey=OpenAIModelId,ParameterValue={config['api_keys']['openai_model']}",
            f"ParameterKey=TavilyAPIKey,ParameterValue={config['api_keys']['tavily']}",
            f"ParameterKey=GitHubURL,ParameterValue={config['github']['url']}",
            f"ParameterKey=CognitoStackName,ParameterValue={config['stacks']['cognito']}",
        ],
        region=config["aws"]["region"],
        bucket_name=config["s3"]["smithy_models_bucket"],
    )


def deploy_host_agent(config: Dict[str, Any]) -> bool:
    """Host Agent CloudFormation スタックをデプロイ"""
    print_header("ステップ 4: ホストエージェントのデプロイ")

    return deploy_stack(
        stack_name=config["stacks"]["host_agent"],
        template_file="cloudformation/host_agent.yaml",
        parameters=[
            f"ParameterKey=GoogleApiKey,ParameterValue={config['api_keys']['google']}",
            f"ParameterKey=GoogleModelId,ParameterValue={config['api_keys']['google_model']}",
            f"ParameterKey=GitHubURL,ParameterValue={config['github']['url']}",
            f"ParameterKey=CognitoStackName,ParameterValue={config['stacks']['cognito']}",
        ],
        region=config["aws"]["region"],
        bucket_name=config["s3"]["smithy_models_bucket"],
    )


def deploy_agent_parallel(
    agent_name: str,
    config: Dict[str, Any],
    stack_key: str,
    template_file: str,
    parameters: list,
) -> Tuple[str, bool]:
    """エージェントスタックを並列でデプロイ（スレッドセーフ）"""
    try:
        print_header(f"Deploying {agent_name}", thread_safe=True)

        success = deploy_stack(
            stack_name=config["stacks"][stack_key],
            template_file=template_file,
            parameters=parameters,
            region=config["aws"]["region"],
            bucket_name=config["s3"]["smithy_models_bucket"],
            thread_safe=True,
        )

        return (agent_name, success)
    except Exception as e:
        print_error(f"Error deploying {agent_name}: {str(e)}", thread_safe=True)
        return (agent_name, False)


def deploy_agents_parallel(config: Dict[str, Any]) -> bool:
    """3つのエージェントスタックを並列でデプロイ"""
    print_header("ステップ 2-4: エージェントスタックのデプロイ（並列）")
    print_info("監視、Web 検索、ホストエージェントを並列でデプロイ中...")
    print_warning("これは高速ですが、出力が混在する可能性があります\n")

    # Prepare deployment tasks
    tasks = [
        (
            "Monitoring Agent",
            config,
            "monitoring_agent",
            "cloudformation/monitoring_agent.yaml",
            [
                f"ParameterKey=GitHubURL,ParameterValue={config['github']['url']}",
                f"ParameterKey=CognitoStackName,ParameterValue={config['stacks']['cognito']}",
                f"ParameterKey=SmithyModelS3Bucket,ParameterValue={config['s3']['smithy_models_bucket']}",
                f"ParameterKey=BedrockModelId,ParameterValue={config['aws']['bedrock_model_id']}",
            ],
        ),
        (
            "Web Search Agent",
            config,
            "web_search_agent",
            "cloudformation/web_search_agent.yaml",
            [
                f"ParameterKey=OpenAIKey,ParameterValue={config['api_keys']['openai']}",
                f"ParameterKey=OpenAIModelId,ParameterValue={config['api_keys']['openai_model']}",
                f"ParameterKey=TavilyAPIKey,ParameterValue={config['api_keys']['tavily']}",
                f"ParameterKey=GitHubURL,ParameterValue={config['github']['url']}",
                f"ParameterKey=CognitoStackName,ParameterValue={config['stacks']['cognito']}",
            ],
        ),
        (
            "Host Agent",
            config,
            "host_agent",
            "cloudformation/host_agent.yaml",
            [
                f"ParameterKey=GoogleApiKey,ParameterValue={config['api_keys']['google']}",
                f"ParameterKey=GoogleModelId,ParameterValue={config['api_keys']['google_model']}",
                f"ParameterKey=GitHubURL,ParameterValue={config['github']['url']}",
                f"ParameterKey=CognitoStackName,ParameterValue={config['stacks']['cognito']}",
            ],
        ),
    ]

    # Deploy agents in parallel using ThreadPoolExecutor
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all deployment tasks
        future_to_agent = {
            executor.submit(deploy_agent_parallel, *task): task[0] for task in tasks
        }

        # Collect results as they complete
        for future in as_completed(future_to_agent):
            agent_name = future_to_agent[future]
            try:
                name, success = future.result()
                results[name] = success
                if success:
                    print_success(f"✓ {name} のデプロイが完了しました", thread_safe=True)
                else:
                    print_error(f"✗ {name} のデプロイに失敗しました", thread_safe=True)
            except Exception as e:
                print_error(
                    f"{agent_name} のデプロイ中に例外が発生しました: {str(e)}", thread_safe=True
                )
                results[agent_name] = False

    # Check if all deployments succeeded
    all_success = all(results.values())

    print()
    if all_success:
        print_success("すべてのエージェントスタックが正常にデプロイされました！")
    else:
        print_error("1つ以上のエージェントスタックのデプロイに失敗しました")
        for agent, success in results.items():
            status = "✓" if success else "✗"
            print_info(f"  {status} {agent}: {'成功' if success else '失敗'}")

    return all_success


def print_cleanup_instructions():
    """デプロイ失敗後のクリーンアップ手順を表示"""
    print()
    print_header("デプロイ失敗 - クリーンアップが必要")
    print_error("デプロイに失敗し、一部のリソースが残っている可能性があります。")
    print_warning(
        "デプロイを再試行する前に、作成されたリソースをクリーンアップしてください。\n"
    )

    print_info("作成されたすべてのリソースをクリーンアップするには、以下を実行してください:")
    print(f"  {Colors.GREEN}uv run cleanup.py{Colors.END}\n")

    print_info("クリーンアップ後、以下を実行してデプロイを再試行できます:")
    print(f"  {Colors.GREEN}python3 deploy.py{Colors.END}")
    print()


def run_deployment(config: Dict[str, Any], parallel: bool = True) -> bool:
    """すべてのデプロイ手順を実行"""
    print_header("デプロイ開始")

    if parallel:
        print_warning(
            "並列デプロイを使用中 - 完了まで約 7-10 分かかります"
        )
    else:
        print_warning(
            "順次デプロイを使用中 - 完了まで約 10-15 分かかります"
        )

    print_info("AWS CloudFormation コンソールで進捗を監視できます\n")

    # Step 0: Create S3 bucket and upload Smithy model
    if not create_s3_bucket_and_upload(config):
        print_error("ステップ 0 で失敗: S3 バケットの作成/アップロード")
        print_cleanup_instructions()
        return False

    print()

    # Step 1: Deploy Cognito stack
    if not deploy_cognito_stack(config):
        print_error("ステップ 1 で失敗: Cognito スタックのデプロイ")
        print_cleanup_instructions()
        return False

    print()

    # Steps 2-4: Deploy agent stacks
    if parallel:
        # Deploy all three agents in parallel
        if not deploy_agents_parallel(config):
            print_error("ステップ 2-4 で失敗: エージェントスタックのデプロイ")
            print_cleanup_instructions()
            return False
    else:
        # Deploy agents sequentially (original behavior)
        # Step 2: Deploy Monitoring Agent
        if not deploy_monitoring_agent(config):
            print_error("ステップ 2 で失敗: 監視エージェントのデプロイ")
            print_cleanup_instructions()
            return False

        print()

        # Step 3: Deploy Web Search Agent
        if not deploy_web_search_agent(config):
            print_error("ステップ 3 で失敗: Web 検索エージェントのデプロイ")
            print_cleanup_instructions()
            return False

        print()

        # Step 4: Deploy Host Agent
        if not deploy_host_agent(config):
            print_error("ステップ 4 で失敗: ホストエージェントのデプロイ")
            print_cleanup_instructions()
            return False

    print()
    print_header("デプロイ完了！")
    print_success("すべてのスタックが正常にデプロイされました！")
    print_info("\n次のステップ:")
    print_info(
        "1. 個々のエージェントをテスト: uv run test/connect_agent.py --agent <monitor|websearch|host>"
    )
    print_info(
        "2. React フロントエンドを実行: cd frontend && npm install && ./setup-env.sh && npm run dev"
    )
    print_info("3. A2A Inspector または ADK Web でデバッグ")

    return True


def main():
    """メインエントリーポイント"""
    try:
        # Run pre-deployment checks
        checks_passed, account_id = run_pre_checks()
        if not checks_passed:
            sys.exit(1)

        # Collect parameters
        config = collect_deployment_parameters(account_id)

        # Display configuration
        display_configuration(config)

        # Confirm and save
        print_header("Save Configuration")
        confirm = get_input(
            "Save this configuration to .a2a.config? (yes/no)",
            default="yes",
            required=True,
        ).lower() in ["yes", "y"]

        if confirm:
            config_path = Path(".a2a.config")
            save_config(config, config_path)

            # Add to .gitignore
            gitignore_path = Path(".gitignore")
            gitignore_content = ""
            if gitignore_path.exists():
                with open(gitignore_path, "r") as f:
                    gitignore_content = f.read()

            if ".a2a.config" not in gitignore_content:
                with open(gitignore_path, "a") as f:
                    f.write("\n# A2A Deployment Configuration\n.a2a.config\n")
                print_success("Added .a2a.config to .gitignore")

            print()
            print_success("Configuration complete!")

            # Ask if user wants to deploy now
            print_header("Deploy Now?")
            deploy_now = get_input(
                "Do you want to start the deployment now? (yes/no)",
                default="yes",
                required=True,
            ).lower() in ["yes", "y"]

            if deploy_now:
                print()

                # Ask about parallel deployment
                use_parallel = get_input(
                    "Use parallel deployment for faster execution? (yes/no)",
                    default="yes",
                    required=True,
                ).lower() in ["yes", "y"]

                print()

                if run_deployment(config, parallel=use_parallel):
                    sys.exit(0)
                else:
                    sys.exit(1)
            else:
                print_info(
                    "\nDeployment skipped. You can run this script again to deploy."
                )
                print_info("Or manually run the AWS CLI commands for each stack.")

        else:
            print_warning("Configuration not saved. Exiting.")
            sys.exit(0)

    except KeyboardInterrupt:
        print_error("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

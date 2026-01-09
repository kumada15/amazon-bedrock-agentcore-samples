#!/usr/bin/env python3
"""
A2A マルチエージェント インシデント対応システムのクリーンアップスクリプト。
このスクリプトはデプロイされたすべてのリソースを正しい順序で削除します。
"""

import sys
import yaml
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
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


# 並列削除用のスレッドセーフな print ロック
print_lock = Lock()


def print_header(text: str, thread_safe: bool = False):
    """フォーマットされたヘッダーを表示"""
    output = f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}\n"
    output += f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.END}\n"
    output += f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}\n"

    if thread_safe:
        with print_lock:
            print(output, end='')
    else:
        print(output, end='')


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


def run_command(cmd: list, capture_output: bool = True, timeout: int = 30) -> Tuple[bool, str]:
    """シェルコマンドを実行し、(成功, 出力) を返す"""
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, timeout=timeout, check=False
        )
        return (result.returncode == 0, result.stdout.strip() if capture_output else "")
    except subprocess.TimeoutExpired:
        return (False, f"コマンドが {timeout} 秒後にタイムアウトしました")
    except FileNotFoundError:
        return (False, f"コマンドが見つかりません: {cmd[0]}")
    except Exception as e:
        return (False, str(e))


def load_config(config_path: Path) -> Optional[Dict[str, Any]]:
    """.a2a.config ファイルから設定を読み込む"""
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return None


def wait_for_stack_deletion(stack_name: str, region: str, thread_safe: bool = False) -> bool:
    """CloudFormation スタックの削除完了を待機"""
    print_info(f"スタック '{stack_name}' の削除を待機中...", thread_safe=thread_safe)

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

        # Stack no longer exists - this is the success case
        if not success:
            # Check for common stack deletion indicators in the output
            output_lower = output.lower()
            if (
                "does not exist" in output_lower
                or "validationerror" in output_lower
                or "stack with id" in output_lower
                or not output.strip()
            ):  # Empty output also means stack is gone
                print_success(f"スタック '{stack_name}' の削除に成功しました！", thread_safe=thread_safe)
                return True
            else:
                # 他の予期しないエラーが発生したが、確認を継続
                # 空の出力に対しては警告を表示しない
                if output.strip():
                    print_warning(f"スタックステータスの確認中にエラー: {output}", thread_safe=thread_safe)
                # 次のイテレーションに進む - スタックは削除された可能性がある

        # スタックはまだ存在する、ステータスを確認
        if success and output:
            status = output.strip()

            # DELETE_COMPLETE はスタックが完全に削除され、まもなく消えることを意味する
            if status == "DELETE_COMPLETE":
                print_success(f"スタック '{stack_name}' の削除に成功しました！", thread_safe=thread_safe)
                return True
            elif status == "DELETE_FAILED":
                print_error(f"スタック '{stack_name}' の削除に失敗しました！", thread_safe=thread_safe)
                print_error("詳細は CloudFormation コンソールを確認してください", thread_safe=thread_safe)
                return False
            else:
                print_info(f"[{stack_name}] ステータス: {status} (待機中...)", thread_safe=thread_safe)

        time.sleep(wait_interval)
        elapsed_time += wait_interval

    print_error(
        f"スタック '{stack_name}' の削除待機がタイムアウトしました ({max_wait_time}秒待機)",
        thread_safe=thread_safe
    )
    return False


def delete_stack(stack_name: str, region: str, step_name: str, thread_safe: bool = False) -> bool:
    """CloudFormation スタックを削除する"""
    if not thread_safe:
        print_header(f"{step_name} を削除中")
    else:
        print_header(f"{step_name} を削除中", thread_safe=True)

    # スタックが存在するか確認
    success, output = run_command(
        [
            "aws",
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            stack_name,
            "--region",
            region,
        ]
    )

    if not success:
        # スタックが存在しない場合（エラーではない）
        output_lower = output.lower()
        if (
            "does not exist" in output_lower
            or "stack with id" in output_lower
            or "validationerror" in output_lower
            or not output.strip()
        ):
            print_info(f"スタック '{stack_name}' は存在しません、スキップします", thread_safe=thread_safe)
            return True
        # その他のエラー
        print_error(f"スタックの確認中にエラー: {output}", thread_safe=thread_safe)
        return False

    # スタックを削除
    print_info(f"CloudFormation スタックを削除中: {stack_name}", thread_safe=thread_safe)
    success, output = run_command(
        [
            "aws",
            "cloudformation",
            "delete-stack",
            "--stack-name",
            stack_name,
            "--region",
            region,
        ]
    )

    if success:
        print_success(f"スタック削除を開始しました: {stack_name}", thread_safe=thread_safe)
        return wait_for_stack_deletion(stack_name, region, thread_safe=thread_safe)
    else:
        print_error(f"スタックの削除に失敗しました: {output}", thread_safe=thread_safe)
        return False


def empty_s3_bucket(bucket_name: str, region: str) -> bool:
    """S3 バケット内のすべてのオブジェクトを削除"""
    print_info(f"バケット '{bucket_name}' が存在するか確認中...")

    # バケットが存在するか確認
    success, output = run_command(
        ["aws", "s3api", "head-bucket", "--bucket", bucket_name, "--region", region]
    )

    if not success:
        if "404" in output or "Not Found" in output:
            print_warning(f"バケット '{bucket_name}' は存在しません、スキップします")
            return True
        print_error(f"バケットの確認中にエラー: {output}")
        return False

    print_info(f"S3 バケットを空にしています: {bucket_name}")
    success, output = run_command(
        ["aws", "s3", "rm", f"s3://{bucket_name}", "--recursive", "--region", region]
    )

    if success or "remove" in output:
        print_success(f"S3 バケット '{bucket_name}' を空にしました")
        return True
    else:
        print_warning(f"削除するオブジェクトがないか、エラーが発生しました: {output}")
        return True  # 空にする処理が失敗しても続行


def delete_s3_bucket(bucket_name: str, region: str) -> bool:
    """S3 バケットを削除する"""
    print_info(f"S3 バケットを削除中: {bucket_name}")

    success, output = run_command(
        ["aws", "s3", "rb", f"s3://{bucket_name}", "--region", region]
    )

    if success:
        print_success(f"S3 バケット '{bucket_name}' の削除に成功しました")
        return True
    else:
        if "NoSuchBucket" in output or "does not exist" in output:
            print_warning(f"バケット '{bucket_name}' は存在しません")
            return True
        print_error(f"バケットの削除に失敗しました: {output}")
        return False


def cleanup_s3_bucket(bucket_name: str, region: str) -> bool:
    """S3 バケットを空にしてから削除する"""
    print_header("ステップ 5: S3 バケットを削除")

    if not empty_s3_bucket(bucket_name, region):
        print_warning("バケットを空にできませんでしたが、続行します...")

    return delete_s3_bucket(bucket_name, region)


def delete_stack_parallel(
    stack_name: str,
    region: str,
    step_name: str
) -> Tuple[str, bool]:
    """スタックを並列で削除する（スレッドセーフ）"""
    try:
        success = delete_stack(stack_name, region, step_name, thread_safe=True)
        return (step_name, success)
    except Exception as e:
        print_error(f"{step_name} の削除中にエラー: {str(e)}", thread_safe=True)
        return (step_name, False)


def delete_agent_stacks_parallel(config: Dict[str, Any], region: str) -> bool:
    """3つのエージェントスタックを並列で削除する"""
    print_header("ステップ 1-3: エージェントスタックを削除（並列）")
    print_info("Host、Web Search、Monitoring エージェントスタックを並列で削除中...")
    print_warning("高速ですが、出力が交互に表示される場合があります\n")

    # 削除タスクを準備（依存関係の逆順）
    tasks = [
        (config["stacks"]["host_agent"], region, "Host Agent Stack"),
        (config["stacks"]["web_search_agent"], region, "Web Search Agent Stack"),
        (config["stacks"]["monitoring_agent"], region, "Monitoring Agent Stack"),
    ]

    # ThreadPoolExecutor を使用してスタックを並列で削除
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        # すべての削除タスクを送信
        future_to_stack = {
            executor.submit(delete_stack_parallel, *task): task[2]
            for task in tasks
        }

        # 完了した結果を収集
        for future in as_completed(future_to_stack):
            stack_label = future_to_stack[future]
            try:
                name, success = future.result()
                results[name] = success
                if success:
                    print_success(f"✓ {name} の削除が完了しました", thread_safe=True)
                else:
                    print_error(f"✗ {name} の削除に失敗しました", thread_safe=True)
            except Exception as e:
                print_error(f"{stack_label} の削除中に例外が発生: {str(e)}", thread_safe=True)
                results[stack_label] = False

    # すべての削除が成功したか確認
    all_success = all(results.values())

    print()
    if all_success:
        print_success("すべてのエージェントスタックの削除に成功しました！")
    else:
        print_error("1つ以上のエージェントスタックの削除に失敗しました")
        for stack, success in results.items():
            status = "✓" if success else "✗"
            print_info(f"  {status} {stack}: {'成功' if success else '失敗'}")

    return all_success


def run_cleanup(config: Dict[str, Any], parallel: bool = True) -> bool:
    """すべてのクリーンアップ手順を逆順で実行する"""
    print_header("クリーンアップを開始")
    print_warning("これはすべてのデプロイ済みリソースを削除します")
    print_warning("この操作は取り消せません！")

    if parallel:
        print_info("並列削除を使用 - 約 7-10 分\n")
    else:
        print_info("順次削除を使用 - 約 10-15 分\n")

    confirm = get_input(
        f"{Colors.RED}本当にすべてのリソースを削除しますか？ 確認するには 'DELETE' と入力してください{Colors.END}",
        default=None,
        required=True,
    )

    if confirm != "DELETE":
        print_warning("クリーンアップがキャンセルされました。リソースは削除されませんでした。")
        return False

    print()
    region = config["aws"]["region"]
    all_success = True

    # ステップ 1-3: エージェントスタックを削除
    if parallel:
        # 3つのエージェントスタックを並列で削除
        if not delete_agent_stacks_parallel(config, region):
            print_error("1つ以上のエージェントスタックの削除に失敗しました")
            all_success = False
    else:
        # エージェントスタックを順次削除（元の動作）
        # ステップ 1: Host Agent を削除（逆順）
        if not delete_stack(config["stacks"]["host_agent"], region, "Host Agent Stack"):
            print_error("Host Agent スタックの削除に失敗しました")
            all_success = False

        print()

        # ステップ 2: Web Search Agent を削除
        if not delete_stack(
            config["stacks"]["web_search_agent"], region, "Web Search Agent Stack"
        ):
            print_error("Web Search Agent スタックの削除に失敗しました")
            all_success = False

        print()

        # ステップ 3: Monitoring Agent を削除
        if not delete_stack(
            config["stacks"]["monitoring_agent"], region, "Monitoring Agent Stack"
        ):
            print_error("Monitoring Agent スタックの削除に失敗しました")
            all_success = False

    print()

    # ステップ 4: Cognito スタックを削除
    if not delete_stack(config["stacks"]["cognito"], region, "Cognito Stack"):
        print_error("Cognito スタックの削除に失敗しました")
        all_success = False

    print()

    # ステップ 5: S3 バケットを削除
    if not cleanup_s3_bucket(config["s3"]["smithy_models_bucket"], region):
        print_error("S3 バケットの削除に失敗しました")
        all_success = False

    print()

    # .a2a.config ファイルを削除
    config_path = Path(".a2a.config")
    if config_path.exists():
        try:
            config_path.unlink()
            print_success(".a2a.config ファイルを削除しました")
        except Exception as e:
            print_warning(f".a2a.config の削除に失敗しました: {e}")
            print_info("必要に応じて手動で削除してください")

    print()

    if all_success:
        print_header("クリーンアップ完了！")
        print_success("すべてのリソースが正常に削除されました！")
        print_info("\n再度デプロイするには: uv run deploy.py を実行してください")
    else:
        print_header("エラーありでクリーンアップ完了")
        print_warning("一部のリソースが正常に削除されなかった可能性があります")
        print_info(
            "上記のエラーを確認し、必要に応じて残りのリソースを手動で削除してください"
        )
        if config_path.exists():
            print_info("注: クリーンアップエラーのため .a2a.config は削除されませんでした")

    return all_success


def list_resources(config: Dict[str, Any]):
    """削除されるすべてのリソースを一覧表示する"""
    print_header("削除されるリソース")

    print(f"{Colors.BOLD}CloudFormation スタック:{Colors.END}")
    print(f"  1. {config['stacks']['host_agent']} (Host Agent)")
    print(f"  2. {config['stacks']['web_search_agent']} (Web Search Agent)")
    print(f"  3. {config['stacks']['monitoring_agent']} (Monitoring Agent)")
    print(f"  4. {config['stacks']['cognito']} (Cognito)")

    print(f"\n{Colors.BOLD}S3 リソース:{Colors.END}")
    print(f"  5. {config['s3']['smithy_models_bucket']} (S3 バケット + コンテンツ)")

    print(f"\n{Colors.BOLD}リージョン:{Colors.END} {config['aws']['region']}")
    print()


def main():
    """メインエントリーポイント"""
    try:
        print_header("A2A マルチエージェントシステム - クリーンアップスクリプト")

        # 設定を読み込む
        config_path = Path(".a2a.config")
        config = load_config(config_path)

        if not config:
            print_error("設定ファイル '.a2a.config' が見つかりません！")
            print_info(
                "デプロイを実行したプロジェクトディレクトリにいることを確認してください。"
            )
            print_info(
                "手動でデプロイした場合は、リソースも手動で削除する必要があります。"
            )
            sys.exit(1)

        print_success(".a2a.config から設定を読み込みました")

        # リソースを一覧表示
        list_resources(config)

        # ユーザーに続行するか確認
        proceed = get_input(
            "クリーンアップを続行しますか？ (yes/no)", default="no", required=True
        ).lower() in ["yes", "y"]

        if not proceed:
            print_warning("ユーザーによりクリーンアップがキャンセルされました。")
            sys.exit(0)

        print()

        # 並列削除について確認
        use_parallel = get_input(
            "高速実行のため並列削除を使用しますか？ (yes/no)",
            default="yes",
            required=True,
        ).lower() in ["yes", "y"]

        print()

        # クリーンアップを実行
        if run_cleanup(config, parallel=use_parallel):
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print_error("\n\nユーザーによりクリーンアップがキャンセルされました。")
        sys.exit(1)
    except Exception as e:
        print_error(f"エラーが発生しました: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

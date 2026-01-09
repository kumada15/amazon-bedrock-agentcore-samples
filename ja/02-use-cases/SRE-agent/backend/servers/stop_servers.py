import logging
import subprocess

from config_utils import get_server_ports

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)


def _stop_servers():
    """実行中のすべてのスタブサーバーを停止します。"""
    # OpenAPI 仕様からポートを取得
    port_config = get_server_ports()

    # ポートと名前のリストを作成
    ports = list(port_config.values())
    server_names = [name.title() for name in port_config.keys()]

    for port, name in zip(ports, server_names):
        try:
            # ポートを使用しているプロセスを検索
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    if pid:
                        logging.info(
                            f"{name} サーバー (PID: {pid}) をポート {port} で停止中"
                        )
                        subprocess.run(["kill", pid], check=False)
            else:
                logging.info(f"ポート {port} で {name} サーバーが見つかりませんでした")

        except FileNotFoundError:
            # lsof が利用できない場合、netstat を試す
            try:
                result = subprocess.run(
                    ["netstat", "-tlnp"], capture_output=True, text=True
                )

                for line in result.stdout.split("\n"):
                    if f":{port}" in line and "LISTEN" in line:
                        # netstat 出力から PID を抽出
                        parts = line.split()
                        if len(parts) > 6:
                            pid_info = parts[6]
                            if "/" in pid_info:
                                pid = pid_info.split("/")[0]
                                if pid.isdigit():
                                    logging.info(
                                        f"{name} サーバー (PID: {pid}) をポート {port} で停止中"
                                    )
                                    subprocess.run(["kill", pid], check=False)
                                    break

            except Exception as e:
                logging.error(f"{name} サーバーの停止中にエラーが発生しました: {str(e)}")


def main():
    """メインエントリーポイント。"""
    logging.info("すべての DevOps マルチエージェントデモサーバーを停止中...")
    _stop_servers()
    logging.info("すべてのサーバーを停止しました。")


if __name__ == "__main__":
    main()

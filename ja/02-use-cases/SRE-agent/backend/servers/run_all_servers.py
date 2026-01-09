import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from config_utils import get_server_ports

# basicConfig でログを設定
logging.basicConfig(
    level=logging.INFO,  # ログレベルを INFO に設定
    # ログメッセージのフォーマットを定義
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)


def _stream_output(process, name):
    """サブプロセスの出力をコンソールにストリーミングします。"""
    # Stream stdout
    for line in iter(process.stdout.readline, b""):
        if line:
            print(f"[{name}] {line.decode().rstrip()}")

    # Stream stderr
    for line in iter(process.stderr.readline, b""):
        if line:
            print(f"[{name} ERROR] {line.decode().rstrip()}", file=sys.stderr)


def _run_servers():
    """すべてのスタブサーバーを同時に実行します。"""
    # OpenAPI 仕様からポートを取得
    ports = get_server_ports()

    servers = [
        ("K8s Server", "k8s_server.py", ports.get("k8s")),
        ("Logs Server", "logs_server.py", ports.get("logs")),
        ("Metrics Server", "metrics_server.py", ports.get("metrics")),
        ("Runbooks Server", "runbooks_server.py", ports.get("runbooks")),
    ]

    # ポートが欠けているサーバーを除外
    valid_servers = []
    for name, script, port in servers:
        if port is not None:
            valid_servers.append((name, script, port))
        else:
            logging.error(f"{name} のポートを特定できませんでした、スキップします")

    servers = valid_servers

    processes = []

    # プロジェクトディレクトリに移動
    project_dir = Path(__file__).parent

    for name, script, port in servers:
        logging.info(f"{name} をポート {port} で起動中...")
        process = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_dir,
            bufsize=1,  # 行バッファリング
            universal_newlines=False,  # より良い制御のためバイナリモードを使用
        )
        processes.append((name, process))

        # 出力をストリーミングするスレッドを開始
        output_thread = threading.Thread(
            target=_stream_output, args=(process, name), daemon=True
        )
        output_thread.start()

        time.sleep(2)  # 各サーバーの起動時間を確保

    logging.info("\n" + "=" * 80)
    logging.info("すべてのサーバーが起動中です。Ctrl+C ですべてのサーバーを停止します。")
    logging.info("=" * 80 + "\n")
    logging.info("テスト URL:")
    for name, _, port in servers:
        service_name = name.split()[0].lower()
        logging.info(f"  {name:<15}: https://localhost:{port}/")

    logging.info("\nAPI ドキュメント（URL に /docs を追加）:")
    for name, _, port in servers:
        service_name = name.split()[0].lower()
        logging.info(f"  {name} Docs: https://localhost:{port}/docs")

    try:
        # スクリプトを実行し続ける
        while True:
            time.sleep(1)
            # プロセスが終了していないかチェック
            for name, process in processes:
                if process.poll() is not None:
                    logging.error(f"{name} が予期せず停止しました！")
                    # 出力は既にスレッドによってストリーミングされている
                    # プロセスが終了したことだけを記録
                    logging.error(f"{name} は終了コード {process.returncode} で終了しました")
    except KeyboardInterrupt:
        logging.info("\n" + "=" * 80)
        logging.info("すべてのサーバーを停止中...")
        logging.info("=" * 80)
        for name, process in processes:
            process.terminate()
            logging.info(f"{name} を停止しました")
            # グレースフルシャットダウンを少し待つ
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # グレースフルに停止しない場合は強制終了
                process.kill()
                logging.warning(f"{name} を強制終了しました")


def main():
    """メインエントリーポイント。"""
    try:
        _run_servers()
    except Exception as e:
        logging.error(f"サーバー実行中にエラーが発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

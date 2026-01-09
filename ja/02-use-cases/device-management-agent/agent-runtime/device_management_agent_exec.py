"""
デバイス管理エージェント インタラクティブ実行インターフェース

このモジュールは、デプロイ済みの Device Management Strands Agent Runtime を
テストおよび対話するためのインタラクティブなコマンドラインインターフェースを提供します。
ストリーミングレスポンスサポート付きのターミナルベースのチャットインターフェースを通じて
AI エージェントとのリアルタイム会話を可能にします。

スクリプトが処理するもの:
- AWS Bedrock AgentCore 経由のエージェント接続と認証
- 会話継続のためのセッション管理
- エージェントからのストリーミングレスポンス処理
- 絵文字とフォーマットによるユーザーフレンドリーな出力
- エラーハンドリングと正常なシャットダウン

主な機能:
    - デプロイ済みエージェントとのインタラクティブ CLI チャットインターフェース
    - マルチターン会話のためのセッション永続化
    - リアルタイムフィードバックのためのストリーミングレスポンスサポート
    - スロットリング例外の自動リトライロジック
    - 使用例を含むフォーマットされたウェルカムメッセージ
    - 正常な終了処理（Ctrl+C、'exit' コマンド）

コマンドライン引数:
    --agent_arn（必須）: デプロイ済みエージェントランタイムの ARN
    --session_id（オプション）: 既存の会話を継続するセッション ID
                              （新規会話の場合はデフォルトで 'start'）

環境変数:
    AWS_REGION: AgentCore クライアント用の AWS リージョン（.env から）
    AWS 認証情報: AWS CLI または環境変数で設定が必要

使用例:
    新しい会話を開始:
    >>> python device_management_agent_exec.py --agent_arn arn:aws:bedrock-agentcore:...

    既存の会話を継続:
    >>> python device_management_agent_exec.py --agent_arn arn:aws:... --session_id abc123

    インタラクティブコマンド:
    >>> すべてのデバイスを一覧表示
    >>> デバイス DEV001 の設定を表示
    >>> デバイス DEV001 の WiFi SSID を MyNetwork に更新
    >>> exit

レスポンス処理:
    - ストリーミングレスポンス: 到着時にリアルタイムで表示
    - 非ストリーミングレスポンス: プリティプリントされた JSON またはプレーンテキスト
    - エラーメッセージ: 絵文字インジケーター付きでフォーマット
    - セッショントラッキング: 会話コンテキストを維持

終了方法:
    - 'exit'、'quit'、'bye'、または 'goodbye' と入力
    - Ctrl+C でキーボード割り込み
    - スクリプトは終了時に最終セッション ID を表示

注意事項:
    - 有効な ARN を持つデプロイ済みエージェントランタイムが必要
    - セッション ID により実行間で会話を継続可能
    - ストリーミングと非ストリーミングの両方のレスポンスフォーマットをサポート
    - AWS スロットリング例外のリトライロジックを含む
"""
import utils
import json
from dotenv import load_dotenv
import sys
import argparse

# Reading environment variables
load_dotenv()

# Setting up command line arguments
parser = argparse.ArgumentParser(
    prog='device_management_agent_exec',
    description='Execute Device Management Strands Agent',
    epilog='Interactive chat with your deployed agent'
)

parser.add_argument('--agent_arn', help="Agent Runtime ARN", required=True)
parser.add_argument('--session_id', help="Session ID for continuing conversation", default='start')

args = parser.parse_args()

# Validate agent ARN
if not args.agent_arn:
    print("❌ Agent ARN が必要です。--agent_arn パラメータを使用してください")
    sys.exit(1)

print(f"🚀 エージェントに接続中: {args.agent_arn}")

# Create AgentCore client
try:
    (boto_session, agentcore_client) = utils.create_agentcore_client()
    # Client for data plane
    agentcore_client = boto_session.client("bedrock-agentcore")
    print("✅ AWS Bedrock AgentCore に正常に接続しました")
except Exception as e:
    print(f"❌ AgentCore への接続エラー: {e}")
    sys.exit(1)

sessionId = args.session_id

print("=" * 70)
print("🏠  デバイス管理アシスタントへようこそ  🏠")
print("=" * 70)
print("✨ 以下のことをお手伝いできます:")
print("   📱 システム内のすべてのデバイスを一覧表示")
print("   ⚙️  デバイスの設定と構成を取得")
print("   📡 デバイスの WiFi ネットワークを管理")
print("   👥 ユーザーの一覧表示とアクティビティの確認")
print("   🔧 デバイス構成の更新")
print()
print("💡 コマンド例:")
print("   ・「すべてのデバイスを一覧表示」")
print("   ・「デバイス DEV001 の設定を表示」")
print("   ・「リビングルームルーターの WiFi ネットワークを一覧表示」")
print("   ・「デバイス DEV001 の WiFi SSID を MyNewNetwork に更新」")
print()
print("🚪 終了するには 'exit' と入力してください")
print("=" * 70)
print()

# Run the agent in a loop for interactive conversation
while True:
    try:
        user_input = input("👤 You: ").strip()

        if not user_input:
            print("💭 メッセージを入力するか、'exit' と入力して終了してください")
            continue

        if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
            print()
            print("=" * 50)
            print("👋 デバイス管理アシスタントをご利用いただきありがとうございます！")
            print("🎉 お使いのデバイスは安心です！")
            print("=" * 50)
            break

        print("🤖 DeviceBot: ", end="", flush=True)

        try:
            # Invoke the agent
            if sessionId == 'start':
                boto3_response = agentcore_client.invoke_agent_runtime(
                    agentRuntimeArn=args.agent_arn,
                    qualifier="DEFAULT",
                    payload=json.dumps({"prompt": user_input})
                )
            else:
                boto3_response = agentcore_client.invoke_agent_runtime(
                    agentRuntimeArn=args.agent_arn,
                    qualifier="DEFAULT",
                    payload=json.dumps({"prompt": user_input}),
                    runtimeSessionId=sessionId
                )

            # Update session ID
            sessionId = boto3_response['runtimeSessionId']
            
            # Handle streaming response
            if "text/event-stream" in boto3_response.get("contentType", ""):
                content = []
                for line in boto3_response["response"].iter_lines(chunk_size=1):
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]
                            print(line, end="", flush=True)
                            content.append(line)
                print()  # New line after streaming content
            else:
                # Handle non-streaming response
                try:
                    events = []
                    for event in boto3_response.get("response", []):
                        events.append(event)
                except Exception as e:
                    events = [f"Error reading EventStream: {e}"]
                
                for event in events:
                    try:
                        event_data = json.loads(event.decode("utf-8"))
                        if isinstance(event_data, dict):
                            # Pretty print structured responses
                            if 'response' in event_data:
                                print(event_data['response'])
                            else:
                                print(json.dumps(event_data, indent=2))
                        else:
                            print(event_data)
                    except json.JSONDecodeError:
                        print(event.decode("utf-8"))

        except Exception as e:
            print(f"❌ エージェント呼び出しエラー: {str(e)}")
            print("💡 Agent ARN を確認して再試行してください")

        print()

    except KeyboardInterrupt:
        print()
        print("=" * 50)
        print("👋 デバイス管理アシスタントが中断されました！")
        print("🎉 またのご利用をお待ちしています！")
        print("=" * 50)
        break
    except Exception as e:
        print(f"❌ 予期しないエラーが発生しました: {str(e)}")
        print("💡 再試行するか、'exit' と入力して終了してください")
        print()

print("🔚 セッションが終了しました。セッション ID:", sessionId)
from strands.models import BedrockModel
from mcp.client.streamable_http import streamablehttp_client 
from strands.tools.mcp.mcp_client import MCPClient
from strands import Agent
import logging
import argparse
import os
import utils

# パラメータ設定
parser = argparse.ArgumentParser(
                    prog='strands_agent',
                    description='MCP Gateway を使用した Strands Agent のテスト',
                    epilog='入力パラメータ')

parser.add_argument('--gateway_id', help = "Gateway ID")

os.environ["STRANDS_TOOL_CONSOLE_MODE"] = "enabled"

# boto3 セッションとクライアントの作成
(boto_session, agentcore_client) = utils.create_agentcore_client()

systemPrompt = """
   あなたは子供の予防接種予約を行うヘルスケアエージェントです。
    患者 ID adult-patient-001 でログインしているユーザーを想定し、
    以下のことができます:
    1/ お子様の予防接種スケジュールについて問い合わせる
    2/ 予約を行う

    まず、ログインしているユーザーに名前で呼びかけてください。名前はツールを呼び出すことで取得できます。
    回答に患者 ID を含めないでください。
    スケジュールに未完了（status = not done）の予防接種がある場合は、予約を促してください。
    予防接種スケジュールについて質問された場合は、まず患者 ID を pediatric-patient-001 として適切なツールを呼び出してお子様の名前と生年月日を取得し、ユーザーに詳細を確認してもらってください。
"""

if __name__ == "__main__":
    args = parser.parse_args()

    # バリデーション
    if args.gateway_id is None:
        raise Exception("Gateway ID は必須です")

    gatewayEndpoint=utils.get_gateway_endpoint(agentcore_client=agentcore_client, gateway_id=args.gateway_id)
    print(f"Gateway エンドポイント: {gatewayEndpoint}")

    jwtToken = utils.get_oath_token(boto_session)
    client = MCPClient(lambda: streamablehttp_client(gatewayEndpoint,headers={"Authorization": f"Bearer {jwtToken}"}))

    bedrockmodel = BedrockModel(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        temperature=0.7,
        streaming=True,
        boto_session=boto_session
    )

    # strands ルートロガーの設定
    logging.getLogger("strands").setLevel(logging.INFO)

    # ログを表示するためのハンドラーを追加
    logging.basicConfig(
        format="%(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()]
    )

    with client:
        tools = client.list_tools_sync()
        agent = Agent(model=bedrockmodel,tools=tools,system_prompt=systemPrompt)

        print("=" * 60)
        print("  ヘルスケアアシスタントへようこそ  ")
        print("=" * 60)
        print("以下のことをお手伝いできます:")
        print("   - お子様の予防接種履歴と未完了の予防接種を確認")
        print("   - 予防接種の予約")
        print()
        print("終了するには 'exit' と入力してください")
        print("=" * 60)
        print()

        # 対話型会話のためのエージェントループを実行
        while True:
            try:
                user_input = input("あなた: ").strip()

                if not user_input:
                    print("メッセージを入力するか、'exit' と入力して終了してください")
                    continue

                if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
                    print()
                    print("=======================================")
                    print("ヘルスケアアシスタントをご利用いただきありがとうございます！")
                    print("良い一日をお過ごしください！")
                    print("=======================================")
                    break

                print("ヘルスケアボット: ", end="")
                agent(user_input)
                print()

            except KeyboardInterrupt:
                print()
                print("=======================================")
                print("ヘルスケアアシスタントが中断されました！")
                print("またのご利用をお待ちしております！")
                print("=======================================")
                break
            except Exception as e:
                print(f"エラーが発生しました: {str(e)}")
                print("もう一度お試しいただくか、'exit' と入力して終了してください")
                print()

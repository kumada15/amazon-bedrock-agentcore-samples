from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model
import asyncio
from dotenv import load_dotenv
import argparse
import os
import utils

load_dotenv()

# パラメータ設定
parser = argparse.ArgumentParser(
                    prog='strands_agent',
                    description='MCP Gateway を使用した Strands Agent のテスト',
                    epilog='入力パラメータ')

parser.add_argument('--gateway_id', help = "Gateway ID")

# boto3 セッションとクライアントの作成
(boto_session, agentcore_client) = utils.create_agentcore_client()

bedrock_client = boto_session.client(
    "bedrock-runtime",
    region_name=os.getenv("aws_default_region")
)

async def main(gateway_endpoint, jwt_token):
    client = MultiServerMCPClient(
        {
            "healthcare": {
                "url": gateway_endpoint,
                "transport": "streamable_http",
                "headers":{"Authorization": f"Bearer {jwt_token}"}
            }
        }
    )

    tools = await client.get_tools()

    LLM = init_chat_model(
        client=bedrock_client,
        model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        model_provider="bedrock_converse",
        temperature=0.7
    )
    #print(LLM)

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

    agent = create_react_agent(
        LLM, 
        tools, 
        prompt=systemPrompt
    )
    history = ""

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

            history = history + "User: " + user_input

            async for message_chunk, metadata in agent.astream({"messages": [("human", user_input), ("developer", history)]}, stream_mode="messages"):
                if message_chunk.content:
                    for content in message_chunk.content:
                        if 'text' in content:
                            print(content['text'], end="", flush=True)

                            history = history + "AI Message Chunk: " + content['text']

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

if __name__ == "__main__":
    args = parser.parse_args()

    # バリデーション
    if args.gateway_id is None:
        raise Exception("Gateway ID は必須です")

    gatewayEndpoint=utils.get_gateway_endpoint(agentcore_client=agentcore_client, gateway_id=args.gateway_id)
    print(f"Gateway エンドポイント: {gatewayEndpoint}")

    jwtToken = utils.get_oath_token(boto_session)
    asyncio.run(main(gatewayEndpoint, jwtToken))

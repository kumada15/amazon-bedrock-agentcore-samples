#!/usr/bin/env python3
"""
Strands と MCP を使用したインタラクティブ自動車保険エージェント

このエージェントはローカルの保険 MCP サーバーに接続し、
インタラクティブなチャット形式で自動車保険の見積もり、
顧客情報、車両詳細をロギング付きで提供します。
"""

# 標準ライブラリのインポート
import logging
from typing import Dict, Any, List, Optional
import time
import json
from datetime import datetime

from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# ロギングを設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler()
    ]
)
logger = logging.getLogger("InsuranceAgent")

# MCP サーバー URL - ローカルの MCP サーバーを指す
MCP_SERVER_URL = "http://localhost:8000/mcp"

# ローカル MCP サーバーを指す MCP クライアントを作成
insurance_client = MCPClient(lambda: streamablehttp_client(MCP_SERVER_URL))

# コンテキストを維持するためのチャット履歴
chat_history: List[Dict[str, str]] = []

# 保険エージェント用のシステムプロンプト
INSURANCE_SYSTEM_PROMPT = """
あなたは、お客様が保険オプションを理解するのをサポートする自動車保険アシスタントです。

あなたの目標は、自動車保険商品、顧客情報、車両情報、保険見積もりについて
正確で役立つ情報を提供することです。

利用可能なツールを使用して、保険データベースから情報を取得してください。
見積もりや情報を提供する際は、プロフェッショナルでありながら親しみやすい対応を心がけてください。
保険用語は分かりやすい言葉で説明し、各オプションの主なメリットを強調してください。

利用可能なツール：
- get_customer_info: ID で顧客情報を検索
- get_vehicle_info: メーカー、モデル、年式で車両仕様を取得
- get_insurance_quote: 顧客と車両に対する保険見積もりを生成
- get_vehicle_safety: 特定の車両メーカーとモデルの安全性評価を取得

常にお客様に情報を確認し、必要に応じて明確化を求めてください。
回答は簡潔に、ユーザーの質問に焦点を当ててください。

お客様が見積もりを求めた場合、以下の情報を収集してください：
1. 顧客 ID（利用可能な場合）
2. 車両のメーカー、モデル、年式

回答時は、会話の以前のコンテキストを覚えておいてください。
"""

def log_conversation(role: str, content: str, tool_calls: Optional[List] = None) -> None:
    """タイムスタンプとオプションのツール呼び出しで各会話ターンをログ記録"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{timestamp}] {role}: {content[:100]}..." if len(content) > 100 else f"[{timestamp}] {role}: {content}")
    
    if tool_calls:
        for call in tool_calls:
            logger.info(f"  Tool used: {call['name']} with args: {json.dumps(call['args'])}")

def insurance_quote_agent(question: str, history: List[Dict[str, str]]) -> Dict[Any, Any]:
    """
    ローカル MCP サーバーの MCP ツールを使用して
    自動車保険に関する質問に回答する Strands エージェントを作成

    Args:
        question: 顧客の質問またはリクエスト
        history: コンテキスト用のチャット履歴

    Returns:
        辞書としてのエージェントのレスポンス
    """
    log_conversation("User", question)
    
    with insurance_client:
        try:
            # MCP サーバーから利用可能なツールのリストを取得
            tools = insurance_client.list_tools_sync()
            logger.info(f"MCP サーバーに接続しました。{len(tools)} 個のツールを検出")

            # Claude と MCP ツールでエージェントを作成
            # chat_history パラメータなしでエージェントを作成
            agent = Agent(
                model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
                tools=tools,
                system_prompt=INSURANCE_SYSTEM_PROMPT,
                callback_handler=None
            )
            
            # 以前の会話を使用してコンテキストを追加
            prompt = question
            if history and len(history) > 1:
                context = "\n\nPrevious conversation:\n"
                # コンテキスト用に以前のやり取り（最大5つ）を追加
                for i in range(max(0, len(history)-10), len(history), 2):
                    if i+1 < len(history):  # ユーザーとアシスタントの両方のメッセージがあることを確認
                        context += f"User: {history[i]['content']}\nAssistant: {history[i+1]['content']}\n\n"
                prompt = context + "\nCurrent question: " + question
            
            start_time = time.time()
            # 質問を処理してレスポンスを返す
            response = agent(prompt)
            end_time = time.time()
            
            logger.info(f"リクエスト処理完了: {end_time - start_time:.2f} 秒")
            
            # アシスタントのレスポンスをログ記録
            try:
                log_conversation("Assistant", response, 
                              response.tool_calls if hasattr(response, "tool_calls") else None)
            except Exception as e:
                logger.error(f"レスポンスのログ記録中にエラーが発生しました: {str(e)}")
                log_conversation("Assistant", str(response))
            
            return response
        except Exception as e:
            logger.error(f"リクエスト処理中にエラーが発生しました: {str(e)}")
            # グレースフルなエラーレスポンスを返す
            return {"message": {"content": f"申し訳ありませんが、エラーが発生しました: {str(e)}。後でもう一度お試しください。"}}

def run_interactive_session():
    """保険エージェントとのインタラクティブセッションを実行"""
    print("\n🚗 インタラクティブ自動車保険アシスタントへようこそ！ 🚗")
    print("自動車保険に関する質問、見積もりの取得、特定の車両についてお問い合わせください。")
    print("セッションを終了するには 'exit'、'quit'、または 'bye' と入力してください。\n")
    
    global chat_history
    
    while True:
        try:
            # ユーザー入力を取得
            user_input = input("\n💬 あなた: ")

            # 終了コマンドをチェック
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\n👋 自動車保険アシスタントをご利用いただきありがとうございました。さようなら！")
                break
            
            # ユーザーメッセージを履歴に追加
            chat_history.append({"role": "user", "content": user_input})
            
            print("\n⏳ リクエストを処理中...")
            
            # エージェントからレスポンスを取得
            response = insurance_quote_agent(user_input, chat_history)
                
            print(f"\n🤖 アシスタント: {response}")
            
            # アシスタントのレスポンスを履歴に追加
            try:
                chat_history.append({"role": "assistant", "content": response})
            except Exception as e:
                logger.error(f"チャット履歴への追加中にエラーが発生しました: {str(e)}")
            
            # 使用されたツールを出力（ユーザー向け情報）
            if hasattr(response, "tool_calls") and response.tool_calls:
                print("\n🔧 使用されたツール:")
                for call in response.tool_calls:
                    print(f"- {call['name']}")
            
        except KeyboardInterrupt:
            print("\n\n👋 セッションが中断されました。さようなら！")
            break
        except Exception as e:
            logger.error(f"インタラクティブセッションでエラーが発生しました: {str(e)}")
            print(f"\n❌ エラーが発生しました: {str(e)}")
            print("再試行するか、アプリケーションを再起動してください。")

def main():
    """インタラクティブ保険エージェントを実行するメイン関数"""
    logger.info("インタラクティブ保険エージェントを開始しています")
    print("\n🚀 保険エージェントを初期化中...")
    
    try:
        run_interactive_session()
    except Exception as e:
        logger.error(f"致命的なエラー: {str(e)}")
        print(f"\n❌ 致命的なエラー: {str(e)}")
    
    logger.info("保険エージェントのセッションが終了しました")

if __name__ == "__main__":
    main()
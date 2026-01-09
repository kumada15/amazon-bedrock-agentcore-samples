#!/usr/bin/env python3
"""
Strands と MCP を使用した自動車保険エージェント

このエージェントはローカルの保険 MCP サーバーに接続し、
自動車保険の見積もり、顧客情報、車両詳細を提供します。

以下の 2 つの方法で使用できます：
1. コマンドライン入力で直接実行: python interactive_insurance_agent.py --user_input "質問"
2. AWS Bedrock Agent として（AgentCore にデプロイした場合）
"""

# 標準ライブラリのインポート
import logging
from typing import Dict, Any, List, Optional
import time
import json
import sys
import argparse
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


def process_single_input(user_input: str, history: List[Dict[str, str]] = None):
    """
    単一のユーザー入力を処理してレスポンスを返す

    Args:
        user_input: ユーザーの質問またはリクエスト
        history: コンテキスト用のオプションのチャット履歴

    Returns:
        文字列としてのエージェントのレスポンス
    """
    if history is None:
        history = []
        
    logger.info(f"単一の入力を処理中: {user_input}")
    
    # エージェントからレスポンスを取得
    response = insurance_quote_agent(user_input, history)
    
    # 表示用にレスポンスをフォーマット
    if isinstance(response, dict):
        if "content" in response:
            return response["content"]
        elif "message" in response and "content" in response["message"]:
            return response["message"]["content"]
    
    # デフォルトで完全なレスポンスを返す
    return str(response)

def main(user_input):
    """
    保険エージェントを実行するメイン関数

    Args:
        user_input: エージェントへのユーザーの質問またはリクエスト
    """
    logger.info("保険エージェントを開始しています")
    
    try:
        print("\n🚀 リクエストを処理中...")
        response = process_single_input(user_input)
        print(f"\n🤖 アシスタント: {response}")
        
        
        # 利用可能な場合はツール呼び出し情報を出力
        if isinstance(response, dict) and "tool_calls" in response:
            print("\n🔧 使用されたツール:")
            for call in response["tool_calls"]:
                print(f"- {call['name']}")
        
        # AgentCore 用の JSON レスポンスを返す
        return {"result": f"You said: {user_input}. Result is {response}!"}
    except Exception as e:
        logger.error(f"リクエスト処理中にエラーが発生しました: {str(e)}")
        print(f"\n❌ エラー: {str(e)}")

    logger.info("保険エージェントのリクエスト処理が完了しました")

if __name__ == "__main__":
    # 後方互換性のためにコマンドライン引数を解析
    parser = argparse.ArgumentParser(description='Auto Insurance Agent using Strands and MCP')
    parser.add_argument('--user_input', type=str, required=True, 
                        help='User input for agent to process (e.g., "What insurance options are available?")')
    
    args = parser.parse_args()
    # 最後に簡単な使用例を追加
    if len(sys.argv) == 1:
        print("\n使用例:\n")
        print("  python strands_insurance_agent.py --user_input \"利用可能な保険オプションは何ですか？\"")
        print("  python strands_insurance_agent.py --user_input \"顧客 cust-001 について教えてください\"")
        print("\nユーザー入力は必須です。--user_input を使用して質問を入力してください。\n")
        sys.exit(1)
    
    # メイン関数を実行
    main(args.user_input)
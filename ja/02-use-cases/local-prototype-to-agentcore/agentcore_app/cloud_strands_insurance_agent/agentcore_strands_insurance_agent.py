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
from typing import Dict, List, Optional
import time
import json
import os
from datetime import datetime

# 環境変数を読み込むために dotenv をインポート
from dotenv import load_dotenv

from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# 追加: BEDROCK_AGENTCORE インポート
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# .env ファイルから環境変数を読み込む
load_dotenv()

# 追加: BEDROCK_AGENTCORE アプリの作成
app = BedrockAgentCoreApp()

# ロギングを設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler()
    ]
)
logger = logging.getLogger("InsuranceAgent")

# 環境変数から MCP サーバー URL とアクセストークンを取得
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")
access_token = os.getenv("MCP_ACCESS_TOKEN")

# 環境変数が設定されているか確認
if not MCP_SERVER_URL:
    logger.error("MCP_SERVER_URL が環境変数に見つかりません。")
    raise ValueError("MCP_SERVER_URL environment variable is required")

if not access_token:
    logger.warning("MCP_ACCESS_TOKEN が環境変数に見つかりません。認証が失敗する可能性があります。")
    # アクセストークンは機密情報のため、環境変数経由で提供する必要があります。デフォルト値は設定しません

# MCP サーバーを指す MCP クライアントを作成
insurance_client = MCPClient(lambda: streamablehttp_client(MCP_SERVER_URL, headers={"Authorization": f"Bearer {access_token}"})) 


# 保険エージェント用のシステムプロンプト
INSURANCE_SYSTEM_PROMPT = """
あなたは、お客様が保険オプションを理解するのをサポートする自動車保険アシスタントです。

あなたの目標は、自動車保険商品、顧客情報、車両情報、保険見積もりについて
正確で役立つ情報を提供することです。

利用可能なツールを使用して、保険データベースから情報を取得してください。
見積もりや情報を提供する際は、プロフェッショナルでありながら親しみやすい対応を心がけてください。
保険用語は分かりやすい言葉で説明し、各オプションの主なメリットを強調してください。

利用可能なツール：
x_amz_bedrock_agentcore_search - コンテキストに基づいてツールの絞り込みリストを返す特別なツールです。
利用可能なツールが多数あり、指定されたコンテキストに一致するサブセットを取得したい場合にのみ、このツールを使用してください。

常にお客様に情報を確認し、必要に応じて明確化を求めてください。
回答は簡潔に、ユーザーの質問に焦点を当ててください。

回答時は、会話の以前のコンテキストを覚えておいてください。
"""

def log_conversation(role: str, content: str, tool_calls: Optional[List] = None) -> None:
    """タイムスタンプとオプションのツール呼び出しで各会話ターンをログ記録"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{timestamp}] {role}: {content[:100]}..." if len(content) > 100 else f"[{timestamp}] {role}: {content}")
    
    if tool_calls:
        for call in tool_calls:
            logger.info(f"  Tool used: {call['name']} with args: {json.dumps(call['args'])}")

def insurance_quote_agent(question: str):
    """
    ローカル MCP サーバーの MCP ツールを使用して
    自動車保険に関する質問に回答する Strands エージェントを作成

    Args:
        question: 顧客の質問またはリクエスト

    Returns:
        エージェントのレスポンス
    """
    log_conversation("User", question)
    
    with insurance_client:
        try:
            # MCP サーバーから利用可能なツールのリストを取得
            tools = insurance_client.list_tools_sync()
            logger.info(f"MCP サーバーに接続しました。{len(tools)} 個のツールを検出")

            # 環境変数からモデル名を取得、またはデフォルトを使用
            model_name = os.getenv("MODEL_NAME", "global.anthropic.claude-haiku-4-5-20251001-v1:0")

            # MCP ツールでエージェントを作成
            agent = Agent(
                model=model_name,
                tools=tools,
                system_prompt=INSURANCE_SYSTEM_PROMPT,
                callback_handler=None
            )
            
            # 以前の会話を使用してコンテキストを追加
            prompt = question

            start_time = time.time()
            # 質問を処理してレスポンスを返す
            response = agent(prompt)
            end_time = time.time()
            
            logger.info(f"リクエスト処理完了: {end_time - start_time:.2f} 秒")
            
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
    response = insurance_quote_agent(user_input)

    # 表示用にレスポンスをフォーマット
    if isinstance(response, dict):
        if "content" in response:
            return response["content"]
        elif "message" in response and "content" in response["message"]:
            return response["message"]["content"]
    
    # デフォルトで完全なレスポンスを返す
    return str(response)

# 追加: BEDROCK_AGENTCORE - アプリのエントリポイント宣言
@app.entrypoint
def main(payload):
    """
    保険エージェントを実行するメイン関数

    Args:
        payload: AgentCore からの入力ペイロード（ユーザーのメッセージを含む場合がある）
    """
    logger.info("保険エージェントを開始しています")
    logger.info(f"ペイロードを受信しました: {payload}")
    logger.info(f"ペイロードは文字列ですか？ {isinstance(payload, str)}")
    
    try:
        # ペイロードからユーザー入力を抽出
        logger.info(f"入力ペイロード: {payload}")
        user_input = payload.get("user_input")

        # 明示的なチェックを追加
        if "user_input" not in payload:
            logger.error("ペイロードに 'user_input' キーが見つかりません。デフォルトを使用します")
        
        logger.info(f"抽出された user_input: {user_input}")
        logger.info("\n🚀 リクエストを処理中...")

        # リクエストを処理
        response = process_single_input(user_input)
        logger.info(f"\n🤖 アシスタント: {response}")
        
        return response
    except Exception as e:
        error_msg = f"リクエスト処理中にエラーが発生しました: {str(e)}"
        logger.error(error_msg)
        logger.info(f"\n❌ {error_msg}")

        # AgentCore 用のエラーレスポンスをフォーマット
        return f"申し訳ありませんが、エラーが発生しました: {str(e)}。後でもう一度お試しください。"
        
    finally:
        logger.info("保険エージェントのリクエスト処理が完了しました")

if __name__ == "__main__":
    # 削除: ローカル処理用の以前のコード
    # 追加: BEDROCK_AGENTCORE - アプリを実行
    app.run()


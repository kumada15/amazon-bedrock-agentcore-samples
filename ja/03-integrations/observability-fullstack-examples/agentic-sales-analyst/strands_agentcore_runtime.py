#!/usr/bin/env python3

import json
import logging
import os
import re
import sys
import traceback

import psycopg2
from psycopg2 import sql
import requests
from strands import Agent, tool
from strands.hooks import AgentInitializedEvent, HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory import MemoryClient
from flask import Flask, request, jsonify
from flask_cors import CORS
from opentelemetry import baggage
from opentelemetry.context import attach

# デプロイメントモードを検出
DEPLOYMENT_MODE = os.getenv('DEPLOYMENT_MODE', 'ecs')  # 'ecs', 'eks'

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

# コンテナ内で Flask がアプリケーションログを表示するように強制
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
app.logger.setLevel(logging.DEBUG)

# Strands オブザーバビリティを設定（オプション）
try:
    from strands.observability import configure_tracer
    configure_tracer()
    print("[OTEL] ✅ Strands observability configured")
except ImportError:
    print("[OTEL] ℹ️ Using ADOT auto-instrumentation for observability")
except Exception as e:
    print(f"[OTEL] ⚠️ Observability configuration failed: {e}")
    print("[OTEL] ℹ️ Falling back to ADOT auto-instrumentation")

# グローバルスキーマキャッシュ
schema_cache = None

print(f"[{DEPLOYMENT_MODE.upper()}] ✅ Flask app created successfully")

def get_system_prompt():
    """現在のデータベーススキーマを含むシステムプロンプトを生成します"""
    schema = discover_schema()
    return f"""
あなたは当社の営業アナリストです。社内の売上データを分析し、市場コンテキストを提供します。

対象範囲: 当社の売上データに関する質問のみに回答してください。関係のない質問については丁寧にお断りしてください。

ツール:
1. execute_sql_query - 売上データベースをクエリ
2. search_web - 売上パフォーマンスの市場コンテキストを取得

データベーススキーマ:
{schema}

重要なルール:
1. 社内売上データに関する質問には必ず execute_sql_query を使用する - クエリ内容を説明するだけでなく実際にクエリを実行する
2. search_web はデータベース結果を補完する市場コンテキストが必要な場合のみ使用
3. 上記スキーマに表示されているテーブルに対して SELECT クエリのみを使用
4. サンプルデータは限られた例のみ - 必ずクエリを実行してすべての実際の値とデータパターンを確認
5. データベースには2025年までのデータが含まれる - データが存在しないと言う前に必ずクエリを実行
6. content フィールドに SQL クエリを含めない - ビジネスインサイトと分析のみを提供
7. 必須: ツールを説明するのではなく、必ずツールを呼び出すこと

ワークフロー:
1. 質問を分析して必要な情報を決定
2. 社内売上データが必要な場合は必ず execute_sql_query を呼び出す
3. データベース結果を補完する市場コンテキストが必要な場合のみ search_web を呼び出す
4. 使用したツールからのインサイトを含む JSON レスポンスを返す

🚨 重要: 必ず JSON 形式で返す 🚨
すべてのレスポンスは有効な JSON でなければならない - 例外なし
リクエストをお断りする場合でも JSON 形式で返すこと

JSON 出力形式（必須）:
{{
  "content": "ここにレスポンステキスト",
  "sources": []
}}

例:
- 売上に関する質問: {{"content": "データを含む分析", "sources": [{{"type": "database", "name": "Sales Database"}}]}}
- 対象外: {{"content": "当社の売上データの分析のみ対応可能です", "sources": []}}
- エラー: {{"content": "リクエストを処理できません", "sources": []}}

JSON の重要な要件:
- {{ で始まり }} で終わる有効な JSON のみを出力
- JSON オブジェクトの前後にテキストを入れない
- 必ず "content" フィールドにレスポンスを文字列として含める
- 必ず "sources" 配列を含める（ツール未使用時は空配列）
- データベースソース: {{"type": "database", "name": "Sales Database"}}
- Web ソース: {{"type": "web", "title": "検索結果の正確なタイトル", "url": "検索結果の正確なURL"}}
- ソースを捏造しない - ツール結果からの正確なデータを使用

🔥 絶対要件 🔥
レスポンスは正確に: {{ "content": "...", "sources": [...] }} でなければならない
プレーンテキストレスポンスは許可されない - システムが失敗する
content に SQL 文を含めない - ビジネス分析のみ
"""

def get_database_connection():
    """データベース接続を取得します"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'postgres'),
            port=os.getenv('DB_PORT', 5432),
            database=os.getenv('DB_NAME', 'sales_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )

# amazonq-ignore-next-line
def discover_schema():
    """すべてのテーブルのデータベーススキーマを動的に検出します"""
    # amazonq-ignore-next-line
    global schema_cache
    if schema_cache:
        print('📋 Using cached schema')
        return schema_cache
    
    print('🔍 Discovering database schema dynamically...')
    # amazonq-ignore-next-line
    conn = get_database_connection()
    cursor = conn.cursor()
    
    # すべてのテーブルを取得
    cursor.execute("""
        SELECT 
            table_name,
            table_type,
            obj_description(c.oid) as table_comment
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name
        WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    print(f'📊 Found {len(tables)} tables: {[t[0] for t in tables]}')
    
    schema_description = 'Database Schema:\n\n'
    
    for table_name, table_type, table_comment in tables:
        print(f'🔍 Analyzing table: {table_name}')
        
        # テーブルスキーマを取得
        cursor.execute("""
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                col_description(pgc.oid, c.ordinal_position) as column_comment
            FROM information_schema.columns c
            LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
            WHERE c.table_name = %s
                AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """, (table_name,))
        columns = cursor.fetchall()
        
        # amazonq-ignore-next-line
        schema_description += f'Table: {table_name}\n'
        if table_comment:
            schema_description += f'Description: {table_comment}\n'
        
        schema_description += 'Columns:\n'
        for col_name, data_type, is_nullable, col_default, col_comment in columns:
            schema_description += f'- {col_name} ({data_type}'
            if is_nullable == 'NO':
                schema_description += ', NOT NULL'
            if col_default:
                schema_description += f', DEFAULT {col_default}'
            if col_comment:
                schema_description += f', -- {col_comment}'
            schema_description += ')\n'
        
        # 多様性を示す包括的なサンプルデータを追加
        try:
            # 最初の2行だけでなく、多様なサンプルデータを取得
            cursor.execute(
                sql.SQL('SELECT * FROM {} ORDER BY RANDOM() LIMIT 5').format(
                    sql.Identifier(table_name)
                )
            )
            sample_data = cursor.fetchall()
            if sample_data:
                col_names = [desc[0] for desc in cursor.description]
                sample_dict = [dict(zip(col_names, row)) for row in sample_data]
                schema_description += f'SAMPLE DATA (5 RANDOM ROWS - NOT COMPLETE DATASET):\n{json.dumps(sample_dict, default=str, indent=2)}\n'
                
                # 主要なカテゴリカル列のデータ多様性サマリを追加
                categorical_cols = ['productline', 'country', 'territory', 'dealsize', 'status']
                for col in categorical_cols:
                    if col in [c.lower() for c in col_names]:
                        cursor.execute(
                            sql.SQL('SELECT {}, COUNT(*) as count FROM {} GROUP BY {} ORDER BY count DESC LIMIT 10').format(
                                sql.Identifier(col),
                                sql.Identifier(table_name),
                                sql.Identifier(col)
                            )
                        )
                        variety_data = cursor.fetchall()
                        if variety_data:
                            schema_description += f'\nDATA VARIETY - {col.upper()} (top values):\n'
                            for value, count in variety_data:
                                schema_description += f'- {value}: {count} records\n'
                
                schema_description += f'\nCRITICAL: Sample shows only 5 random rows. The actual table contains thousands more records with extensive variety in all categorical columns. ALWAYS query the database to discover all actual values and patterns.\n'
                print(f'✅ Added comprehensive sample data for {table_name}')
        except Exception as e:
            print(f'⚠️ Could not get sample data for {table_name}: {e}')
        
        schema_description += '\n'
    
    cursor.close()
    conn.close()
    
    print('✅ Schema discovery complete')
    schema_cache = schema_description
    return schema_cache

@tool
def execute_sql_query(sql_query: str) -> str:
    """PostgreSQLデータベースでSQLクエリを実行します。システムはSQLクエリの生成が必要な場合、すべてのテーブル、カラム、サンプルデータを含む現在のデータベーススキーマを自動的に提供します。"""
    print("\n" + "="*50)
    print("🔥 EXECUTE_SQL_QUERY TOOL CALLED!")
    print(f"🔥 SQL Query: {sql_query}")
    print("="*50 + "\n")
    try:
        # デバッグ: 接続詳細を出力
        database_url = os.getenv('DATABASE_URL')
        print(f"[DB Debug] DATABASE_URL exists: {bool(database_url)}")
        if database_url:
            print("[DB Debug] Using DATABASE_URL connection")
            # amazonq-ignore-next-line
            conn = get_database_connection()
        else:
            print("[DB Debug] Using individual env vars")
            conn = get_database_connection()
        
        print("[DB Debug] Connection successful")
        print(f"[DB Debug] Executing SQL: {sql_query}")
        
        # amazonq-ignore-next-line
        cursor = conn.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        data = [dict(zip(columns, row)) for row in results]
        print(f"[DB Debug] Query returned {len(data)} rows")
        
        cursor.close()
        conn.close()
        
        response = {
            "data": data,
            "sql_query": sql_query,
            "source": "PostgreSQL Database",
            "record_count": len(data)
        }
        
        return json.dumps(response, default=str)
        
    except Exception as e:
        error_msg = f"Database query failed: {str(e)}"
        print(f"[DB Debug] {error_msg}")
        return json.dumps({"error": error_msg})

@tool
def search_web(query: str) -> str:
    """Brave Search APIを使用してクエリに関連する情報をウェブ検索します"""
    print("\n" + "="*50)
    print("🔥 SEARCH_WEB TOOL CALLED WITH QUERY ONLY!")
    print(f"🔥 Query: {query}")
    print("="*50 + "\n")
    
    all_results = []
    
    try:
        print("[Web Search Debug] Using Brave Search API...")
        
        # 環境変数から Brave Search API キーを取得
        brave_api_key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not brave_api_key:
            print("[Web Search Debug] ❌ BRAVE_SEARCH_API_KEY not found in environment")
            return json.dumps({"error": "Brave Search API key not configured"})
        
        print(f"[Web Search Debug] Starting Brave search for: '{query}'")
        
        # Brave Search API エンドポイント
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_api_key
        }
        params = {
            "q": query,
            # amazonq-ignore-next-line
            "count": 3
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        # amazonq-ignore-next-line
        print(f"[Web Search Debug] Brave API response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            web_results = data.get('web', {}).get('results', [])
            print(f"[Web Search Debug] Brave search returned {len(web_results)} results")
            
            for i, result in enumerate(web_results):
                search_result = {
                    'title': result.get('title', '')[:100],
                    'url': result.get('url', ''),
                    'snippet': result.get('description', '')[:200],
                    'source': 'Web Search'
                }
                all_results.append(search_result)
                print(f"[Web Search Debug] Result {i+1}: {search_result['title']} - {search_result['url']}")
                
        elif response.status_code == 429:
            print("[Web Search Debug] ❌ Rate limit exceeded for Brave Search API")
            return json.dumps({"error": "Brave Search API rate limit exceeded"})
        else:
            print(f"[Web Search Debug] ❌ Brave API error: {response.status_code} - {response.text}")
            return json.dumps({"error": f"Brave Search API error: {response.status_code}"})
                
    # amazonq-ignore-next-line
    except Exception as search_error:
        print(f"[Web Search Debug] ❌ Brave search error: {search_error}")
        print(f"[Web Search Debug] Traceback: {traceback.format_exc()}")
        return json.dumps({"error": f"Brave search failed: {search_error}"})
    
    response = {
        "query": query,
        "results": all_results,
        "source": "Web Search",
        "total_results": len(all_results)
    }
    
    print(f"[Web Search Debug] Returning {len(all_results)} results:")
    for i, result in enumerate(all_results):
        print(f"[Web Search Debug] Result {i+1}: {result['title']} - {result['url']}")
    
    print(f"[Web Search Debug] FULL RESPONSE TO AGENT:")
    print(json.dumps(response, indent=2)[:500] + "...")
    
    result = json.dumps(response)
    print(f"[Web Search Debug] Final JSON length: {len(result)}")
    return result



@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "runtime": f"Strands {DEPLOYMENT_MODE.upper()}"})

@app.route('/api/chat/message', methods=['POST'])
def chat_message():
    """フロントエンド互換のチャットエンドポイント"""
    try:
        data = request.get_json()
        user_message = data.get('message')  # フロントエンドは 'message' を送信
        session_id = data.get('sessionId')
        user_id = data.get('userId')  # 'anonymous' をデフォルトにしない

        # メインの invoke 関数を呼び出し
        return invoke_agent(user_message, session_id, user_id)
    except Exception as e:
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Chat API ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/invoke', methods=['POST'])
def invoke():
    """直接呼び出しエンドポイント"""
    try:
        data = request.get_json()
        user_message = data.get('prompt')
        session_id = data.get('sessionId')
        user_id = data.get('userId')  # 'anonymous' をデフォルトにしない

        return invoke_agent(user_message, session_id, user_id)
    except Exception as e:
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Invoke ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# amazonq-ignore-next-line
def invoke_agent(user_message, session_id, user_id):
    """コアエージェント呼び出しロジック"""
    try:
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Processing: {user_message}")
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Session: {session_id}, User: {user_id}")
        
        # オブザーバビリティのために OTEL baggage にセッション ID を設定
        if session_id:
            ctx = baggage.set_baggage("session.id", session_id)
            attach(ctx)
            print(f"[OTEL] Set session.id in baggage: {session_id}")
        
        # コンテナデプロイメント用に AgentCore Memory を初期化
        # amazonq-ignore-next-line
        global memory_id
        if not memory_id:
            try:
                print(f"🔄 Initializing AgentCore memory: {MEMORY_NAME}")
                memories = memory_client.list_memories()
                memory_id = next((m['id'] for m in memories if m['id'].startswith(MEMORY_NAME)), None)
                
                if memory_id:
                    print(f"✅ Found existing AgentCore memory: {memory_id}")
                else:
                    print(f"🔄 Creating new AgentCore memory: {MEMORY_NAME}")
                    memory = memory_client.create_memory_and_wait(
                        name=MEMORY_NAME,
                        strategies=[],
                        description="Short-term memory for sales assistant",
                        event_expiry_days=30
                    )
                    memory_id = memory['id']
                    print(f"✅ Created AgentCore memory: {memory_id}")
            # amazonq-ignore-next-line
            except Exception as e:
                print(f"❌ Memory initialization failed: {e}")
                memory_id = None
        
        # AgentCore Memory フックを使用してエージェントを作成
        hooks = []
        if memory_id:
            hooks.append(MemoryHookProvider(memory_client, memory_id))
        
        # amazonq-ignore-next-line
        agent = Agent(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            system_prompt=get_system_prompt(),
            tools=[execute_sql_query, search_web],
            hooks=hooks,
            state={"actor_id": user_id, "session_id": session_id}
        )
        
        # エージェントを呼び出し
        response = agent(user_message)
        result = response.message['content'][0]['text']
        
        # JSON をクリーンアップして検証
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            json_str = json_match.group(0)
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Original JSON length: {len(json_str)}")
            
            # 制御文字をクリーンアップして空白を正規化
            cleaned_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
            cleaned_json = re.sub(r'\s+', ' ', cleaned_json)
            
            # content フィールド内のエスケープされていないクォートを修正
            try:
                # パースして再シリアライズしてエスケープを修正
                parsed = json.loads(cleaned_json)
                cleaned_json = json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                # フォールバックとして手動でクォートをエスケープ
                cleaned_json = re.sub(r'"([^"]*?)"([^"]*?)"([^"]*?)"', r'"\1\\"\2\\"\3"', cleaned_json)
            
            try:
                json.loads(cleaned_json)
                result = cleaned_json
                print(f"[{DEPLOYMENT_MODE.upper()} Runtime] JSON validation successful")
            except json.JSONDecodeError as e:
                print(f"[{DEPLOYMENT_MODE.upper()} Runtime] JSON validation failed: {e}")
                print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Keeping original response")
        
        # エージェント結果をパースしてフロントエンド互換にフォーマット
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Final result for parsing: {result[:200]}...")
        try:
            parsed_result = json.loads(result)
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Successfully parsed JSON")
            # フロントエンドの期待に合わせてレスポンスをフォーマット
            streaming_response = {
                "type": "complete",
                "response": {
                    "answer": parsed_result.get("content", ""),
                    "sources": parsed_result.get("sources", []),
                    "reasoning": [],
                    "citations": []
                },
                "timestamp": "2025-10-03T04:26:37.529Z"
            }
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Returning streaming response")
            return jsonify(streaming_response)
        except json.JSONDecodeError as e:
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] JSON parse error: {e}")
            print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Error at position {e.pos}: {repr(result[max(0, e.pos-50):e.pos+50]) if hasattr(e, 'pos') else 'N/A'}")
            # 有効な JSON でない場合はエラーフォーマットを返す
            error_response = {
                "type": "error",
                "error": f"Failed to parse agent response: {str(e)}"
            }
            return jsonify(error_response)
        
    except Exception as e:
        print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Agent ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# リクエストごとにエージェントを作成して新しいスキーマ検出を保証
agent = None

# AgentCore Memory 設定

# メモリ設定
REGION = os.getenv('AWS_REGION', 'ap-southeast-2')
MEMORY_NAME = "SalesAnalystMemory"

# Memory クライアントを初期化
# amazonq-ignore-next-line
memory_client = MemoryClient(region_name=REGION)
memory_id = None

# 適切なロギングを保証するためリクエストごとにメモリを初期化
memory_id = None

class MemoryHookProvider(HookProvider):
    def __init__(self, memory_client: MemoryClient, memory_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
    
    def on_agent_initialized(self, event: AgentInitializedEvent):
        """エージェント開始時に最近の会話履歴を読み込みます"""
        try:
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")
            
            # 匿名ユーザーの場合、session_id を actor_id として使用
            if not actor_id:
                actor_id = session_id

            if not actor_id or not session_id or not self.memory_id:
                return
            
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                # amazonq-ignore-next-line
                k=6  # Last 6 turns for context
            )
            
            if recent_turns:
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        role = message['role']
                        # amazonq-ignore-next-line
                        content = message['content']['text']
                        context_messages.append(f"{role}: {content}")
                
                context = "\n".join(context_messages)
                event.agent.system_prompt += f"\n\nPREVIOUS CONVERSATION CONTEXT:\n{context}\n\nCURRENT QUESTION:\n"
                # amazonq-ignore-next-line
                print(f"✅ Loaded {len(recent_turns)} conversation turns from AgentCore Memory")
                
        except Exception as e:
            if "Memory not found" in str(e):
                print(f"❌ Memory not found during load, recreating: {e}")
                self._recreate_memory()
            else:
                print(f"❌ Memory load error: {e}")
    
    def on_message_added(self, event: MessageAddedEvent):
        """AgentCore Memoryにメッセージを保存します"""
        try:
            messages = event.agent.messages
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")
            
            # 匿名ユーザーの場合、session_id を actor_id として使用
            if not actor_id:
                actor_id = session_id

            # amazonq-ignore-next-line
            if messages and messages[-1]["content"][0].get("text") and self.memory_id:
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[(messages[-1]["content"][0]["text"], messages[-1]["role"])]
                )
        except Exception as e:
            # amazonq-ignore-next-line
            if "Memory not found" in str(e):
                print(f"❌ Memory not found, recreating: {e}")
                self._recreate_memory()
            else:
                print(f"❌ Memory save error: {e}")
    
    def _recreate_memory(self):
        """削除された場合にメモリを再作成します"""
        try:
            # amazonq-ignore-next-line
            global memory_id
            print(f"🔄 Recreating AgentCore memory: {MEMORY_NAME}")
            memory = self.memory_client.create_memory_and_wait(
                name=MEMORY_NAME,
                strategies=[],
                description="Short-term memory for sales assistant",
                event_expiry_days=30
            )
            # amazonq-ignore-next-line
            memory_id = memory['id']
            self.memory_id = memory_id
            print(f"✅ Recreated AgentCore memory: {memory_id}")
        # amazonq-ignore-next-line
        except Exception as e:
            print(f"❌ Failed to recreate memory: {e}")
    
    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)

# AgentCore エントリーポイント（app が BedrockAgentCoreApp の場合のみ動作）
# amazonq-ignore-next-line
def agentcore_invoke(payload):
    """エージェント呼び出しハンドラー"""
    try:
        print(f"[AgentCore Runtime] Received payload: {payload}")
        
        # メッセージとセッション ID を抽出
        user_message = payload.get('prompt')
        session_id = payload.get('sessionId')
        
        if not user_message:
            messages = payload.get('messages', [])
            user_message = messages[0]['content'] if messages else payload.get('inputText', '')
        
        if not user_message:
            print("[AgentCore Runtime] No prompt found in payload")
            return "No prompt found in input, please provide a message"
        
        # AgentCore Memory 用にペイロードからユーザー ID を抽出
        user_id = payload.get('userId') or payload.get('user_id')
        actor_id = user_id  # 匿名ユーザーには None を使用
        
        print(f"[AgentCore Runtime] Processing message: {user_message}")
        print(f"[AgentCore Runtime] Session ID: {session_id}")
        print(f"[AgentCore Runtime] User ID: {user_id}")
        print(f"[AgentCore Runtime] Actor ID: {actor_id}")
        contextual_message = user_message

        # まだ初期化されていない場合はメモリを初期化
        # amazonq-ignore-next-line
        global memory_id
        # amazonq-ignore-next-line
        if not memory_id:
            try:
                print(f"🔄 Initializing AgentCore memory: {MEMORY_NAME}")
                memories = memory_client.list_memories()
                memory_id = next((m['id'] for m in memories if m['id'].startswith(MEMORY_NAME)), None)
                
                if memory_id:
                    print(f"✅ Found existing AgentCore memory: {memory_id}")
                else:
                    print(f"🔄 Creating new AgentCore memory: {MEMORY_NAME}")
                    memory = memory_client.create_memory_and_wait(
                        name=MEMORY_NAME,
                        strategies=[],
                        description="Short-term memory for sales assistant",
                        event_expiry_days=30
                    )
                    memory_id = memory['id']
                    print(f"✅ Created AgentCore memory: {memory_id}")
            except Exception as e:
                print(f"❌ Memory initialization failed: {e}")
                memory_id = None
        else:
            print(f"✅ Using existing memory: {memory_id}")
        
        # スキーマは最初の検出後にキャッシュされる

        # AgentCore Memory フックを使用してエージェントを作成
        print('🔥 INITIALIZING AGENT WITH DYNAMIC SCHEMA DISCOVERY')
        print('='*60)
        
        hooks = []
        if memory_id:
            hooks.append(MemoryHookProvider(memory_client, memory_id))
            print(f"✅ Added memory hook with ID: {memory_id}")
        
        # amazonq-ignore-next-line
        agent = Agent(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            system_prompt=get_system_prompt(),
            tools=[execute_sql_query, search_web],
            hooks=hooks,
            state={"actor_id": actor_id, "session_id": session_id}
        )
        print('✅ Agent initialized with dynamic schema and AgentCore Memory')
        print('='*60)
        
        # OTEL トレーシングでエージェントを呼び出し
        print("🚀 INVOKING AGENT NOW...")
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("agent_invoke") as span:
                span.set_attribute("session_id", session_id or "unknown")
                span.set_attribute("user_id", user_id or "unknown")
                span.add_event("Agent invocation started")
                response = agent(contextual_message)
                span.add_event("Agent invocation completed")
                print("[OTEL] ✅ Agent invocation traced")
        # amazonq-ignore-next-line
        except Exception as otel_error:
            print(f"[OTEL] ⚠️ Tracing failed: {otel_error}")
            response = agent(contextual_message)
        
        print("✅ AGENT INVOCATION COMPLETE")
        print(f"[AgentCore Runtime] Agent response type: {type(response)}")
        
        # JSON レスポンスをパースしてクリーンアップ
        result = response.message['content'][0]['text']
        print(f"[AgentCore Runtime] Raw result length: {len(result)}")
        
        # レスポンスから JSON オブジェクトを抽出してクリーンアップ

        # 最終レスポンスに含まれるべきでないデバッグリフレクションテキストを削除
        result = re.sub(r'<search_quality_reflection>.*?</search_quality_reflection>', '', result, flags=re.DOTALL)
        result = re.sub(r'<search_quality_score>.*?</search_quality_score>', '', result, flags=re.DOTALL)
        
        # amazonq-ignore-next-line
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            json_str = json_match.group(0)
            print(f"[AgentCore Runtime] Original JSON length: {len(json_str)}")
            print(f"[AgentCore Runtime] First 200 chars: {repr(json_str[:200])}")
            
            # 制御文字をクリーンアップして空白を正規化
            cleaned_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
            cleaned_json = re.sub(r'\s+', ' ', cleaned_json)
            
            # content フィールド内のエスケープされていないクォートを修正
            try:
                # パースして再シリアライズしてエスケープを修正
                parsed = json.loads(cleaned_json)
                cleaned_json = json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                # フォールバックとして手動でクォートをエスケープ
                cleaned_json = re.sub(r'"([^"]*?)"([^"]*?)"([^"]*?)"', r'"\1\\"\2\\"\3"', cleaned_json)
            print(f"[AgentCore Runtime] Cleaned JSON length: {len(cleaned_json)}")
            print(f"[AgentCore Runtime] Cleaned first 200 chars: {repr(cleaned_json[:200])}")
            
            try:
                json.loads(cleaned_json)
                result = cleaned_json
                print(f"[AgentCore Runtime] JSON validation successful")
            except json.JSONDecodeError as e:
                print(f"[AgentCore Runtime] JSON validation failed: {e}")
                print(f"[AgentCore Runtime] Error at position {e.pos}: {repr(cleaned_json[max(0, e.pos-50):e.pos+50])}")
                print("[AgentCore Runtime] Keeping original response")
        else:
            print("[AgentCore Runtime] No JSON object found in response")
        
        # AgentCore Memory はフックを介して会話ストレージを自動的に処理
        print(f"[AgentCore Runtime] Conversation stored in AgentCore Memory for user: {actor_id}, session: {session_id}")
        
        # AgentCore の場合は生のレスポンスを返す（JSON パースは AgentCore が処理）
        return result
        
    except Exception as e:
        print(f"[AgentCore Runtime] ERROR: {str(e)}")
        print(f"[AgentCore Runtime] Traceback: {traceback.format_exc()}")
        return f"Error processing request: {str(e)}"

if __name__ == "__main__":
    # コンテナロギング用にバッファリングなし出力を強制
    sys.stdout.flush()
    sys.stderr.flush()
    
    print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Starting Strands Agent with ADOT observability")
    print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Available tools: execute_sql_query, search_web")
    print(f"[{DEPLOYMENT_MODE.upper()} Runtime] Deployment mode: {DEPLOYMENT_MODE}")
    
    # セキュリティ: ローカル開発時のみデバッグモードを有効化
    debug_mode = DEPLOYMENT_MODE == 'local'
    # 注意: host='0.0.0.0' はコンテナデプロイメントで外部接続を受け入れるために必要
    # コンテナネットワーキングとロードバランサーがセキュリティ境界を提供
    app.run(host='0.0.0.0', port=8080, debug=debug_mode, use_reloader=False)  # nosec B104
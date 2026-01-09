"""
Bedrock Guardrails を使用した Gateway MCP RESPONSES 用 PII マスキングインターセプター

この Lambda 関数は Gateway MCP tools/call RESPONSES をインターセプトし、
Amazon Bedrock Guardrails API を使用してすべてのツールレスポンスの機密 PII データを
マスクします。任意のツールレスポンスを変換する RESPONSE インターセプターとして設定されます。
"""

import json
import os
import boto3
from typing import Any, Dict

# Bedrock Runtime クライアントを初期化
bedrock_runtime = boto3.client('bedrock-runtime')

# 環境変数から Guardrail 設定を取得
GUARDRAIL_ID = os.environ.get('GUARDRAIL_ID')
GUARDRAIL_VERSION = os.environ.get('GUARDRAIL_VERSION', 'DRAFT')

def mask_pii_with_guardrails(text: str) -> str:
    """
    Use Bedrock Guardrails to mask PII in text.
    
    Args:
        text: Text content that may contain PII
    
    Returns:
        Text with PII masked/anonymized by Guardrails
    """
    print(f"[DEBUG] mask_pii_with_guardrails - INPUT text (first 200 chars): {text[:200]}")
    
    if not GUARDRAIL_ID:
        print("[DEBUG] WARNING: GUARDRAIL_ID not configured, skipping PII masking")
        print(f"[DEBUG] mask_pii_with_guardrails - RETURNING original text (no guardrail)")
        return text
    
    try:
        print(f"[DEBUG] Calling Bedrock Guardrails API with ID: {GUARDRAIL_ID}, Version: {GUARDRAIL_VERSION}")
        
        # テキストに guardrail を適用
        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=GUARDRAIL_ID,
            guardrailVersion=GUARDRAIL_VERSION,
            source='OUTPUT', # We're filtering output from tools
            outputScope='FULL',  
            content=[{
                'text': {
                    'text': text
                }
            }]
        )
        
        print(f"[DEBUG] Guardrails API response received: {json.dumps(response, default=str)}")
        
        # レスポンスからマスクされたテキストを抽出
        outputs = response.get('outputs', [])
        if outputs and len(outputs) > 0:
            masked_text = outputs[0].get('text', text)
            print(f"[DEBUG] 抽出されたマスク済みテキスト (最初の200文字): {masked_text[:200]}")

            # PII 検出の詳細をログ出力
            usage = response.get('usage', {})
            assessments = response.get('assessments', [])

            if usage.get('contentPolicyUnits', 0) > 0:
                print(f"[DEBUG] Guardrails によって PII が検出され匿名化されました")

                # 検出された PII のタイプをログ出力
                if assessments:
                    for assessment in assessments:
                        sensitive_info = assessment.get('sensitiveInformationPolicy', {})
                        pii_entities = sensitive_info.get('piiEntities', [])
                        if pii_entities:
                            detected_types = [entity.get('type') for entity in pii_entities]
                            print(f"[DEBUG]   検出された PII タイプ: {', '.join(detected_types)}")
            
            print(f"[DEBUG] mask_pii_with_guardrails - マスク済みテキストを返します")
            return masked_text

        print(f"[DEBUG] Guardrails からの出力がありません。元のテキストを返します")
        return text

    except Exception as e:
        error_message = str(e)
        print(f"[DEBUG] Guardrails 適用中にエラー: {error_message}")
        print(f"[DEBUG]   Guardrail ID: {GUARDRAIL_ID}")
        print(f"[DEBUG]   Guardrail Version: {GUARDRAIL_VERSION}")

        # guardrail が存在しないことに関する検証エラーかどうかを確認
        if 'does not exist' in error_message or 'ValidationException' in error_message:
            print("[DEBUG]   警告: Guardrail ID またはバージョンが無効または存在しません")
            print("[DEBUG]   警告: ステップ 1.3 が正常に実行されて Guardrail が作成されていることを確認してください")
            print("[DEBUG]   警告: Lambda 環境変数が正しく設定されていることを確認してください")

        # エラー時は元のテキストを返す（ブロッキングを避けるためフェイルオープン）
        print(f"[DEBUG] mask_pii_with_guardrails - 元のテキストを返します (エラー発生)")
        return text

def mask_tool_response(response_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask PII in tool response by extracting text from body->result->content->text,
    parsing the JSON, anonymizing it with Bedrock Guardrails, and reconstructing properly.
    
    Args:
        response_body: MCP JSON-RPC response body
    
    Returns:
        Response body with masked PII in the text field
    """
    print(f"[DEBUG] mask_tool_response - INPUT response_body: {json.dumps(response_body, default=str)}")
    
    # 元のデータを変更しないようにディープコピーを作成
    masked_response = json.loads(json.dumps(response_body))
    print(f"[DEBUG] response_body のディープコピーを作成しました")

    # body->result->content に移動
    if 'result' not in masked_response:
        print(f"[DEBUG] No 'result' field in response_body")
        return masked_response
    
    if 'content' not in masked_response['result']:
        print(f"[DEBUG] No 'content' field in result")
        return masked_response
    
    content_list = masked_response['result']['content']
    if not isinstance(content_list, list) or len(content_list) == 0:
        print(f"[DEBUG] 'content' is not a list or is empty")
        return masked_response
    
    print(f"[DEBUG] Processing {len(content_list)} content items")
    
    # 各コンテンツアイテムを処理
    for i, content_item in enumerate(content_list):
        if content_item.get('type') != 'text':
            print(f"[DEBUG] Content item {i} is not type 'text', skipping")
            continue
        
        text_value = content_item.get('text', '')
        if not text_value:
            print(f"[DEBUG] Content item {i} has empty text, skipping")
            continue
        
        print(f"[DEBUG] Content item {i} text (first 200 chars): {text_value[:200]}")
        
        try:
            # テキストを JSON としてパースを試みる
            parsed_json = json.loads(text_value)
            print(f"[DEBUG] テキストを JSON として正常にパースしました")
            print(f"[DEBUG] パースされた JSON 構造: {json.dumps(parsed_json, default=str)[:300]}")

            # パースされた JSON を Guardrails 処理用のきれいな文字列に変換
            json_string = json.dumps(parsed_json, indent=2)
            print(f"[DEBUG] Guardrails 用に JSON 文字列に変換しました (最初の300文字): {json_string[:300]}")

            # Bedrock Guardrails を適用して JSON コンテンツを匿名化
            print(f"[DEBUG] Bedrock Guardrails を適用して JSON コンテンツを匿名化中...")
            anonymized_json_string = mask_pii_with_guardrails(json_string)
            print(f"[DEBUG] 匿名化された JSON 文字列 (最初の300文字): {anonymized_json_string[:300]}")

            # 匿名化された文字列を JSON オブジェクトに再パース
            try:
                anonymized_json = json.loads(anonymized_json_string)
                print(f"[DEBUG] 匿名化された文字列を JSON に正常に再パースしました")
                print(f"[DEBUG] 匿名化された JSON オブジェクト: {json.dumps(anonymized_json, default=str)[:300]}")

                # JSON オブジェクトとして直接置換（文字列ではなく）
                masked_response['result']['content'][i]['text'] = anonymized_json
                print(f"[DEBUG] コンテンツアイテム {i} のテキストを JSON オブジェクトで置換しました（文字列ではない）")

            except json.JSONDecodeError as e:
                print(f"[DEBUG] 匿名化された文字列を JSON に再パースできませんでした: {e}")
                print(f"[DEBUG] 匿名化された文字列をそのまま使用します")
                masked_response['result']['content'][i]['text'] = anonymized_json_string

        except json.JSONDecodeError:
            # JSON ではない場合、プレーンテキストとして処理
            print(f"[DEBUG] テキストは JSON ではありません。プレーンテキストとして処理します")

            # Bedrock Guardrails を適用してテキストを匿名化
            print(f"[DEBUG] Bedrock Guardrails を適用してプレーンテキストを匿名化中...")
            anonymized_text = mask_pii_with_guardrails(text_value)
            print(f"[DEBUG] 匿名化されたテキスト (最初の200文字): {anonymized_text[:200]}")

            # レスポンスにテキストを戻す
            masked_response['result']['content'][i]['text'] = anonymized_text
            print(f"[DEBUG] コンテンツアイテム {i} のテキストを置換しました")
    
    print(f"[DEBUG] mask_tool_response - RETURNING masked_response")
    return masked_response

def lambda_handler(event, context):
    """
    Main Lambda handler for Gateway RESPONSE interceptor.
    
    This handler applies PII masking to ALL tool responses using Bedrock Guardrails.
    
    Expected event structure (from Gateway RESPONSE for tools/call):
    {
        "interceptorInputVersion": "1.0",
        "mcp": {
            "gatewayResponse": {
                "headers": {...},
                "body": {
                    "jsonrpc": "2.0",
                    "id": "invoke-tool-request",
                    "result": {
                        "isError": false,
                        "content": [
                            {
                                "type": "text",
                                "text": "{...tool data with potential PII...}"
                            }
                        ]
                    }
                },
                "statusCode": 200
            },
            "gatewayRequest": {...}
        }
    }
    
    Returns transformed response with masked PII for any tool.
    """
    print(f"[DEBUG] ========== LAMBDA HANDLER START ==========")
    print(f"[DEBUG] PII Masking Interceptor - Received event: {json.dumps(event, default=str)}")
    
    try:
        # MCP データを抽出
        mcp_data = event.get('mcp', {})
        print(f"[DEBUG] 抽出された mcp_data: {json.dumps(mcp_data, default=str)}")

        gateway_response = mcp_data.get('gatewayResponse', {})
        print(f"[DEBUG] 抽出された gateway_response: {json.dumps(gateway_response, default=str)}")

        gateway_request = mcp_data.get('gatewayRequest', {})
        print(f"[DEBUG] 抽出された gateway_request: {json.dumps(gateway_request, default=str)}")

        # レスポンスデータを取得
        response_headers = gateway_response.get('headers', {})
        print(f"[DEBUG] response_headers: {response_headers}")

        response_body = gateway_response.get('body', {})
        print(f"[DEBUG] response_body: {json.dumps(response_body, default=str)}")

        status_code = gateway_response.get('statusCode', 200)
        print(f"[DEBUG] status_code: {status_code}")

        # どのツールが呼び出されたかを確認するためリクエストデータを取得
        request_body = gateway_request.get('body', {})
        print(f"[DEBUG] request_body: {json.dumps(request_body, default=str)}")

        method = request_body.get('method', '')
        print(f"[DEBUG] メソッド: {method}")

        # tools/call レスポンスのみを処理
        if method == 'tools/call':
            params = request_body.get('params', {})
            tool_name = params.get('name', '')
            
            print(f"[DEBUG] 呼び出されたツール: {tool_name}")
            print(f"[DEBUG] ツールレスポンスに PII マスキングを適用中...")

            # 任意のツールのレスポンスで PII をマスク
            masked_body = mask_tool_response(response_body)

            print(f"[DEBUG] マスクされたレスポンスボディ: {json.dumps(masked_body, default=str)}")

            # 返却オブジェクトを構築
            return_obj = {
                "interceptorOutputVersion": "1.0",
                "mcp": {
                    "transformedGatewayResponse": {
                        "headers": response_headers,
                        "body": masked_body,
                        "statusCode": status_code
                    }
                }
            }
            
            print(f"[DEBUG] lambda_handler - RETURNING (tools/call): {json.dumps(return_obj, default=str)}")
            print(f"[DEBUG] ========== LAMBDA HANDLER END (tools/call) ==========")
            return return_obj
        
        # 非顧客データレスポンスは変更せずにパススルー
        print(f"[DEBUG] メソッドが 'tools/call' ではないため、変更せずにパススルーします")
        
        passthrough_obj = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "headers": response_headers,
                    "body": response_body,
                    "statusCode": status_code
                }
            }
        }
        
        print(f"[DEBUG] lambda_handler - RETURNING (passthrough): {json.dumps(passthrough_obj, default=str)}")
        print(f"[DEBUG] ========== LAMBDA HANDLER END (passthrough) ==========")
        return passthrough_obj
    
    except Exception as e:
        print(f"[DEBUG] ERROR in lambda_handler: {e}")
        
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        
        # エラー時は変更せずにパススルー（ブロッキングより安全）
        error_obj = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "headers": gateway_response.get('headers', {}),
                    "body": gateway_response.get('body', {}),
                    "statusCode": gateway_response.get('statusCode', 500)
                }
            }
        }
        
        print(f"[DEBUG] lambda_handler - RETURNING (error): {json.dumps(error_obj, default=str)}")
        print(f"[DEBUG] ========== LAMBDA HANDLER END (error) ==========")
        return error_obj
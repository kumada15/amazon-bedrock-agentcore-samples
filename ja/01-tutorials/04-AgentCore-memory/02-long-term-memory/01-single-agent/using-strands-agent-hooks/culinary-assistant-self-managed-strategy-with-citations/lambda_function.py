import json
import boto3
import logging
import uuid
import time
from datetime import datetime
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class NotificationHandler:
    """SQS イベントの解析と S3 ペイロードの取得を処理します"""

    def __init__(self):
        self.s3_client = boto3.client('s3')

    def process_sqs_event(self, event):
        """SQS イベントからジョブ詳細を抽出し、S3 ペイロードをダウンロードします"""
        if len(event['Records']) != 1:
            raise ValueError(f"Expected 1 record, got {len(event['Records'])}")

        # Parse SQS message
        record = event['Records'][0]
        message = json.loads(record['body'])
        sqs_message = json.loads(message['Message'])

        logger.info(f"メッセージを受信しました: {json.dumps(sqs_message)}")

        # Extract job metadata
        job_metadata = {
            'job_id': sqs_message['jobId'],
            'memory_id': sqs_message['memoryId'],
            'strategy_id': sqs_message['strategyId'],
            's3_location': sqs_message['s3PayloadLocation']
        }

        # Download and parse payload
        payload = self._download_payload(job_metadata['s3_location'])

        return job_metadata, payload

    def _download_payload(self, s3_location):
        """S3 ロケーションからペイロードをダウンロードします"""
        parsed_url = urlparse(s3_location)
        bucket = parsed_url.netloc
        key = parsed_url.path.lstrip('/')

        logger.info(f"バケットからペイロードをダウンロード中: bucket={bucket}, key={key}")

        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(response['Body'].read())


class MemoryExtractor:
    """会話ペイロードからメモリレコードを抽出します"""

    def __init__(self, model_id='global.anthropic.claude-haiku-4-5-20251001-v1:0'):
        self.bedrock_client = boto3.client('bedrock-runtime')
        self.model_id = model_id

    def extract_memories(self, payload, s3_location=None, job_id=None):
        """Bedrock モデルを使用して会話ペイロードからメモリを抽出します"""
        conversation_text = self._build_conversation_text(payload)

        prompt = f"""Extract user preferences, interests, and facts from this conversation.
Return ONLY a valid JSON array with this format:
[{{"content": "detailed description", "type": "preference|interest|fact", "confidence": 0.0-1.0}}]

Focus on extracting specific, meaningful pieces of information that would be useful to remember.
Conversation:
{conversation_text}"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            extracted_text = response_body['content'][0]['text']

            # Find JSON in the response
            start_idx = extracted_text.find('[')
            end_idx = extracted_text.rfind(']') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = extracted_text[start_idx:end_idx]
                extracted_data = json.loads(json_str)
                logger.info(f"メモリを {len(extracted_data)} 件抽出しました")
                return self._format_extracted_memories(extracted_data, payload, s3_location, job_id)
            else:
                logger.error("モデルのレスポンスに JSON が見つかりませんでした")
                return []

        except Exception as e:
            logger.error(f"メモリの抽出中にエラーが発生しました: {str(e)}")
            return []

    def _build_conversation_text(self, payload):
        """ペイロードからフォーマットされた会話テキストを構築します"""
        text = ""

        # Include historical context if available
        if 'historicalContext' in payload:
            text += "Previous conversation:\n"
            for msg in payload['historicalContext']:
                if 'role' in msg and 'content' in msg and 'text' in msg['content']:
                    text += f"{msg['role']}: {msg['content']['text']}\n"

        # Add current context
        if 'currentContext' in payload:
            text += "\nCurrent conversation:\n"
            for msg in payload['currentContext']:
                if 'role' in msg and 'content' in msg and 'text' in msg['content']:
                    text += f"{msg['role']}: {msg['content']['text']}\n"

        return text

    def _format_extracted_memories(self, extracted_data, payload, s3_location=None, job_id=None):
        """抽出されたメモリをメタデータと引用情報でフォーマットします"""
        memories = []
        session_id = payload.get('sessionId', 'unknown-session')
        actor_id = payload.get('actorId', 'unknown-actor')

        # Get timestamp from payload or use current time
        timestamp = payload.get('endingTimestamp', int(time.time()))

        # Get starting timestamp for context window
        starting_timestamp = payload.get('startingTimestamp', timestamp)

        for item in extracted_data:
            if not isinstance(item, dict) or 'content' not in item or 'type' not in item:
                logger.warning(f"無効なメモリアイテムをスキップしています: {item}")
                continue

            # For this demo we'll focus only on user interests with a hierarchical namespace
            # Format: /interests/actor/{actorId}/session/{sessionId}
            namespace = f"/interests/actor/{actor_id}/session/{session_id}"

            # Build citation information to link long-term memory back to short-term memory source
            citation_info = {
                'source_type': 'short_term_memory',
                'session_id': session_id,
                'actor_id': actor_id,
                'starting_timestamp': starting_timestamp,
                'ending_timestamp': timestamp
            }

            # Add S3 URI if available
            if s3_location:
                citation_info['s3_uri'] = s3_location
                citation_info['s3_payload_location'] = s3_location

            # Add job ID if available
            if job_id:
                citation_info['extraction_job_id'] = job_id

            # Format citation as readable text to append to content
            citation_text = f"\n\n[Citation: Extracted from session {session_id}, actor {actor_id}"
            if s3_location:
                citation_text += f", source: {s3_location}"
            if job_id:
                citation_text += f", job: {job_id}"
            citation_text += f", timestamp: {timestamp}]"

            # Append citation to content
            content_with_citation = item['content'] + citation_text

            memory = {
                'content': content_with_citation,
                'namespaces': [namespace],
                'memoryStrategyId': None,  # Will be set later
                'timestamp': timestamp,
                'metadata': citation_info  # Store structured citation metadata
            }

            logger.info(f"名前空間付きでメモリを抽出しました: {namespace}")
            logger.info(f"引用付きでメモリを抽出しました: {memory}")

            memories.append(memory)

        return memories


class MemoryIngestor:
    """抽出されたメモリを AgentCore に取り込みます"""

    def __init__(self):
        self.agentcore_client = boto3.client('bedrock-agentcore')

    def batch_ingest_memories(self, memory_id, memory_records, strategy_id):
        """AgentCore バッチ API を使用してメモリレコードを取り込みます"""
        if not memory_records:
            logger.info("取り込むメモリレコードがありません")
            return {'recordsIngested': 0}

        # Set strategy ID for all records
        for record in memory_records:
            record['memoryStrategyId'] = strategy_id

        # Prepare batch request
        batch_records = []
        for record in memory_records:
            batch_record = {
                'requestIdentifier': str(uuid.uuid4()),
                'content': {
                    'text': record['content']
                },
                'namespaces': record['namespaces'],
                'memoryStrategyId': record['memoryStrategyId']
            }

            # Add timestamp if provided - handle millisecond timestamps
            if 'timestamp' in record:
                try:
                    ts_value = record['timestamp']

                    # Check if timestamp is in milliseconds (13 digits)
                    if isinstance(ts_value, int) and ts_value > 10000000000:  # More than 10 billion = milliseconds
                        # Convert milliseconds to seconds
                        ts_seconds = ts_value / 1000.0
                        batch_record['timestamp'] = datetime.fromtimestamp(ts_seconds)
                        logger.info(f"ミリ秒タイムスタンプを datetime に変換しました: {batch_record['timestamp']}")
                    else:
                        # Handle as regular Unix timestamp
                        batch_record['timestamp'] = datetime.fromtimestamp(ts_value)
                except Exception as e:
                    logger.error(f"タイムスタンプ処理中にエラーが発生しました {record['timestamp']}: {str(e)}")
                    # Use current time as fallback
                    batch_record['timestamp'] = datetime.now()
                    logger.info(f"フォールバックタイムスタンプを使用しています: {batch_record['timestamp']}")

            batch_records.append(batch_record)

        # Execute batch create
        try:
            logger.info(f"{len(batch_records)} 件のメモリレコードを取り込み中")

            response = self.agentcore_client.batch_create_memory_records(
                memoryId=memory_id,
                records=batch_records,
                clientToken=str(uuid.uuid4())
            )

            logger.info(f"{len(batch_records)} 件のメモリレコードを正常に取り込みました")
            return {
                'recordsIngested': len(batch_records)
            }

        except Exception as e:
            logger.error(f"メモリレコードの取り込みに失敗しました: {str(e)}")
            raise


def lambda_handler(event, context):
    """メモリ処理パイプラインを調整するメインの Lambda ハンドラー"""

    # Initialize components
    notification_handler = NotificationHandler()
    extractor = MemoryExtractor()
    ingestor = MemoryIngestor()

    try:
        # 1. Handle notification and download payload
        job_metadata, payload = notification_handler.process_sqs_event(event)
        logger.info(f"ジョブ {job_metadata['job_id']} をメモリ {job_metadata['memory_id']} 用に処理中")

        # 2. Extract memories using Bedrock model with citation information
        extracted_memories = extractor.extract_memories(
            payload,
            s3_location=job_metadata['s3_location'],
            job_id=job_metadata['job_id']
        )
        logger.info(f"S3 引用付きでメモリを {len(extracted_memories)} 件抽出しました: {job_metadata['s3_location']}")

        # 3. Ingest extracted memories into AgentCore
        if extracted_memories:
            ingest_result = ingestor.batch_ingest_memories(
                job_metadata['memory_id'],
                extracted_memories,
                job_metadata['strategy_id']
            )

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'jobId': job_metadata['job_id'],
                    'extractedMemories': len(extracted_memories),
                    'ingestedRecords': ingest_result['recordsIngested'],
                })
            }
        else:
            logger.info("メモリが抽出されなかったため、取り込むものがありません")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'jobId': job_metadata['job_id'],
                    'extractedMemories': 0,
                    'ingestedRecords': 0,
                })
            }

    except Exception as e:
        logger.error(f"パイプラインが失敗しました: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
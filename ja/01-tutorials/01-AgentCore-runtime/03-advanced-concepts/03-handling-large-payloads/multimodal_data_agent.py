from strands import Agent, tool
from strands.models import BedrockModel
import pandas as pd
import base64
import io
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# モデルとエージェントを初期化
model_id = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(
    model_id=model_id,
    max_tokens=16000
)

agent = Agent(
    model=model,
    system_prompt="""
    あなたは大きなExcelファイルと画像を処理できるデータ分析アシスタントです。
    マルチモーダルデータが与えられた場合、構造化データと視覚的コンテンツの両方を分析し、
    両方のデータソースを組み合わせた包括的なインサイトを提供してください。
    """
)

@app.entrypoint
def multimodal_data_processor(payload, context):
    """
    Excelデータと画像を含む大容量マルチモーダルペイロードを処理します。

    Args:
        payload: prompt、excel_data（base64）、image_data（base64）を含む
        context: ランタイムコンテキスト情報

    Returns:
        str: 両方のデータソースからの分析結果
    """
    prompt = payload.get("prompt", "Analyze the provided data.")
    excel_data = payload.get("excel_data", "")
    image_data = payload.get("image_data", "")

    print(f"=== 大容量ペイロードの処理 ===")
    print(f"セッションID: {context.session_id}")

    if excel_data:
        print(f"Excelデータサイズ: {len(excel_data) / 1024 / 1024:.2f} MB")
    if image_data:
        print(f"画像データサイズ: {len(image_data) / 1024 / 1024:.2f} MB")
    print(f"Excelデータ {excel_data}")
    print(f"画像データ {image_data}")
    print(f"=== 処理開始 ===")
    # base64をバイトにデコード
    excel_bytes = base64.b64decode(excel_data)
    # base64をバイトにデコード
    image_bytes = base64.b64decode(image_data)

    # データコンテキストを含む拡張プロンプト
    enhanced_prompt = f"""{prompt}
    両方のデータソースを分析し、インサイトを提供してください。
    """

    response = agent(
        [{
            "document": {
                "format": "xlsx",
                "name": "excel_data",
                "source": {
                    "bytes": excel_bytes
                }
            }
        },
        {
            "image": {
                "format": "png",
                "source": {
                    "bytes": image_bytes
                }
            }
        },
        {
            "text": enhanced_prompt
        }]
    )
    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()

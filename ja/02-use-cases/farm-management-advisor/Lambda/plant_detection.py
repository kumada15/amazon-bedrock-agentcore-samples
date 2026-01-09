# Plant detection Lambda code - uses Nova Premier to analyze plant images

import json
import boto3
import base64


def lambda_handler(event, context):
    try:
        print(f"受信したイベントキー: {list(event.keys())}")

        # Extract inputs
        image_path = event.get("image_path")
        image_data = event.get("image_data")

        print(f"image_path の有無: {bool(image_path)}")
        print(f"image_data の有無: {bool(image_data)}")

        if not image_path and not image_data:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Either image_path or image_data required"}
                ),
            }

        # Process image input - FIXED LOGIC
        image_bytes = None

        if image_data:
            # Handle base64 image data
            print("image_data を処理中...")
            try:
                image_bytes = base64.b64decode(image_data)
                print(f"Base64 画像をデコードしました: {len(image_bytes)} バイト")
            except Exception as e:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": f"Invalid base64: {e}"}),
                }

        elif image_path:
            # Handle image path (S3 or URL only)
            print(f"image_path を処理中: {image_path}")
            if image_path.startswith("s3://"):
                try:
                    s3_client = boto3.client("s3")
                    bucket = image_path.split("/")[2]
                    key = "/".join(image_path.split("/")[3:])
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    image_bytes = response["Body"].read()
                    print(f"S3 から読み込みました: {len(image_bytes)} バイト")
                except Exception as e:
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": f"S3 error: {e}"}),
                    }
            else:
                return {
                    "statusCode": 404,
                    "body": json.dumps(
                        {"error": f"Only S3 paths supported: {image_path}"}
                    ),
                }

        if not image_bytes:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No image data processed"}),
            }

        # Detect format - CORRECTED
        if image_bytes.startswith(b"\xff\xd8\xff"):
            image_format = "jpeg"
        elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            image_format = "png"
        else:
            image_format = "jpeg"  # Default

        print(f"検出されたフォーマット: {image_format}")

        # Call Nova
        bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

        response = bedrock_client.converse(
            modelId="us.amazon.nova-premier-v1:0",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": image_format,
                                "source": {"bytes": image_bytes},
                            }
                        },
                        {
                            "text": "Analyze this plant image and provide ONLY valid JSON format: {'plant_type': 'name', 'health_analysis': 'detailed analysis'}. Use specific plant names you inferred from the data, such as: sweet_potato_leaf, tomato, bean, lettuce, pepper, cucumber, spinach, okra, sweet potato, carrot, onion, garlic, herbs. For health_analysis, describe in detail: leaf color (green, yellow, brown, purple), spots (black spots, brown spots, white spots), wilting, malnutrition signs, holes or other symptoms of pest damage, disease symptoms, nutrient deficiency, overall plant condition."
                        },
                    ],
                }
            ],
            inferenceConfig={"temperature": 0.1, "maxTokens": 300},
        )

        output = response["output"]["message"]["content"][0]["text"]

        try:
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            json_part = output[json_start:json_end]
            parsed = json.loads(json_part)
        except (ValueError, json.JSONDecodeError):
            parsed = {"plant_type": "unknown", "health_analysis": "Parse error"}

        print("解析結果: ", parsed)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "plant_name": parsed.get("plant_type", "unknown"),
                    "health_issues": parsed.get("health_analysis", "No analysis"),
                }
            ),
        }

    except Exception as e:
        print(f"Lambda エラー: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

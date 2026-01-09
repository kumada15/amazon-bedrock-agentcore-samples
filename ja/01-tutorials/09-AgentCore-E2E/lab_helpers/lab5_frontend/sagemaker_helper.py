import json
import sys
import boto3


def get_streamlit_url():
    try:
        # Read the JSON file
        with open("/opt/ml/metadata/resource-metadata.json", "r") as file:
            data = json.load(file)
            domain_id = data["DomainId"]
            space_name = data["SpaceName"]
    except FileNotFoundError:
        print(
            "resource-metadata.json ファイルが見つかりません -- SageMaker Studio 外で実行中"
        )
        domain_id = None
        space_name = None
        # sys.exit(1)
    except json.JSONDecodeError:
        print("エラー: resource-metadata.json の JSON フォーマットが無効です")
        sys.exit(1)
    except KeyError as e:
        print(f"エラー: 必要なキー {e} が JSON に見つかりません")
        sys.exit(1)

    # Now you can use domain_id and space_name variables in your code
    print(f"ドメイン ID: {domain_id}")
    print(f"スペース名: {space_name}")
    print("\nStreamlit アプリケーションにログインしてテストするには、以下を使用してください")
    print("ユーザー名:     testuser")
    print("パスワード:     MyPassword123!")
    if domain_id is not None:
        sagemaker_client = boto3.client("sagemaker")
        # Replace 'your-space-name' and 'your-domain-id' with your actual values
        response = sagemaker_client.describe_space(
            DomainId=domain_id, SpaceName=space_name
        )

        streamlit_url = response["Url"] + "/proxy/8501/"
    else:
        streamlit_url = "http://localhost:8501"
    return streamlit_url

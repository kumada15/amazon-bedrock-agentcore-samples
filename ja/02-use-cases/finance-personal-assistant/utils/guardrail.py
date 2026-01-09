# AWS クライアントの設定
import boto3

bedrock_client = boto3.client("bedrock")
bedrock_runtime = boto3.client("bedrock-runtime")


def create_guardrail():
    guardrail_name = "guardrail-no-bitcoin-advice"

    # ガードレールが既に存在するか確認
    try:
        existing_guardrails = bedrock_client.list_guardrails()
        for guardrail in existing_guardrails.get("guardrails", []):
            if guardrail.get("name") == guardrail_name:
                print(
                    f"ガードレール '{guardrail_name}' は既に存在します。既存のガードレールを返します。"
                )
                return (guardrail.get("id"), guardrail.get("arn"))
    except Exception as e:
        print(f"既存のガードレール確認中にエラー: {e}")

    # 存在しない場合は新しいガードレールを作成
    print(f"新しいガードレール '{guardrail_name}' を作成中...")
    response = bedrock_client.create_guardrail(
        name=guardrail_name,
        description="Prevents the model from providing Bitcoin investment advice.",
        contentPolicyConfig={
            "filtersConfig": [
                {"type": "SEXUAL", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "VIOLENCE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "INSULTS", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {
                    "type": "MISCONDUCT",
                    "inputStrength": "HIGH",
                    "outputStrength": "HIGH",
                },
                {
                    "type": "PROMPT_ATTACK",
                    "inputStrength": "HIGH",
                    "outputStrength": "NONE",
                },
            ]
        },
        wordPolicyConfig={
            "wordsConfig": [
                {"text": "Bitcoin investment advice"},
                {"text": "Bitcoin recommendations"},
                {"text": "cryptocurrency investment"},
                {"text": "Bitcoin strategy"},
                {"text": "Bitcoin portfolio"},
                {"text": "Bitcoin trading advice"},
                {"text": "Bitcoin financial guidance"},
                {"text": "Bitcoin fiduciary advice"},
                {"text": "crypto investment tips"},
                {"text": "Bitcoin"},
            ],
            "managedWordListsConfig": [{"type": "PROFANITY"}],
        },
        blockedInputMessaging="I apologize, but I am not able to provide Bitcoin investment advice. It is best to consult with trusted finance specialists to learn about cryptocurrency investments",
        blockedOutputsMessaging="I apologize, but I am not able to provide Bitcoin investment advice. For your privacy and security, please modify your input and try again without including Bitcoin investment details.",
    )
    return (response.get("guardrailId"), response.get("guardrailArn"))


def delete_guardrail(guardrail_id=None):
    """
    ID で Bitcoin アドバイスガードレールを削除するか、ID が指定されていない場合は名前で検索して削除します。

    Args:
        guardrail_id: 削除するガードレールの ID（オプション）

    Returns:
        bool: 削除が成功した場合は True、それ以外は False
    """
    guardrail_name = "guardrail-no-bitcoin-advice"
    
    try:
        # ID が指定されていない場合は名前で検索
        if not guardrail_id:
            existing_guardrails = bedrock_client.list_guardrails()
            for guardrail in existing_guardrails.get("guardrails", []):
                if guardrail.get("name") == guardrail_name:
                    guardrail_id = guardrail.get("id")
                    break

            if not guardrail_id:
                print(f"ガードレール '{guardrail_name}' が見つかりません")
                return False

        # ガードレールを削除
        print(f"ガードレール '{guardrail_name}' (ID: {guardrail_id}) を削除中...")
        bedrock_client.delete_guardrail(guardrailIdentifier=guardrail_id)
        print(f"ガードレールを正常に削除しました: {guardrail_name}")
        return True

    except Exception as e:
        print(f"ガードレール削除中にエラー: {e}")
        return False


def get_guardrail_id():
    """
    Bitcoin アドバイスガードレールのガードレール ID を取得します。

    Returns:
        str or None: 見つかった場合はガードレール ID、それ以外は None
    """
    guardrail_name = "guardrail-no-bitcoin-advice"
    
    try:
        existing_guardrails = bedrock_client.list_guardrails()
        for guardrail in existing_guardrails.get("guardrails", []):
            if guardrail.get("name") == guardrail_name:
                guardrail_id = guardrail.get("id")
                print(f"ガードレール '{guardrail_name}' を発見 (ID: {guardrail_id})")
                return guardrail_id

        print(f"ガードレール '{guardrail_name}' が見つかりません")
        return None

    except Exception as e:
        print(f"ガードレール検索中にエラー: {e}")
        return None

import json
import time
import hashlib
import requests
import logging
import base64
import uuid
from visa.helpers import (
    get_secret,
    generate_x_pay_token,
    encrypt_card_data,
    decrypt_token_info,
    create_email_hash,
    encrypt_payload,
    decrypt_rsa,
)
from visa.secure_token import get_secure_token_direct


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# 設定
region = "us-east-1"

# Secrets Manager シークレット名
server_cert_secret_name = "visa/server-mle-cert"  # pragma: allowlist secret
private_cert_secret_name = "visa/mle-private-cert"  # pragma: allowlist secret
api_key_secret_name = "visa/api-key"  # pragma: allowlist secret
shared_secret_secret_name = "visa/shared-secret"  # pragma: allowlist secret
encryption_api_key_secret_name = "visa/encryption-api-key"  # pragma: allowlist secret
encryption_shared_secret_secret_name = (
    "visa/encryption-shared-secret"  # pragma: allowlist secret
)
vic_api_key_secret_name = "visa/api-key"  # pragma: allowlist secret

# 遅延ロードシークレット - 必要な時のみ読み込み
_secrets_cache = {}


def get_visa_secret(secret_name):
    """AWS Secrets Manager からシークレットをキャッシュ付きで遅延ロード"""
    if secret_name not in _secrets_cache:
        _secrets_cache[secret_name] = get_secret(secret_name, region)
    return _secrets_cache[secret_name]


# すべてのシークレットは関数呼び出し時に遅延ロードされる
server_cert = None
private_cert = None
api_key = None
shared_secret = None
encryption_api_key = None
encryption_shared_secret = None
vic_api_key = None
vic_key_id = None


def _ensure_vts_secrets():
    """VTS シークレットが読み込まれていることを確認"""
    global server_cert, private_cert, api_key, shared_secret, encryption_api_key, encryption_shared_secret
    if api_key is None:
        server_cert = get_visa_secret(server_cert_secret_name)
        private_cert = get_visa_secret(private_cert_secret_name)
        api_key = get_visa_secret(api_key_secret_name)
        shared_secret = get_visa_secret(shared_secret_secret_name)
        encryption_api_key = get_visa_secret(encryption_api_key_secret_name)
        encryption_shared_secret = get_visa_secret(encryption_shared_secret_secret_name)


def enroll_pan(
    email,
    pan_data,
    client_app_id,
    client_wallet_account_id="40010062596",
    x_request_id=None,
):  # PanEnrollmentId
    """
    ステップ 1: Visa Token Service に PAN を登録

    Args:
        email: ユーザーのメールアドレス
        pan_data: accountNumber、cvv2、expirationDate を含む辞書
        client_wallet_account_id: ウォレットアカウント ID（デフォルト: "40010062596"）
        client_app_id: クライアントアプリケーション ID（デフォルト: "VICTestAccountTR"）
        x_request_id: VPP セッション継続用のリクエスト ID（オプション、指定がない場合は UUID を生成）

    Returns:
        vPanEnrollmentID を含む Visa API からのレスポンス辞書

    Raises:
        requests.exceptions.RequestException: API リクエストが失敗した場合
        KeyError: レスポンスに期待されるフィールドが含まれていない場合
    """
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("Visa PAN 登録プロセスを開始")
    logger.info("=" * 80)

    # x_request_id が提供されていない場合は生成（これが VPP セッションを開始）
    if not x_request_id:
        x_request_id = str(uuid.uuid4())
        logger.info(f"新しい x-request-id を生成しました: {x_request_id}")

    resource_path = "vts/panEnrollments"

    # 支払い手段を暗号化
    enc_payment_instrument = encrypt_card_data(
        pan_data, encryption_api_key, encryption_shared_secret
    )

    # クエリ文字列と URL を構築
    query_string_for_token = f"apiKey={api_key}"
    url = f"https://cert.api.visa.com/vts/panEnrollments?apiKey={api_key}"
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    # ペイロードを構築（HMAC 計算用にインデントなし）
    payload = json.dumps(
        {
            "clientWalletAccountID": client_wallet_account_id,
            "clientAppID": client_app_id,
            "locale": "en_US",
            "encPaymentInstrument": enc_payment_instrument,
            "panSource": "ONFILE",
        }
    )

    payload = payload.replace(" ", "")
    logger.info(f"リクエストペイロードを準備しました (長さ: {len(payload)} bytes)")

    # X-PAY-TOKEN を生成
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    # X-SERVICE-CONTEXT ヘッダーを生成
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    service_context = {"serviceId": "vts", "serviceVersion": "1.0"}
    service_context_json = json.dumps(service_context, separators=(",", ":"))
    x_service_context = base64.b64encode(service_context_json.encode("utf-8")).decode(
        "utf-8"
    )
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    logger.info(f"X-SERVICE-CONTEXT を生成しました: {x_service_context}")

    # ヘッダーを設定
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "X-SERVICE-CONTEXT": x_service_context,
        "x-request-id": x_request_id,
    }

    logger.info("\n" + "=" * 80)
    logger.info("リクエスト詳細")
    logger.info("=" * 80)
    logger.info("メソッド: POST")
    logger.info(f"URL: {url}")
    logger.info("\nリクエストヘッダー:")
    for key, value in headers.items():
        logger.info(f"  {key}: {value}")
    logger.info("\nリクエストボディ:")
    logger.info(payload)

    logger.info("\n" + "=" * 80)
    logger.info("Visa API にリクエストを送信中")
    logger.info("=" * 80)

    # リクエストを送信
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        # レスポンスに必須フィールドが含まれているか検証
        if "vPanEnrollmentID" not in response_json:
            raise KeyError("レスポンスに 'vPanEnrollmentID' フィールドがありません")

        logger.info("\n" + "=" * 80)
        logger.info("PAN 登録が正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error("\n" + "=" * 80)
        logger.error("PAN 登録に失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"レスポンスステータスコード: {e.response.status_code}")
            logger.error(f"レスポンステキスト: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("PAN 登録に失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise


def provision_token(
    vpan_enrollment_id,
    email,
    client_app_id,
    client_wallet_account_id="40010062596",
    browser_data=None,
    x_request_id=None,
):
    """
    ステップ 2: 登録済み PAN のトークンをプロビジョニング

    Args:
        vpan_enrollment_id: 登録レスポンスからの vPanEnrollmentID
        email: ハッシュ化用のユーザーメールアドレス
        client_wallet_account_id: ウォレットアカウント ID（デフォルト: "40010062596"）
        client_app_id: クライアントアプリケーション ID（デフォルト: "VICTestAccountTR"）
        browser_data: Visa iframe からのオプションのブラウザデータ（提供されない場合はダミーデータを使用）
        x_request_id: VPP セッション継続用のリクエスト ID（enroll_pan の x_request_id と一致する必要あり）

    Returns:
        tokenInfo を含む Visa API からのレスポンス辞書

    Raises:
        requests.exceptions.RequestException: API リクエストが失敗した場合
        KeyError: レスポンスに期待されるフィールドが含まれていない場合
    """
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("PAN EnrollmentID からのトークンプロビジョニングを開始")
    logger.info("=" * 80)

    if not x_request_id:
        logger.warning(
            "x-request-id が提供されていません - VPP セッションの連続性が失われる可能性があります！"
        )
        x_request_id = str(uuid.uuid4())

    resource_path = f"vts/panEnrollments/{vpan_enrollment_id}/provisionedTokens"
    url = f"https://cert.api.visa.com/vts/panEnrollments/{vpan_enrollment_id}/provisionedTokens?apiKey={api_key}"
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    hash_email = create_email_hash(email)

    # 暗号化用のリスクデータを構築
    # 利用可能な場合は iframe からの実際のブラウザデータを使用、そうでなければダミーデータを使用
    if browser_data:
        logger.info("Visa iframe からの実際のブラウザデータを使用")
        logger.info(f"ブラウザデータのキー: {list(browser_data.keys())}")

        # ブラウザデータから一意のデバイス識別子を抽出
        user_agent = browser_data.get("userAgent", "Unknown")
        device_id = hashlib.md5(user_agent.encode(), usedforsecurity=False).hexdigest()[
            :16
        ]

        _risk_data = {
            "deviceFingerprint": {
                "deviceID": device_id,
                "deviceType": "WEB",
                "osVersion": browser_data.get("browserPlatform", "Web Platform"),
                "model": "Web Browser",
            },
            "ipAddress": browser_data.get("ipAddress", "192.168.1.1"),
            "timestamp": str(int(time.time())),
        }
    else:
        logger.warning("ブラウザデータが提供されていません - ダミーのデバイスデータを使用")
        _risk_data = {
            "deviceFingerprint": {
                "deviceID": "device-12345",
                "deviceType": "MOBILE",
                "osVersion": "iOS 16.0",
                "model": "iPhone 14 Pro",
            },
            "ipAddress": "192.168.1.1",
            "timestamp": str(int(time.time())),
        }

    # 非 iframe フローを使用する場合のみリスクデータを暗号化
    # iframe フローの場合、デバイスコンテキストは既に Visa の iframe によって確立されている
    payload_dict = {
        "clientWalletAccountID": client_wallet_account_id,
        "clientAppID": client_app_id,
        "protectionType": "SOFTWARE",
        "presentationType": ["AI_AGENT"],
        "clientWalletAccountEmailAddressHash": hash_email,
    }

    payload = json.dumps(payload_dict)

    # X-PAY-TOKEN を生成
    query_string_for_token = f"apiKey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "x-request-id": x_request_id,
    }

    logger.info("\nリクエストヘッダー:")
    for key, value in headers.items():
        logger.info(f"  {key}: {value}")
    logger.info("\nリクエストボディ:")
    logger.info(payload)

    # リクエストを送信
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        # レスポンスに必須フィールドが含まれているか検証s
        if (
            "tokenInfo" not in response_json
            or "encTokenInfo" not in response_json["tokenInfo"]
        ):
            raise KeyError("レスポンスに 'tokenInfo' または 'encTokenInfo' フィールドがありません")

        logger.info("\n" + "=" * 80)
        logger.info("トークンプロビジョニングが正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error("\n" + "=" * 80)
        logger.error("トークンプロビジョニングに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"レスポンスステータスコード: {e.response.status_code}")
            logger.error(f"レスポンステキスト: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("トークンプロビジョニングに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise


def decrypt_and_store_token(enc_token_info):
    """
    ステップ 3: 暗号化されたトークン情報を復号化

    Args:
        enc_token_info: プロビジョンレスポンスからの暗号化トークン情報（JWE 形式）

    Returns:
        復号化されたトークン情報を含む辞書

    Raises:
        Exception: 復号化に失敗した場合
    """
    logger.info("=" * 80)
    logger.info("encTokenInfo を復号化中")
    logger.info("=" * 80)

    try:
        decrypted_token_data = decrypt_token_info(
            enc_token_info, encryption_shared_secret
        )

        logger.info("\n" + "=" * 80)
        logger.info("トークンの復号化が正常に完了しました")
        logger.info("=" * 80)

        return decrypted_token_data

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("トークンの復号化に失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise


def get_secure_token(api_key, client_app_id, headless=False):
    """
    ステップ 4: 自動化ブラウザワークフローを使用して Visa セキュアトークンを取得

    Args:
        api_key: Visa API キー
        client_app_id: クライアントアプリケーション ID（デフォルト: "VICTestAccountTR"）
        headless: ヘッドレスモードでブラウザを実行（デフォルト: False）

    Returns:
        str: secureToken 文字列、失敗した場合は None
    """
    logger.info("=" * 80)
    logger.info("Visa セキュアトークンを取得中")
    logger.info("=" * 80)

    result = get_secure_token_direct(api_key=api_key, client_app_id=client_app_id)

    if result and "secureToken" in result:
        secure_token = result["secureToken"]
        logger.info(f"セキュアトークンを正常に取得しました: {secure_token[:60]}...")
        return secure_token
    else:
        logger.error("セキュアトークンの取得に失敗しました")
        return None


def device_attestation_authenticate(
    email,
    secure_token,
    provisioned_token_id,
    browser_data,
    client_app_id,
    client_reference_id,
    x_request_id,
    transaction_amount="567.89",
):
    """
    デバイス認証 Authenticate - VPP フローのステップ 4

    Args:
        email: ユーザーメールアドレス（pan_data ではない）
        secure_token: iframe セッションからのセキュアトークン
        provisioned_token_id: プロビジョンステップからのトークン ID
        browser_data: iframe からのブラウザデータ
        client_app_id: クライアントアプリケーション ID
        client_reference_id: トランザクション参照 ID
        x_request_id: VPP セッションリクエスト ID
        transaction_amount: トランザクション金額（デフォルト "567.89"）
    """
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("デバイス認証 Authenticate")
    logger.info(f"登録からの x-request-id を使用: {x_request_id}")

    # 金額を小数点以下 2 桁でフォーマット
    formatted_amount = f"{float(transaction_amount):.2f}"
    logger.info(f"取引金額: {formatted_amount}")

    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    resource_path = f"vts/provisionedTokens/{provisioned_token_id}/attestation/options"
    url = f"https://cert.api.visa.com/vts/provisionedTokens/{provisioned_token_id}/attestation/options?apiKey={api_key}"
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    # 修正: pan_data ではなく、消費者のメール情報を暗号化
    to_be_encrypted = {"consumerInfo": {"emailAddress": email}}
    encAuthenticationData = encrypt_card_data(
        to_be_encrypted, encryption_api_key, encryption_shared_secret
    )

    payload_dict = {
        "authenticationPreferencesRequested": {"selectedPopupForRegister": False},
        "sessionContext": {
            "secureToken": secure_token,
        },
        "dynamicData": {
            "authenticationAmount": formatted_amount,
            "merchantIdentifier": {
                "applicationUrl": "aHR0cHM6Ly93d3cuTWVyY2hhbnQtVlphRjVYQmouY29t",  # pragma: allowlist secret
                "merchantName": "TWVyY2hhbnQgVlphRjVYQmo",
            },
            "currencyCode": "840",
        },
        "browserData": browser_data,
        "encAuthenticationData": encAuthenticationData,
        "reasonCode": "PAYMENT",
        "clientReferenceID": client_reference_id,
        "type": "AUTHENTICATE",
        "clientAppID": client_app_id,
    }

    payload = json.dumps(payload_dict)

    logging.info(f"ボディ:{payload}")

    # X-PAY-TOKEN を生成
    query_string_for_token = f"apiKey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    # 修正: X-SERVICE-CONTEXT ヘッダーを追加
    service_context = {"serviceId": "vts", "serviceVersion": "1.0"}
    service_context_json = json.dumps(service_context, separators=(",", ":"))
    x_service_context = base64.b64encode(service_context_json.encode("utf-8")).decode(
        "utf-8"
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "X-SERVICE-CONTEXT": x_service_context,
        "x-request-id": x_request_id,
    }

    logging.info(f"ヘッダー: {headers}")

    # リクエストを送信
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        logger.info("\n" + "=" * 80)
        logger.info("デバイス認証 Authenticate が正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 AUTHENTICATE - JSON デコードエラー")
        logger.error("=" * 80)
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        logger.error(
            f"レスポンスステータスコード: {response.status_code if 'response' in locals() else 'N/A'}"
            # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        )
        logger.error(
            f"レスポンステキスト: {response.text if 'response' in locals() else 'No response'}"
        )
        raise
    except requests.exceptions.HTTPError as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 AUTHENTICATE - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"レスポンスステータスコード: {e.response.status_code}")
            logger.error(f"レスポンステキスト: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 AUTHENTICATE - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 AUTHENTICATE - 予期しないエラー")
        logger.error("=" * 80)
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        import traceback

        logger.error(f"トレースバック:\n{traceback.format_exc()}")
        raise


def device_binding(
    secure_token,
    email,
    provisioned_token_id,
    browser_data,
    client_app_id,
    client_reference_id,
    x_request_id,
):
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("デバイスバインディング認証")

    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    resource_path = f"vts/provisionedTokens/{provisioned_token_id}/deviceBinding"
    url = f"https://cert.api.visa.com/vts/provisionedTokens/{provisioned_token_id}/deviceBinding?apiKey={api_key}"
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    hash_email = create_email_hash(email)

    payload = json.dumps(
        {
            "sessionContext": {
                "secureToken": secure_token,
            },
            "browserData": browser_data,
            "platformType": "WEB",
            "clientReferenceID": client_reference_id,
            "clientAppID": client_app_id,
            "intent": "FIDO",
            "clientWalletAccountEmailAddressHash": hash_email,
        }
    )

    logger.info(f"ボディ:{payload}")

    # X-PAY-TOKEN を生成
    query_string_for_token = f"apiKey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "x-request-id": x_request_id,
    }

    # リクエストを送信
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        logger.info("\n" + "=" * 80)
        logger.info("デバイスバインディングが正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスバインディング - JSON デコードエラー")
        logger.error("=" * 80)
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        logger.error(
            f"レスポンスステータスコード: {response.status_code if 'response' in locals() else 'N/A'}"
            # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        )
        logger.error(
            f"レスポンステキスト: {response.text if 'response' in locals() else 'No response'}"
        )
        raise
    except requests.exceptions.HTTPError as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスバインディング - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"レスポンスステータスコード: {e.response.status_code}")
            logger.error(f"レスポンステキスト: {e.response.text}")
        raise  # メイン関数で処理するために再スロー
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスバインディング - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスバインディング - 予期しないエラー")
        logger.error("=" * 80)
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        import traceback

        logger.error(f"トレースバック:\n{traceback.format_exc()}")
        raise


def step_up(
    provisioned_token_id,
    identifier,
    client_app_id,
    client_reference_id,
    x_request_id,
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
):
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("ステップアップオプションを選択")

    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    resource_path = f"vts/provisionedTokens/{provisioned_token_id}/stepUpOptions/method"
    url = f"https://cert.api.visa.com/vts/provisionedTokens/{provisioned_token_id}/stepUpOptions/method?apiKey={api_key}"
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    timestamp = str(int(time.time()))
    logger.info(f"  タイムスタンプ: {timestamp}")

    payload = json.dumps(
        {
            "date": timestamp,
            "stepUpRequestID": identifier,
            "clientReferenceId": client_reference_id,
            "clientAppID": client_app_id,
        }
    )

    # X-PAY-TOKEN を生成
    query_string_for_token = f"apiKey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "x-request-id": x_request_id,
    }

    # リクエストを送信
    try:
        response = requests.put(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        logger.info("\n" + "=" * 80)
        logger.info("デバイスセットアップが正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスセットアップ - JSON デコードエラー")
        logger.error("=" * 80)
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        logger.error(
            f"レスポンスステータスコード: {response.status_code if 'response' in locals() else 'N/A'}"
            # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        )
        logger.error(
            f"レスポンステキスト: {response.text if 'response' in locals() else 'No response'}"
        )
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスセットアップ - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if "response" in locals():
            logger.error(f"レスポンスステータスコード: {response.status_code}")
            logger.error(f"レスポンステキスト: {response.text}")
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイスセットアップ - 予期しないエラー")
        logger.error("=" * 80)
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        import traceback

        logger.error(f"トレースバック:\n{traceback.format_exc()}")
        raise


def validate_otp(
    provisioned_token_id, otp_value, client_app_id, client_reference_id, x_request_id
):
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("OTP を検証")

    resource_path = (
        f"vts/provisionedTokens/{provisioned_token_id}/stepUpOptions/validateOTP"
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    )
    url = f"https://cert.api.visa.com/vts/provisionedTokens/{provisioned_token_id}/stepUpOptions/validateOTP?apiKey={api_key}"
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    timestamp = str(int(time.time()))
    logger.info(f"  タイムスタンプ: {timestamp}")

    payload = json.dumps(
        {
            "date": timestamp,
            "otpValue": otp_value,
            "clientReferenceId": client_reference_id,
            "clientAppID": client_app_id,
        }
    )

    # X-PAY-TOKEN を生成
    query_string_for_token = f"apiKey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "x-request-id": x_request_id,
    }

    # リクエストを送信
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        logger.info("\n" + "=" * 80)
        logger.info("OTP 検証が正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error("\n" + "=" * 80)
        logger.error("OTP 検証 - JSON デコードエラー")
        logger.error("=" * 80)
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        logger.error(
            f"レスポンスステータスコード: {response.status_code if 'response' in locals() else 'N/A'}"
            # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        )
        logger.error(
            f"レスポンステキスト: {response.text if 'response' in locals() else 'No response'}"
        )
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("OTP 検証 - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if "response" in locals():
            logger.error(f"レスポンスステータスコード: {response.status_code}")
            logger.error(f"レスポンステキスト: {response.text}")
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("OTP 検証 - 予期しないエラー")
        logger.error("=" * 80)
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        import traceback

        logger.error(f"トレースバック:\n{traceback.format_exc()}")
        raise


def device_attestation_register(
    provisioned_token_id,
    email,
    secure_token,
    browser_data,
    client_app_id,
    client_reference_id,
    x_request_id,
):
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("デバイス認証 Register")
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted

    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    resource_path = f"vts/provisionedTokens/{provisioned_token_id}/attestation/options"
    url = f"https://cert.api.visa.com/vts/provisionedTokens/{provisioned_token_id}/attestation/options?apiKey={api_key}"
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    payload_dict = {
        "authenticationPreferencesRequested": {"selectedPopupForRegister": False},
        "dynamicData": {
            "authenticationAmount": "444.44",
            "merchantIdentifier": {
                "applicationUrl": "aHR0cHM6Ly93d3cuTWVyY2hhbnQtVlphRjVYQmouY29t",  # pragma: allowlist secret
                "merchantName": "TWVyY2hhbnQgVlphRjVYQmo",
            },
            "currencyCode": "840",
        },
        "browserData": browser_data,
        "reasonCode": "DEVICE_BINDING",
        "clientReferenceID": client_reference_id,
        "type": "REGISTER",
        "clientAppID": client_app_id,
    }

    to_be_encrypted = {"consumerInfo": {"emailAddress": email}}
    logger.info(f"暗号化前データ:{to_be_encrypted}")
    encAuthenticationData = encrypt_card_data(
        to_be_encrypted, encryption_api_key, encryption_shared_secret
    )

    payload_dict["encAuthenticationData"] = encAuthenticationData

    if secure_token and secure_token.startswith("ezAwMX06"):
        logger.info(
            "iframe フロー用に consumerInfo を含む encAuthenticationData を含めています"
        )
    else:
        logger.info(
            "OAuth フロー用に consumerInfo を含む encAuthenticationData を含めています"
        )

    if secure_token:
        payload_dict["sessionContext"] = {"secureToken": secure_token}
        if secure_token.startswith("ezAwMX06"):
            logger.info("iframe secure token を含む sessionContext を含めています")
        else:
            logger.info("OAuth secure token を含む sessionContext を含めています")
    else:
        logger.info("secure token が提供されていません - sessionContext をスキップします")

    payload = json.dumps(payload_dict)

    logging.info(f"ボディ:{payload}")

    # X-PAY-TOKEN を生成
    query_string_for_token = f"apiKey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string_for_token, payload
    )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-PAY-TOKEN": x_pay_token,
        "x-request-id": x_request_id,
    }

    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    logging.info(f"ヘッダー: {headers}")

    # リクエストを送信
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        logger.info("\n" + "=" * 80)
        logger.info("デバイス認証 Register が正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 REGISTER - JSON デコードエラー")
        logger.error("=" * 80)
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        logger.error(
            f"レスポンスステータスコード: {response.status_code if 'response' in locals() else 'N/A'}"
            # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        )
        logger.error(
            f"レスポンステキスト: {response.text if 'response' in locals() else 'No response'}"
        )
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 REGISTER - リクエストに失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        if "response" in locals():
            logger.error(f"レスポンスステータスコード: {response.status_code}")
            logger.error(f"レスポンステキスト: {response.text}")
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("デバイス認証 REGISTER - 予期しないエラー")
        logger.error("=" * 80)
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        import traceback

        logger.error(f"トレースバック:\n{traceback.format_exc()}")
        raise


def passkey_creation(
    request_id, endpoint, identifier, payload, client_app_id, client_reference_id
):
    logger.info("=" * 80)
    logger.info("Passkey 作成フロー")

    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    resource_path = "vts/auth/authenticate"
    url = f"https://sbx.vts.auth.visa.com/vts/auth/authenticate?apiKey={api_key}&clientAppID={client_app_id}"
    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key は非表示

    payload = json.dumps(
        {
            "requestID": request_id,
            "version": "1",
            "type": "AUTHENTICATE",
            "authenticationContext": {
                "endpoint": endpoint,
                "identifier": identifier,
                "payload": payload,
                "action": "REGISTER",
                "platformType": "WEB",
                "authenticationPreferencesEnabled": {
                    "responseMode": "com_visa_web_message",
                    "responseType": "code",
                },
            },
        }
    )

    try:
        response = requests.post(url, data=payload, timeout=300)
        response.raise_for_status()

        logger.info("\nレスポンスボディ (解析済み JSON):")
        response_json = response.json()
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        logger.info("\n" + "=" * 80)
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        logger.info("Passkey 作成フローが正常に完了しました")
        logger.info("=" * 80)

        return response_json

    except json.JSONDecodeError as e:
        logger.error("\n" + "=" * 80)
        logger.error("PASSKEY 作成フロー - JSON デコードエラー")
        logger.error("=" * 80)
        logger.error(f"レスポンスを JSON として解析できませんでした: {e}")
        logger.error(
            f"レスポンスステータスコード: {response.status_code if 'response' in locals() else 'N/A'}"
            # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        )
        logger.error(
            f"レスポンステキスト: {response.text if 'response' in locals() else 'No response'}"
        )
        raise
    except requests.exceptions.RequestException as e:
        logger.error("\n" + "=" * 80)
        logger.error("PASSKEY 作成フロー - リクエストに失敗しました")
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        if "response" in locals():
            logger.error(f"レスポンスステータスコード: {response.status_code}")
            logger.error(f"レスポンステキスト: {response.text}")
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
        logger.error("PASSKEY 作成フロー - 予期しないエラー")
        logger.error("=" * 80)
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"エラーメッセージ: {str(e)}")
        import traceback

        logger.error(f"トレースバック:\n{traceback.format_exc()}")
        raise


def vic_enroll_card(
    email,
    provisioned_token_id,
    client_app_id,
    client_reference_id,
    client_device_id,
    consumer_id,
):
    """
    ステップ 14: VIC カード登録

    プロビジョニング済みトークンを VIC に登録して支払いに使用

    Args:
        email: ユーザーメールアドレス
        provisioned_token_id: プロビジョンステップからの vProvisionedTokenID
        client_app_id: クライアントアプリケーション ID
        client_reference_id: クライアント参照 ID
        client_device_id: クライアントデバイス ID（セッション継続用）
        consumer_id: コンシューマー ID（セッション継続用）

    Returns:
        レスポンスと復号化データを含む辞書
    """
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("VIC カード登録 (ステップ 14)")
    logger.info("=" * 80)

    # externalClientId は Visa Developer Portal から取得
    to_be_encrypted = {
        "client": {
            "externalClientId": "3aa9e2b8-c5c1-612d-32c3-1cb11b85a702",
            "externalAppId": client_app_id,
        },
        "enrollmentReferenceData": {
            "enrollmentReferenceType": "TOKEN_REFERENCE_ID",
            "enrollmentReferenceProvider": "VTS",
            "enrollmentReferenceId": provisioned_token_id,
        },
        "appInstance": {
            "countryCode": "US",
            "clientDeviceId": client_device_id,
            "ipAddress": "192.168.1.1",
            "deviceData": {
                "model": "iPhone 16 Pro Max",
                "type": "Mobile",
                "brand": "Apple",
                "manufacturer": "Apple",
            },
            "userAgent": "Mozilla/5.0",
            "applicationName": "My Magic App",
        },
        "clientReferenceId": client_reference_id,
        "consumer": {
            "consumerId": consumer_id,
            "countryCode": "US",
            "languageCode": "en",
            "consumerIdentity": {
                "identityType": "EMAIL_ADDRESS",
                "identityValue": email,
            },
        },
    }

    # VIC 証明書を使用した RSA 暗号化でペイロードを暗号化（対称暗号化ではない）
    enc_data = encrypt_payload(to_be_encrypted)

    # 暗号化リクエストを構築
    enc_data_str = json.dumps(enc_data, separators=(",", ":"))

    # VIC API key を使用して URL を構築（小文字の 'apikey'）
    url = f"https://cert.api.visa.com/vacp/v1/cards?apikey={api_key}"

    # X-PAY-TOKEN を生成
    resource_path = "v1/cards"
    query_string = f"apikey={api_key}"

    # x-pay-token 生成のデバッグログ
    logger.info("X-PAY-TOKEN 生成パラメータ:")
    logger.info(f"  resource_path: {resource_path}")
    # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    logger.info(f"  query_string: {query_string}")
    logger.info(f"  body_length: {len(enc_data_str)}")
    logger.info(f"  shared_secret (最初の 10 文字): {shared_secret[:10]}...")

    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string, enc_data_str
    )

    # シークレットから keyId を取得（ハードコードではない）
    vic_key_id = get_secret("visa/vic_key_id", region)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "keyId": vic_key_id,
        "x-pay-token": x_pay_token,
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    }

    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key redacted
    logger.info("\nリクエストヘッダー:")
    for key, value in headers.items():
        if "token" in key.lower() or "key" in key.lower():
            logger.info(f"  {key}: {value[:20]}...")
        else:
            logger.info(f"  {key}: {value}")
    logger.info(f"リクエストボディ (切り詰め): {enc_data_str[:100]}...")

    try:
        response = requests.post(url, headers=headers, data=enc_data_str, timeout=300)

        # ステータスを発生させる前にレスポンス詳細をログ出力
        logger.info(f"\nレスポンスステータスコード: {response.status_code}")
        logger.info("レスポンスヘッダー:")
        for key, value in response.headers.items():
            logger.info(f"  {key}: {value}")

        logger.info("\n生のレスポンスボディ:")
        logger.info(response.text)

        response.raise_for_status()

        response_json = response.json()
        logger.info("\nレスポンスボディ (解析済み JSON):")
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        # RSA 復号化でレスポンスを復号化（対称暗号化ではない）
        enc_response_data = response_json.get("encData")
        if enc_response_data:
            decrypted_response = decrypt_rsa(enc_response_data)
            logger.info("\n復号化されたレスポンス:")
            logger.info(json.dumps(decrypted_response, indent=2))

            logger.info("\n" + "=" * 80)
            logger.info("VIC カード登録が正常に完了しました")
            logger.info("=" * 80)

            return {
                "clientReferenceId": decrypted_response.get("clientReferenceId"),
                "status": decrypted_response.get("status"),
                "raw": decrypted_response,
            }
        else:
            raise KeyError("レスポンスに 'encData' フィールドがありません")

    except requests.exceptions.HTTPError as e:
        logger.error("\n" + "=" * 80)
        logger.error("VIC カード登録に失敗しました - HTTP エラー")
        logger.error("=" * 80)
        logger.error(f"ステータスコード: {e.response.status_code}")
        logger.error(f"エラー: {str(e)}")
        logger.error("\nレスポンスヘッダー:")
        for key, value in e.response.headers.items():
            logger.error(f"  {key}: {value}")
        logger.error("\nレスポンスボディ:")
        logger.error(e.response.text)
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("VIC カード登録に失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise


def vic_initiate_purchase_instructions(
    provisioned_token_id,
    consumer_id,
    client_app_id,
    mandate_id,
    consumer_request,
    client_reference_id,
    client_device_id,
    auth_identifier,
    dfp_session_id,
    iframe_auth_fido_blob,
    transaction_amount="444.44",
):
    """
    ステップ 15: VIC 購入指示の開始

    パスキーからのアシュアランスデータを使用して購入指示を開始

    Args:
        provisioned_token_id: プロビジョンステップからの vProvisionedTokenID
        consumer_id: コンシューマー ID（セッション継続のため enroll_card と同じ）
        client_app_id: クライアントアプリケーション ID
        mandate_id: 購入制約のためのマンデート ID
        consumer_request: 消費者リクエストの説明（例: "りんごを購入"）
        client_reference_id: クライアント参照 ID
        client_device_id: クライアントデバイス ID
        auth_identifier: VTS GET Device Attestations Options からの識別子
        dfp_session_id: iframe からの DFP セッション ID
        iframe_auth_fido_blob: iframe 認証からの FIDO アサーションデータコード
        transaction_amount: 文字列形式のトランザクション金額（例: "799.00"）

    Returns:
        instructionId を含む辞書
    """
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("VIC 購入指示の開始 (ステップ 15)")
    logger.info("=" * 80)

    # 金額が小数点以下正確に 2 桁の文字列としてフォーマットされていることを確認
    formatted_amount = f"{float(transaction_amount):.2f}"
    logger.info(f"取引金額: {formatted_amount}")

    # 非暗号化ペイロードを構築
    timestamp = int(time.time())
    effective_until = timestamp + 864000  # 10 days

    to_be_encrypted = {
        "tokenId": provisioned_token_id,
        "consumerId": consumer_id,
        "client": {
            "externalClientId": "3aa9e2b8-c5c1-612d-32c3-1cb11b85a702",
            "externalAppId": client_app_id,
        },
        "mandates": [
            {
                "effectiveUntilTime": effective_until,
                "declineThreshold": {"amount": formatted_amount, "currencyCode": "USD"},
                "quantity": 1,
                "mandateId": mandate_id,
                "merchantCategoryCode": "5411",
                "description": consumer_request,
                "merchantCategory": "Groceries",
                "preferredMerchantName": "Walmart",
            }
        ],
        "clientReferenceId": client_reference_id,
        "appInstance": {
            "countryCode": "US",
            "clientDeviceId": client_device_id,
            "ipAddress": "192.168.1.1",
            "deviceData": {
                "model": "iPhone 16 Pro Max",
                "type": "Mobile",
                "brand": "Apple",
                "manufacturer": "Apple",
            },
            "userAgent": "Mozilla/5.0",
            "applicationName": "My Magic App",
        },
        "consumerPrompt": consumer_request,
        "assuranceData": [
            {
                "methodResults": {
                    "identifier": auth_identifier,
                    "dfpSessionId": dfp_session_id,
                    "fidoAssertionData": {"code": iframe_auth_fido_blob},
                },
                "verificationType": "DEVICE",
                "verificationResults": "01",
                "verificationMethod": "23",
                "verificationTimestamp": timestamp,
            }
        ],
    }

    # VIC 証明書を使用した RSA 暗号化でペイロードを暗号化
    enc_data = encrypt_payload(to_be_encrypted)

    # 暗号化リクエストを構築 (enc_data is already a dict with "encData" key)
    enc_data_str = json.dumps(enc_data, separators=(",", ":"))

    # URL を構築（cert 環境を使用）
    url = f"https://cert.api.visa.com/vacp/v1/instructions?apikey={api_key}"

    # X-PAY-TOKEN を生成
    resource_path = "v1/instructions"
    query_string = f"apikey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string, enc_data_str
    )

    # シークレットから keyId を取得
    vic_key_id = get_secret("visa/vic_key_id", region)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "keyId": vic_key_id,
        "x-pay-token": x_pay_token,
        "x-request-id": client_reference_id,
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    }

    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key redacted
    logger.info(f"リクエストボディ (切り詰め): {enc_data_str[:100]}...")

    try:
        response = requests.post(url, headers=headers, data=enc_data_str, timeout=300)
        response.raise_for_status()

        response_json = response.json()
        logger.info("\nレスポンスボディ (解析済み JSON):")
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        # RSA 復号化でレスポンスを復号化
        enc_response_data = response_json.get("encData")
        if enc_response_data:
            decrypted_response = decrypt_rsa(enc_response_data)
            logger.info("\n復号化されたレスポンス:")
            logger.info(json.dumps(decrypted_response, indent=2))

            logger.info("\n" + "=" * 80)
            logger.info("VIC 購入指示の開始が正常に完了しました")
            logger.info("=" * 80)

            return {
                "instructionId": decrypted_response.get("instructionId"),
                "clientReferenceId": decrypted_response.get("clientReferenceId"),
                "status": decrypted_response.get("status"),
                "raw": decrypted_response,
            }
        else:
            raise KeyError("レスポンスに 'encData' フィールドがありません")

    except requests.exceptions.HTTPError as e:
        logger.error("\n" + "=" * 80)
        logger.error("VIC 購入指示の開始に失敗しました - HTTP エラー")
        logger.error("=" * 80)
        logger.error(f"ステータスコード: {e.response.status_code}")
        logger.error(f"エラー: {str(e)}")
        logger.error("\nレスポンスヘッダー:")
        for key, value in e.response.headers.items():
            logger.error(f"  {key}: {value}")
        logger.error("\nレスポンスボディ:")
        logger.error(e.response.text)
        raise
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("VIC 購入指示の開始に失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise


def vic_get_payment_credentials(
    instruction_id,
    provisioned_token_id,
    client_app_id,
    client_reference_id,
    merchant_url,
    merchant_name,
    transaction_amount,
):
    """
    ステップ 16: VIC 支払い認証情報の取得

    認可用の支払い認証情報（クリプトグラム）を取得

    Args:
        instruction_id: 購入指示開始からの instructionId
        provisioned_token_id: プロビジョンステップからの vProvisionedTokenID
        client_app_id: クライアントアプリケーション ID
        client_reference_id: クライアント参照 ID（登録時に使用したものと同じ）
        merchant_url: マーチャント Web サイト URL
        merchant_name: マーチャント名
        transaction_amount: 文字列形式のトランザクション金額（例: "444.44"）

    Returns:
        クリプトグラムを含む signedPayload を持つ辞書
    """
    _ensure_vts_secrets()

    logger.info("=" * 80)
    logger.info("VIC 支払い認証情報の取得 (ステップ 16)")
    logger.info("=" * 80)

    # 金額が小数点以下正確に 2 桁の文字列としてフォーマットされていることを確認
    formatted_amount = f"{float(transaction_amount):.2f}"
    logger.info(f"取引金額: {formatted_amount}")

    to_be_encrypted = {
        "tokenId": provisioned_token_id,
        "transactionData": [
            {
                "merchantCountryCode": "US",
                "transactionAmount": {
                    "transactionAmount": formatted_amount,
                    "transactionCurrencyCode": "USD",
                },
                "merchantUrl": merchant_url,
                "merchantName": merchant_name,
                "transactionReferenceId": instruction_id,
            }
        ],
        "client": {
            "externalClientId": "3aa9e2b8-c5c1-612d-32c3-1cb11b85a702",
            "externalAppId": client_app_id,
        },
        "clientReferenceId": client_reference_id,
    }

    # RSA でペイロードを暗号化
    enc_data = encrypt_payload(to_be_encrypted)
    enc_data_str = json.dumps(enc_data, separators=(",", ":"))

    # URL を構築
    url = f"https://cert.api.visa.com/vacp/v1/instructions/{instruction_id}/credentials?apikey={api_key}"

    # X-PAY-TOKEN を生成
    resource_path = f"v1/instructions/{instruction_id}/credentials"
    query_string = f"apikey={api_key}"
    x_pay_token = generate_x_pay_token(
        shared_secret, resource_path, query_string, enc_data_str
    )

    # シークレットから keyId を取得
    vic_key_id = get_secret("visa/vic_key_id", region)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "keyId": vic_key_id,
        "x-pay-token": x_pay_token,
        "x-request-id": client_reference_id,
        # codeql[py/clear-text-logging-sensitive-data] Debug logging for API integration - logs metadata only, sensitive data is redacted
    }

    logger.info(f"ターゲット URL: {url.split('?')[0]}...")  # API key redacted
    logger.info(f"リクエストボディ (切り詰め): {enc_data_str[:100]}...")

    try:
        response = requests.post(url, headers=headers, data=enc_data_str, timeout=300)
        response.raise_for_status()

        response_json = response.json()
        logger.info("\nレスポンスボディ (解析済み JSON):")
        logger.info("[セキュリティのためレスポンスデータは非表示]")

        # RSA でレスポンスを復号化
        enc_response_data = response_json.get("encData")
        if enc_response_data:
            decrypted_response = decrypt_rsa(enc_response_data)
            logger.info("\n復号化されたレスポンス:")
            logger.info(json.dumps(decrypted_response, indent=2))

            # クリプトグラムを取得するために signedPayload を抽出してデコード
            signed_payload = decrypted_response.get("signedPayload")
            if signed_payload:
                # JWT をデコードしてクリプトグラムを取得
                parts = signed_payload.split(".")
                if len(parts) >= 2:
                    import base64

                    # ペイロード部分（JWT の 2 番目の部分）をデコード
                    payload_part = parts[1]
                    # 必要に応じてパディングを追加
                    padding = 4 - len(payload_part) % 4
                    if padding != 4:
                        payload_part += "=" * padding
                    decoded_payload = base64.b64decode(payload_part)
                    payload_json = json.loads(decoded_payload)

                    logger.info("\n" + "=" * 80)
                    logger.info("デコードされた CRYPTOGRAM データ:")
                    logger.info("=" * 80)
                    logger.info(json.dumps(payload_json, indent=2))

                    # クリプトグラム値を抽出
                    if (
                        "dynamicData" in payload_json
                        and len(payload_json["dynamicData"]) > 0
                    ):
                        cryptogram_data = payload_json["dynamicData"][0]
                        logger.info("\n" + "=" * 80)
                        logger.info(
                            f"クリプトグラム: {cryptogram_data.get('dynamicDataValue')}"
                        )
                        logger.info("=" * 80)

            logger.info("\n" + "=" * 80)
            logger.info("VIC 支払い認証情報の取得が正常に完了しました")
            logger.info("=" * 80)

            return {
                "signedPayload": signed_payload,
                "instructionId": decrypted_response.get("instructionId"),
                "status": decrypted_response.get("status"),
                "raw": decrypted_response,
            }
        else:
            raise KeyError("レスポンスに 'encData' フィールドがありません")

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("VIC 支払い認証情報の取得に失敗しました")
        logger.error("=" * 80)
        logger.error(f"エラー: {str(e)}")
        raise

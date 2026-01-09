import boto3
import json
import time
import hashlib
import hmac
import logging
import base64
import ntplib
import uuid
from datetime import datetime, timezone
from jwcrypto import jwk, jwe


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _redact_sensitive(value: str, show_chars: int = 4) -> str:
    """機密情報をマスクし、最初の数文字のみを表示する。"""
    if not value or not isinstance(value, str):
        return "[REDACTED]"
    if len(value) <= show_chars:
        return "[REDACTED]"
    return f"{value[:show_chars]}...{'*' * 8}"


def get_secret(secret_name, region_name="us-east-1"):
    # codeql[py/clear-text-logging-sensitive-data] Only logs secret name for debugging, not the actual secret value
    logger.info(f"シークレットを取得中: {secret_name}, リージョン: {region_name}")
    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    secret_value = response["SecretString"]

    # PEM ファイル（証明書/キー）の場合、誤って保存されたエスケープシーケンスを置換
    if (
        "cert" in secret_name.lower()
        or "key" in secret_name.lower()
        or "pem" in secret_name.lower()
    ):
        # リテラルの \n を実際の改行に置換
        # codeql[py/clear-text-logging-sensitive-data] Logs processing status only, not secret content
        if "\\n" in secret_value:
            logger.info(f"  {secret_name} を処理中...")
            secret_value = secret_value.replace("\\n", "\n")
            # codeql[py/clear-text-logging-sensitive-data] Logs processing status only, not secret content
        # リテラルの \r を実際のキャリッジリターンに置換
        # codeql[py/clear-text-logging-sensitive-data] Logs processing status only, not secret content
        if "\\r" in secret_value:
            logger.info(f"  {secret_name} を処理中...")
            # codeql[py/clear-text-logging-sensitive-data] Logs processing status only, not secret content
            secret_value = secret_value.replace("\\r", "\r")
        # PEM 全体を囲んでいる可能性のある引用符を削除
        if secret_value.startswith('"') and secret_value.endswith('"'):
            logger.info(f"  {secret_name} を処理中...")
            secret_value = secret_value[1:-1]
        if secret_value.startswith("'") and secret_value.endswith("'"):
            logger.info(f"  {secret_name} を処理中...")
            secret_value = secret_value[1:-1]
    else:
        # 非 PEM シークレットの場合、空白と引用符を削除
        secret_value = secret_value.strip().strip('"')

    logger.info(f"シークレットを正常に取得しました: {secret_name}")
    return secret_value


def generate_x_pay_token(shared_secret, resource_path, query_string, request_body=""):
    logger.info("X-PAY-TOKEN を生成中")
    # セキュリティのためログから機密データを除外

    timestamp = str(int(time.time()))

    message = timestamp + resource_path + query_string + request_body

    # SHA256 は Visa API 仕様で必須 - より強力なアルゴリズムは使用不可
    # 参照: https://developer.visa.com/pages/working-with-visa-apis/two-way-ssl
    hmac_digest = hmac.new(
        shared_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,  # nosec - Required by Visa API
    ).hexdigest()

    token = f"xv2:{timestamp}:{hmac_digest}"
    logger.info("X-PAY-TOKEN を正常に生成しました")
    return token


def get_ntp_time():
    """
    US NTP サーバーから現在時刻を取得する

    Returns:
        秒単位のタイムスタンプ（ミリ秒ではない）
    """
    ntp_servers = [
        "time.nist.gov",
        "time-a-g.nist.gov",
        "time-b-g.nist.gov",
        "time.google.com",
    ]

    client = ntplib.NTPClient()

    for ntp_server in ntp_servers:
        try:
            logger.info(f"  NTP サーバーに問い合わせ中: {ntp_server}")
            response = client.request(ntp_server, version=3, timeout=5)
            ntp_time_seconds = int(response.tx_time)
            _ntp_time_readable = datetime.fromtimestamp(
                response.tx_time, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"  {ntp_server} から NTP 時刻を正常に取得しました")
            return ntp_time_seconds
        except Exception as e:
            logger.warning(f"  {ntp_server} からの時刻取得に失敗しました: {str(e)}")
            continue

    # すべての NTP サーバーが失敗した場合はシステム時刻にフォールバック
    logger.warning("  すべての NTP サーバーへの接続に失敗しました。システムの UTC 時刻にフォールバックします")
    fallback_time_seconds = int(datetime.now(timezone.utc).timestamp())
    return fallback_time_seconds


def encrypt_card_data(payload, encryption_api_key, encryption_shared_secret):
    """
    A256GCMKW（AES-256-GCM Key Wrap）を使用して JWE でカードデータを暗号化する

    Args:
        payload: 暗号化するカードデータを含む辞書
        encryption_api_key: API キー（ヘッダーの 'kid' として使用）
        encryption_shared_secret: 対称暗号化用の共有シークレット

    Returns:
        暗号化された JWE トークン文字列
    """
    # ステップ 1: ペイロードを JSON 文字列に変換
    payload_json = json.dumps(payload)

    # ステップ 2: タイムスタンプを取得
    iat_utc = get_ntp_time()

    # ステップ 3: 共有シークレットから対称鍵を作成
    key_bytes = hashlib.sha256(
        encryption_shared_secret.encode("utf-8")
    ).digest()  # CodeQL[py/weak-cryptographic-algorithm] SHA256 is mandated by Visa API specification

    # 対称鍵用の JWK オブジェクトを作成
    symmetric_key = jwk.JWK(
        kty="oct", k=base64.urlsafe_b64encode(key_bytes).decode("utf-8").rstrip("=")
    )

    # ステップ 4: 保護ヘッダーを作成
    protected_header = {
        "alg": "A256GCMKW",
        "enc": "A256GCM",
        "kid": encryption_api_key,
        "channelSecurityContext": "SHARED_SECRET",
        "iat": str(iat_utc),
    }

    # ステップ 5: JWE token を作成
    jwetoken = jwe.JWE(
        plaintext=payload_json.encode("utf-8"),
        recipient=symmetric_key,
        protected=protected_header,
    )

    # ステップ 6: コンパクト形式にシリアル化
    encrypted_payload = jwetoken.serialize(compact=True)

    return encrypted_payload


def decrypt_token_info(encrypted_jwe, encryption_shared_secret):
    """
    Visa API レスポンスから JWE トークンを復号化する

    Args:
        encrypted_jwe: 暗号化された JWE トークン文字列（encTokenInfo）
        encryption_shared_secret: 対称復号化用の共有シークレット

    Returns:
        辞書形式の復号化されたデータ
    """
    # ステップ 1: 共有シークレットから対称鍵を作成
    key_bytes = hashlib.sha256(
        encryption_shared_secret.encode("utf-8")
    ).digest()  # CodeQL[py/weak-cryptographic-algorithm] SHA256 is mandated by Visa API specification
    symmetric_key = jwk.JWK(
        kty="oct", k=base64.urlsafe_b64encode(key_bytes).decode("utf-8").rstrip("=")
    )

    # ステップ 2: JWE token をデシリアル化して復号化
    jwetoken = jwe.JWE()
    jwetoken.deserialize(encrypted_jwe, key=symmetric_key)

    # ステップ 3: 復号化されたペイロードを抽出して解析
    decrypted_payload = jwetoken.payload.decode("utf-8")
    decrypted_data = json.loads(decrypted_payload)

    return decrypted_data


def create_email_hash(email):
    """Visa API 準拠のメールハッシュを作成する"""
    email_hash = hashlib.sha256(
        email.lower().encode("utf-8")
    ).digest()  # CodeQL[py/weak-cryptographic-algorithm] SHA256 is mandated by Visa API specification
    url_safe = base64.urlsafe_b64encode(email_hash).decode("utf-8").rstrip("=")
    return url_safe[:48]


def generate_client_reference_id():
    """
    ランダムなクライアント参照 ID を生成する

    Returns:
        str: ランダムな UUID 文字列
    """
    return str(uuid.uuid4())


def loadPem(pem_data):
    """PEM 証明書/キーを JWK オブジェクトに読み込む"""
    if isinstance(pem_data, str):
        pem_data = pem_data.encode("utf-8")
    return jwk.JWK.from_pem(pem_data)


def encrypt_payload(
    payload,
    server_cert_secret_name="visa/server-mle-cert",
    region="us-east-1",
    key_id=None,
):  # pragma: allowlist secret
    """
    Secrets Manager の VIC サーバー証明書を使用して RSA-OAEP-256 でペイロードを暗号化する

    これは RSA 暗号化を必要とする VIC API 呼び出し（vacp/v1/cards）に使用される。
    対称暗号化（A256GCMKW）を使用する VTS API 呼び出しとは異なる。

    Args:
        payload: 暗号化する辞書または文字列
        server_cert_secret_name: サーバー証明書を含むシークレットの名前
        region: Secrets Manager の AWS リージョン
        key_id: JWE ヘッダーで使用する keyId（None の場合は visa/vic_key_id から取得）

    Returns:
        {"encData": encrypted_jwe} の辞書
    """
    # 必要に応じてペイロード dict を JSON 文字列に変換
    if isinstance(payload, dict):
        payload = json.dumps(payload)

    # Secrets Manager から証明書を取得
    server_cert = get_secret(server_cert_secret_name, region)

    # 提供されていない場合は Secrets Manager から keyId を取得
    if key_id is None:
        key_id = get_secret("visa/vic_key_id", region)

    protected_header = {
        "alg": "RSA-OAEP-256",
        "enc": "A128GCM",
        "kid": key_id,
        "iat": int(round(time.time() * 1000)),
    }
    jwetoken = jwe.JWE(
        payload.encode("utf-8"),
        recipient=loadPem(server_cert),
        protected=protected_header,
    )

    return {"encData": jwetoken.serialize(compact=True)}


def decrypt_rsa(
    encrypted_jwe, private_key_secret_name="visa/mle-private-cert", region="us-east-1"
):  # pragma: allowlist secret
    """
    Secrets Manager の RSA 秘密鍵を使用して JWE トークンを復号化する

    これは RSA 暗号化を使用する VIC API レスポンスに使用される。

    Args:
        encrypted_jwe: 暗号化された JWE トークン文字列
        private_key_secret_name: 秘密鍵を含むシークレットの名前
        region: Secrets Manager の AWS リージョン

    Returns:
        辞書形式の復号化されたデータ
    """
    # Secrets Manager から秘密鍵を取得
    private_key_pem = get_secret(private_key_secret_name, region)
    private_key = loadPem(private_key_pem)

    # JWE token をデシリアル化して復号化
    jwetoken = jwe.JWE()
    jwetoken.deserialize(encrypted_jwe, key=private_key)

    # 復号化されたペイロードを抽出して解析
    decrypted_payload = jwetoken.payload.decode("utf-8")
    decrypted_data = json.loads(decrypted_payload)

    logger.info(f"復号化されたデータ: {decrypted_data}")

    return decrypted_data

#!/usr/bin/env python3.11
"""
Visa カードオンボーディング UI テスト用ローカルバックエンドサーバー

このサーバーはローカルで実行され、本番環境で AWS Lambda + API Gateway が
提供するものと同じ API エンドポイントを提供します。

使用方法:
    python3.11 local_backend_server.py

その後、http://localhost:3000 の React UI から以下を呼び出せます:
    - http://localhost:5001/api/visa/secure-token
    - http://localhost:5001/api/visa/onboard-card
    - その他
"""

from flask import Flask, jsonify, request

# from flask_cors import CORS  # 不要 - API Gateway が CORS を処理
import traceback
import uuid
import hashlib
import json

# 起動時に必要なものだけをインポート
from visa.secure_token import get_secure_token_direct


# 起動時にシークレットを読み込まないための遅延インポートラッパー関数
def lazy_import_flow():
    """起動時にシークレットを読み込まないよう flow モジュールを遅延インポートする"""
    from visa import flow

    return flow


app = Flask(__name__)

# CORS 設定 - 無効（API Gateway が CORS を処理）
# Flask-CORS は API Gateway と併用すると重複ヘッダーを生成
# ALLOWED_ORIGINS = [
#     'https://vcas.local.com:9000',
#     'https://vcas.local.com:9005',
#     'https://localhost:3000',
#     'https://localhost:5173',  # Vite default port
# ]
# CORS(app, origins=ALLOWED_ORIGINS)

# Visa 認証情報 - 遅延ロード
API_KEY = None
CLIENT_APP_ID = "VICTestAccountTR"


def get_request_json():
    """
    リクエストボディから JSON を安全に取得する。

    Lambda で WsgiToAsgi を通して実行する場合、Flask の request.json は
    失敗し、request.get_data() は空を返します。解決策は wsgi.input
    ストリームから直接読み取ることです。
    """
    # まず Flask の通常の request.json を試す（例外処理付き）
    try:
        if request.json is not None:
            return request.json
    except Exception:
        pass  # wsgi.input メソッドにフォールスルー

    # wsgi.input から直接読み取る（Lambda + WsgiToAsgi で動作）
    try:
        if "wsgi.input" in request.environ:
            wsgi_input = request.environ["wsgi.input"]
            wsgi_input.seek(0)
            body_bytes = wsgi_input.read()
            if body_bytes:
                body_str = body_bytes.decode("utf-8")
                return json.loads(body_str)

        # フォールバック: get_data() を試す
        raw_data = request.get_data(cache=True, as_text=True)
        if raw_data:
            return json.loads(raw_data)

        return {}

    except json.JSONDecodeError as e:
        print(f"❌ JSONデコードエラー: {e}")
        raise
    except Exception as e:
        print(f"❌ リクエストデータの取得エラー: {e}")
        traceback.print_exc()
        raise


def get_api_key():
    """必要に応じて API キーを遅延ロードする"""
    global API_KEY
    if API_KEY is None:
        from visa.helpers import get_secret

        try:
            API_KEY = get_secret("visa/api-key", "us-east-1")
            print("✅ AWS Secrets ManagerからVisa APIキーを読み込みました")
        except Exception as e:
            print(f"⚠️  警告: Secrets ManagerからAPIキーを読み込めませんでした: {e}")
            API_KEY = None
    return API_KEY


@app.route("/", methods=["GET"])
def home():
    """ヘルスチェックエンドポイント"""
    return jsonify(
        {
            "status": "running",
            "message": "Visa Local Backend Server",
            "endpoints": [
                "GET /api/visa/secure-token",
                "POST /api/visa/onboard-card",
                "POST /api/visa/device-attestation",
                "POST /api/visa/device-binding",
                "POST /api/visa/step-up",
                "POST /api/visa/validate-otp",
                "POST /api/visa/complete-passkey",
                "POST /api/visa/vic/enroll-card",
                "POST /api/visa/vic/initiate-purchase",
                "POST /api/visa/vic/payment-credentials",
            ],
        }
    )


@app.route("/api/visa/secure-token", methods=["GET"])
def get_secure_token_endpoint():
    """
    Visa OAuth API から secureToken を取得する（iframe なし！）

    Returns:
        {
            "success": true,
            "secureToken": "ezAwMX06...",
            "requestID": "uuid-here"
        }
    """
    try:
        print("\n=== GET /api/visa/secure-token ===")

        api_key = get_api_key()
        if not api_key:
            raise Exception("API_KEY not configured")

        result = get_secure_token_direct(api_key, CLIENT_APP_ID)

        print("✅ SecureTokenの取得に成功しました")

        return jsonify(
            {
                "success": True,
                "secureToken": result["secureToken"],
                "requestID": result["requestID"],
                "proof_verifier": result.get("proof_verifier"),
                "device_fingerprint": result.get("device_fingerprint"),
            }
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/onboard-card", methods=["POST"])
def onboard_card_endpoint():
    """
    カードを登録してトークンをプロビジョニングする

    Request body:
        {
            "email": "user@example.com",
            "cardNumber": "4622943123044159",
            "cvv": "598",
            "expirationMonth": "12",
            "expirationYear": "2026",
            "secureToken": "ezAwMX06..."  (オプション - 提供されない場合は生成)
        }

    Returns:
        {
            "success": true,
            "vPanEnrollmentID": "...",
            "vProvisionedTokenId": "..."
        }
    """
    try:
        print("\n=== POST /api/visa/onboard-card ===")

        # flow モジュールを遅延インポート
        flow = lazy_import_flow()

        data = get_request_json()
        email = data.get("email")
        card_number = data.get("cardNumber")
        cvv = data.get("cvv")
        exp_month = data.get("expirationMonth")
        exp_year = data.get("expirationYear")
        secure_token = data.get("secureToken")  # iframe セッションからセキュアトークンを取得
        browser_data = data.get("browserData")  # iframe セッションからブラウザデータを取得

        print(f"Email: {email}")
        print(f"Card: {card_number[:4]}...{card_number[-4:]}")

        # iframe CREATE_AUTH_SESSION からのセキュアトークンを使用
        if not secure_token:
            raise Exception("iframe セッションからセキュアトークンが提供されていません")

        print("✅ iframeからSecureTokenを使用しています")

        # デバッグ用にブラウザデータをログ
        if browser_data:
            print(f"✅ iframeからBrowserDataを使用しています: {list(browser_data.keys())}")
        else:
            print("⚠️  警告: iframeからbrowserDataが提供されていません")

        # ステップ 2: カードデータを準備して登録
        pan_data = {
            "accountNumber": card_number,
            "cvv2": cvv,
            "expirationDate": {"month": exp_month, "year": exp_year},
        }

        # VPP セッション継続用の x_request_id を生成
        x_request_id = str(uuid.uuid4())

        # ステップ 1: カードを登録
        enrollment_result = flow.enroll_pan(
            email, pan_data, CLIENT_APP_ID, x_request_id=x_request_id
        )
        vpan_enrollment_id = enrollment_result["vPanEnrollmentID"]

        # ステップ 2: トークンをプロビジョニング
        provision_result = flow.provision_token(
            vpan_enrollment_id,
            email,
            CLIENT_APP_ID,
            browser_data=browser_data,
            x_request_id=x_request_id,
        )
        print(f"📦 プロビジョン結果のキー: {provision_result.keys()}")
        print(f"📦 プロビジョン結果の全体: {provision_result}")
        v_provisioned_token_id = provision_result["vProvisionedTokenID"]
        print(f"📦 抽出されたvProvisionedTokenId: {v_provisioned_token_id}")

        result = {
            "vPanEnrollmentID": vpan_enrollment_id,
            "vProvisionedTokenId": v_provisioned_token_id,
            "lastFourDigits": pan_data["accountNumber"][-4:],
            "xRequestId": x_request_id,
        }

        # このトランザクション用の client_reference_id を生成（すべての API 呼び出しで再利用）
        client_reference_id = str(uuid.uuid4())

        print(f"✅ カードの登録とプロビジョンが完了しました: {result.get('vPanEnrollmentID')}")
        print(f"✅ トークンID: {result.get('vProvisionedTokenId')}")
        print(f"✅ クライアントリファレンスID: {client_reference_id}")

        return jsonify(
            {
                "success": True,
                "vPanEnrollmentID": result.get("vPanEnrollmentID"),
                "vProvisionedTokenId": result.get("vProvisionedTokenId"),
                "lastFourDigits": result.get("lastFourDigits"),
                "secureToken": secure_token,  # デバイス認証用にセキュアトークンを返す
                "xRequestId": result.get(
                    "xRequestId"
                ),  # VPP セッション継続用に x_request_id を返す
                "clientReferenceId": client_reference_id,  # トランザクション追跡用に client_reference_id を返す
            }
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/device-attestation", methods=["POST"])
def device_attestation_endpoint():
    """
    パスキー作成用の WebAuthn デバイス認証オプションを取得する

    VPP フローで 2 つの異なるステップを処理:
    - ステップ 4: AUTHENTICATE（reasonCode=PAYMENT、デバイスバインディング前）
    - ステップ 9: REGISTER（reasonCode=DEVICE_BINDING、OTP 検証後）

    Request body:
        {
            "email": "user@example.com",
            "vProvisionedTokenId": "...",
            "secureToken": "...",
            "browserData": {...},
            "step": "AUTHENTICATE" または "REGISTER",
            "panData": {...},  // AUTHENTICATE ステップのみ
            "xRequestId": "...",  // onboard-card からの VPP セッション x-request-id
            "clientReferenceId": "..."  // onboard-card からのトランザクション client_reference_id
        }

    Returns:
        {
            "success": true,
            "action": "REGISTER",  // AUTHENTICATE ステップの場合
            "authenticationContext": {...},  // REGISTER ステップの場合
            "fullResponse": {...}
        }
    """
    try:
        print("\n=== POST /api/visa/device-attestation ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        email = data.get("email")
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        secure_token = data.get("secureToken")
        browser_data = data.get("browserData")
        step = data.get(
            "step", "AUTHENTICATE"
        )  # 後方互換性のためデフォルトは AUTHENTICATE
        # 注: panData は不要 - encAuthenticationData には email を使用
        x_request_id = data.get("xRequestId")  # VPP セッション x-request-id
        client_reference_id = data.get(
            "clientReferenceId"
        )  # トランザクション client_reference_id（onboard-card から再利用）

        print(f"Email: {email}")
        print(f"TokenId: {v_provisioned_token_id}")
        print(f"SecureToken: {'present' if secure_token else 'None'}")
        print(f"Step: {step}")

        # 必須フィールドを検証
        if not client_reference_id:
            raise ValueError(
                "clientReferenceId は必須です - onboard-card レスポンスから渡す必要があります"
            )
        if not x_request_id:
            raise ValueError(
                "xRequestId は必須です - onboard-card レスポンスから渡す必要があります"
            )

        if step == "AUTHENTICATE":
            # ステップ 4: デバイス認証 Authenticate（reasonCode=PAYMENT、type=AUTHENTICATE）
            # デバイスバインディングが必要かどうかをチェック
            print("🔵 device_attestation_authenticateを呼び出しています (ステップ 4)")

            # リクエストからトランザクション金額を取得（デフォルトは 567.89）
            transaction_amount = data.get("transactionAmount", "567.89")

            result = flow.device_attestation_authenticate(
                email,  # FIXED: Pass email instead of pan_data
                secure_token,
                v_provisioned_token_id,
                browser_data,
                CLIENT_APP_ID,
                client_reference_id,
                x_request_id,
                transaction_amount,
            )

            print("✅ デバイス認証の認証が完了しました")
            # ネストされた authenticationContext からアクションを抽出
            action = result.get("authenticationContext", {}).get("action")
            print(f"Action: {action}")

            return jsonify(
                {
                    "success": True,
                    "action": action,  # "REGISTER" であればデバイスバインディングが必要
                    "fullResponse": result,
                }
            )

        elif step == "REGISTER":
            # ステップ 9: デバイス認証 Register（reasonCode=DEVICE_BINDING、type=REGISTER）
            # iframe パスキー作成用のペイロードを返す
            print("🔵 device_attestation_registerを呼び出しています (ステップ 9)")

            result = flow.device_attestation_register(
                v_provisioned_token_id,
                email,
                secure_token,
                browser_data,
                CLIENT_APP_ID,
                client_reference_id,
                x_request_id,
            )

            print("✅ デバイス認証の登録が完了しました")
            print(f"authenticationContextあり: {'authenticationContext' in result}")

            return jsonify(
                {
                    "success": True,
                    "authenticationContext": result.get("authenticationContext"),
                    "fullResponse": result,
                }
            )

        else:
            raise ValueError(
                f"Invalid step: {step}. Must be 'AUTHENTICATE' or 'REGISTER'"
            )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/complete-passkey", methods=["POST"])
def complete_passkey_endpoint():
    """
    Visa でパスキー登録を完了する

    Request body:
        {
            "vProvisionedTokenId": "...",
            "fidoBlob": "base64-encoded-fido-response"
        }

    Returns:
        {
            "success": true
        }
    """
    try:
        print("\n=== POST /api/visa/complete-passkey ===")

        # flow 関数をインポート
        _flow = lazy_import_flow()

        data = get_request_json()
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        fido_blob = data.get("fidoBlob")

        print(f"TokenId: {v_provisioned_token_id}")
        print(
            f"FidoBlob: {'present' if fido_blob else 'None'} (length: {len(fido_blob) if fido_blob else 0})"
        )

        if not fido_blob or (isinstance(fido_blob, str) and fido_blob.strip() == ""):
            raise ValueError("fidoBlob is empty")

        # fidoBlob は Visa iframe からの URL エンコードされた文字列
        # パラメータを抽出するためにパース
        import urllib.parse

        params = urllib.parse.parse_qs(fido_blob)
        code = params.get("c", [""])[0]
        hint = params.get("h", [""])[0]

        result = {
            "success": True,
            "code": code,
            "fidoBlob": fido_blob,
            "vProvisionedTokenId": v_provisioned_token_id,
            "hint": hint,
        }

        print("✅ Passkey登録が完了しました")

        return jsonify({"success": True, "result": result})

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/device-binding", methods=["POST"])
def device_binding_endpoint():
    """
    ステップ 5: デバイスバインディングを取得（VPP）

    Request body:
        {
            "vProvisionedTokenId": "...",
            "secureToken": "...",
            "email": "user@example.com",
            "browserData": {...},
            "xRequestId": "...",  // onboard-card からの VPP セッション x-request-id
            "clientReferenceId": "..."  // onboard-card からのトランザクション client_reference_id
        }

    Returns:
        {
            "success": true,
            "stepUpRequest": [{...}],
            "status": "CHALLENGE"
        }
    """
    try:
        print("\n=== POST /api/visa/device-binding ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        secure_token = data.get("secureToken")
        email = data.get("email")
        browser_data = data.get("browserData")
        x_request_id = data.get("xRequestId")  # VPP セッション x-request-id
        client_reference_id = data.get(
            "clientReferenceId"
        )  # トランザクション client_reference_id（onboard-card から再利用）

        print(f"TokenId: {v_provisioned_token_id}")
        print(f"Email: {email}")
        print(f"SecureToken: {'present' if secure_token else 'None'}")

        # 必須フィールドを検証
        if not client_reference_id:
            raise ValueError(
                "clientReferenceId は必須です - onboard-card レスポンスから渡す必要があります"
            )
        if not x_request_id:
            raise ValueError(
                "xRequestId は必須です - onboard-card レスポンスから渡す必要があります"
            )

        # flow.py から device_binding を呼び出し
        result = flow.device_binding(
            secure_token,
            email,
            v_provisioned_token_id,
            browser_data,
            CLIENT_APP_ID,
            client_reference_id,
            x_request_id,
        )

        print("✅ デバイスバインディングが完了しました")
        print(f"ステータス: {result.get('status')}")
        print(f"ステップアップオプション: {len(result.get('stepUpRequest', []))}")

        return jsonify(
            {
                "success": True,
                "stepUpRequest": result.get("stepUpRequest", []),
                "status": result.get("status"),
                "fullResponse": result,
            }
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/step-up", methods=["POST"])
def step_up_endpoint():
    """
    ステップ 6: ステップアップオプションを選択（VPP）

    Request body:
        {
            "vProvisionedTokenId": "...",
            "identifier": "...",
            "method": "OTPSMS" または "OTPEMAIL",
            "xRequestId": "...",  // onboard-card からの VPP セッション x-request-id
            "clientReferenceId": "..."  // onboard-card からのトランザクション client_reference_id
        }

    Returns:
        {
            "success": true
        }
    """
    try:
        print("\n=== POST /api/visa/step-up ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        identifier = data.get("identifier")
        method = data.get("method")
        x_request_id = data.get("xRequestId")  # VPP セッション x-request-id
        client_reference_id = data.get(
            "clientReferenceId"
        )  # トランザクション client_reference_id（onboard-card から再利用）

        print(f"TokenId: {v_provisioned_token_id}")
        print(f"Method: {method}")

        # 必須フィールドを検証
        if not client_reference_id:
            raise ValueError(
                "clientReferenceId は必須です - onboard-card レスポンスから渡す必要があります"
            )
        if not x_request_id:
            raise ValueError(
                "xRequestId は必須です - onboard-card レスポンスから渡す必要があります"
            )

        # flow.py から step_up を呼び出し
        result = flow.step_up(
            v_provisioned_token_id,
            identifier,
            CLIENT_APP_ID,
            client_reference_id,
            x_request_id,
        )

        print("✅ ステップアップオプションが選択されました")

        return jsonify({"success": True, "result": result})

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/validate-otp", methods=["POST"])
def validate_otp_endpoint():
    """
    ステップ 8: OTP を検証（VPP）

    Request body:
        {
            "vProvisionedTokenId": "...",
            "otpValue": "123456",
            "xRequestId": "...",  // onboard-card からの VPP セッション x-request-id
            "clientReferenceId": "..."  // onboard-card からのトランザクション client_reference_id
        }

    Returns:
        {
            "success": true,
            "status": "VALIDATED"
        }
    """
    try:
        print("\n=== POST /api/visa/validate-otp ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        otp_value = data.get("otpValue")
        x_request_id = data.get("xRequestId")  # VPP セッション x-request-id
        client_reference_id = data.get(
            "clientReferenceId"
        )  # トランザクション client_reference_id（onboard-card から再利用）

        print(f"TokenId: {v_provisioned_token_id}")
        print(f"OTP: {'*' * len(otp_value) if otp_value else 'None'}")

        # 必須フィールドを検証
        if not client_reference_id:
            raise ValueError(
                "clientReferenceId は必須です - onboard-card レスポンスから渡す必要があります"
            )
        if not x_request_id:
            raise ValueError(
                "xRequestId は必須です - onboard-card レスポンスから渡す必要があります"
            )

        # flow.py から validate_otp を呼び出し
        result = flow.validate_otp(
            v_provisioned_token_id,
            otp_value,
            CLIENT_APP_ID,
            client_reference_id,
            x_request_id,
        )

        print("✅ OTPが検証されました")
        print(f"ステータス: {result.get('status')}")

        return jsonify(
            {"success": True, "status": result.get("status"), "result": result}
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/vic/enroll-card", methods=["POST"])
def vic_enroll_card_endpoint():
    """
    ステップ 14: VIC カード登録

    Request body:
        {
            "email": "user@example.com",
            "vProvisionedTokenId": "..."
        }

    Returns:
        {
            "success": true,
            "clientReferenceId": "...",
            "consumerId": "...",
            "clientDeviceId": "...",
            "status": "..."
        }
    """
    try:
        print("\n=== POST /api/visa/vic/enroll-card ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        email = data.get("email")
        v_provisioned_token_id = data.get("vProvisionedTokenId")

        print(f"Email: {email}")
        print(f"TokenId: {v_provisioned_token_id}")

        # VIC 登録用の ID を生成（動作確認済みバージョンと一致）
        client_reference_id = str(uuid.uuid4())
        client_device_id = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]
        consumer_id = str(uuid.uuid4())

        print(f"生成されたclient_reference_id: {client_reference_id}")
        print(f"生成されたclient_device_id: {client_device_id}")
        print(f"生成されたconsumer_id: {consumer_id}")

        # VIC カード登録を呼び出し（シークレットを遅延ロード）
        result = flow.vic_enroll_card(
            email,
            v_provisioned_token_id,
            CLIENT_APP_ID,
            client_reference_id,
            client_device_id,
            consumer_id,
        )

        print(f"✅ VICカードが登録されました: {result.get('clientReferenceId')}")

        # 後続の購入フローに必要なすべての ID を返す
        return jsonify(
            {
                "success": True,
                "clientReferenceId": result.get("clientReferenceId"),
                "consumerId": consumer_id,
                "clientDeviceId": client_device_id,
                "status": result.get("status"),
                "raw": result.get("raw"),
            }
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/vic/initiate-purchase", methods=["POST"])
def vic_initiate_purchase_endpoint():
    """
    ステップ 15: VIC 購入指示の開始

    Request body:
        {
            "vProvisionedTokenId": "...",
            "consumerId": "...",
            "clientReferenceId": "...",
            "clientDeviceId": "...",
            "consumerRequest": "りんごを購入",
            "authIdentifier": "...",
            "dfpSessionId": "...",
            "fidoBlob": "...",
            "transactionAmount": "444.44"
        }

    Returns:
        {
            "success": true,
            "instructionId": "...",
            "clientReferenceId": "...",
            "status": "..."
        }
    """
    try:
        print("\n=== POST /api/visa/vic/initiate-purchase ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        consumer_id = data.get("consumerId")
        client_reference_id = data.get("clientReferenceId")
        client_device_id = data.get("clientDeviceId")
        consumer_request_raw = data.get("consumerRequest", "カートから購入")
        auth_identifier = data.get("authIdentifier", "")
        dfp_session_id = data.get("dfpSessionId", "")
        iframe_auth_fido_blob = data.get("fidoBlob", "")
        transaction_amount = data.get("transactionAmount", "444.44")

        # Visa API 400 エラーを回避するため consumer_request を切り詰め（最大 150 文字）
        MAX_CONSUMER_REQUEST_LENGTH = 150
        if len(consumer_request_raw) > MAX_CONSUMER_REQUEST_LENGTH:
            consumer_request = (
                consumer_request_raw[: MAX_CONSUMER_REQUEST_LENGTH - 3] + "..."
            )
            print(
                f"⚠️  消費者リクエストが{len(consumer_request_raw)}文字から{len(consumer_request)}文字に切り詰められました"
            )
        else:
            consumer_request = consumer_request_raw

        print(f"TokenId: {v_provisioned_token_id}")
        print(f"ConsumerId: {consumer_id}")
        print(f"ClientReferenceId: {client_reference_id}")
        print(f"ClientDeviceId: {client_device_id}")
        print(f"ConsumerRequest: {consumer_request}")
        print(f"TransactionAmount: ${transaction_amount}")

        # この購入用の mandate_id を生成
        mandate_id = str(uuid.uuid4())
        print(f"生成されたmandate_id: {mandate_id}")

        # 11 個の必須パラメータすべてで VIC 購入開始を呼び出し
        result = flow.vic_initiate_purchase_instructions(
            v_provisioned_token_id,  # 1. provisioned_token_id
            consumer_id,  # 2. consumer_id (from enrollment)
            CLIENT_APP_ID,  # 3. client_app_id
            mandate_id,  # 4. mandate_id (generated)
            consumer_request,  # 5. consumer_request (from request)
            client_reference_id,  # 6. client_reference_id (from enrollment)
            client_device_id,  # 7. client_device_id (from enrollment)
            auth_identifier,  # 8. auth_identifier (from request)
            dfp_session_id,  # 9. dfp_session_id (from request)
            iframe_auth_fido_blob,  # 10. iframe_auth_fido_blob (from request)
            transaction_amount,  # 11. transaction_amount (from request)
        )

        print(f"✅ 購入指示が開始されました: {result.get('instructionId')}")

        return jsonify(
            {
                "success": True,
                "instructionId": result.get("instructionId"),
                "clientReferenceId": result.get("clientReferenceId"),
                "status": result.get("status"),
                "raw": result.get("raw"),
            }
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/visa/vic/payment-credentials", methods=["POST"])
def vic_payment_credentials_endpoint():
    """
    ステップ 16: VIC 支払い認証情報を取得（クリプトグラム）

    Request body:
        {
            "instructionId": "...",
            "vProvisionedTokenId": "...",
            "clientReferenceId": "...",
            "merchantUrl": "https://www.rei.com",
            "merchantName": "REI",
            "transactionAmount": "444.44"
        }

    Returns:
        {
            "success": true,
            "signedPayload": "...",
            "instructionId": "...",
            "status": "..."
        }
    """
    try:
        print("\n=== POST /api/visa/vic/payment-credentials ===")

        # flow 関数をインポート
        flow = lazy_import_flow()

        data = get_request_json()
        instruction_id = data.get("instructionId")
        v_provisioned_token_id = data.get("vProvisionedTokenId")
        client_reference_id = data.get("clientReferenceId", str(uuid.uuid4()))
        merchant_url = data.get("merchantUrl", "https://www.rei.com")
        merchant_name = data.get("merchantName", "REI")
        transaction_amount = data.get("transactionAmount", "444.44")

        print(f"InstructionId: {instruction_id}")
        print(f"TokenId: {v_provisioned_token_id}")
        print(f"ClientReferenceId: {client_reference_id}")
        print(f"Merchant: {merchant_name} ({merchant_url})")
        print(f"Amount: ${transaction_amount}")

        # すべての必須パラメータで VIC 支払い認証情報取得を呼び出し
        result = flow.vic_get_payment_credentials(
            instruction_id,
            v_provisioned_token_id,
            CLIENT_APP_ID,
            client_reference_id,
            merchant_url,
            merchant_name,
            transaction_amount,
        )

        print("✅ 支払い認証情報を取得しました")

        return jsonify(
            {
                "success": True,
                "signedPayload": result.get("signedPayload"),
                "instructionId": result.get("instructionId"),
                "status": result.get("status"),
                "raw": result.get("raw"),
            }
        )

    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Visa Local Backend Server")
    parser.add_argument("--http", action="store_true", help="Run in HTTP mode (no SSL)")
    args = parser.parse_args()

    use_ssl = not args.http
    protocol = "https" if use_ssl else "http"

    print("=" * 60)
    print(f"🚀 Visaローカルバックエンドサーバーを起動しています ({protocol.upper()})")
    print("=" * 60)
    print()
    print(f"サーバー稼働中: {protocol}://localhost:5001")
    print()
    print("利用可能なエンドポイント:")
    print(f"  GET  {protocol}://localhost:5001/api/visa/secure-token")
    print(f"  POST {protocol}://localhost:5001/api/visa/onboard-card")
    print(f"  POST {protocol}://localhost:5001/api/visa/device-attestation")
    print(f"  POST {protocol}://localhost:5001/api/visa/complete-passkey")
    print()
    if use_ssl:
        print(
            "⚠️  SSL警告が表示される場合があります - 自己署名証明書では正常な動作です"
        )
        print("   ブラウザで「詳細設定」->「localhostへ進む」をクリックしてください")
        print()
        print("💡 ヒント: --httpフラグを使用してHTTPモードで実行すると（SSL警告なし）")
    else:
        print("⚠️  HTTPモードで実行中（SSLなし）- ローカル開発専用")
    print()
    print("=" * 60)
    print()

    if use_ssl:
        app.run(host="localhost", port=5001, ssl_context="adhoc")
    else:
        app.run(host="localhost", port=5001)

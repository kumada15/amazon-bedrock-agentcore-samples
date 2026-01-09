"""Lab 03 用の JWT トークンデコードと表示ユーティリティ"""
import json
import base64
from typing import Dict, List


def decode_jwt(token: str) -> Dict:
    """JWT トークンのペイロードをデコード"""
    parts = token.split('.')
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += '=' * padding
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def print_token_claims(claims: Dict, title: str = "Token Claims") -> None:
    """JWT クレームを整形して表示"""
    print(f"\n {title}:")
    print(f"   ユーザー名: {claims.get('username', 'N/A')}")
    print(f"   グループ: {claims.get('cognito:groups', [])}")
    print(f"   クライアント ID: {claims.get('client_id', 'N/A')}")
    print(f"   トークン用途: {claims.get('token_use', 'N/A')}")
    print(f"   スコープ: {claims.get('scope', 'N/A')}")


def compare_tokens(sre_claims: Dict, approver_claims: Dict) -> None:
    """2 つのトークンクレームを並べて比較"""
    print("\n" + "="*80)
    print("トークン比較: SRE vs 承認者")
    print("="*80)

    print(f"\n{'クレーム':<20} {'SRE ユーザー':<30} {'承認者ユーザー':<30}")
    print("-" * 80)

    claims_to_compare = ['username', 'cognito:groups', 'client_id', 'token_use', 'scope']
    for claim in claims_to_compare:
        sre_val = str(sre_claims.get(claim, 'N/A'))
        approver_val = str(approver_claims.get(claim, 'N/A'))
        marker = "!!" if sre_val != approver_val else "  "
        print(f"{marker} {claim:<18} {sre_val:<30} {approver_val:<30}")

    print("\n主要な違い: cognito:groups クレーム")
    print(f"   SRE グループ: {sre_claims.get('cognito:groups', [])}")
    print(f"   承認者グループ: {approver_claims.get('cognito:groups', [])}")
    print("   このクレームは Lambda インターセプターによる認可に使用されます。")

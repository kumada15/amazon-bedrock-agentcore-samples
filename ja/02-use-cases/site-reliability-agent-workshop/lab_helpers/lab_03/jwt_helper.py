"""Lab 03 用 JWT トークンデコードおよび表示ユーティリティ"""
import json
import base64
from typing import Dict, List


def decode_jwt(token: str) -> Dict:
    """JWT トークンペイロードをデコード"""
    parts = token.split('.')
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += '=' * padding
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def print_token_claims(claims: Dict, title: str = "Token Claims") -> None:
    """JWT クレームを整形して出力"""
    print(f"\n📋 {title}:")
    print(f"   Username: {claims.get('username', 'N/A')}")
    print(f"   Groups: {claims.get('cognito:groups', [])}")
    print(f"   Client ID: {claims.get('client_id', 'N/A')}")
    print(f"   Token Use: {claims.get('token_use', 'N/A')}")
    print(f"   Scope: {claims.get('scope', 'N/A')}")


def compare_tokens(sre_claims: Dict, approver_claims: Dict) -> None:
    """2 つのトークンクレームを並べて比較"""
    print("\n" + "="*80)
    print("TOKEN COMPARISON: SRE vs APPROVER")
    print("="*80)
    
    print(f"\n{'Claim':<20} {'SRE User':<30} {'Approver User':<30}")
    print("-" * 80)
    
    claims_to_compare = ['username', 'cognito:groups', 'client_id', 'token_use', 'scope']
    for claim in claims_to_compare:
        sre_val = str(sre_claims.get(claim, 'N/A'))
        approver_val = str(approver_claims.get(claim, 'N/A'))
        marker = "⚠️" if sre_val != approver_val else "  "
        print(f"{marker} {claim:<18} {sre_val:<30} {approver_val:<30}")
    
    print("\n🔑 KEY DIFFERENCE: cognito:groups claim")
    print(f"   SRE groups: {sre_claims.get('cognito:groups', [])}")
    print(f"   Approver groups: {approver_claims.get('cognito:groups', [])}")
    print("   This claim is used by Lambda interceptor for authorization.")

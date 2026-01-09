#!/usr/bin/env python3
"""
シンプルな Cognito 認証スクリプト
オリジナルチュートリアルのアプローチと一致
"""

import boto3
import sys


def get_token(client_id, username, password, region=None):
    """Cognito から認証トークンを取得"""
    # 指定されたリージョンを使用するか、環境/設定からデフォルトを使用
    if region:
        cognito_client = boto3.client("cognito-idp", region_name=region)
    else:
        cognito_client = boto3.client("cognito-idp")

    try:
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )

        return auth_response["AuthenticationResult"]["AccessToken"]

    except Exception as e:
        print(f"エラー: {e}")
        print("トラブルシューティング:")
        print("  - クライアントIDが正しいことを確認してください")
        print("  - 正しいリージョンを使用していることを確認してください")
        print("  - ユーザーが存在し、パスワードが正しいことを確認してください")
        print("  - USER_PASSWORD_AUTHがこのクライアントで有効になっていることを確認してください")
        sys.exit(1)


def main():
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print("使用方法: python get_token.py <client_id> <username> <password> [region]")
        print("\n例:")
        print("  python get_token.py abc123xyz testuser MyPassword123!")
        print("  python get_token.py abc123xyz testuser MyPassword123! us-west-2")
        sys.exit(1)

    client_id = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    region = sys.argv[4] if len(sys.argv) == 5 else None

    if region:
        print(f"リージョン{region}でCognitoの認証を実行中...")
    else:
        print("Cognitoの認証を実行中...")

    token = get_token(client_id, username, password, region)

    print("\n" + "=" * 70)
    print("認証に成功しました！")
    print("=" * 70)
    print("\nアクセストークン:")
    print(token)
    print("\n" + "=" * 70)
    print("エクスポートコマンド:")
    print("=" * 70)
    print(f'\nexport JWT_TOKEN="{token}"')
    print("\ncurlで使用する場合:")
    print('curl -H "Authorization: Bearer $JWT_TOKEN" <your-api-url>')
    print()


if __name__ == "__main__":
    main()

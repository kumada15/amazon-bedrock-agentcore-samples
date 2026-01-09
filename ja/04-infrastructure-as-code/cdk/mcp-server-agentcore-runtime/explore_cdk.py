#!/usr/bin/env python3

import aws_cdk.aws_bedrockagentcore as bedrockagentcore
import inspect

print("=== aws_cdk.aws_bedrockagentcoreモジュールを探索 ===")
print()

# モジュール内のすべての属性をリスト
print("利用可能なクラスと関数:")
for name in dir(bedrockagentcore):
    if not name.startswith('_'):
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

print()
print("=== CfnRuntimeクラスの詳細 ===")

# Explore CfnRuntime class
runtime_class = bedrockagentcore.CfnRuntime
print(f"CfnRuntime: {runtime_class}")

print("\nCfnRuntimeの属性:")
for name in dir(runtime_class):
    if not name.startswith('_'):
        try:
            attr = getattr(runtime_class, name)
            print(f"  {name}: {type(attr)}")
        except Exception as e:
            print(f"  {name}: アクセスエラー - {e}")

print("\nPropertyクラスを検索中:")
for name in dir(bedrockagentcore):
    if 'Property' in name:
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

print("\nAuthorizer関連クラスを検索中:")
for name in dir(bedrockagentcore):
    if 'Auth' in name.lower():
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

print("\nJWT関連クラスを検索中:")
for name in dir(bedrockagentcore):
    if 'jwt' in name.lower() or 'JWT' in name:
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

# コンストラクタのシグネチャを取得
print("\n=== CfnRuntimeコンストラクタのシグネチャ ===")
try:
    sig = inspect.signature(runtime_class.__init__)
    print(f"コンストラクタのシグネチャ: {sig}")
except Exception as e:
    print(f"シグネチャの取得エラー: {e}")

# CfnRuntime プロパティを探索
print("\n=== ネストされたPropertyクラスを検索中 ===")
try:
    # ネストされたクラスがあるか確認
    for name in dir(runtime_class):
        if not name.startswith('_') and name.endswith('Property'):
            prop_class = getattr(runtime_class, name)
            print(f"  {name}: {prop_class}")

            # コンストラクタのシグネチャを取得
            try:
                prop_sig = inspect.signature(prop_class.__init__)
                print(f"    コンストラクタ: {prop_sig}")
            except Exception as e:
                print(f"    コンストラクタの取得エラー: {e}")

except Exception as e:
    print(f"ネストされたクラスの探索エラー: {e}")

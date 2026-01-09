#!/usr/bin/env python3
"""
Okta セットアップ画像のラジオボタンに赤いハイライトと矢印を追加するスクリプト
"""

from PIL import Image, ImageDraw, ImageFont
import os

def add_radio_button_highlights(image_path, output_path, radio_positions):
    """
    ラジオボタンの位置に赤いハイライトを追加します
    """
    # 画像を開く
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # ハイライト用の赤色
    red_color = (255, 0, 0)

    for x, y in radio_positions:
        # ラジオボタンの周りに太い赤い円を描画
        radius = 20
        for r in range(4):  # 太さのために複数の円を描画
            draw.ellipse([x-radius-r, y-radius-r, x+radius+r, y+radius+r], 
                        outline=red_color, width=3)
    
    # 加工した画像を保存
    img.save(output_path)
    print(f"加工した画像を保存しました: {output_path}")

def add_box_highlights(image_path, output_path, box_positions):
    """
    特定の領域に赤いボックスハイライトを追加します
    """
    # 画像を開く
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # ハイライト用の赤色
    red_color = (255, 0, 0)

    for x1, y1, x2, y2 in box_positions:
        # 太い赤い四角形を描画
        for r in range(4):
            draw.rectangle([x1-r, y1-r, x2+r, y2+r],
                          outline=red_color, width=3)

    # 加工した画像を保存
    img.save(output_path)
    print(f"加工した画像を保存しました: {output_path}")

def main():
    base_dir = "/Users/suramac/amazon-bedrock-agentcore-samples/03-integrations/IDP-examples/Okta/images"
    
    # Image 2.png - サインイン方法とアプリケーションタイプのラジオボタン
    image2_positions = [
        (388, 65),   # OIDC - OpenID Connect ラジオボタン
        (388, 473)   # Web Application ラジオボタン
    ]
    
    add_radio_button_highlights(
        os.path.join(base_dir, "2.png"),
        os.path.join(base_dir, "2_enhanced.png"),
        image2_positions
    )
    
    # Image 5.png - アクセス制御と即時アクセス有効化のラジオボタン
    image5_positions = [
        (362, 62),   # 組織内の全員にアクセスを許可するラジオボタン
        (362, 194)   # 即時アクセスを有効にするチェックボックス（ラジオボタンとして扱う）
    ]

    # Image 3.png - グラントタイプのラジオボタンとチェックボックス
    image3_positions = [
        (408, 364),  # 認可コードチェックボックス（選択済み）
    ]
    
    add_radio_button_highlights(
        os.path.join(base_dir, "3.png"),
        os.path.join(base_dir, "3_enhanced.png"),
        image3_positions
    )
    
    # Image 6.png - クライアント認証のラジオボタンとクライアント資格情報のハイライト
    image6_positions = [
        (317, 391),  # クライアントシークレットラジオボタン（選択済み）
        (653, 289),  # クライアントIDコピーボタン
        (530, 725),  # クライアントシークレットコピーボタン
    ]
    
    add_radio_button_highlights(
        os.path.join(base_dir, "6.png"),
        os.path.join(base_dir, "6_enhanced.png"),
        image6_positions
    )
    
    # Image 7.png - 発行者メタデータURIのボックスハイライト
    image7_boxes = [
        (20, 462, 300, 511),  # 発行者メタデータURIラベルボックス（下に移動）
    ]
    
    add_box_highlights(
        os.path.join(base_dir, "7.png"),
        os.path.join(base_dir, "7_enhanced.png"),
        image7_boxes
    )

if __name__ == "__main__":
    main()

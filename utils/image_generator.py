# utils/image_generator.py
from PIL import Image, ImageDraw, ImageFont
import os
from django.conf import settings

def generate_pwa_icons():
    """PWA用アイコンを生成"""
    
    # 保存先ディレクトリ
    icons_dir = os.path.join(settings.STATIC_ROOT or settings.STATICFILES_DIRS[0], 'images')
    os.makedirs(icons_dir, exist_ok=True)
    
    # メインアイコン生成
    create_main_icon(icons_dir, 192)
    create_main_icon(icons_dir, 512)
    
    # ショートカットアイコン生成
    create_shortcut_icon(icons_dir, 'create', 96)
    create_shortcut_icon(icons_dir, 'analytics', 96)
    
    # スクリーンショット生成
    create_screenshot(icons_dir)
    
    print("✅ PWA画像生成完了")

def create_main_icon(output_dir, size):
    """メインアイコン生成"""
    # RGBAモードで画像作成（透明度サポートのため）
    img = Image.new('RGBA', (size, size), color=(90, 126, 197, 255))  # #5a7ec5
    draw = ImageDraw.Draw(img)
    
    # 「株」文字を描画
    font_size = int(size * 0.4)
    try:
        # macOS用フォント
        font_paths = [
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/System/Library/Fonts/ヒラギノ角ゴ ProN W3.otf',
            '/Library/Fonts/Arial Unicode MS.ttf',
            # Windows用（念のため）
            'C:/Windows/Fonts/msgothic.ttc',
            'C:/Windows/Fonts/meiryo.ttc',
            # Linux用
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
        ]
        font = None
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except:
                    continue
        if not font:
            font = ImageFont.load_default()
    except Exception as e:
        print(f"フォント読み込みエラー: {e}")
        font = ImageFont.load_default()
    
    # 「株」を中央に配置
    text = "株"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - int(size * 0.05)
    
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)  # 白色
    
    # 簡単なグラフを下部に描画
    graph_y = size - int(size * 0.15)
    graph_points = []
    for i in range(5):
        x_pos = int(size * 0.2) + (i * int(size * 0.15))
        y_pos = graph_y - (i * int(size * 0.02))
        graph_points.extend([x_pos, y_pos])
    
    if len(graph_points) >= 4:
        draw.line(graph_points, fill=(255, 255, 255, 255), width=max(2, size//100))
    
    # 四隅に装飾（RGB色で指定）
    corner_size = max(3, size//40)
    margin = int(size * 0.1)
    positions = [(margin, margin), (size-margin, margin), 
                (margin, size-margin), (size-margin, size-margin)]
    
    for pos in positions:
        draw.ellipse([pos[0]-corner_size, pos[1]-corner_size, 
                     pos[0]+corner_size, pos[1]+corner_size], 
                     fill=(248, 194, 145, 180))  # #f8c291 with alpha
    
    # PNG形式で保存（RGBAをサポート）
    filename = os.path.join(output_dir, f'icon-{size}.png')
    img.save(filename, 'PNG')
    print(f"✅ 作成: {filename}")

def create_shortcut_icon(output_dir, icon_type, size):
    """ショートカットアイコン生成"""
    img = Image.new('RGBA', (size, size), color=(90, 126, 197, 255))
    draw = ImageDraw.Draw(img)
    
    # 円形背景
    margin = size // 10
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 fill=(90, 126, 197, 255), outline=(255, 255, 255, 255), width=3)
    
    if icon_type == 'create':
        # プラス記号
        line_width = max(4, size//15)
        center = size // 2
        line_length = size // 3
        
        # 縦線
        draw.line([center, center-line_length, center, center+line_length], 
                 fill=(255, 255, 255, 255), width=line_width)
        # 横線  
        draw.line([center-line_length, center, center+line_length, center], 
                 fill=(255, 255, 255, 255), width=line_width)
    
    elif icon_type == 'analytics':
        # 棒グラフ
        bar_width = size // 12
        base_y = size - size // 4
        start_x = size // 4
        
        heights = [0.3, 0.5, 0.7, 0.9]
        colors = [(248, 194, 145, 255), (93, 176, 117, 255)]  # オレンジと緑
        
        for i, height in enumerate(heights):
            bar_height = int(size * 0.4 * height)
            x = start_x + (i * bar_width * 1.5)
            color = colors[i % 2]
            draw.rectangle([x, base_y-bar_height, x+bar_width, base_y], 
                          fill=color)
    
    filename = os.path.join(output_dir, f'shortcut-{icon_type}.png')
    img.save(filename, 'PNG')
    print(f"✅ 作成: {filename}")

def create_screenshot(output_dir):
    """スクリーンショット生成"""
    width, height = 390, 844
    img = Image.new('RGB', (width, height), color=(246, 248, 250))  # #f6f8fa
    draw = ImageDraw.Draw(img)
    
    # ヘッダー
    draw.rectangle([0, 0, width, 120], fill=(255, 255, 255), outline=(229, 231, 235))
    
    # タイトル
    try:
        title_font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 18)
    except:
        try:
            title_font = ImageFont.load_default()
        except:
            title_font = None
    
    if title_font:
        draw.text((20, 50), 'カブログ', fill=(51, 51, 51), font=title_font)
    else:
        draw.text((20, 50), 'カブログ', fill=(51, 51, 51))
    
    # ロゴ（小さな円）
    draw.ellipse([320, 45, 340, 65], fill=(90, 126, 197))
    
    # 検索バー
    draw.rectangle([20, 140, 370, 190], fill=(255, 255, 255), outline=(222, 226, 230))
    draw.text((30, 162), '銘柄名で検索...', fill=(156, 163, 175))
    
    # 検索アイコン
    draw.ellipse([340, 158, 352, 170], outline=(156, 163, 175), width=1)
    
    # 日記カード1
    draw.rectangle([20, 210, 370, 350], fill=(255, 255, 255), outline=(229, 231, 235))
    if title_font:
        draw.text((30, 235), 'トヨタ自動車 (7203)', fill=(51, 51, 51), font=title_font)
    else:
        draw.text((30, 235), 'トヨタ自動車 (7203)', fill=(51, 51, 51))
    draw.text((30, 260), '2024年3月15日', fill=(107, 114, 128))
    
    # 価格表示（緑）
    draw.rectangle([280, 230, 360, 250], fill=(93, 176, 117, 25))  # 薄い緑
    draw.text((290, 235), '+2.5%', fill=(93, 176, 117))
    
    # タグ
    draw.rectangle([30, 275, 80, 295], fill=(93, 161, 229), outline=None)  # 青いタグ
    draw.text((40, 280), '自動車', fill=(255, 255, 255))
    
    draw.rectangle([90, 275, 130, 295], fill=(247, 183, 49), outline=None)  # 黄色いタグ
    draw.text((100, 280), '長期', fill=(255, 255, 255))
    
    # メモテキスト
    draw.text((30, 310), '電気自動車への転換が加速中。', fill=(75, 85, 99))
    draw.text((30, 325), '競合他社との差別化に注目。', fill=(75, 85, 99))
    
    # 日記カード2
    draw.rectangle([20, 370, 370, 510], fill=(255, 255, 255), outline=(229, 231, 235))
    if title_font:
        draw.text((30, 395), 'ソニー (6758)', fill=(51, 51, 51), font=title_font)
    else:
        draw.text((30, 395), 'ソニー (6758)', fill=(51, 51, 51))
    draw.text((30, 420), '2024年3月12日', fill=(107, 114, 128))
    
    # 価格表示（赤）
    draw.rectangle([280, 390, 360, 410], fill=(225, 90, 90, 25))  # 薄い赤
    draw.text((290, 395), '-1.2%', fill=(225, 90, 90))
    
    # タグ
    draw.rectangle([30, 435, 90, 455], fill=(199, 177, 193), outline=None)  # 紫っぽいタグ
    draw.text((40, 440), 'エンタメ', fill=(255, 255, 255))
    
    # メモテキスト
    draw.text((30, 470), 'ゲーム事業が好調継続中。', fill=(75, 85, 99))
    draw.text((30, 485), 'PS5供給改善に期待。', fill=(75, 85, 99))
    
    # フローティングアクションボタン
    draw.ellipse([322, 752, 378, 808], fill=(90, 126, 197), outline=(255, 255, 255), width=3)
    # プラス記号
    draw.line([340, 768, 340, 792], fill=(255, 255, 255), width=4)
    draw.line([328, 780, 352, 780], fill=(255, 255, 255), width=4)
    
    # ホームインジケーター（iPhone風）
    draw.rectangle([134, 810, 256, 814], fill=(0, 0, 0, 77))  # 半透明の黒
    
    filename = os.path.join(output_dir, 'screenshot-mobile.png')
    img.save(filename, 'PNG')
    print(f"✅ 作成: {filename}")

def create_apple_touch_icon(output_dir):
    """Apple Touch Icon生成 (180x180px)"""
    size = 180
    img = Image.new('RGBA', (size, size), color=(90, 126, 197, 255))
    draw = ImageDraw.Draw(img)
    
    # 「株」文字を中央に
    font_size = int(size * 0.5)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc', font_size)
    except:
        font = ImageFont.load_default()
    
    text = "株"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    
    filename = os.path.join(output_dir, 'apple-touch-icon.png')
    img.save(filename, 'PNG')
    print(f"✅ 作成: {filename}")
# stockdiary/management/commands/generate_og_image.py
"""SNS シェア用の OGP 画像（1200×630）を生成する。

X などでカブログの URL が共有されたときに表示されるブランドカード。
「なぜ買ったか」を記録する というメッセージと、関連グラフを想起させる
ノードモチーフを、グロー（光彩）・背景ブロブ・ドットグリッドで
リッチに表現する。左上のバッジにはアプリアイコンを配置する。

日本語フォントは mac（ヒラギノ）/ linux（Noto CJK）の代表パスを順に探索する。
生成物は static/images/og-card.png。Pillow のみで完結し再生成可能。

使い方:
    python manage.py generate_og_image
"""
import math
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# 日本語が描画できるフォントの候補（mac → linux の順）
JP_FONT_CANDIDATES = [
    '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc',
    '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc',
]

W, H = 1200, 630


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Command(BaseCommand):
    help = 'SNSシェア用のOGP画像（static/images/og-card.png）を生成します'

    def _font(self, size):
        for path in JP_FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
        raise OSError(
            '日本語フォントが見つかりません。NotoSansCJK を入れるか '
            'JP_FONT_CANDIDATES にパスを追加してください。'
        )

    def handle(self, *args, **options):
        img = Image.new('RGB', (W, H), '#0a0f1e')

        self._draw_background(img)        # 縦グラデ + 光のブロブ + ドットグリッド
        self._draw_graph(img)             # 右側に関連グラフ（グロー付き）

        d = ImageDraw.Draw(img, 'RGBA')

        # 上端のアクセントライン（シアン→ブルー→バイオレット）
        for x in range(W):
            t = x / W
            col = _lerp((34, 211, 238), (124, 58, 237), t)
            d.line([(x, 0), (x, 5)], fill=col)

        # 左上ブランド: 白バッジ + アプリアイコン
        self._draw_brand(img, d)

        # メインコピー
        h1 = self._font(74)
        d.text((80, 196), '「なぜ買ったか」を', font=h1, fill='#ffffff')
        d.text((80, 292), '記録する投資日記。', font=h1, fill='#36d6f0')

        # アクセントバー（見出し下のグラデーション下線）
        self._draw_gradient_bar(d, 84, 392, 360, 8)

        # サブコピー
        sub = self._font(29)
        d.text((84, 424), '売買ではなく「思考」を残す。', font=sub, fill='#b7c0d0')
        d.text((84, 466), '記録が、自分だけの投資知識ベースになる。', font=sub, fill='#b7c0d0')

        # 下部: 機能チップ（淡い塗り + 枠）
        self._draw_chips(d, ['記録', '想起', '振り返り', '関連グラフ'], 84, 540)

        out_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'og-card.png')
        img.save(out_path, 'PNG')
        self.stdout.write(self.style.SUCCESS(f'✅ OGP画像を生成しました: {out_path}'))
        self.stdout.write('  collectstatic を実行して本番へ反映してください。')

    # ───────────────────────── 背景 ─────────────────────────
    def _draw_background(self, img):
        d = ImageDraw.Draw(img)
        # 斜めの縦グラデーション（上＝やや明るい紺、下＝濃紺）
        top = (20, 32, 58)      # #14203a
        bottom = (8, 12, 26)    # #080c1a
        for y in range(H):
            d.line([(0, y), (W, y)], fill=_lerp(top, bottom, y / H))

        # 光のブロブ（別レイヤーに描いてブラー→合成）で奥行きを出す
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        blobs = [
            (980, 120, 320, (34, 211, 238, 70)),    # 右上・シアン
            (180, 540, 300, (124, 58, 237, 60)),    # 左下・バイオレット
            (640, 300, 280, (59, 130, 246, 38)),    # 中央・ブルー
        ]
        for cx, cy, r, color in blobs:
            gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        glow = glow.filter(ImageFilter.GaussianBlur(90))
        img.paste(Image.alpha_composite(img.convert('RGBA'), glow).convert('RGB'), (0, 0))

        # 微細なドットグリッド（うっすら）
        d = ImageDraw.Draw(img, 'RGBA')
        for gy in range(70, H, 34):
            for gx in range(70, W, 34):
                d.ellipse([gx, gy, gx + 2, gy + 2], fill=(255, 255, 255, 10))

    # ───────────────────────── ブランド ─────────────────────────
    def _draw_brand(self, img, d):
        bx, by, bs = 80, 56, 90  # バッジ位置とサイズ
        # 影
        shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle([bx, by + 6, bx + bs, by + bs + 6], radius=22,
                             fill=(0, 0, 0, 110))
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))
        img.paste(Image.alpha_composite(img.convert('RGBA'), shadow).convert('RGB'), (0, 0))

        d = ImageDraw.Draw(img, 'RGBA')
        # 白バッジ
        d.rounded_rectangle([bx, by, bx + bs, by + bs], radius=22, fill=(255, 255, 255, 255))

        # アプリアイコンを中に配置
        icon_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'icon-512.png')
        if os.path.exists(icon_path):
            icon = Image.open(icon_path).convert('RGBA')
            pad = 12
            isize = bs - pad * 2
            icon = icon.resize((isize, isize), Image.LANCZOS)
            img.paste(icon, (bx + pad, by + pad), icon)
            d = ImageDraw.Draw(img, 'RGBA')

        # ブランド名
        brand = self._font(36)
        d.text((bx + bs + 22, by + 24), 'カブログ', font=brand, fill='#eef2f8')

    # ───────────────────────── パーツ ─────────────────────────
    def _draw_gradient_bar(self, d, x, y, w, h):
        stops = [(34, 211, 238), (59, 130, 246), (124, 58, 237)]
        for i in range(w):
            t = i / w
            if t < 0.5:
                col = _lerp(stops[0], stops[1], t / 0.5)
            else:
                col = _lerp(stops[1], stops[2], (t - 0.5) / 0.5)
            d.line([(x + i, y), (x + i, y + h)], fill=col)

    def _draw_chips(self, d, labels, x, y):
        chip = self._font(24)
        for label in labels:
            tw = d.textlength(label, font=chip)
            pad = 18
            d.rounded_rectangle([x, y, x + tw + pad * 2, y + 44], radius=22,
                                fill=(59, 130, 246, 28), outline=(99, 134, 200, 200), width=2)
            d.text((x + pad, y + 8), label, font=chip, fill='#d3dcec')
            x += tw + pad * 2 + 14

    # ───────────────────────── 関連グラフ ─────────────────────────
    def _draw_graph(self, img):
        cx, cy = 945, 300
        nodes = [(cx, cy, 32, (54, 214, 240))]
        ring = [
            (0, 150), (55, 165), (130, 140), (200, 120),
            (260, 150), (310, 110), (180, 200),
        ]
        for i, (ang, dist) in enumerate(ring):
            rad = math.radians(ang)
            nx = cx + int(dist * math.cos(rad))
            ny = cy + int(dist * math.sin(rad) * 0.62) - 60 + i * 8
            size = 14 + (i % 3) * 5
            color = [(59, 130, 246), (124, 58, 237), (34, 211, 238)][i % 3]
            nodes.append((nx, ny, size, color))

        # グロー（ノードの色の光彩）を別レイヤーで
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for nx, ny, size, color in nodes:
            r = size * 2.4
            gd.ellipse([nx - r, ny - r, nx + r, ny + r], fill=color + (90,))
        glow = glow.filter(ImageFilter.GaussianBlur(16))
        img.paste(Image.alpha_composite(img.convert('RGBA'), glow).convert('RGB'), (0, 0))

        d = ImageDraw.Draw(img, 'RGBA')
        # エッジ
        for n in nodes[1:]:
            d.line([(cx, cy), (n[0], n[1])], fill=(120, 150, 210, 150), width=2)
        for a, b in [(1, 2), (3, 4), (4, 5), (2, 7)]:
            if a < len(nodes) and b < len(nodes):
                d.line([(nodes[a][0], nodes[a][1]), (nodes[b][0], nodes[b][1])],
                       fill=(90, 115, 175, 130), width=2)
        # ノード本体（白の細リング付き）
        for nx, ny, size, color in nodes:
            d.ellipse([nx - size, ny - size, nx + size, ny + size], fill=color + (255,))
            d.ellipse([nx - size, ny - size, nx + size, ny + size],
                      outline=(255, 255, 255, 70), width=2)

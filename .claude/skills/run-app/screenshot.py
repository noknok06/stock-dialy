"""カブログの任意ページをログイン済みで撮影する（モバイル375px / PC1440px）

使い方:
    python3.11 .claude/skills/run-app/screenshot.py <URLパス> <ラベル>
例:
    python3.11 .claude/skills/run-app/screenshot.py /2/ detail
    python3.11 .claude/skills/run-app/screenshot.py /timeline/ timeline

前提: SKILL.md の手順でサーバー(127.0.0.1:8765)起動・/tmp/cdn 準備済み。
出力: /tmp/shots/{mobile,pc}_<ラベル>*.png
"""
import mimetypes
import os
import re
import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765'
CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
OUT = '/tmp/shots'
CDN_DIR = '/tmp/cdn'
USERNAME, PASSWORD = 'uxcheck', 'uxcheck-pass'

path = sys.argv[1] if len(sys.argv) > 1 else '/'
label = sys.argv[2] if len(sys.argv) > 2 else 'page'
os.makedirs(OUT, exist_ok=True)

# cdn.jsdelivr.net/npm/<pkg>@<ver>/<path> → /tmp/cdn/<pkg>/package/<path>
JSDELIVR_RE = re.compile(r'https://cdn\.jsdelivr\.net/npm/([^@]+)@[^/]+/(.+?)(?:\?.*)?$')


def serve_cdn(route):
    m = JSDELIVR_RE.match(route.request.url)
    if m:
        rel = m.group(2)
        # jsdelivr は .min.js を動的生成するが npm tarball には無いことがある
        for candidate in (rel, rel.replace('.min.js', '.js'), rel.replace('.min.css', '.css')):
            local = os.path.join(CDN_DIR, m.group(1), 'package', candidate)
            if os.path.exists(local):
                ctype = mimetypes.guess_type(local)[0] or 'application/octet-stream'
                route.fulfill(status=200, content_type=ctype, body=open(local, 'rb').read())
                return
    route.abort()


def serve_htmx(route):
    body = open(os.path.join(CDN_DIR, 'htmx.org/package/dist/htmx.min.js'), 'rb').read()
    route.fulfill(status=200, content_type='application/javascript',
                  headers={'Access-Control-Allow-Origin': '*'}, body=body)


def shoot(p, width, height, dev_label):
    browser = p.chromium.launch(
        executable_path=CHROME,
        args=['--no-sandbox', '--ignore-certificate-errors'])
    ctx = browser.new_context(viewport={'width': width, 'height': height},
                              device_scale_factor=2)
    ctx.route('https://cdn.jsdelivr.net/**', serve_cdn)
    ctx.route('https://unpkg.com/htmx.org**', serve_htmx)
    ctx.route('https://pagead2.googlesyndication.com/**', lambda r: r.abort())
    page = ctx.new_page()
    errors = []
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)

    page.goto(f'{BASE}/users/login/')
    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')

    page.goto(f'{BASE}{path}')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1200)
    page.screenshot(path=f'{OUT}/{dev_label}_{label}_firstview.png')
    page.screenshot(path=f'{OUT}/{dev_label}_{label}_full.png', full_page=True)

    # 日記詳細ページならタブも撮影
    for tab_id, name in [('transactions-tab', 'transactions'),
                         ('notes-tab', 'notes'), ('events-tab', 'events')]:
        if page.query_selector(f'#{tab_id}'):
            page.click(f'#{tab_id}')
            page.wait_for_timeout(1200)
            page.screenshot(path=f'{OUT}/{dev_label}_{label}_tab_{name}.png',
                            full_page=True)

    print(f'{dev_label}: console errors = {len(errors)}')
    for e in errors[:5]:
        print('  ', e[:160])
    browser.close()


with sync_playwright() as p:
    shoot(p, 375, 812, 'mobile')
    shoot(p, 1440, 900, 'pc')
print('DONE →', OUT)

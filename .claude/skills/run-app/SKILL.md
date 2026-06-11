---
name: run-app
description: カブログ（Django）をサンドボックス内で起動し、シードデータ投入・ログイン済み状態でのスクリーンショット取得（モバイル/PC）まで行う。UI変更の実機確認・画面レビューに使う。
---

# カブログをローカル起動してスクリーンショット確認する

ネットワーク制限付きサンドボックス（Claude Code on the web）で実証済みの手順。
2026-06 に日記詳細ページのレイアウトレビューで使用し、全ステップ動作確認済み。

## 1. 環境構築（初回のみ）

```bash
cd /home/user/stock-dialy
python3.11 -m venv venv
./venv/bin/pip install -q --upgrade pip
# psycopg2 は libpq ヘッダがなくビルド失敗する。SQLite運用なので除外する
grep -v "^psycopg2" requirements.txt > /tmp/reqs_no_pg.txt
./venv/bin/pip install -q -r /tmp/reqs_no_pg.txt
```

## 2. DB初期化とシード

**重要**: 環境変数は Bash 呼び出し間で持続しない。毎回インラインで指定する。
`DJANGO_TESTING=1` がないと settings.py が `EMAIL_HOST_PASSWORD environment
variable is required` で落ちる。

```bash
DJANGO_TESTING=1 DJANGO_SETTINGS_MODULE=config.test_settings \
  ./venv/bin/python manage.py migrate --run-syncdb
DJANGO_TESTING=1 DJANGO_SETTINGS_MODULE=config.test_settings \
  ./venv/bin/python manage.py shell < .claude/skills/run-app/seed_demo.py
# → "SEED_OK diary_id=N other_id=M" が出る。diary_id を控える
```

シードの注意:
- `Transaction` 作成後は必ず `AggregateService.recalculate(diary)`（CLAUDE.md 規約）
- `DiaryNote.note_type` の有効値: analysis / news / earnings / insight / risk /
  retrospective / other（`memo` は無効）
- ログイン情報: ユーザー `uxcheck` / パスワード `uxcheck-pass`

## 3. サーバー起動

```bash
DJANGO_TESTING=1 DJANGO_SETTINGS_MODULE=config.test_settings \
  nohup ./venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload \
  >/tmp/server.log 2>&1 &
timeout 30 bash -c 'until curl -sf -o /dev/null http://127.0.0.1:8765/users/login/; do sleep 1; done' && echo SERVER_UP
```

- **テンプレートを編集したらサーバーを再起動すること**（古いテンプレートが
  使われ続ける現象を確認済み）: `pkill -f "runserver 127.0.0.1:8765"` して再起動
- URLは `config.test_urls` ベース: stockdiary がルート直下（詳細= `/<diary_id>/`）、
  ログイン= `/users/login/`。ads/contact はダミー応答

## 4. CDN資産のローカル化（初回のみ）

cdn.jsdelivr.net / unpkg.com はプロキシ許可リスト外（403）。
**registry.npmjs.org と raw.githubusercontent.com は到達可能**なので、
npm tarball を落として Playwright のルートインターセプトで差し替える。

```bash
mkdir -p /tmp/cdn && cd /tmp/cdn
for p in "bootstrap/-/bootstrap-5.3.0" "bootstrap-icons/-/bootstrap-icons-1.11.1" \
         "chart.js/-/chart.js-4.4.0" "d3/-/d3-7.9.0" "easymde/-/easymde-2.18.0" \
         "fullcalendar/-/fullcalendar-5.10.1" "htmx.org/-/htmx.org-1.9.10"; do
  name=$(echo $p | cut -d/ -f1)
  curl -sk -o "$name.tgz" "https://registry.npmjs.org/$p.tgz"
  mkdir -p "$name" && tar xzf "$name.tgz" -C "$name"
done
```

バージョンは templates/base.html / detail.html の CDN URL に合わせる
（変わっていたら `grep -o 'https://[^"]*\.\(css\|js\)' templates/base.html` で確認）。

## 5. スクリーンショット取得

Playwright はインストール済みでもブラウザDLは CDN ブロックで失敗する。
**プリインストールの `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` を
`executable_path` で直接使う**。プロキシのMITM証明書対策で
`--ignore-certificate-errors` が必須。

```bash
pip install -q playwright   # 未導入なら
python3.11 .claude/skills/run-app/screenshot.py /2/ detail
# → /tmp/shots/{mobile,pc}_detail*.png が生成される
```

`screenshot.py <URLパス> <ラベル>`: ログイン→該当ページをモバイル375px/PC1440pxで
ファーストビュー+全ページ撮影。詳細ページ(`/<id>/`)の場合はタブ切替の撮影も行う。

## 既知の無害なエラー

- `SW registration failed`（/sw.js が test_urls に未登録で404）
- googlesyndication への403（広告、ルートで abort 済み）
- 取引カードが全ページスクショで薄く写る → 0.3s の fadeInUp アニメーション中の
  撮影によるもの。バグではない。wait を 1200ms 程度に増やすと解消

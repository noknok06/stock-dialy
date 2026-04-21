# CLAUDE.md

Claude Code（claude.ai/code）がこのリポジトリで作業する際のガイダンス。

---

## プロジェクト概要

**Stock-Dialy（カブログ）** は Django 製の株式投資日記 Web アプリ。
ユーザーは銘柄ごとに「なぜ投資したか」「取引」「振り返り」を記録する。
FIFO 損益集計・AI分析・EDINET/TDNET（日本の開示 API）連携・Web Push 通知を含む。

プロダクトの背景・機能開発の判断軸 → `docs/product_context.md` を参照。

---

## コマンド

### 開発環境セットアップ
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 認証情報を記入
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### テスト
```bash
# 全テスト
pytest

# 特定ファイル
pytest tests/test_models_updated.py

# 特定テスト
pytest tests/test_models_updated.py::TestClassName::test_method_name

# マーカー指定
pytest -m unit
pytest -m integration
pytest -m django_db
```

設定: `config.test_settings` / `--nomigrations` / `--reuse-db` / カバレッジ対象: `stockdiary`, `analysis_template`, `tags`

### データベース
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py sqlmigrate <app> <migration>
```

### 本番
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000
python manage.py collectstatic
```

本番環境の設定例は `etc/systemd/` と `etc/cron.d/` を参照。

---

## アーキテクチャ

### アプリ構成

| アプリ | 役割 |
|--------|------|
| `stockdiary` | コア: 日記・取引・ノート・損益集計 |
| `earnings_analysis` | 企業財務分析（Gemini AI + EDINET + TDNET）URL prefix: `/copomo/` |
| `analysis_template` | 再利用可能な分析フレームワーク |
| `company_master` | 銘柄・企業マスタ |
| `tags` | 日記へのタグ付け |
| `users` | カスタム `CustomUser`（メール認証・Google OAuth） |
| `subscriptions` | 有料プランによる機能制限（Stripe 連携） |
| `margin_tracking` | 信用取引の独立追跡 URL namespace: `margin_tracking` |
| `security` | レート制限・IP フィルタリングミドルウェア |
| `ads`, `contact`, `maintenance` | 運用系 |
| `utils`, `common` | 共有 Mixin・ヘルパー |

### コアデータフロー

`StockDiary` が中心モデル。ユーザー×銘柄で 1 レコード。
保有数・損益などの集計フィールドを `StockDiary` 自身が保持し、
`Transaction` の作成・更新・削除のたびに `AggregateService` が再計算する。

- **FIFO 損益計算**: `stockdiary/services/aggregate_service.py`
- 現物取引と信用取引は別フィールドで追跡（`cash_only_*`）
- `DiaryNote` が保有中の時系列更新を記録
- `linked_diaries` は非対称 M2M（A→B ≠ B→A）
- `StockDiary` には EDINET から定期更新される `latest_disclosure_date` / `latest_disclosure_doc_type_name` フィールドがある

### ⚠️ AggregateService — 必須呼び出しルール

`Transaction` を作成・更新・削除した後は **必ず** 以下を呼ぶこと。
呼び忘れると `StockDiary` の集計値（保有数・損益等）がずれる。

```python
from stockdiary.services.aggregate_service import AggregateService

AggregateService.recalculate(diary)
# ※ recalculate() 内で diary.save() まで実行される
```

### サービス層

**`stockdiary/services/`**

| サービス | 役割 |
|----------|------|
| `AggregateService` | 全取引から損益・保有数をゼロから再計算 |
| `GeminiStockAnalysis` | Google Gemini AI による銘柄分析 |
| `ImageService` | django-q で非同期 WebP 圧縮（800×600） |
| `NotificationService` | Web Push（VAPID）・アプリ内・メール通知 |

**`earnings_analysis/services/`**

| サービス | 役割 |
|----------|------|
| `EDINETAPIService` | 日本の EDINET 開示書類取得 |
| `TDNETReportGenerator` | TDNET 適時開示レポート生成 |
| `AIExpertAnalyzer` | マルチターン AI 分析エンジン |
| `GeminiService` / `GeminiInsights` | Gemini API 呼び出しラッパー |
| `XBRLExtractor` / `XBRLAnalysisService` | XBRL 形式の財務データ抽出 |
| `SentimentAnalyzer` / `LangExtractSentiment` | NLP 感情分析 |
| `PDFProcessor` | PDF テキスト変換 |
| `FinancialAnalyzer` | 財務指標計算 |
| `ComprehensiveAnalyzer` | 総合分析 |
| `BreakoutDetector` | ブレイクアウト検出 |
| `BatchService` | 一括処理 |
| `DisclosureSync` | EDINET 開示情報の同期 |
| `DocumentService` | 書類管理 |

**`common/services/`**（全アプリ共通）

| サービス | 役割 |
|----------|------|
| `YahooFinanceService` | yfinance を用いた株価・財務データ取得。PER・PBR・ROE・配当利回り・時価総額を計算。静的メソッド方式。 |

### 主要な技術的決定

- **django-q**（ORM ブローカー）: Celery/Redis 不要
- **HTMX**: React/Vue なしの動的 UI
- **StockDiary が計算済みフィールドを保持**: オンザフライ計算ではなく取引変更時に再計算
- **カスタムミドルウェア 15 層**: サブスクリプション制限・IP フィルタ・レート制限・CSP
- 管理画面は `/admin_xyz/`（難読化済み）
- **PWA 対応**: Service Worker（`/sw.js`）・オフラインページ（`/offline/`）

### 外部連携

| サービス | 用途 | 環境変数 |
|----------|------|----------|
| Google Gemini API | AI 銘柄・財務分析 | `GEMINI_API_KEY` |
| EDINET API | 日本の開示書類取得 | `EDINET_API_KEY` |
| TDNET | 適時開示情報 | — |
| yfinance | 株価履歴・財務データ | — |
| Google OAuth | 認証（allauth 経由） | `GOOGLE_CLIENT_ID` |
| Stripe | 決済・サブスクリプション | `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Web Push（VAPID） | プッシュ通知 | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_ADMIN_EMAIL` |
| Gmail SMTP | メール送信 | `EMAIL_HOST_PASSWORD` |

---

## 実際のコードパターン

### ディレクトリ構成の実態

アプリによって構成が異なる。**新規ファイルを追加する前に当該アプリの既存パターンを確認すること。**

```
stockdiary/               ← 単一ファイル方式
  views.py                # メインビュー（約 3,600 行）
  views_comparison.py     # 銘柄比較・InvestmentHub
  views_mobile_ux.py      # クイック記録（モバイル向け）
  api.py                  # 株式情報 API（yfinance）
  api_views.py            # 通知・関連日記・グラフ API
  models.py               # 全モデル（単一ファイル）
  forms.py                # 全フォーム（単一ファイル）
  utils.py                # ヘルパー関数
  admin.py                # Django 管理画面カスタマイズ
  services/               # サービス層（ファイル分割済み）
  templates/stockdiary/
    *.html                # ページテンプレート（home, detail, diary_form, stock_list, etc.）
    partials/             # HTMX 応答用部分テンプレート
    components/           # 再利用 UI コンポーネント
      _*.html             # アトミックコンポーネント（_ プレフィックス）

earnings_analysis/        ← サブディレクトリ方式（URL namespace: copomo）
  views/                  # ビュー分割
    ui.py                 # メイン UI
    download.py           # ダウンロード
    financial.py          # 財務 API
    financial_ui.py       # 財務 UI
    search.py             # 検索
    sentiment.py          # 感情分析 API
    sentiment_ui.py       # 感情分析 UI
    tdnet_admin.py        # TDNET 管理
    tdnet_ui.py           # TDNET UI
  models/                 # モデル分割
    batch.py, company.py, document.py,
    financial.py, sentiment.py, tdnet.py
  services/               # サービス分割（上記サービス層を参照）

common/
  services/
    yahoo_finance_service.py  # 全アプリ共通の yfinance ラッパー
```

### View パターン

```python
# CBV — Mixin 順: 機能Mixin → LoginRequiredMixin → 基底View
class StockDiaryDetailView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DetailView):
    model = StockDiary
    redirect_url = 'stockdiary:home'

# CBV — サブスクリプション制限が必要な場合
class TagCreateView(SubscriptionLimitCheckMixin, LoginRequiredMixin, CreateView):
    ...

# FBV — シンプルな API / HTMX 向け
@login_required
@require_POST
def add_transaction(request, diary_id):
    ...
```

**利用可能な Mixin:**

| Mixin | インポート元 | 用途 |
|-------|-------------|------|
| `LoginRequiredMixin` | `django.contrib.auth.mixins` | ログイン必須 |
| `ObjectNotFoundRedirectMixin` | `utils.mixins` | 404 時にリダイレクト |
| `SubscriptionLimitCheckMixin` | `subscriptions.mixins` | サブスク制限（現在全バイパス中） |

### HTMX パターン

```python
# View でのリクエスト判定
is_htmx = (
    request.headers.get('HX-Request') == 'true'
    or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
)

if is_htmx:
    return render(request, 'stockdiary/partials/diary_list.html', context)
return render(request, 'stockdiary/home.html', context)
```

```django
{# テンプレート内での対象要素判定 #}
{% if request.htmx.target == "diary-container" %}
  ...
{% endif %}

{# 複数箇所の同時更新 #}
<div hx-swap-oob="true" id="search-result-info">...</div>
```

### URL パターン

```python
app_name = 'stockdiary'  # 各アプリで namespace 設定

urlpatterns = [
    # API エンドポイントは api/ プレフィックス（JSON 返却）
    path('api/stock/info/<str:stock_code>/', api.get_stock_info, name='api_stock_info'),

    # リソース操作は <pk>/ または <diary_id>/
    path('<int:pk>/update/', views.StockDiaryUpdateView.as_view(), name='update'),
    path('<int:diary_id>/transaction/add/', views.add_transaction, name='add_transaction'),
]
```

JSON を返す View → `api.py` / `api_views.py` に集約する。

**ルート URL 構成（`config/urls.py`）:**

| パス | アプリ | namespace |
|------|--------|-----------|
| `/stockdiary/` | `stockdiary` | `stockdiary` |
| `/copomo/` | `earnings_analysis` | `copomo` |
| `/tags/` | `tags` | — |
| `/analysis_template/` | `analysis_template` | — |
| `/company_master/` | `company_master` | — |
| `/subscriptions/` | `subscriptions` | — |
| `/margin/` | `margin_tracking` | `margin_tracking` |
| `/users/` | `users` | — |
| `/accounts/` | allauth | — |
| `/admin_xyz/` | Django admin | — |
| `/api/notifications/…` | `stockdiary.api_views` | — |
| `/api/push/…` | `stockdiary.api_views` | — |

### テンプレート命名規則

| 配置 | 用途 |
|------|------|
| `app/templates/app/*.html` | ページテンプレート（フルページ） |
| `app/templates/app/partials/*.html` | HTMX 応答用の部分テンプレート |
| `app/templates/app/components/*.html` | 再利用 UI コンポーネント |
| `app/templates/app/components/_*.html` | アトミックコンポーネント（`_` プレフィックス） |
| `templates/base.html` | サイト全体のマスターレイアウト |
| `templates/landing_page.html` | 公開ランディングページ |

**stockdiary の主要テンプレート:**

| ファイル | 用途 |
|----------|------|
| `home.html` | ダッシュボード |
| `detail.html` | 日記詳細（タブ: 取引・ノート・分析・詳細） |
| `diary_form.html` | 作成・編集 |
| `stock_list.html` | 銘柄一覧 |
| `diary_graph.html` | パフォーマンスチャート |
| `comparison.html` | 銘柄比較 |
| `investment_hub.html` | InvestmentHub ページ |
| `trading_dashboard.html` | トレーディングダッシュボード |
| `trade_upload.html` | 取引 CSV インポート |
| `notification_list.html` | 通知一覧 |
| `explore.html` | 銘柄探索 |

### Settings 構成

| ファイル | 用途 |
|----------|------|
| `config/settings.py` | 本番設定（`DEBUG` フラグで環境分岐） |
| `config/settings_local.py` | ローカル上書き用 |
| `config/test_settings.py` | テスト用（SQLite・subscription middleware 除外） |

---

## テスト基盤

テストは `/tests/` 配下。`pytest-django` + `config.test_settings` を使用。
マイグレーション不要（`--nomigrations`）、DB 再利用（`--reuse-db`）。

**共通フィクスチャ（`tests/conftest.py`）:**

| フィクスチャ | 内容 |
|-------------|------|
| `user` | テスト用ユーザー（testuser） |
| `another_user` | 別のテスト用ユーザー |
| `client` | Django テストクライアント |
| `authenticated_client` | ログイン済みクライアント |
| `sample_diary` | トヨタ自動車の基本日記 |
| `sample_diary_with_transaction` | 買い取引付き日記 |
| `sample_sold_diary` | 買い→売り完結済み日記 |
| `sample_memo_diary` | 取引なし・メモのみ日記 |
| `complex_diary_with_multiple_transactions` | 5 件の複数取引日記 |
| `diary_with_notes` | 継続記録（DiaryNote）付き日記 |
| `diary_with_stock_split` | 株式分割（StockSplit）含む日記 |
| `sample_tags` | 3 件のタグ（長期投資・配当狙い・成長株） |

カバレッジ対象: `stockdiary` / `analysis_template` / `tags`

---

## CI/CD

`.github/workflows/django-tests.yml` で push / PR 時に `pytest` が自動実行される。

---

## 開発規約

### 基本方針
- **既存ファイルを優先して編集する** — 新規ファイルは原則作らない
- 既存ファイルを使わなくなる場合は、**古いファイルの削除を明示的に指示する**
- 変更の意図を明確にする（機能拡張・改善・バグ修正など）

### 新規ファイルを作る場合
- 既存アプリの構成パターンに従う（`views.py` 方式か `views/` 方式かを確認）
- `views.py` が肥大化する場合は `views_<機能名>.py` に分割（既存パターンに倣う）
- ファイル名は責務が明確になるよう命名する（例: `request_create.py`）
- 再利用可能なロジックは `services/` や `utils/` に切り出す

### 禁止事項
- ❌ 同じ用途のファイルを複数作成して並行利用する（保守性低下）
- ❌ 理由なく既存の構造を変更する

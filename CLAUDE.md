# CLAUDE.md

Claude Code（claude.ai/code）がこのリポジトリで作業する際のガイダンス。

---

## プロジェクト概要

**Stock-Dialy（カブログ）** は Django 製の株式投資日記 Web アプリ。
ユーザーは銘柄ごとに「なぜ投資したか」「取引」「振り返り」を記録する。
FIFO 損益集計・AI分析・EDINET（日本の開示 API）連携を含む。

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

---

## アーキテクチャ

### アプリ構成

| アプリ | 役割 |
|--------|------|
| `stockdiary` | コア: 日記・取引・ノート・損益集計 |
| `earnings_analysis` | 企業財務分析（Gemini AI + EDINET） |
| `analysis_template` | 再利用可能な分析フレームワーク |
| `company_master` | 銘柄・企業マスタ |
| `tags` | 日記へのタグ付け |
| `users` | カスタム `CustomUser`（メール認証・Google OAuth） |
| `subscriptions` | 有料プランによる機能制限 |
| `margin_tracking` | 信用取引の独立追跡 |
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

### ⚠️ AggregateService — 必須呼び出しルール

`Transaction` を作成・更新・削除した後は **必ず** 以下を呼ぶこと。
呼び忘れると `StockDiary` の集計値（保有数・損益等）がずれる。

```python
from stockdiary.services.aggregate_service import AggregateService

AggregateService.recalculate(diary)
# ※ recalculate() 内で diary.save() まで実行される
```

### サービス層（`stockdiary/services/`）

| サービス | 役割 |
|----------|------|
| `AggregateService` | 全取引から損益・保有数をゼロから再計算 |
| `GeminiStockAnalysis` | Google Gemini AI による銘柄分析 |
| `ImageService` | django-q で非同期 WebP 圧縮（800×600） |
| `NotificationService` | Web Push（VAPID）・アプリ内・メール通知 |

### 主要な技術的決定

- **django-q**（ORM ブローカー）: Celery/Redis 不要
- **HTMX**: React/Vue なしの動的 UI
- **StockDiary が計算済みフィールドを保持**: オンザフライ計算ではなく取引変更時に再計算
- **カスタムミドルウェア 15 層**: サブスクリプション制限・IP フィルタ・レート制限・CSP
- 管理画面は `/admin_xyz/`（難読化済み）

### 外部連携

| サービス | 用途 | 環境変数 |
|----------|------|----------|
| Google Gemini API | AI 銘柄分析 | `GEMINI_API_KEY` |
| EDINET API | 日本の開示書類 | `EDINET_API_KEY` |
| yfinance | 株価履歴 | — |
| Google OAuth | 認証 | `GOOGLE_CLIENT_ID` |
| Stripe | 決済 | `STRIPE_*` |
| Web Push（VAPID） | プッシュ通知 | — |

---

## 実際のコードパターン

### ディレクトリ構成の実態

アプリによって構成が異なる。**新規ファイルを追加する前に当該アプリの既存パターンを確認すること。**

```
stockdiary/               ← 単一ファイル方式
  views.py                # メインビュー（3,600行超）
  views_comparison.py     # 銘柄比較・InvestmentHub
  views_mobile_ux.py      # クイック記録（モバイル向け）
  api.py                  # 株式情報 API（yfinance）
  api_views.py            # 通知・関連日記・グラフ API
  models.py               # 全モデル（単一ファイル）
  forms.py                # 全フォーム（単一ファイル）
  services/               # サービス層（ファイル分割済み）
  templates/stockdiary/
    *.html                # ページテンプレート
    partials/             # HTMX 応答用部分テンプレート
    components/           # 再利用 UI コンポーネント
      _*.html             # アトミックコンポーネント（_ プレフィックス）

earnings_analysis/        ← サブディレクトリ方式
  views/                  # ビュー分割（download.py, financial.py, ...）
  models/                 # モデル分割
  services/               # サービス分割
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

### テンプレート命名規則

| 配置 | 用途 |
|------|------|
| `app/templates/app/*.html` | ページテンプレート（フルページ） |
| `app/templates/app/partials/*.html` | HTMX 応答用の部分テンプレート |
| `app/templates/app/components/*.html` | 再利用 UI コンポーネント |
| `app/templates/app/components/_*.html` | アトミックコンポーネント（`_` プレフィックス） |

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

```python
@pytest.fixture
def user(db):         # テスト用ユーザー（testuser）
def another_user(db): # 別ユーザー
def client():         # Django テストクライアント
```

カバレッジ対象: `stockdiary` / `analysis_template` / `tags`

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

# テスト設計

## ファイル構成の確認

your_project/
├── pytest.ini                          # Pytest設定ファイル
├── requirements-dev.txt                # 開発用パッケージ
│
└── tests/
    ├── __init__.py                     # 空ファイル
    ├── conftest.py                     # 共通フィクスチャ
    ├── test_models_updated.py          # モデルテスト（12個）
    ├── test_views_updated.py           # ビューテスト
    └── test_integration.py             # 統合テスト

## 基本的なテスト実行方法

1. 全テスト実行

```
# プロジェクトルートで実行
pytest

# 詳細表示
pytest -v

# 最も詳細な出力
pytest -vv
```

2. 特定のファイルのみ実行

```
# モデルテストのみ
pytest tests/test_models_updated.py

# ビューテストのみ
pytest tests/test_views_updated.py

# 統合テストのみ
pytest tests/test_integration.py
```

HTMLレポート生成

```
# HTMLレポート作成
pytest --cov=stockdiary --cov=analysis_template --cov=tags --cov-report=html

# レポートを開く
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```


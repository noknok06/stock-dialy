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

`
# プロジェクトルートで実行
pytest

# 詳細表示
pytest -v

# 最も詳細な出力
pytest -vv
`


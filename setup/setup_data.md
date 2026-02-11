# サブスクリプションプラン
python manage.py initialize_plans

# 広告配置・ユニット
python manage.py initialize_ad_units

# 分析指標定義
<!-- python manage.py create_default_metrics
python manage.py load_metric_definitions -->

# 業種別ベンチマーク
<!-- python manage.py load_industry_benchmarks -->

# タグ作成
python manage.py create_tags --username naoki

# 株式日記テストデータ（リアルなサンプル）
python manage.py create_realistic_test_data --username h

# テスト環境一括セットアップ（プラン・ユーザー・広告）
python manage.py setup_test_environment --all


# API接続テスト
python manage.py test_edinet_api --api-version v2

# 初期データ収集（過去1年分）
python manage.py collect_initial_data --days 365 --api-version v2

# 企業マスタ更新
python manage.py update_company_master
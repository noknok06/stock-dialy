# 環境変数セットアップガイド

このドキュメントでは、Stock-Dialyアプリケーションの環境変数設定方法を説明します。

## セキュリティアップデート

セキュリティ向上のため、以下の変更を実施しました：

- ハードコードされた認証情報を環境変数に移行
- CSRF保護の強化
- ミドルウェアでの外部API呼び出しにキャッシング追加
- 包括的なロギングシステムの実装

## 環境変数の設定

### 1. `.env`ファイルの作成

プロジェクトのルートディレクトリに`.env`ファイルを作成します：

```bash
cp .env.example .env
```

### 2. 必須環境変数の設定

`.env`ファイルを編集し、以下の環境変数を設定してください：

#### Django Core Settings

```env
# Djangoのシークレットキー（必須）
# 生成方法: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY=your-secret-key-here
```

#### Database Configuration

```env
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432
```

#### Email Configuration

```env
# Gmail SMTP用のアプリパスワード（必須）
# 取得方法: https://support.google.com/accounts/answer/185833
EMAIL_HOST_PASSWORD=your_gmail_app_password_here
```

#### External API Keys

```env
# Google Gemini AI APIキー（必須）
# 取得方法: https://makersuite.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# EDINET APIキー（必須）
# 取得方法: https://disclosure2.edinet-fsa.go.jp/
EDINET_API_KEY=your_edinet_api_key_here
```

#### Stripe Payment (オプション)

```env
# Stripeを使用する場合のみ設定
# STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
# STRIPE_SECRET_KEY=sk_test_your_secret_key_here
# STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

### 3. 環境変数の確認

アプリケーションを起動して、環境変数が正しく読み込まれることを確認します：

```bash
python manage.py check
```

必須の環境変数が設定されていない場合、エラーメッセージが表示されます。

## アプリケーションの起動

### 開発環境

```bash
# 環境変数を読み込んでサーバーを起動
python manage.py runserver
```

### 本番環境

本番環境では、以下のいずれかの方法で環境変数を設定してください：

1. **システム環境変数として設定**
   ```bash
   export SECRET_KEY="your-secret-key"
   export EMAIL_HOST_PASSWORD="your-password"
   # その他の環境変数...
   ```

2. **`.env`ファイルを使用** （推奨）
   - `.env`ファイルをプロジェクトルートに配置
   - `python-dotenv`が自動的に読み込みます

3. **環境変数管理サービスを使用**
   - AWS Secrets Manager
   - Azure Key Vault
   - Docker Secrets
   など

## トラブルシューティング

### エラー: "EMAIL_HOST_PASSWORD environment variable is required"

`.env`ファイルに`EMAIL_HOST_PASSWORD`が設定されているか確認してください。

```bash
# .envファイルの確認
cat .env | grep EMAIL_HOST_PASSWORD
```

### エラー: アプリケーションが起動しない

1. `.env`ファイルがプロジェクトルートに存在することを確認
2. 必須の環境変数がすべて設定されていることを確認
3. `python-dotenv`がインストールされていることを確認:
   ```bash
   pip install python-dotenv
   ```

### Gmail アプリパスワードの取得方法

1. Googleアカウントにログイン
2. セキュリティ設定へ移動
3. 「2段階認証プロセス」を有効化
4. 「アプリパスワード」を生成
5. 生成されたパスワードを`EMAIL_HOST_PASSWORD`に設定

## ロギング

このアップデートで、包括的なロギングシステムが実装されました：

- **ログファイルの場所**: `logs/app.log`, `logs/error.log`
- **ログレベル**: INFO（通常の操作）、ERROR（エラー）、WARNING（警告）、DEBUG（デバッグ）
- **ログローテーション**: 10MBごとに自動ローテーション、最大5ファイル保持

ログファイルは`.gitignore`に追加されており、バージョン管理には含まれません。

## セキュリティのベストプラクティス

1. **`.env`ファイルをバージョン管理に含めない**
   - `.gitignore`に`.env`が含まれていることを確認

2. **定期的にシークレットキーを更新**
   - 本番環境のシークレットキーは定期的に変更

3. **アプリパスワードの管理**
   - Gmail アプリパスワードは定期的に再生成

4. **環境変数の暗号化**
   - 本番環境では環境変数管理サービスの使用を推奨

## サポート

問題が発生した場合は、以下にお問い合わせください：
- Email: kabulog.information@gmail.com

---

最終更新: 2025年

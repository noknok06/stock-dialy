# stockdiary/management/commands/test_notification.py
from django.core.management.base import BaseCommand
from stockdiary.models import DiaryNotification, StockDiary
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'テスト通知を作成します'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='ユーザー名')
        parser.add_argument('--diary-id', type=int, help='日記ID')

    def handle(self, *args, **options):
        username = options['username']
        diary_id = options.get('diary_id')
        
        try:
            user = User.objects.get(username=username)
            
            if diary_id:
                diary = StockDiary.objects.get(id=diary_id, user=user)
            else:
                diary = StockDiary.objects.filter(user=user).first()
                if not diary:
                    self.stdout.write(
                        self.style.ERROR('日記が見つかりません')
                    )
                    return
            
            # テスト通知を作成
            notification = DiaryNotification.objects.create(
                diary=diary,
                notification_type='reminder',
                message='これはテスト通知です',
                is_active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ テスト通知を作成しました\n'
                    f'通知ID: {notification.id}\n'
                    f'日記: {diary.stock_name}\n'
                    f'ユーザー: {user.username}'
                )
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'ユーザー "{username}" が見つかりません')
            )
        except StockDiary.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'日記ID {diary_id} が見つかりません')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'エラーが発生しました: {str(e)}')
            )


## 5. トラブルシューティング手順

### ステップ1: ブラウザのコンソールを確認

# 1. ブラウザのDevToolsを開く（F12）
# 2. Consoleタブを開く
# 3. 通知を設定する
# 4. コンソールに表示されるログを確認

# **期待される出力:**
# ```
# === Saving Notification ===
# Type: reminder
# Message: テストメッセージ
# Remind at: 2025-10-26T10:00
# Sending data: { ... }
# CSRF Token: Found
# Response status: 200
# Response data: { success: true, ... }
# ✅ CSRFトークンが見つかりました
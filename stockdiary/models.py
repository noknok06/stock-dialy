# stockdiary/models.py
from django.db import models
from django.contrib.auth import get_user_model
from tags.models import Tag
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import reverse
import os
import uuid
from PIL import Image
import io


def get_diary_image_path(instance, filename):
    """日記画像のアップロードパスを生成"""
    # ファイル拡張子を取得
    ext = filename.split('.')[-1].lower()
    # UUIDでファイル名を生成
    filename = f"{uuid.uuid4().hex}.{ext}"
    # ユーザーIDごとにディレクトリを分ける
    return f"diary_images/{instance.user.id}/{filename}"


def get_note_image_path(instance, filename):
    """継続記録画像のアップロードパスを生成"""
    # ファイル拡張子を取得
    ext = filename.split('.')[-1].lower()
    # UUIDでファイル名を生成
    filename = f"{uuid.uuid4().hex}.{ext}"
    # ユーザーIDごとにディレクトリを分ける
    return f"note_images/{instance.diary.user.id}/{filename}"


class StockDiary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=50, blank=True, db_index=True)
    stock_name = models.CharField(max_length=100)
    purchase_date = models.DateField(db_index=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_quantity = models.IntegerField(null=True, blank=True)
    reason = models.TextField(verbose_name='購入理由', blank=True, max_length=1000)
    checklist = models.ManyToManyField('checklist.Checklist', blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    sell_date = models.DateField(null=True, blank=True, db_index=True)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    memo = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_memo = models.BooleanField(default=False, verbose_name='メモ記録', db_index=True) 
    sector = models.CharField(max_length=50, blank=True, verbose_name='業種')

    # 画像関連フィールド（内部ストレージ）
    image = models.ImageField(
        upload_to=get_diary_image_path,
        null=True, 
        blank=True,
        help_text="日記に関連する画像"
    )

    class Meta:
        indexes = [
            models.Index(fields=['user', 'purchase_date']),
            models.Index(fields=['user', 'stock_symbol']),
            models.Index(fields=['user', 'sell_date']),
            models.Index(fields=['user', 'is_memo']),
        ]
    
    def clean(self):
        """モデルレベルでのバリデーション"""
        super().clean()
        
        # stock_nameの文字数チェック
        if self.stock_name and len(self.stock_name) > 100:
            raise ValidationError({
                'stock_name': '銘柄名は100文字以内で入力してください。'
            })
        
        # reasonの文字数チェック
        if self.reason and len(self.reason) > 1000:
            raise ValidationError({
                'reason': '購入理由は1000文字以内で入力してください。'
            })
        
        # memoの文字数チェック
        if self.memo and len(self.memo) > 1000:
            raise ValidationError({
                'memo': 'メモは1000文字以内で入力してください。'
            })
        
    def save(self, *args, **kwargs):
        # 売却情報が設定されている場合は購入情報もチェック
        if self.sell_date is not None and not self.can_be_sold():
            raise ValueError("購入価格と株数が設定されていない株式は売却できません")
        
        # 価格や数量が入力されているかを確認してメモフラグを設定
        if self.purchase_price is None or self.purchase_quantity is None:
            self.is_memo = True
        else:
            self.is_memo = False
        
        # バリデーションを実行
        self.full_clean()
        
        super().save(*args, **kwargs)

    def process_and_save_image(self, image_file):
        """画像を圧縮・処理して保存"""
        try:
            # 既存の画像があれば削除
            if self.image:
                self.delete_image()
            
            # 画像を開く
            img = Image.open(image_file)
            
            # RGBA画像の場合はRGBに変換
            if img.mode in ('RGBA', 'LA', 'P'):
                # 白背景でRGBに変換
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # リサイズ処理（アスペクト比を保持）
            max_width, max_height = 800, 600
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 圧縮して保存
            output = io.BytesIO()
            
            # 元のフォーマットを確認
            original_format = img.format or 'JPEG'
            
            # WebPをサポートしている場合は優先的に使用
            try:
                img.save(output, format='WebP', quality=85, optimize=True)
                format_used = 'webp'
            except Exception:
                # WebPが使用できない場合はJPEGにフォールバック
                img.save(output, format='JPEG', quality=85, optimize=True)
                format_used = 'jpg'
            
            # ファイル名を生成
            file_extension = format_used
            filename = f"{uuid.uuid4().hex}.{file_extension}"
            
            # ContentFileとして保存
            content_file = ContentFile(output.getvalue())
            
            # ImageFieldに保存
            self.image.save(filename, content_file, save=False)
            self.save(update_fields=['image'])
            
            return True
            
        except Exception as e:
            print(f"Image processing failed: {str(e)}")
            return False

    def delete_image(self):
        """画像を削除"""
        try:
            if self.image:
                # ファイルを削除
                self.image.delete(save=False)
                # フィールドをクリア
                self.image = None
                self.save(update_fields=['image'])
                return True
        except Exception as e:
            print(f"Image deletion failed: {str(e)}")
        return False
        
    def __str__(self):
        return f"{self.stock_name} ({self.stock_symbol})"

    def add_checklist(self, checklist):
        """チェックリストを日記に追加し、関連するアイテムの状態を初期化する"""
        from checklist.models import DiaryChecklistItem
        
        # チェックリストを追加
        self.checklist.add(checklist)
        
        # 関連するアイテムごとにDiaryChecklistItemを作成
        for item in checklist.items.all():
            DiaryChecklistItem.objects.get_or_create(
                diary=self,
                checklist_item=item,
                defaults={'status': False}
            )

    def get_checklist_item_status(self, checklist_item):
        """特定のチェックリストアイテムの状態を取得"""
        from checklist.models import DiaryChecklistItem
        
        try:
            item_status = DiaryChecklistItem.objects.get(
                diary=self,
                checklist_item=checklist_item
            )
            return item_status.status
        except DiaryChecklistItem.DoesNotExist:
            return False            

    def can_be_sold(self):
        """この株式が売却可能かどうかを確認"""
        return self.purchase_price is not None and self.purchase_quantity is not None and not self.is_memo

    def get_image_url(self):
        """画像URLを取得（ユーザー認証付き）"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.id,
                'image_type': 'diary'
            })
        return None

    def get_thumbnail_url(self, width=300, height=200):
        """サムネイル用の画像URLを取得"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.id,
                'image_type': 'diary'
            }) + f'?thumbnail=1&w={width}&h={height}'
        return None

    @property
    def image_url(self):
        """互換性のためのプロパティ"""
        return self.get_image_url()


class DiaryNote(models.Model):
    """日記エントリーへの継続的な追記"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = models.TextField(verbose_name='記録内容', blank=True, max_length=1000)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                       verbose_name='記録時点の価格')
    
    # 画像関連フィールド（内部ストレージ）
    image = models.ImageField(
        upload_to=get_note_image_path,
        null=True, 
        blank=True,
        help_text="継続記録に関連する画像"
    )
    
    # メモタイプ
    TYPE_CHOICES = [
        ('analysis', '分析更新'),
        ('news', 'ニュース'),
        ('earnings', '決算情報'),
        ('insight', '新たな気づき'),
        ('risk', 'リスク要因'),
        ('other', 'その他')
    ]
    note_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='analysis')
    
    # メモの重要度
    IMPORTANCE_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低')
    ]
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default='medium')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
    
    def clean(self):
        """モデルレベルでのバリデーション"""
        super().clean()
        
        # contentの文字数チェック
        if self.content and len(self.content) > 1000:
            raise ValidationError({
                'content': '記録内容は1000文字以内で入力してください。'
            })
    
    def save(self, *args, **kwargs):
        # バリデーションを実行
        self.full_clean()
        
        # ノートを保存
        super().save(*args, **kwargs)
        
        # 親日記のupdated_atを現在時刻に更新
        from django.utils import timezone
        self.diary.updated_at = timezone.now()
        self.diary.save(update_fields=['updated_at'])

    def process_and_save_image(self, image_file):
        """画像を圧縮・処理して保存"""
        try:
            # 既存の画像があれば削除
            if self.image:
                self.delete_image()
            
            # 画像を開く
            img = Image.open(image_file)
            
            # RGBA画像の場合はRGBに変換
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # 継続記録用はサイズを小さめに設定
            max_width, max_height = 600, 400
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 圧縮して保存
            output = io.BytesIO()
            
            # WebPをサポートしている場合は優先的に使用
            try:
                img.save(output, format='WebP', quality=80, optimize=True)
                format_used = 'webp'
            except Exception:
                img.save(output, format='JPEG', quality=80, optimize=True)
                format_used = 'jpg'
            
            # ファイル名を生成
            file_extension = format_used
            filename = f"{uuid.uuid4().hex}.{file_extension}"
            
            # ContentFileとして保存
            content_file = ContentFile(output.getvalue())
            
            # ImageFieldに保存
            self.image.save(filename, content_file, save=False)
            self.save(update_fields=['image'])
            
            return True
            
        except Exception as e:
            print(f"Note image processing failed: {str(e)}")
            return False

    def delete_image(self):
        """画像を削除"""
        try:
            if self.image:
                self.image.delete(save=False)
                self.image = None
                self.save(update_fields=['image'])
                return True
        except Exception as e:
            print(f"Note image deletion failed: {str(e)}")
        return False
    
    def __str__(self):
        return f"{self.diary.stock_name} - {self.date}"
    
    def get_price_change(self):
        """購入価格からの変動率を計算"""
        if self.current_price and self.diary.purchase_price:
            change = ((self.current_price - self.diary.purchase_price) / self.diary.purchase_price) * 100
            return change
        return None

    def get_image_url(self):
        """画像URLを取得（ユーザー認証付き）"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.diary.id,
                'image_type': 'note',
                'note_id': self.id
            })
        return None

    def get_thumbnail_url(self, width=200, height=150):
        """サムネイル用の画像URLを取得"""
        if self.image:
            return reverse('stockdiary:serve_image', kwargs={
                'diary_id': self.diary.id,
                'image_type': 'note',
                'note_id': self.id
            }) + f'?thumbnail=1&w={width}&h={height}'
        return None

    @property
    def image_url(self):
        """互換性のためのプロパティ"""
        return self.get_image_url()
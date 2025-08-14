# stockdiary/models.py
from django.db import models
from django.contrib.auth import get_user_model
from tags.models import Tag
from django.conf import settings
from django.core.exceptions import ValidationError
import cloudinary
import cloudinary.uploader


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

    # 画像関連フィールド（CloudinaryのURLを保存）
    image_url = models.URLField(
        max_length=500,
        null=True, 
        blank=True,
        help_text="日記に関連する画像のURL"
    )
    image_public_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Cloudinary上の画像のpublic_id"
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

    def upload_image(self, image_file):
        """画像をCloudinaryにアップロード"""
        try:
            # 既存の画像があれば削除
            if self.image_public_id:
                cloudinary.uploader.destroy(self.image_public_id)
            
            # 新しい画像をアップロード
            result = cloudinary.uploader.upload(
                image_file,
                folder="stockdiary/diary_images",
                public_id_prefix=f"diary_{self.id}_",
                overwrite=True,
                resource_type="image"
            )
            
            self.image_url = result.get('secure_url')
            self.image_public_id = result.get('public_id')
            self.save(update_fields=['image_url', 'image_public_id'])
            
            return True
            
        except Exception as e:
            print(f"Image upload failed: {str(e)}")
            return False

    def delete_image(self):
        """画像をCloudinaryから削除"""
        try:
            if self.image_public_id:
                cloudinary.uploader.destroy(self.image_public_id)
                self.image_url = None
                self.image_public_id = None
                self.save(update_fields=['image_url', 'image_public_id'])
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
        """画像URLを取得（存在しない場合はNone）"""
        return self.image_url

    @property
    def image(self):
        """CloudinaryFieldの互換性のため"""
        class ImageProxy:
            def __init__(self, url):
                self.url = url
            
            @property
            def url(self):
                return self._url
            
            @url.setter
            def url(self, value):
                self._url = value
        
        if self.image_url:
            return ImageProxy(self.image_url)
        return None


class DiaryNote(models.Model):
    """日記エントリーへの継続的な追記"""
    diary = models.ForeignKey(StockDiary, on_delete=models.CASCADE, related_name='notes')
    date = models.DateField()
    content = models.TextField(verbose_name='記録内容', blank=True, max_length=1000)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                       verbose_name='記録時点の価格')
    
    # 画像関連フィールド（CloudinaryのURLを保存）
    image_url = models.URLField(
        max_length=500,
        null=True, 
        blank=True,
        help_text="継続記録に関連する画像のURL"
    )
    image_public_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Cloudinary上の画像のpublic_id"
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
        super().save(*args, **kwargs)

    def upload_image(self, image_file):
        """画像をCloudinaryにアップロード"""
        try:
            # 既存の画像があれば削除
            if self.image_public_id:
                cloudinary.uploader.destroy(self.image_public_id)
            
            # 新しい画像をアップロード
            result = cloudinary.uploader.upload(
                image_file,
                folder="stockdiary/note_images",
                public_id_prefix=f"note_{self.id}_",
                overwrite=True,
                resource_type="image"
            )
            
            self.image_url = result.get('secure_url')
            self.image_public_id = result.get('public_id')
            self.save(update_fields=['image_url', 'image_public_id'])
            
            return True
            
        except Exception as e:
            print(f"Image upload failed: {str(e)}")
            return False

    def delete_image(self):
        """画像をCloudinaryから削除"""
        try:
            if self.image_public_id:
                cloudinary.uploader.destroy(self.image_public_id)
                self.image_url = None
                self.image_public_id = None
                self.save(update_fields=['image_url', 'image_public_id'])
                return True
        except Exception as e:
            print(f"Image deletion failed: {str(e)}")
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
        """画像URLを取得（存在しない場合はNone）"""
        return self.image_url

    @property
    def image(self):
        """CloudinaryFieldの互換性のため"""
        class ImageProxy:
            def __init__(self, url):
                self.url = url
            
            @property
            def url(self):
                return self._url
            
            @url.setter
            def url(self, value):
                self._url = value
        
        if self.image_url:
            return ImageProxy(self.image_url)
        return None
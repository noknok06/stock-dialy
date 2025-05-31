from django.db import models
from django.utils import timezone
from django.urls import reverse
import uuid
import re

class ContactMessage(models.Model):
    """お問い合わせメッセージを保存するモデル"""
    # 基本フィールド
    name = models.CharField('お名前', max_length=100)
    email = models.EmailField('メールアドレス')
    subject = models.CharField('件名', max_length=200)
    message = models.TextField('メッセージ')
    created_at = models.DateTimeField('送信日時', default=timezone.now)
    is_read = models.BooleanField('既読', default=False)
    
    # スパム対策フィールド
    ip_address = models.GenericIPAddressField('IPアドレス', null=True, blank=True)
    spam_score = models.IntegerField('スパムスコア', default=0)
    is_spam = models.BooleanField('スパム判定', default=False)
    
    # メール認証フィールド
    verification_token = models.UUIDField('認証トークン', default=uuid.uuid4, unique=True)
    is_verified = models.BooleanField('メール認証済み', default=False)
    verified_at = models.DateTimeField('認証日時', null=True, blank=True)
    verification_expires_at = models.DateTimeField('認証期限', null=True, blank=True)
    
    class Meta:
        verbose_name = 'お問い合わせ'
        verbose_name_plural = 'お問い合わせ'
        ordering = ['-created_at']
    
    def __str__(self):
        spam_flag = " [SPAM]" if self.is_spam else ""
        verified_flag = " [未認証]" if not self.is_verified else ""
        return f"{self.name}: {self.subject}{spam_flag}{verified_flag}"
    
    def is_verification_expired(self):
        """認証期限が切れているかチェック"""
        if not self.verification_expires_at:
            return True
        return timezone.now() > self.verification_expires_at
    
    def verify_email(self):
        """メール認証を完了させる"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save()
    
    def get_verification_url(self, request):
        """認証URLを生成"""
        return request.build_absolute_uri(
            reverse('contact:verify_email', kwargs={'token': self.verification_token})
        )
    
    def calculate_spam_score(self):
        """スパムスコアを計算する"""
        score = 0
        
        # ランダムな文字列パターンをチェック
        random_patterns = [
            r'^[a-z]{10,}$',
            r'^[a-zA-Z]{20,}$',
        ]
        
        for pattern in random_patterns:
            if re.match(pattern, self.name) or re.match(pattern, self.message):
                score += 2
        
        # 意味のない繰り返し文字
        if len(set(self.name.lower())) < 3 and len(self.name) > 5:
            score += 1
        
        # メッセージの品質チェック
        if len(self.message) > 10:
            # 日本語が含まれているかチェック
            has_japanese = any('\u3040' <= char <= '\u309F' or
                              '\u30A0' <= char <= '\u30FF' or
                              '\u4E00' <= char <= '\u9FAF'
                              for char in self.message)
            
            # 英語の一般的な単語が含まれているかチェック
            common_words = ['the', 'and', 'you', 'that', 'was', 'for', 'are', 'with', 'his', 'they']
            has_common_english = any(word in self.message.lower() for word in common_words)
            
            if not has_japanese and not has_common_english:
                score += 2
            
            # 同じ文字が連続で5回以上
            if re.search(r'(.)\1{4,}', self.message):
                score += 1
        
        # 短すぎるメッセージ
        if len(self.message.strip()) < 10:
            score += 1
        
        # 件名が選択されていない
        if '選択してください' in self.subject:
            score += 2
        
        # 既知のスパムパターン
        spam_keywords = ['wkxprysmyph', 'accordini', 'gfwljsiqtrr', 'oyvjwyyrxg']
        for keyword in spam_keywords:
            if keyword.lower() in self.message.lower() or keyword.lower() in self.name.lower():
                score += 3
        
        # 使い捨てメールサービスのチェック
        disposable_domains = [
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com', 
            'mailinator.com', 'trash-mail.com', 'yopmail.com',
            'temp-mail.org', 'mohmal.com'
        ]
        email_domain = self.email.split('@')[-1].lower()
        if email_domain in disposable_domains:
            score += 2
        
        return score
    
    def save(self, *args, **kwargs):
        """保存時にスパムスコアと認証期限を設定"""
        if not self.spam_score:
            self.spam_score = self.calculate_spam_score()
            self.is_spam = self.spam_score > 3
        
        # 認証期限を24時間後に設定
        if not self.verification_expires_at:
            self.verification_expires_at = timezone.now() + timezone.timedelta(hours=24)
        
        super().save(*args, **kwargs)
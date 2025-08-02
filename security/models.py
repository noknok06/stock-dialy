# security/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
import ipaddress

class BlockedIP(models.Model):
    """ブロックされたIPアドレスを管理するモデル"""
    
    BLOCK_REASON_CHOICES = [
        ('spam', 'スパム送信'),
        ('abuse', '不正利用'),
        ('security', 'セキュリティ脅威'),
        ('manual', '手動ブロック'),
        ('automated', '自動検出'),
    ]
    
    ip_address = models.GenericIPAddressField('IPアドレス', unique=True)
    cidr_notation = models.CharField('CIDR記法', max_length=20, blank=True, help_text='例: 192.168.1.0/24')
    reason = models.CharField('ブロック理由', max_length=20, choices=BLOCK_REASON_CHOICES, default='manual')
    description = models.TextField('詳細', blank=True, help_text='ブロックした理由の詳細説明')
    created_at = models.DateTimeField('作成日時', default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='作成者'
    )
    is_active = models.BooleanField('有効', default=True)
    expires_at = models.DateTimeField('有効期限', null=True, blank=True, help_text='空の場合は無期限')
    
    class Meta:
        verbose_name = 'ブロック済みIP'
        verbose_name_plural = 'ブロック済みIP'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ip_address} ({self.get_reason_display()})"
    
    def clean(self):
        """IPアドレスの妥当性をチェック"""
        try:
            ipaddress.ip_address(self.ip_address)
        except ValueError:
            raise ValidationError({'ip_address': '有効なIPアドレスを入力してください。'})
        
        if self.cidr_notation:
            try:
                ipaddress.ip_network(self.cidr_notation)
            except ValueError:
                raise ValidationError({'cidr_notation': '有効なCIDR記法を入力してください。'})
    
    def is_expired(self):
        """ブロックが期限切れかどうかチェック"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def is_blocking_ip(self, ip):
        """指定されたIPアドレスをブロックするかチェック"""
        if not self.is_active or self.is_expired():
            return False
        
        try:
            check_ip = ipaddress.ip_address(ip)
            
            # 単一IPの一致
            if str(check_ip) == self.ip_address:
                return True
            
            # CIDR記法での一致
            if self.cidr_notation:
                network = ipaddress.ip_network(self.cidr_notation)
                return check_ip in network
                
        except ValueError:
            pass
        
        return False


class BlockedEmail(models.Model):
    """ブロックされたメールアドレスを管理するモデル"""
    
    BLOCK_TYPE_CHOICES = [
        ('exact', '完全一致'),
        ('domain', 'ドメイン一致'),
        ('pattern', 'パターン一致'),
    ]
    
    BLOCK_REASON_CHOICES = [
        ('spam', 'スパム送信'),
        ('abuse', '不正利用'),
        ('fake', '偽装メール'),
        ('manual', '手動ブロック'),
        ('automated', '自動検出'),
    ]
    
    email_pattern = models.CharField('メールパターン', max_length=255, unique=True)
    block_type = models.CharField('ブロックタイプ', max_length=10, choices=BLOCK_TYPE_CHOICES, default='exact')
    reason = models.CharField('ブロック理由', max_length=20, choices=BLOCK_REASON_CHOICES, default='manual')
    description = models.TextField('詳細', blank=True)
    created_at = models.DateTimeField('作成日時', default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='作成者'
    )
    is_active = models.BooleanField('有効', default=True)
    expires_at = models.DateTimeField('有効期限', null=True, blank=True)
    
    class Meta:
        verbose_name = 'ブロック済みメール'
        verbose_name_plural = 'ブロック済みメール'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email_pattern} ({self.get_block_type_display()})"
    
    def clean(self):
        """メールパターンの妥当性をチェック"""
        if self.block_type == 'exact':
            try:
                validate_email(self.email_pattern)
            except ValidationError:
                raise ValidationError({'email_pattern': '有効なメールアドレスを入力してください。'})
        elif self.block_type == 'domain':
            if not self.email_pattern.startswith('@'):
                self.email_pattern = '@' + self.email_pattern
    
    def is_expired(self):
        """ブロックが期限切れかどうかチェック"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def is_blocking_email(self, email):
        """指定されたメールアドレスをブロックするかチェック"""
        if not self.is_active or self.is_expired():
            return False
        
        email = email.lower()
        pattern = self.email_pattern.lower()
        
        if self.block_type == 'exact':
            return email == pattern
        elif self.block_type == 'domain':
            return email.endswith(pattern)
        elif self.block_type == 'pattern':
            import re
            try:
                return bool(re.search(pattern, email))
            except re.error:
                return False
        
        return False


class BlockLog(models.Model):
    """ブロック履歴を記録するモデル"""
    
    BLOCK_TYPE_CHOICES = [
        ('ip', 'IPアドレス'),
        ('email', 'メールアドレス'),
    ]
    
    block_type = models.CharField('ブロックタイプ', max_length=10, choices=BLOCK_TYPE_CHOICES)
    blocked_value = models.CharField('ブロックされた値', max_length=255)
    ip_address = models.GenericIPAddressField('アクセス元IP', null=True, blank=True)
    user_agent = models.TextField('ユーザーエージェント', blank=True)
    request_path = models.CharField('リクエストパス', max_length=255, blank=True)
    blocked_at = models.DateTimeField('ブロック日時', default=timezone.now)
    
    class Meta:
        verbose_name = 'ブロック履歴'
        verbose_name_plural = 'ブロック履歴'
        ordering = ['-blocked_at']
    
    def __str__(self):
        return f"{self.get_block_type_display()}: {self.blocked_value} ({self.blocked_at})"
# contact/views.py の更新部分
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.utils import timezone
from .models import ContactMessage
import time
import logging
import re
import unicodedata

# ロガーの設定
logger = logging.getLogger(__name__)

def contact_view(request):
    """お問い合わせフォームの処理を行うビュー（第1段階：メール認証リンク送信）"""
    if request.method == 'POST':
        # レート制限チェック
        if not check_contact_rate_limit(request):
            messages.error(request, '送信間隔が短すぎます。しばらく経ってからもう一度お試しください。')
            return render(request, 'contact.html')
        
        # POSTデータの取得
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        privacy_agreement = request.POST.get('privacy_agreement', '')
        
        # ハニーポット チェック（隠しフィールド）
        honeypot = request.POST.get('website', '')
        if honeypot:
            logger.warning(f"ハニーポット検出: IP={get_client_ip(request)}, honeypot={honeypot}")
            return redirect('contact:verification_sent')
        
        # 基本バリデーション
        if not all([name, email, subject, message]):
            messages.error(request, '全ての項目を入力してください。')
            return render(request, 'contact.html')
            
        if not privacy_agreement:
            messages.error(request, 'プライバシーポリシーへの同意が必要です。')
            return render(request, 'contact.html')
        
        # メールアドレスのブロックチェック
        if is_blocked_email(email):
            logger.warning(f"ブロック済みメールアドレスからの問い合わせ: {email}")
            # ブロックされていても攻撃者に分からないよう、認証送信画面に遷移
            return redirect('contact:verification_sent')
        
        # メールアドレスの形式チェック
        if not is_valid_email_domain(email):
            messages.error(request, 'このメールアドレスはご利用いただけません。別のメールアドレスをお使いください。')
            return render(request, 'contact.html')
        
        # データベースに未認証状態で保存
        contact_message = ContactMessage.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message,
            ip_address=get_client_ip(request),
            is_verified=False
        )
        
        # スパム判定
        if contact_message.is_spam:
            logger.warning(f"スパム判定のため認証メール送信をスキップ: {email}")
            return redirect('contact:verification_sent')
        
        # 認証メールの送信
        try:
            send_verification_email(contact_message, request)
            logger.info(f"認証メール送信: {email} [ID: {contact_message.id}]")
            return redirect('contact:verification_sent')
            
        except Exception as e:
            logger.error(f"認証メール送信エラー: {str(e)}")
            messages.error(request, 'メールの送信に失敗しました。しばらく経ってからもう一度お試しください。')
            contact_message.delete()
            return render(request, 'contact.html')
    
    # GETリクエスト時
    return render(request, 'contact.html')

def verify_email(request, token):
    """メール認証処理（第2段階：認証完了と実際の問い合わせ送信）"""
    contact_message = get_object_or_404(ContactMessage, verification_token=token)
    
    # 既に認証済みの場合
    if contact_message.is_verified:
        messages.info(request, 'このメールアドレスは既に認証済みです。')
        return redirect('contact:already_verified')
    
    # 認証期限切れの場合
    if contact_message.is_verification_expired():
        messages.error(request, '認証期限が切れています。もう一度お問い合わせフォームからお送りください。')
        contact_message.delete()
        return redirect('contact:verification_expired')
    
    # スパム判定の場合（念のため再チェック）
    if contact_message.is_spam:
        logger.warning(f"スパム判定のため認証を拒否: {contact_message.email}")
        messages.error(request, '認証に失敗しました。')
        return redirect('contact:verification_failed')
    
    # メールアドレスの再ブロックチェック（認証時にも確認）
    if is_blocked_email(contact_message.email):
        logger.warning(f"認証時にブロック済みメールを検出: {contact_message.email}")
        contact_message.delete()
        return redirect('contact:verification_failed')
    
    # メール認証完了
    contact_message.verify_email()
    
    # 管理者への実際の問い合わせメール送信
    try:
        send_contact_to_admin(contact_message)
        send_confirmation_to_user(contact_message)
        
        logger.info(f"お問い合わせ認証完了・送信: {contact_message.email} [ID: {contact_message.id}]")
        messages.success(request, 'メール認証が完了しました。お問い合わせを受け付けました。')
        return redirect('contact:success')
        
    except Exception as e:
        logger.error(f"認証後メール送信エラー: {str(e)}")
        messages.error(request, 'お問い合わせの処理中にエラーが発生しました。')
        return redirect('contact:verification_failed')

# 他のビュー関数は既存のまま...
def verification_sent_view(request):
    """認証メール送信完了ページ"""
    return render(request, 'verification_sent.html')

def verification_expired_view(request):
    """認証期限切れページ"""
    return render(request, 'verification_expired.html')

def verification_failed_view(request):
    """認証失敗ページ"""
    return render(request, 'verification_failed.html')

def already_verified_view(request):
    """既に認証済みページ"""
    return render(request, 'already_verified.html')

def contact_success_view(request):
    """お問い合わせ完了ページを表示するビュー"""
    return render(request, 'contact_success.html')

# ヘルパー関数

def is_blocked_email(email):
    """メールアドレスがブロックされているかチェック"""
    if not email:
        return False
    
    # キャッシュキーを生成
    cache_key = f"blocked_email_check_{email.lower()}"
    
    # キャッシュから結果を取得（5分間キャッシュ）
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        from security.models import BlockedEmail
        
        # アクティブで期限切れでないブロックをチェック
        blocked_emails = BlockedEmail.objects.filter(is_active=True)
        
        for blocked_email in blocked_emails:
            if blocked_email.is_blocking_email(email):
                # ブロック対象として結果をキャッシュ
                cache.set(cache_key, True, 300)  # 5分間キャッシュ
                
                # ブロック試行をログに記録
                try:
                    from security.models import BlockLog
                    BlockLog.objects.create(
                        block_type='email',
                        blocked_value=email,
                        ip_address=None,  # この時点ではリクエストオブジェクトがない
                        request_path='/contact/',
                    )
                except:
                    pass
                
                return True
        
        # ブロック対象外として結果をキャッシュ
        cache.set(cache_key, False, 300)  # 5分間キャッシュ
        return False
        
    except Exception as e:
        logger.error(f"Error checking blocked email: {e}")
        return False

def send_verification_email(contact_message, request):
    """認証メールを送信"""
    verification_url = contact_message.get_verification_url(request)
    
    subject = '【カブログ】お問い合わせの確認'
    message = f"""{contact_message.name} 様

カブログへのお問い合わせありがとうございます。
お問い合わせを完了するため、下記のリンクをクリックしてメールアドレスの確認をお願いします：

{verification_url}

※このリンクは24時間有効です。
※心当たりがない場合は、このメールを無視してください。

--
カブログ サポートチーム
Email: kabulog.information@gmail.com
URL: https://kabulog.net
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [contact_message.email],
        fail_silently=False,
    )

def send_contact_to_admin(contact_message):
    """管理者に実際の問い合わせメールを送信"""
    admin_subject = f'【カブログ】お問い合わせ: {contact_message.subject}'
    admin_message = f"""カブログお問い合わせがありました（メール認証済み）。

■ お名前: {contact_message.name}
■ メールアドレス: {contact_message.email}
■ 件名: {contact_message.subject}
■ 認証日時: {contact_message.verified_at}
■ IP: {contact_message.ip_address}

■ お問い合わせ内容:
{contact_message.message}
"""
    
    send_mail(
        admin_subject,
        admin_message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.EMAIL_HOST_USER],
        fail_silently=False,
    )

def send_confirmation_to_user(contact_message):
    """ユーザーに最終確認メールを送信"""
    user_subject = '【カブログ】お問い合わせを受け付けました'
    user_message = f"""{contact_message.name} 様

メール認証が完了し、お問い合わせを受け付けました。
通常3営業日以内にご返信いたします。

■ お名前: {contact_message.name}
■ 件名: {contact_message.subject}
■ お問い合わせ内容:
{contact_message.message}

※このメールは自動送信されています。

--
カブログ サポートチーム
Email: kabulog.information@gmail.com
URL: https://kabulog.net
"""
    
    send_mail(
        user_subject,
        user_message,
        settings.DEFAULT_FROM_EMAIL,
        [contact_message.email],
        fail_silently=False,
    )

def is_valid_email_domain(email):
    """メールドメインの妥当性をチェック"""
    blocked_domains = [
        '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
        'mailinator.com', 'trash-mail.com', 'yopmail.com',
        'temp-mail.org', 'mohmal.com', 'throwaway.email',
        'getnada.com', 'maildrop.cc'
    ]
    
    try:
        domain = email.split('@')[-1].lower()
        return domain not in blocked_domains
    except:
        return False

def check_contact_rate_limit(request):
    """お問い合わせフォームのレート制限をチェック"""
    client_ip = get_client_ip(request)
    cache_key = f"contact_rate_limit_{client_ip}"
    
    attempts = cache.get(cache_key, 0)
    if attempts >= 3:
        return False
    
    cache.set(cache_key, attempts + 1, 3600)
    return True

def get_client_ip(request):
    """クライアントのIPアドレスを取得"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
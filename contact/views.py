# contact/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
import time
import logging

# ロガーの設定
logger = logging.getLogger(__name__)

def contact_view(request):
    """お問い合わせフォームの処理を行うビュー"""
    if request.method == 'POST':
        # POSTデータの取得
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        subject = request.POST.get('subject', '')
        message = request.POST.get('message', '')
        privacy_agreement = request.POST.get('privacy_agreement', '')
        
        # バリデーション
        if not all([name, email, subject, message]):
            messages.error(request, '全ての項目を入力してください。')
            return render(request, 'contact.html')
            
        if not privacy_agreement:
            messages.error(request, 'プライバシーポリシーへの同意が必要です。')
            return render(request, 'contact.html')
            
        # メールの送信
        try:
            # ログ出力
            logger.info(f"お問い合わせを受信: {name} ({email}) - {subject}")
            
            # 管理者へのメール
            admin_subject = f'【カブログ】お問い合わせ: {subject}'
            admin_message = f"""カブログお問い合わせがありました。

■ お名前: {name}
■ メールアドレス: {email}
■ 件名: {subject}

■ お問い合わせ内容:
{message}
"""

            send_mail(
                admin_subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,  # 送信元
                [settings.EMAIL_HOST_USER],   # 管理者のメールアドレス
                fail_silently=False,
            )
            
            # ユーザーへの自動返信メール
            user_subject = '【カブログ】お問い合わせありがとうございます'
            user_message = f"""{name} 様

カブログへのお問い合わせありがとうございます。
以下の内容でお問い合わせを受け付けました。
通常3営業日以内にご返信いたします。

■ お名前: {name}
■ メールアドレス: {email}
■ 件名: {subject}

■ お問い合わせ内容:
{message}

※このメールは自動送信されています。返信はご遠慮ください。

--
カブログ サポートチーム
Email: kabulog.information@gmail.com
URL: https://kabulog.net
"""
            
            send_mail(
                user_subject,
                user_message,
                settings.DEFAULT_FROM_EMAIL,  # 送信元
                [email],  # ユーザーのメールアドレス
                fail_silently=False,
            )
            
            # 成功メッセージ
            messages.success(request, 'お問い合わせを受け付けました。確認メールをお送りしましたのでご確認ください。')
            return redirect('contact_success')
            
        except Exception as e:
            # エラーをログに記録
            logger.error(f"メール送信エラー: {str(e)}")
            
            # メール送信エラー時
            messages.error(request, 'メールの送信に失敗しました。しばらく経ってからもう一度お試しください。')
            return render(request, 'contact.html', {
                'form_data': {
                    'name': name,
                    'email': email,
                    'subject': subject,
                    'message': message
                }
            })
    
    # GETリクエスト時
    return render(request, 'contact.html')

def contact_success_view(request):
    """お問い合わせ完了ページを表示するビュー"""
    return render(request, 'contact_success.html')
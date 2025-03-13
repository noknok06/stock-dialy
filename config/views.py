from django.shortcuts import render, redirect

def landing_page(request):
    # ユーザーがログイン済みの場合は直接アプリのホームページへリダイレクト
    if request.user.is_authenticated:
        return redirect('stockdiary:home')
    
    # ランディングページを表示
    return render(request, 'landing_page.html')
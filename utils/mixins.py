from django.shortcuts import redirect
from django.contrib import messages
from django.http import Http404
from django.urls import reverse_lazy, NoReverseMatch


class ObjectNotFoundRedirectMixin:
    """
    オブジェクトが見つからない場合に指定URLにリダイレクトするミックスイン。
    
    使用例:
    class MyDetailView(ObjectNotFoundRedirectMixin, DetailView):
        model = MyModel
        redirect_url = 'myapp:list'  # リダイレクト先のURL名
        not_found_message = "アイテムが見つかりません"  # カスタムメッセージ
    """
    redirect_url = None  # デフォルトはNone。継承先で上書きする必要がある
    not_found_message = "リクエストされたオブジェクトが見つかりません。削除された可能性があります。"
    
    def get_redirect_url(self):
        """リダイレクト先のURLを返す。オーバーライド可能"""
        if self.redirect_url:
            return reverse_lazy(self.redirect_url)
        # モデル名からデフォルトのリスト用URLを推測
        if hasattr(self, 'model') and self.model:
            app_label = self.model._meta.app_label
            model_name = self.model._meta.model_name
            try:
                return reverse_lazy(f'{app_label}:{model_name}_list')
            except NoReverseMatch:
                try:
                    return reverse_lazy(f'{app_label}:list')
                except NoReverseMatch:
                    pass
        # 推測できない場合はホームページへ
        return reverse_lazy('home')
    
    def get_not_found_message(self):
        """表示するエラーメッセージを返す。オーバーライド可能"""
        return self.not_found_message
    
    def get(self, request, *args, **kwargs):
        """getメソッドをオーバーライドしてオブジェクト非存在時の処理を追加"""
        try:
            self.object = self.get_object()
            return super().get(request, *args, **kwargs)
        except (Http404, self.model.DoesNotExist):
            messages.error(request, self.get_not_found_message())
            return redirect(self.get_redirect_url())
    
    def post(self, request, *args, **kwargs):
        """postメソッドをオーバーライドしてオブジェクト非存在時の処理を追加"""
        try:
            self.object = self.get_object()
            return super().post(request, *args, **kwargs)
        except (Http404, self.model.DoesNotExist):
            messages.error(request, self.get_not_found_message())
            return redirect(self.get_redirect_url())
# portfolio/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from .models import PortfolioSnapshot, HoldingRecord, SectorAllocation
from stockdiary.models import StockDiary
from decimal import Decimal
from utils.mixins import ObjectNotFoundRedirectMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

class SnapshotListView(LoginRequiredMixin, ListView):
    model = PortfolioSnapshot
    template_name = 'portfolio/list.html'
    context_object_name = 'snapshots'
    
    def get_queryset(self):
        return PortfolioSnapshot.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diary_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('stockdiary:home'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('portfolio:create_snapshot'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            },
            {
                'type': 'snap',
                'url': reverse_lazy('portfolio:compare'),
                'icon': 'bi-input-cursor',
                'label': '比較分析'
            }
        ]
        context['page_actions'] = diary_actions  # この行を必ず追加する
        return context

class SnapshotDetailView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DetailView):
    model = PortfolioSnapshot
    template_name = 'portfolio/detail.html'
    context_object_name = 'snapshot'
    redirect_url = 'portfolio:list'
    not_found_message = "スナップショットが見つかりません。削除された可能性があります。"
    
    def get_queryset(self):
        return PortfolioSnapshot.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['holdings'] = self.object.holdings.all()
        context['sector_allocations'] = self.object.sector_allocations.all()
        diary_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('portfolio:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            {
                'type': 'add',
                'url': reverse_lazy('portfolio:create_snapshot'),
                'icon': 'bi-plus-lg',
                'label': '新規作成'
            },
            {
                'type': 'snap',
                'url': reverse_lazy('portfolio:compare'),
                'icon': 'bi-camera',
                'label': '比較分析'
            }
        ]
        context['diary_actions'] = diary_actions  # この行を必ず追加する
        return context

# portfolio/views.py の CreateSnapshotView クラスを修正

class CreateSnapshotView(LoginRequiredMixin, CreateView):
    model = PortfolioSnapshot
    template_name = 'portfolio/form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('portfolio:list')
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        page_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('portfolio:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            # 分析ページに必要な他のアクションを追加
        ]
        context['page_actions'] = page_actions

        return context
        
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # アクティブな株式日記を取得（売却されていないもの）
        active_diaries = StockDiary.objects.filter(
            user=self.request.user, 
            sell_date__isnull=True,
            purchase_price__isnull=False,
            purchase_quantity__isnull=False
        )
        
        # 合計評価額を計算
        total_value = Decimal('0')
        for diary in active_diaries:
            if diary.purchase_price and diary.purchase_quantity:
                total_value += diary.purchase_price * diary.purchase_quantity
        
        form.instance.total_value = total_value
        
        # スナップショットを保存
        response = super().form_valid(form)
        
        # 各株式の保有記録を作成
        for diary in active_diaries:
            if diary.purchase_price and diary.purchase_quantity:
                stock_value = diary.purchase_price * diary.purchase_quantity
                percentage = (stock_value / total_value * 100) if total_value else Decimal('0')

                # セクター情報を取得 - StockDiaryから直接取得し、空の場合はタグから推測
                sector = diary.sector
                
                # # セクターが未設定の場合はタグから推測
                # if not sector or sector.strip() == "":
                #     sector_tags = ['テクノロジー', '金融', 'ヘルスケア', '消費財', '素材', 'エネルギー', '通信', '公共', '不動産', '産業']
                #     for tag in diary.tags.all():
                #         tag_name = tag.name
                #         if any(s in tag_name for s in sector_tags):
                #             sector = tag_name
                #             break
                
                # それでも設定できない場合は「未分類」
                if not sector or sector.strip() == "":
                    sector = "未分類"         

                HoldingRecord.objects.create(
                    snapshot=self.object,
                    stock_symbol=diary.stock_symbol,
                    stock_name=diary.stock_name,
                    quantity=diary.purchase_quantity,
                    price=diary.purchase_price,
                    total_value=stock_value,
                    sector=diary.sector,  # StockDiary から直接取得
                    percentage=percentage
                )
        
        # セクター配分を計算
        self.calculate_sector_allocations()
        
        return response
    
    def calculate_sector_allocations(self):
        """セクター別の配分を計算して保存"""
        # 全ホールディングを取得
        holdings = self.object.holdings.all()
        
        # セクターごとにグループ化
        sectors = {}
        for holding in holdings:
            sector = holding.sector if holding.sector else "未分類"
            
            if sector in sectors:
                sectors[sector] += holding.percentage
            else:
                sectors[sector] = holding.percentage
        
        # セクター配分を保存
        for sector_name, percentage in sectors.items():
            SectorAllocation.objects.create(
                snapshot=self.object,
                sector_name=sector_name,
                percentage=percentage
            )

# portfolio/views.py に追加
# portfolio/views.py のCompareSnapshotsViewクラスを修正

class CompareSnapshotsView(LoginRequiredMixin, TemplateView):
    template_name = 'portfolio/compare.html'
    redirect_url = 'portfolio:list'
    not_found_message = "比較対象のスナップショットが見つかりません。"
    model = PortfolioSnapshot  # ミックスインで使用するため必要
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 利用可能なすべてのスナップショットを取得
        snapshots = PortfolioSnapshot.objects.filter(user=self.request.user).order_by('-created_at')
        context['snapshots'] = snapshots
        
        # 選択された2つのスナップショットを取得
        snapshot1_id = self.request.GET.get('snapshot1')
        snapshot2_id = self.request.GET.get('snapshot2')
        
        # いずれかのIDが指定されていて、存在しない場合の処理
        if (snapshot1_id and not PortfolioSnapshot.objects.filter(
                id=snapshot1_id, user=self.request.user).exists()) or \
           (snapshot2_id and not PortfolioSnapshot.objects.filter(
                id=snapshot2_id, user=self.request.user).exists()):
            messages.error(self.request, "比較対象のスナップショットが見つかりません。")
            return redirect('portfolio:list')
        
        if snapshot1_id and snapshot2_id:
            try:
                snapshot1 = PortfolioSnapshot.objects.get(id=snapshot1_id, user=self.request.user)
                snapshot2 = PortfolioSnapshot.objects.get(id=snapshot2_id, user=self.request.user)
                
                context['snapshot1'] = snapshot1
                context['snapshot2'] = snapshot2
                
                # セクター配分の比較データを生成
                context['sector_comparison'] = self.generate_sector_comparison(snapshot1, snapshot2)
                
                # 保有銘柄の比較データを生成
                context['holdings_comparison'] = self.generate_holdings_comparison(snapshot1, snapshot2)
                
            except PortfolioSnapshot.DoesNotExist:
                context['error'] = "指定されたスナップショットが見つかりません。"

        page_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('portfolio:list'),
                'icon': 'bi-arrow-left',
                'label': '戻る'
            },
            # 分析ページに必要な他のアクションを追加
        ]
        context['page_actions'] = page_actions
        
        return context
    
    def generate_sector_comparison(self, snapshot1, snapshot2):
        """2つのスナップショット間のセクター配分の差分を計算"""
        # すべてのセクター名を収集
        sectors = set()
        
        # snapshot1のセクター配分を取得
        snapshot1_allocations = SectorAllocation.objects.filter(snapshot=snapshot1)
        for allocation in snapshot1_allocations:
            sectors.add(allocation.sector_name)
        
        # snapshot2のセクター配分を取得
        snapshot2_allocations = SectorAllocation.objects.filter(snapshot=snapshot2)
        for allocation in snapshot2_allocations:
            sectors.add(allocation.sector_name)
        
        # 各セクターの割合を格納する辞書
        sector_data = {}
        
        # セクターごとの初期データを設定
        for sector in sectors:
            sector_data[sector] = {
                'name': sector,
                'snapshot1': 0,
                'snapshot2': 0,
                'change': 0
            }
        
        # スナップショット1のデータを設定
        for allocation in snapshot1_allocations:
            sector_name = allocation.sector_name
            sector_data[sector_name]['snapshot1'] = allocation.percentage
        
        # スナップショット2のデータを設定
        for allocation in snapshot2_allocations:
            sector_name = allocation.sector_name
            sector_data[sector_name]['snapshot2'] = allocation.percentage
        
        # 変化を計算
        for sector in sector_data:
            sector_data[sector]['change'] = sector_data[sector]['snapshot2'] - sector_data[sector]['snapshot1']
        
        # 辞書からリストに変換
        result = list(sector_data.values())
        
        # 変化の絶対値でソート（変化が大きい順）
        result.sort(key=lambda x: abs(x['change']), reverse=True)
        
        return result
    
    def generate_holdings_comparison(self, snapshot1, snapshot2):
        """保有銘柄の比較データを生成"""
        symbols = set()
        holdings_data = {}
        
        # すべての銘柄を収集
        for holding in snapshot1.holdings.all():
            symbols.add(holding.stock_symbol)
        
        for holding in snapshot2.holdings.all():
            symbols.add(holding.stock_symbol)
        
        # 各銘柄のデータを初期化
        for symbol in symbols:
            holdings_data[symbol] = {
                'symbol': symbol,
                'name': '',
                'snapshot1_quantity': 0,
                'snapshot1_price': 0,
                'snapshot1_value': 0,
                'snapshot1_percentage': 0,
                'snapshot2_quantity': 0,
                'snapshot2_price': 0,
                'snapshot2_value': 0,
                'snapshot2_percentage': 0,
                'quantity_change': 0,
                'price_change': 0,
                'percentage_change': 0,
                'value_change': 0
            }
        
        # スナップショット1のデータを設定
        for holding in snapshot1.holdings.all():
            holdings_data[holding.stock_symbol].update({
                'name': holding.stock_name,
                'snapshot1_quantity': holding.quantity,
                'snapshot1_price': holding.price,
                'snapshot1_value': holding.total_value,
                'snapshot1_percentage': holding.percentage
            })
        
        # スナップショット2のデータを設定
        for holding in snapshot2.holdings.all():
            holdings_data[holding.stock_symbol].update({
                'name': holding.stock_name,
                'snapshot2_quantity': holding.quantity,
                'snapshot2_price': holding.price,
                'snapshot2_value': holding.total_value,
                'snapshot2_percentage': holding.percentage
            })
        
        # 変化を計算
        for symbol in holdings_data:
            data = holdings_data[symbol]
            data['quantity_change'] = data['snapshot2_quantity'] - data['snapshot1_quantity']
            data['price_change'] = data['snapshot2_price'] - data['snapshot1_price']
            data['value_change'] = data['snapshot2_value'] - data['snapshot1_value']
            data['percentage_change'] = data['snapshot2_percentage'] - data['snapshot1_percentage']
        
        # リストに変換してソート（変化の大きさ順）
        result = list(holdings_data.values())
        result.sort(key=lambda x: abs(x['value_change']), reverse=True)
        
        return result

# portfolio/views.py に追加
class SnapshotDeleteView(ObjectNotFoundRedirectMixin, LoginRequiredMixin, DeleteView):
    model = PortfolioSnapshot
    success_url = reverse_lazy('portfolio:list')
    template_name = 'portfolio/snapshot_confirm_delete.html'
    redirect_url = 'portfolio:list'
    not_found_message = "削除対象のスナップショットが見つかりません。"
    
    def get_queryset(self):
        return PortfolioSnapshot.objects.filter(user=self.request.user)
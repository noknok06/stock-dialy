# portfolio/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from .models import PortfolioSnapshot, HoldingRecord, SectorAllocation
from stockdiary.models import StockDiary
from decimal import Decimal

class SnapshotListView(LoginRequiredMixin, ListView):
    model = PortfolioSnapshot
    template_name = 'portfolio/snapshot_list.html'
    context_object_name = 'snapshots'
    
    def get_queryset(self):
        return PortfolioSnapshot.objects.filter(user=self.request.user)

class SnapshotDetailView(LoginRequiredMixin, DetailView):
    model = PortfolioSnapshot
    template_name = 'portfolio/snapshot_detail.html'
    context_object_name = 'snapshot'
    
    def get_queryset(self):
        return PortfolioSnapshot.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['holdings'] = self.object.holdings.all()
        context['sector_allocations'] = self.object.sector_allocations.all()
        return context

# portfolio/views.py の CreateSnapshotView クラスを修正

class CreateSnapshotView(LoginRequiredMixin, CreateView):
    model = PortfolioSnapshot
    template_name = 'portfolio/snapshot_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('portfolio:snapshot_list')
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        page_actions = [
            {
                'type': 'back',
                'url': reverse_lazy('portfolio:snapshot_list'),
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
    template_name = 'portfolio/compare_snapshots.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 利用可能なすべてのスナップショットを取得
        snapshots = PortfolioSnapshot.objects.filter(user=self.request.user).order_by('-created_at')
        context['snapshots'] = snapshots
        
        # 選択された2つのスナップショットを取得
        snapshot1_id = self.request.GET.get('snapshot1')
        snapshot2_id = self.request.GET.get('snapshot2')
        
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
                'url': reverse_lazy('portfolio:snapshot_list'),
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
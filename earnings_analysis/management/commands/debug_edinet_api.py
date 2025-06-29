# earnings_analysis/management/commands/debug_edinet_api.py
"""
EDINET API v2のレスポンス内容をデバッグするコマンド
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import json

from earnings_analysis.services import EDINETAPIService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'EDINET API v2のレスポンス内容をデバッグ'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='テスト対象日 (YYYY-MM-DD形式。未指定時は過去の書類がある日)',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='特定企業の証券コード (例: 7203)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='表示する書類数の上限 (デフォルト: 5)',
        )
    
    def handle(self, *args, **options):
        test_date = options['date']
        company_code = options['company']
        limit = options['limit']
        
        # 書類が多い日を使用（決算発表が集中する時期）
        if not test_date:
            # 過去の決算発表が多そうな日を使用
            test_dates = [
                '2025-05-15',  # 3月決算企業の決算発表時期
                '2025-05-30',  # 決算書類提出が多い時期
                '2025-06-20',  # 有価証券報告書提出時期
                '2025-04-30',  # 決算短信発表時期
            ]
            
            # どの日付に書類が多いかチェック
            test_date = self._find_best_test_date(test_dates)
        
        self.stdout.write(
            self.style.SUCCESS(f'EDINET API v2 デバッグテストを開始します...')
        )
        self.stdout.write(f'テスト日: {test_date}')
        if company_code:
            self.stdout.write(f'対象企業: {company_code}')
        
        try:
            # APIサービスの初期化
            edinet_service = EDINETAPIService()
            
            # 1. 生データの取得
            self.stdout.write('\n=== 生データの取得 ===')
            raw_documents = self._get_raw_documents(edinet_service, test_date)
            
            if not raw_documents:
                self.stdout.write(self.style.WARNING('書類が見つかりませんでした'))
                return
            
            self.stdout.write(f'取得した書類数: {len(raw_documents)}')
            
            # 2. 書類種別の分析
            self.stdout.write('\n=== 書類種別の分析 ===')
            self._analyze_document_types(raw_documents)
            
            # 3. データ構造の分析
            self.stdout.write('\n=== データ構造の分析 ===')
            self._analyze_data_structure(raw_documents[:3])
            
            # 4. 企業名の一覧表示
            self.stdout.write('\n=== 企業名の一覧 ===')
            self._show_company_names(raw_documents[:limit])
            
            # 5. 特定企業の検索
            if company_code:
                self.stdout.write(f'\n=== 企業 {company_code} の検索 ===')
                self._search_specific_company(raw_documents, company_code)
            
            # 6. 決算関連書類の検索
            self.stdout.write('\n=== 決算関連書類の検索 ===')
            self._search_earnings_documents(raw_documents)
            
            # 7. トヨタ関連の検索
            self.stdout.write('\n=== トヨタ関連の検索 ===')
            self._search_toyota_related(raw_documents)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'デバッグテスト中にエラーが発生しました: {str(e)}')
            )
            raise CommandError(f'デバッグテストに失敗しました: {str(e)}')
    
    def _find_best_test_date(self, test_dates):
        """書類が最も多い日付を見つける"""
        try:
            edinet_service = EDINETAPIService()
            best_date = test_dates[0]
            max_count = 0
            
            for date in test_dates:
                documents = self._get_raw_documents(edinet_service, date)
                count = len(documents)
                self.stdout.write(f"📅 {date}: {count}件")
                
                if count > max_count:
                    max_count = count
                    best_date = date
            
            self.stdout.write(f"✅ 最適な日付: {best_date} ({max_count}件)")
            return best_date
            
        except Exception:
            return test_dates[0]
    
    def _analyze_document_types(self, documents):
        """書類種別を分析"""
        from collections import Counter
        
        doc_types = [doc.get('docTypeCode', 'unknown') for doc in documents]
        type_counts = Counter(doc_types)
        
        self.stdout.write("書類種別の分布:")
        for doc_type, count in type_counts.most_common(10):
            # 書類種別の説明
            type_descriptions = {
                '120': '有価証券報告書',
                '130': '四半期報告書',
                '140': '半期報告書',
                '180': '臨時報告書',
                '350': '決算短信',
                '160': '半期報告書（投資信託）',
                '030': '有価証券届出書',
                '040': '訂正有価証券届出書',
            }
            
            description = type_descriptions.get(doc_type, f'その他({doc_type})')
            self.stdout.write(f"  {doc_type}: {count}件 - {description}")
        
        # 決算関連書類をカウント
        earnings_types = ['120', '130', '140', '350']
        earnings_count = sum(count for doc_type, count in type_counts.items() if doc_type in earnings_types)
        self.stdout.write(f"\n📊 決算関連書類: {earnings_count}件")
    
    def _search_earnings_documents(self, documents):
        """決算関連書類を検索"""
        earnings_types = ['120', '130', '140', '350']
        earnings_docs = [doc for doc in documents if doc.get('docTypeCode', '') in earnings_types]
        
        if earnings_docs:
            self.stdout.write(f"決算関連書類が {len(earnings_docs)} 件見つかりました:")
            for i, doc in enumerate(earnings_docs[:5], 1):
                company_name = doc.get('filerName', 'N/A')
                sec_code = doc.get('secCode', 'N/A')
                doc_type = doc.get('docTypeCode', 'N/A')
                doc_desc = doc.get('docDescription', 'N/A')[:50]
                
                self.stdout.write(f"{i}. {company_name}")
                self.stdout.write(f"   証券コード: {sec_code}")
                self.stdout.write(f"   書類種別: {doc_type}")
                self.stdout.write(f"   書類説明: {doc_desc}...")
                self.stdout.write("")
        else:
            self.stdout.write("決算関連書類は見つかりませんでした")
    
    def _get_raw_documents(self, edinet_service, test_date):
        """生の書類データを取得"""
        try:
            # APIを直接呼び出して生データを取得
            url = f"{edinet_service.base_url}/api/v2/documents.json"
            params = {
                'date': test_date,
                'type': 2,
                'Subscription-Key': edinet_service.api_key
            }
            
            response = edinet_service.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('results', [])
            
        except Exception as e:
            self.stdout.write(f"データ取得エラー: {str(e)}")
            return []
    
    def _analyze_data_structure(self, documents):
        """データ構造を分析"""
        if not documents:
            self.stdout.write("分析するデータがありません")
            return
        
        self.stdout.write("最初の書類のデータ構造:")
        doc = documents[0]
        
        # JSON形式で見やすく表示
        formatted_doc = json.dumps(doc, ensure_ascii=False, indent=2)
        self.stdout.write(formatted_doc[:1000] + "..." if len(formatted_doc) > 1000 else formatted_doc)
        
        # キー一覧
        self.stdout.write(f"\n利用可能なキー: {list(doc.keys())}")
        
        # 重要なフィールドの確認
        important_fields = ['filerName', 'edinetCode', 'docDescription', 'docTypeCode']
        self.stdout.write("\n重要フィールドの値:")
        for field in important_fields:
            value = doc.get(field, 'N/A')
            self.stdout.write(f"  {field}: {value}")
    
    def _show_company_names(self, documents):
        """企業名の一覧を表示"""
        self.stdout.write("企業名一覧:")
        for i, doc in enumerate(documents, 1):
            company_name = doc.get('filerName', 'N/A')
            edinet_code = doc.get('edinetCode', 'N/A')
            doc_type = doc.get('docTypeCode', 'N/A')
            doc_desc = doc.get('docDescription', 'N/A')[:50]
            
            self.stdout.write(f"{i:2d}. {company_name}")
            self.stdout.write(f"    EDINETコード: {edinet_code}")
            self.stdout.write(f"    書類種別: {doc_type}")
            self.stdout.write(f"    書類説明: {doc_desc}...")
            self.stdout.write("")
    
    def _search_specific_company(self, documents, company_code):
        """特定企業の書類を検索（secCode対応版）"""
        matches = []
        
        for doc in documents:
            company_name = doc.get('filerName', '') or ''
            edinet_code = doc.get('edinetCode', '') or ''
            sec_code = doc.get('secCode', '') or ''  # 新しく追加
            
            # 証券コードでの検索（最も確実）
            if sec_code and sec_code.startswith(company_code):
                matches.append(doc)
            # 従来の検索も継続
            elif company_code in company_name or company_code in edinet_code:
                matches.append(doc)
        
        if matches:
            self.stdout.write(f"企業コード {company_code} に関連する書類が {len(matches)} 件見つかりました:")
            for i, doc in enumerate(matches[:3], 1):
                self.stdout.write(f"{i}. {doc.get('filerName', 'N/A')}")
                self.stdout.write(f"   証券コード: {doc.get('secCode', 'N/A')}")
                self.stdout.write(f"   EDINETコード: {doc.get('edinetCode', 'N/A')}")
                self.stdout.write(f"   書類種別: {doc.get('docTypeCode', 'N/A')}")
                self.stdout.write(f"   書類説明: {doc.get('docDescription', 'N/A')}")
        else:
            self.stdout.write(f"企業コード {company_code} に関連する書類は見つかりませんでした")
            
            # 証券コードの分析
            self.stdout.write("\n📊 証券コードの分析:")
            sec_codes = [doc.get('secCode', '') for doc in documents[:20] if doc.get('secCode')]
            unique_sec_codes = sorted(set(sec_codes))[:10]
            self.stdout.write(f"サンプル証券コード: {unique_sec_codes}")
    
    def _search_toyota_related(self, documents):
        """トヨタ関連の書類を検索"""
        toyota_keywords = ['トヨタ', 'TOYOTA', 'toyota']
        matches = []
        
        for doc in documents:
            company_name = doc.get('filerName', '') or ''
            edinet_code = doc.get('edinetCode', '') or ''
            doc_desc = doc.get('docDescription', '') or ''
            
            # トヨタ関連キーワードでの検索
            if any(keyword in company_name.lower() for keyword in [k.lower() for k in toyota_keywords]):
                matches.append(doc)
            elif any(keyword in doc_desc.lower() for keyword in [k.lower() for k in toyota_keywords]):
                matches.append(doc)
            elif '7203' in edinet_code:
                matches.append(doc)
        
        if matches:
            self.stdout.write(f"トヨタ関連の書類が {len(matches)} 件見つかりました:")
            for i, doc in enumerate(matches[:5], 1):
                self.stdout.write(f"{i}. {doc.get('filerName', 'N/A')}")
                self.stdout.write(f"   EDINETコード: {doc.get('edinetCode', 'N/A')}")
                self.stdout.write(f"   書類説明: {doc.get('docDescription', 'N/A')[:100]}...")
                self.stdout.write("")
        else:
            self.stdout.write("トヨタ関連の書類は見つかりませんでした")
            
            # 部分一致での検索も試行
            partial_matches = []
            for doc in documents:
                company_name = doc.get('filerName', '') or ''
                if 'トヨタ' in company_name or 'TOYOTA' in company_name:
                    partial_matches.append(doc)
            
            if partial_matches:
                self.stdout.write(f"部分一致で {len(partial_matches)} 件見つかりました:")
                for doc in partial_matches[:3]:
                    self.stdout.write(f"- {doc.get('filerName', 'N/A')}")
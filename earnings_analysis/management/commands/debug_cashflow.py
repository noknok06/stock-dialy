# earnings_analysis/management/commands/debug_cashflow.py
"""
キャッシュフロー抽出のデバッグ用コマンド
"""

from django.core.management.base import BaseCommand
from earnings_analysis.services import EDINETAPIService, XBRLTextExtractor, CashFlowExtractor
import json

class Command(BaseCommand):
    help = 'キャッシュフロー抽出をデバッグ'
    
    def add_arguments(self, parser):
        parser.add_argument('company_code', type=str, help='企業コード')
        parser.add_argument('--document-id', type=str, help='特定の書類ID')
        parser.add_argument('--save-text', action='store_true', help='抽出テキストをファイルに保存')
    
    def handle(self, *args, **options):
        company_code = options['company_code']
        document_id = options.get('document_id')
        save_text = options['save_text']
        
        self.stdout.write(f'🔍 {company_code} のキャッシュフロー抽出をデバッグします...')
        
        try:
            # 1. 最新書類の取得
            if document_id:
                self.stdout.write(f'指定された書類ID: {document_id}')
                doc_id = document_id
            else:
                self.stdout.write('最新書類を検索中...')
                edinet_service = EDINETAPIService()
                from datetime import datetime, timedelta
                
                # 過去30日分で検索
                for i in range(30):
                    date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                    documents = edinet_service.get_document_list(date, company_code)
                    if documents:
                        doc_id = documents[0]['document_id']
                        self.stdout.write(f'見つかった書類: {doc_id} ({date})')
                        break
                else:
                    raise Exception('書類が見つかりませんでした')
            
            # 2. 書類内容の取得
            self.stdout.write(f'書類をダウンロード中: {doc_id}')
            edinet_service = EDINETAPIService()
            document_content = edinet_service.get_document_content(doc_id)
            
            if not document_content:
                raise Exception('書類のダウンロードに失敗')
            
            self.stdout.write(f'ダウンロード完了: {len(document_content)} bytes')
            
            # 3. テキスト抽出
            self.stdout.write('テキスト抽出中...')
            xbrl_extractor = XBRLTextExtractor()
            text_sections = xbrl_extractor.extract_text_from_zip(document_content)
            
            self.stdout.write(f'抽出されたセクション数: {len(text_sections)}')
            for section_name in text_sections.keys():
                self.stdout.write(f'  - {section_name}: {len(text_sections[section_name])} 文字')
            
            # 4. 全テキストの結合
            all_text = ' '.join(text_sections.values())
            self.stdout.write(f'全テキスト長: {len(all_text)} 文字')
            
            # テキストをファイルに保存（デバッグ用）
            if save_text:
                filename = f'debug_text_{company_code}_{doc_id}.txt'
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(all_text)
                self.stdout.write(f'テキストを保存: {filename}')
            
            # 5. キャッシュフロー抽出のデバッグ
            self.stdout.write('\n=== キャッシュフロー抽出デバッグ ===')
            cf_extractor = CashFlowExtractor()
            
            # デバッグ版抽出を実行
            debug_results = cf_extractor.debug_extract_cashflow_data(all_text)
            
            self.stdout.write(f"テキスト長: {debug_results['text_length']}")
            self.stdout.write(f"サンプルテキスト: {debug_results['sample_text'][:200]}...")
            
            # パターンマッチの詳細表示
            for cf_type, matches in debug_results['pattern_matches'].items():
                self.stdout.write(f'\n--- {cf_type} のマッチ結果 ---')
                if matches:
                    for match_info in matches:
                        self.stdout.write(f'  パターン {match_info["pattern_index"]}: {match_info["matches"]}')
                        self.stdout.write(f'    パターン: {match_info["pattern"][:100]}...')
                else:
                    self.stdout.write('  マッチなし')
            
            # 最終抽出結果
            self.stdout.write('\n=== 最終抽出結果 ===')
            extracted_values = debug_results['extracted_values']
            for cf_type, value in extracted_values.items():
                if value is not None:
                    self.stdout.write(f'{cf_type}: {value:,.0f} 百万円')
                else:
                    self.stdout.write(f'{cf_type}: 抽出失敗')
            
            # 6. テキスト内のキーワード検索
            self.stdout.write('\n=== キーワード検索 ===')
            keywords = ['キャッシュ', 'フロー', '営業', '投資', '財務', '活動', '百万円', '千円']
            for keyword in keywords:
                count = all_text.count(keyword)
                self.stdout.write(f'{keyword}: {count} 回出現')
            
            # 7. 手動パターンテスト
            self.stdout.write('\n=== 手動パターンテスト ===')
            import re
            
            # シンプルなパターンでテスト
            simple_patterns = [
                r'営業.*?(\d{1,6})',
                r'投資.*?(\d{1,6})',
                r'財務.*?(\d{1,6})',
                r'(\d{1,6}).*?百万',
                r'キャッシュ.*?(\d{1,6})',
            ]
            
            for pattern in simple_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                if matches:
                    self.stdout.write(f'パターン "{pattern}": {matches[:5]}')
            
            self.stdout.write('\n✅ デバッグ完了')
            
        except Exception as e:
            self.stdout.write(f'❌ エラー: {str(e)}')
            raise


# コマンドの使用例をシェルスクリプトで提供
debug_script = '''
#!/bin/bash

# キャッシュフロー抽出デバッグの実行例

echo "=== トヨタ自動車のキャッシュフロー抽出デバッグ ==="
python manage.py debug_cashflow 7203 --save-text

echo "=== ソフトバンクグループのキャッシュフロー抽出デバッグ ==="
python manage.py debug_cashflow 9984 --save-text

echo "=== 特定書類IDでのデバッグ ==="
# python manage.py debug_cashflow 7203 --document-id=S100W47T --save-text

echo "デバッグ完了！"
echo "保存されたテキストファイルを確認して、手動でキャッシュフロー数値を探してください"
'''
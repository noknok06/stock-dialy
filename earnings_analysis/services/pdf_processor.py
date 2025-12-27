# earnings_analysis/services/pdf_processor.py

import requests
import fitz  # PyMuPDF
from typing import Dict, Optional
from django.conf import settings
import os
import hashlib
import logging
try:
    import pymupdf as fitz  # 新しいバージョン
except ImportError:
    import fitz  # 古いバージョン
logger = logging.getLogger('earnings_analysis.tdnet')


class PDFProcessor:
    """
    PDFファイルの処理
    
    PDF URLからダウンロード→テキスト抽出を行う
    """
    
    def __init__(self):
        tdnet_settings = getattr(settings, 'TDNET_API_SETTINGS', {})
        self.cache_dir = tdnet_settings.get('CACHE_DIR', 'media/tdnet_cache')
        
        # キャッシュディレクトリ作成
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def download_pdf(self, pdf_url: str) -> Optional[str]:
        """
        PDFをダウンロード
        
        Args:
            pdf_url: PDF URL
        
        Returns:
            ダウンロードしたPDFのローカルパス or None
        """
        try:
            logger.info(f"PDFダウンロード開始: {pdf_url}")
            
            # URLからファイル名を生成（ハッシュ化）
            url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
            local_path = os.path.join(self.cache_dir, f"{url_hash}.pdf")
            
            # 既にダウンロード済みならそれを返す
            if os.path.exists(local_path):
                logger.info(f"キャッシュヒット: {local_path}")
                return local_path
            
            # PDFをダウンロード
            response = requests.get(pdf_url, timeout=60)
            response.raise_for_status()
            
            # ファイル保存
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"PDFダウンロード完了: {len(response.content)} bytes -> {local_path}")
            return local_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PDFダウンロードエラー: {e}")
            return None
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_path: str, max_pages: int = 50) -> Dict:
        """
        PDFからテキスト抽出
        
        Args:
            pdf_path: PDFファイルのローカルパス
            max_pages: 抽出する最大ページ数
        
        Returns:
            {
                'success': True/False,
                'text': 抽出したテキスト,
                'pages': ページ数,
                'error': エラーメッセージ
            }
        """
        try:
            logger.info(f"テキスト抽出開始: {pdf_path}")
            
            # PDFを開く
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # テキスト抽出（最大ページ数まで）
            extracted_text = []
            pages_to_process = min(total_pages, max_pages)
            
            for page_num in range(pages_to_process):
                page = doc[page_num]
                text = page.get_text()
                extracted_text.append(text)
            
            doc.close()
            
            full_text = "\n\n".join(extracted_text)
            
            logger.info(f"テキスト抽出完了: {total_pages}ページ中{pages_to_process}ページ処理, {len(full_text)}文字")
            
            return {
                'success': True,
                'text': full_text,
                'pages': total_pages,
                'processed_pages': pages_to_process,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"テキスト抽出エラー: {e}")
            return {
                'success': False,
                'text': '',
                'pages': 0,
                'processed_pages': 0,
                'error': str(e)
            }
    
    def process_pdf_url(self, pdf_url: str, max_pages: int = 50) -> Dict:
        """
        PDF URLからダウンロード→テキスト抽出を一括実行
        
        Args:
            pdf_url: PDF URL
            max_pages: 抽出する最大ページ数
        
        Returns:
            {
                'success': True/False,
                'text': 抽出したテキスト,
                'pdf_path': ローカルPDFパス,
                'pages': ページ数,
                'error': エラーメッセージ
            }
        """
        # PDFダウンロード
        pdf_path = self.download_pdf(pdf_url)
        if not pdf_path:
            return {
                'success': False,
                'text': '',
                'pdf_path': None,
                'pages': 0,
                'error': 'PDFのダウンロードに失敗しました'
            }
        
        # テキスト抽出
        result = self.extract_text_from_pdf(pdf_path, max_pages)
        
        if result['success']:
            result['pdf_path'] = pdf_path
            return result
        else:
            return {
                'success': False,
                'text': '',
                'pdf_path': pdf_path,
                'pages': 0,
                'error': result['error']
            }
    
    def extract_metadata_from_text(self, text: str) -> Dict:
        """
        テキストから基本情報を推測
        
        Args:
            text: 抽出したテキスト
        
        Returns:
            {
                'company_name': 推測された企業名,
                'company_code': 推測された証券コード,
                'disclosure_type': 推測された開示種別,
                'title': 推測されたタイトル
            }
        """
        import re
        
        metadata = {
            'company_name': '',
            'company_code': '',
            'disclosure_type': 'other',
            'title': ''
        }
        
        # 最初の500文字から推測
        header_text = text[:500]
        
        # 証券コード抽出（4桁の数字）
        code_match = re.search(r'証券コード[：:]\s*(\d{4})', header_text)
        if code_match:
            metadata['company_code'] = code_match.group(1)
        
        # 企業名抽出（株式会社を含む）
        company_match = re.search(r'([^　\s]{2,20}株式会社)', header_text)
        if company_match:
            metadata['company_name'] = company_match.group(1)
        
        # 開示種別判定
        if '決算短信' in text:
            metadata['disclosure_type'] = 'earnings'
            metadata['title'] = '決算短信'
        elif '業績予想' in text:
            metadata['disclosure_type'] = 'forecast'
            metadata['title'] = '業績予想修正'
        elif '配当' in text:
            metadata['disclosure_type'] = 'dividend'
            metadata['title'] = '配当予想修正'
        elif '自己株式' in text:
            metadata['disclosure_type'] = 'buyback'
            metadata['title'] = '自己株式取得'
        
        logger.info(f"メタデータ抽出: {metadata}")
        return metadata
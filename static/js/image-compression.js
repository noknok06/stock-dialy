/**
 * 共通画像圧縮機能 - WebP対応版
 * ファイルパス: static/js/image-compression.js
 */

class ImageCompressionHandler {
  constructor() {
    this.validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
  }

  /**
   * 画像圧縮関数（WebP対応版）
   * @param {File} file - 元画像ファイル
   * @param {number} maxWidth - 最大幅
   * @param {number} maxHeight - 最大高さ
   * @param {number} quality - 品質 (0.0-1.0)
   * @returns {Promise<Blob>} 圧縮された画像Blob
   */
  compressImage(file, maxWidth = 800, maxHeight = 600, quality = 0.8) {
    return new Promise((resolve, reject) => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();
      
      img.onload = () => {
        try {
          // アスペクト比を保持して最大サイズ内にリサイズ
          const { width, height } = this.calculateSize(img.width, img.height, maxWidth, maxHeight);
          
          canvas.width = width;
          canvas.height = height;
          
          // 画像を描画
          ctx.drawImage(img, 0, 0, width, height);
          
          // WebP対応チェックと形式選択
          const bestFormat = this.getBestImageFormat();
          
          console.log(`圧縮形式: ${bestFormat}`);
          
          // 圧縮された画像をBlobとして取得
          canvas.toBlob((blob) => {
            if (blob) {
              console.log(`圧縮完了: ${this.formatFileSize(file.size)} → ${this.formatFileSize(blob.size)} (${bestFormat})`);
              resolve(blob);
            } else {
              reject(new Error('画像の圧縮に失敗しました'));
            }
          }, bestFormat, quality);
        } catch (error) {
          reject(error);
        }
      };
      
      img.onerror = () => reject(new Error('画像の読み込みに失敗しました'));
      img.src = URL.createObjectURL(file);
    });
  }

  /**
   * ブラウザの対応状況に応じて最適な画像形式を取得
   * @returns {string} 最適な画像形式
   */
  getBestImageFormat() {
    // AVIF 対応チェック（最新技術、最も小さい）
    if (this.supportsImageFormat('image/avif')) {
      return 'image/avif';
    }
    
    // WebP 対応チェック（JPEG より 25-35% 小さい）
    if (this.supportsImageFormat('image/webp')) {
      return 'image/webp';
    }
    
    // フォールバック: JPEG
    return 'image/jpeg';
  }

  /**
   * ブラウザが指定した画像形式をサポートしているかチェック
   * @param {string} format - 画像形式 ('image/webp', 'image/avif', etc.)
   * @returns {boolean} サポート状況
   */
  supportsImageFormat(format) {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    
    try {
      const dataURL = canvas.toDataURL(format, 0.1);
      return dataURL.startsWith(`data:${format}`);
    } catch (e) {
      return false;
    }
  }

  /**
   * 画像形式から適切なファイル拡張子を取得
   * @param {string} mimeType - MIME タイプ
   * @returns {string} ファイル拡張子
   */
  getFileExtension(mimeType) {
    const extensionMap = {
      'image/webp': 'webp',
      'image/avif': 'avif',
      'image/jpeg': 'jpg',
      'image/png': 'png',
      'image/gif': 'gif'
    };
    return extensionMap[mimeType] || 'jpg';
  }

  /**
   * ファイル名の拡張子を変更
   * @param {string} fileName - 元のファイル名
   * @param {string} newExtension - 新しい拡張子
   * @returns {string} 新しいファイル名
   */
  changeFileExtension(fileName, newExtension) {
    const baseName = fileName.replace(/\.[^/.]+$/, '');
    return `${baseName}.${newExtension}`;
  }

  /**
   * サイズ計算関数
   * @param {number} width - 元幅
   * @param {number} height - 元高さ
   * @param {number} maxWidth - 最大幅
   * @param {number} maxHeight - 最大高さ
   * @returns {Object} 計算されたサイズ
   */
  calculateSize(width, height, maxWidth, maxHeight) {
    if (width <= maxWidth && height <= maxHeight) {
      return { width, height };
    }
    
    const ratio = Math.min(maxWidth / width, maxHeight / height);
    return {
      width: Math.round(width * ratio),
      height: Math.round(height * ratio)
    };
  }

  /**
   * ファイルサイズを人間が読める形式に変換
   * @param {number} bytes - バイト数
   * @returns {string} フォーマットされたファイルサイズ
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  /**
   * ファイルタイプ検証
   * @param {File} file - 検証するファイル
   * @returns {boolean} 有効なファイルタイプかどうか
   */
  validateFileType(file) {
    return this.validTypes.includes(file.type);
  }

  /**
   * 汎用画像処理関数（WebP対応版）
   * @param {HTMLInputElement} inputElement - ファイル入力要素
   * @param {HTMLImageElement} previewElement - プレビュー画像要素
   * @param {HTMLElement} containerElement - プレビューコンテナ要素
   * @param {Object} options - 圧縮オプション
   */
  async handleImageUpload(inputElement, previewElement, containerElement, options = {}) {
    const file = inputElement.files[0];
    
    const config = {
      maxWidth: options.maxWidth || 600,
      maxHeight: options.maxHeight || 450,
      quality: options.quality || 0.75,        // WebP対応で品質向上
      maxFileSize: options.maxFileSize || 5 * 1024 * 1024,
      compressionThreshold: options.compressionThreshold || 0, // 全ファイル圧縮
      uploadArea: options.uploadArea || null,
      onCompressionStart: options.onCompressionStart || null,
      onCompressionEnd: options.onCompressionEnd || null,
      onError: options.onError || null
    };
    
    if (!file) {
      containerElement.style.display = 'none';
      if (config.uploadArea) config.uploadArea.style.display = 'block';
      return;
    }
    
    // ファイルタイプチェック
    if (!this.validateFileType(file)) {
      const message = 'JPEG、PNG、GIF、WebP形式の画像ファイルのみアップロード可能です。';
      if (config.onError) {
        config.onError(message);
      } else {
        alert(message);
      }
      this.clearInput(inputElement, containerElement, config.uploadArea);
      return;
    }
    
    try {
      console.log('元のファイルサイズ:', this.formatFileSize(file.size));
      console.log('元のファイル形式:', file.type);
      
      let processedFile = file;
      
      // 全ファイル圧縮（compressionThreshold: 0 で強制実行）
      const shouldCompress = config.compressionThreshold === 0 || file.size > config.compressionThreshold;
      
      if (shouldCompress) {
        if (config.onCompressionStart) {
          config.onCompressionStart(file);
        }
        
        // 最適形式で圧縮実行
        processedFile = await this.compressImage(file, config.maxWidth, config.maxHeight, config.quality);
        
        console.log('圧縮後のファイルサイズ:', this.formatFileSize(processedFile.size));
        
        // 圧縮率を計算
        const compressionRate = ((file.size - processedFile.size) / file.size * 100).toFixed(1);
        console.log(`圧縮率: ${compressionRate}%`);
        
        // 最適な形式でFileオブジェクトを作成
        const bestFormat = this.getBestImageFormat();
        const fileExtension = this.getFileExtension(bestFormat);
        const fileName = this.changeFileExtension(file.name, fileExtension);
        
        const compressedFile = new File([processedFile], fileName, {
          type: bestFormat,
          lastModified: Date.now()
        });
        
        // DataTransferでファイルを設定
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(compressedFile);
        inputElement.files = dataTransfer.files;
        
        if (config.onCompressionEnd) {
          config.onCompressionEnd(file, processedFile);
        }
      }
      
      // 最終サイズチェック
      if (processedFile.size > config.maxFileSize) {
        const message = `画像ファイルが大きすぎます (${this.formatFileSize(processedFile.size)})。\n別の画像を選択してください。`;
        if (config.onError) {
          config.onError(message);
        } else {
          alert(message);
        }
        this.clearInput(inputElement, containerElement, config.uploadArea);
        return;
      }
      
      // プレビュー表示
      const reader = new FileReader();
      reader.onload = (e) => {
        previewElement.src = e.target.result;
        containerElement.style.display = 'block';
        if (config.uploadArea) config.uploadArea.style.display = 'none';
      };
      reader.readAsDataURL(processedFile);
      
    } catch (error) {
      console.error('画像処理エラー:', error);
      const message = '画像の処理中にエラーが発生しました。';
      if (config.onError) {
        config.onError(message, error);
      } else {
        alert(message);
      }
      this.clearInput(inputElement, containerElement, config.uploadArea);
    }
  }

  /**
   * 入力とプレビューをクリア
   * @param {HTMLInputElement} inputElement - ファイル入力要素
   * @param {HTMLElement} containerElement - プレビューコンテナ要素
   * @param {HTMLElement} uploadArea - アップロードエリア要素
   */
  clearInput(inputElement, containerElement, uploadArea = null) {
    inputElement.value = '';
    containerElement.style.display = 'none';
    if (uploadArea) uploadArea.style.display = 'block';
  }

  /**
   * ドラッグ&ドロップ機能を設定
   * @param {HTMLElement} dropArea - ドロップエリア要素
   * @param {HTMLInputElement} inputElement - ファイル入力要素
   * @param {Function} handleUpload - アップロード処理関数
   */
  setupDragAndDrop(dropArea, inputElement, handleUpload) {
    const events = ['dragenter', 'dragover', 'dragleave', 'drop'];
    
    events.forEach(eventName => {
      dropArea.addEventListener(eventName, this.preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
      dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'), false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
      dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'), false);
    });
    
    dropArea.addEventListener('drop', async (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      
      if (files.length > 0) {
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(files[0]);
        inputElement.files = dataTransfer.files;
        
        await handleUpload();
      }
    }, false);
  }

  /**
   * デフォルトのドラッグイベント処理を防ぐ
   * @param {Event} e - イベントオブジェクト
   */
  preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }
}

// グローバルに利用可能にする
window.ImageCompressionHandler = ImageCompressionHandler;

// 使用例のヘルパー関数
window.setupImageCompression = function(config) {
  const handler = new ImageCompressionHandler();
  
  const inputElement = document.getElementById(config.inputId);
  const previewElement = document.getElementById(config.previewId);
  const containerElement = document.getElementById(config.containerId);
  const uploadArea = config.uploadAreaSelector ? document.querySelector(config.uploadAreaSelector) : null;
  const removeBtn = config.removeBtnId ? document.getElementById(config.removeBtnId) : null;
  
  if (!inputElement || !previewElement || !containerElement) {
    console.error('必要な要素が見つかりません:', config);
    return;
  }
  
  // ファイル選択時の処理
  inputElement.addEventListener('change', async () => {
    await handler.handleImageUpload(inputElement, previewElement, containerElement, config.options || {});
  });
  
  // 削除ボタンの処理
  if (removeBtn) {
    removeBtn.addEventListener('click', () => {
      handler.clearInput(inputElement, containerElement, uploadArea);
    });
  }
  
  // ドラッグ&ドロップの設定
  if (uploadArea) {
    handler.setupDragAndDrop(uploadArea, inputElement, async () => {
      await handler.handleImageUpload(inputElement, previewElement, containerElement, config.options || {});
    });
  }
  
  return handler;
};

// ブラウザ対応状況のログ出力
document.addEventListener('DOMContentLoaded', function() {
  console.log('=== 画像形式対応状況 ===');
  
  const canvas = document.createElement('canvas');
  canvas.width = 1;
  canvas.height = 1;
  
  const formats = [
    { name: 'AVIF', mime: 'image/avif', savings: '50%' },
    { name: 'WebP', mime: 'image/webp', savings: '25-35%' },
    { name: 'JPEG', mime: 'image/jpeg', savings: 'ベースライン' }
  ];
  
  formats.forEach(format => {
    try {
      const supported = canvas.toDataURL(format.mime, 0.1).startsWith(`data:${format.mime}`);
      console.log(`${format.name}: ${supported ? '✅対応' : '❌非対応'} (JPEG比 ${format.savings} 削減)`);
    } catch (e) {
      console.log(`${format.name}: ❌非対応 (エラー)`);
    }
  });
  
  console.log('========================');
});
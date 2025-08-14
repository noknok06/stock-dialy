/**
 * 共通画像圧縮機能
 * ファイルパス: static/js/image-compression.js
 */

class ImageCompressionHandler {
  constructor() {
    this.validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
  }

  /**
   * 画像圧縮関数
   * @param {File} file - 元画像ファイル
   * @param {number} maxWidth - 最大幅
   * @param {number} maxHeight - 最大高さ
   * @param {number} quality - JPEG品質 (0.0-1.0)
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
          
          // 圧縮された画像をBlobとして取得
          canvas.toBlob((blob) => {
            if (blob) {
              resolve(blob);
            } else {
              reject(new Error('画像の圧縮に失敗しました'));
            }
          }, 'image/jpeg', quality);
        } catch (error) {
          reject(error);
        }
      };
      
      img.onerror = () => reject(new Error('画像の読み込みに失敗しました'));
      img.src = URL.createObjectURL(file);
    });
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
   * 汎用画像処理関数
   * @param {HTMLInputElement} inputElement - ファイル入力要素
   * @param {HTMLImageElement} previewElement - プレビュー画像要素
   * @param {HTMLElement} containerElement - プレビューコンテナ要素
   * @param {Object} options - 圧縮オプション
   */
  async handleImageUpload(inputElement, previewElement, containerElement, options = {}) {
    const file = inputElement.files[0];
    
    const config = {
      maxWidth: options.maxWidth || 800,
      maxHeight: options.maxHeight || 600,
      quality: options.quality || 0.8,
      maxFileSize: options.maxFileSize || 5 * 1024 * 1024, // 5MB
      compressionThreshold: options.compressionThreshold || 1 * 1024 * 1024, // 2MB
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
      
      let processedFile = file;
      
      // 圧縮閾値以上の場合は圧縮
      if (file.size > config.compressionThreshold) {
        if (config.onCompressionStart) {
          config.onCompressionStart(file);
        }
        
        processedFile = await this.compressImage(file, config.maxWidth, config.maxHeight, config.quality);
        
        console.log('圧縮後のファイルサイズ:', this.formatFileSize(processedFile.size));
        
        // 圧縮ファイルをinput要素に設定
        const dataTransfer = new DataTransfer();
        const compressedFile = new File([processedFile], file.name, {
          type: 'image/jpeg',
          lastModified: Date.now()
        });
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
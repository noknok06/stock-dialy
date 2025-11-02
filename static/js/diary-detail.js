/**
 * diary-detail.js - 日記詳細ページ専用スクリプト
 * 継続記録削除、フォーム制御、画像圧縮機能など
 */

// ========== 継続記録削除関連のJavaScript ==========
(function() {
  let deleteNoteId = null;

  // 削除確認モーダルを表示
  function showDeleteModal() {
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  // 削除確認モーダルを閉じる
  function closeDeleteModal() {
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
      modal.style.display = 'none';
      document.body.style.overflow = '';
    }
    deleteNoteId = null;
  }

  // detail画面専用の削除確認関数（モーダル版）
  window.confirmDeleteNoteModal = function(noteId, noteDate, noteType) {
    deleteNoteId = noteId;
    const deleteTargetInfo = document.getElementById('deleteTargetInfo');
    if (deleteTargetInfo) {
      deleteTargetInfo.querySelector('div').innerHTML = 
        `<i class="bi bi-calendar-date me-2"></i>${noteDate}<br><span class="text-muted">${noteType}</span>`;
    }
    showDeleteModal();
  };

  // detail画面の継続記録削除機能
  if (typeof window.confirmDeleteNote === 'undefined') {
    window.confirmDeleteNote = function(noteId, noteDate, noteType, diaryId) {
      if (confirm(`${noteDate}の${noteType}を削除しますか？\n\nこの操作は元に戻せません。`)) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                        document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
        
        if (!csrfToken) {
          alert('CSRFトークンが見つかりません。ページを再読み込みしてください。');
          return;
        }

        fetch(`/stockdiary/${diaryId}/note/${noteId}/delete/`, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
          }
        })
        .then(response => {
          if (response.ok) {
            window.location.reload();
          } else {
            throw new Error('削除に失敗しました');
          }
        })
        .catch(error => {
          console.error('Delete error:', error);
          alert('削除に失敗しました。もう一度お試しください。');
        });
      }
    };
  }

  // 削除実行関数（detail画面専用）
  function executeDelete(noteId) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                     document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    
    if (!csrfToken) {
      alert('CSRFトークンが見つかりません。ページを再読み込みしてください。');
      return;
    }

    // diaryIdを動的に取得（URLから）
    const diaryId = window.location.pathname.match(/\/stockdiary\/(\d+)\//)?.[1];
    if (!diaryId) {
      alert('日記IDが取得できませんでした。');
      return;
    }

    fetch(`/stockdiary/${diaryId}/note/${noteId}/delete/`, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken
      }
    })
    .then(response => {
      if (response.ok) {
        closeDeleteModal();
        window.location.reload();
      } else {
        throw new Error('削除に失敗しました');
      }
    })
    .catch(error => {
      console.error('Delete error:', error);
      alert('削除に失敗しました。もう一度お試しください。');
      closeDeleteModal();
    });
  }

  // グローバル削除実行関数（tab_notes.htmlで使用）
  if (typeof window.executeDeleteNote === 'undefined') {
    window.executeDeleteNote = function(noteId, diaryId) {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                       document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
      
      if (!csrfToken) {
        alert('CSRFトークンが見つかりません。ページを再読み込みしてください。');
        return;
      }

      fetch(`/stockdiary/${diaryId}/note/${noteId}/delete/`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken
        }
      })
      .then(response => {
        if (response.ok) {
          // home画面の場合はタブコンテンツを再読み込み
          if (window.location.pathname === '/stockdiary/') {
            const activeTab = document.querySelector(`#notes-tab-${diaryId}`);
            if (activeTab) {
              activeTab.click();
            } else {
              window.location.reload();
            }
          } else {
            window.location.reload();
          }
        } else {
          throw new Error('削除に失敗しました');
        }
      })
      .catch(error => {
        console.error('Delete error:', error);
        alert('削除に失敗しました。もう一度お試しください。');
      });
    };
  }

  // イベントリスナーの設定
  document.addEventListener('DOMContentLoaded', function() {
    // キャンセルボタン
    const cancelBtn = document.getElementById('cancelDelete');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', closeDeleteModal);
    }

    // 削除実行ボタン
    const confirmBtn = document.getElementById('confirmDelete');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', function() {
        if (deleteNoteId) {
          executeDelete(deleteNoteId);
        }
      });
    }

    // モーダル外クリックで閉じる
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
      modal.addEventListener('click', function(e) {
        if (e.target === modal) {
          closeDeleteModal();
        }
      });
    }
  });
})();

// ========== スワイプヒント制御 ==========
function hideSwipeHint() {
  const hint = document.getElementById('swipeHint');
  if (hint) {
    hint.classList.add('fade-out');
    setTimeout(() => {
      hint.style.display = 'none';
    }, 500);
    
    // ローカルストレージに保存（今後表示しない）
    localStorage.setItem('swipeHintDismissed', 'true');
  }
}

// ========== オプションピルとフォーム制御 ==========
document.addEventListener('DOMContentLoaded', function() {
  // スワイプヒントの制御
  const swipeHint = document.getElementById('swipeHint');
  const isMobile = window.innerWidth < 768;
  const isDismissed = localStorage.getItem('swipeHintDismissed');
  
  if (swipeHint && isMobile && !isDismissed) {
    setTimeout(() => {
      swipeHint.classList.add('show');
    }, 1000);
    
    // 8秒後に自動で非表示
    setTimeout(() => {
      hideSwipeHint();
    }, 8000);
  }
  
  // オプションピルのイベントリスナー
  document.querySelectorAll('.option-pill').forEach(pill => {
    pill.addEventListener('click', function() {
      const target = this.getAttribute('data-target');
      const value = this.getAttribute('data-value');
      const targetInput = document.getElementById(target);
      
      if (targetInput) {
        // 同じグループの他のピルからactiveクラスを削除
        const group = this.closest('.option-pills');
        group.querySelectorAll('.option-pill').forEach(p => p.classList.remove('active'));
        
        // このピルにactiveクラスを追加
        this.classList.add('active');
        
        // 隠しフィールドに値を設定
        targetInput.value = value;
      }
    });
  });
  
  // 株価取得ボタンの処理
  const fetchPriceBtn = document.getElementById('fetch-note-price');
  if (fetchPriceBtn) {
    fetchPriceBtn.addEventListener('click', function() {
      // URLから株式シンボルを動的に取得するか、data属性から取得
      const stockSymbol = this.dataset.stockSymbol || 
                         document.querySelector('[data-stock-symbol]')?.dataset.stockSymbol;
      const priceInput = document.getElementById('note_current_price');
      
      if (!stockSymbol) {
        alert('株式シンボルが取得できませんでした。');
        return;
      }
      
      this.disabled = true;
      this.innerHTML = '<i class="bi bi-hourglass-split"></i><span class="d-none d-sm-inline ms-1">取得中...</span>';
      
      fetch(`/stockdiary/api/stock/price/${stockSymbol}/`)
        .then(response => response.json())
        .then(data => {
          if (data.price && priceInput) {
            priceInput.value = data.price;
          }
        })
        .catch(error => {
          console.error('価格取得エラー:', error);
        })
        .finally(() => {
          this.disabled = false;
          this.innerHTML = '<i class="bi bi-arrow-repeat"></i><span class="d-none d-sm-inline ms-1">取得</span>';
        });
    });
  }

  // フォーム切り替えボタンのアイコン変更
  const toggleButton = document.getElementById('toggleNoteForm');
  const formCollapse = document.getElementById('noteFormCollapse');
  
  if (toggleButton && formCollapse) {
    formCollapse.addEventListener('shown.bs.collapse', function() {
      const icon = toggleButton.querySelector('i');
      if (icon) {
        icon.className = 'bi bi-dash-circle me-1';
      }
      toggleButton.classList.add('btn-secondary');
      toggleButton.classList.remove('btn-primary');
    });
    
    formCollapse.addEventListener('hidden.bs.collapse', function() {
      const icon = toggleButton.querySelector('i');
      if (icon) {
        icon.className = 'bi bi-plus-circle me-1';
      }
      toggleButton.classList.add('btn-primary');
      toggleButton.classList.remove('btn-secondary');
      
      // フォームをリセット
      const form = document.getElementById('quickNoteForm');
      if (form) {
        form.reset();
        // オプションピルのアクティブ状態をリセット
        document.querySelectorAll('.option-pill').forEach(pill => pill.classList.remove('active'));
        document.querySelector('.option-pill[data-value="analysis"]')?.classList.add('active');
        document.querySelector('.option-pill[data-value="medium"]')?.classList.add('active');
        // 隠しフィールドもリセット
        const noteTypeInput = document.getElementById('note_type');
        const noteImportanceInput = document.getElementById('note_importance');
        if (noteTypeInput) noteTypeInput.value = 'analysis';
        if (noteImportanceInput) noteImportanceInput.value = 'medium';
      }
    });
  }
  
  // URLハッシュで直接フォームを開く（#add-note）
  if (window.location.hash === '#add-note') {
    const formCollapse = document.getElementById('noteFormCollapse');
    if (formCollapse && typeof bootstrap !== 'undefined') {
      const bsCollapse = new bootstrap.Collapse(formCollapse, {
        show: true
      });
    }
  }
});

// ========== 継続記録用画像圧縮機能 ==========
document.addEventListener('DOMContentLoaded', function() {
  // 画像圧縮機能が利用可能かチェック
  if (typeof window.ImageCompressionHandler === 'undefined') {
    console.error('❌ ImageCompressionHandler が読み込まれていません');
    // console.log('💡 static/js/image-compression.js が正しく読み込まれているか確認してください');
    return;
  }

  // WebP対応状況を確認
  function checkWebPSupport() {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    try {
      const dataURL = canvas.toDataURL('image/webp', 0.1);
      return dataURL.startsWith('data:image/webp');
    } catch (e) {
      return false;
    }
  }
  
  const supportsWebP = checkWebPSupport();
  
  // 継続記録用の画像圧縮設定（必須要素の存在確認を強化）
  const noteImageInput = document.getElementById('note_image');
  const noteImagePreview = document.getElementById('note-image-preview');
  const noteImageContainer = document.getElementById('note-image-preview-container');
  const noteUploadArea = document.querySelector('.image-upload-area-note');
  const noteRemoveBtn = document.getElementById('note-remove-image');
  
  // 必須要素が揃っている場合のみ圧縮機能を設定
  if (noteImageInput && noteImagePreview && noteImageContainer) {
    
    try {
      const handler = window.setupImageCompression({
        inputId: 'note_image',
        previewId: 'note-image-preview',
        containerId: 'note-image-preview-container',
        uploadAreaSelector: '.image-upload-area-note',
        removeBtnId: 'note-remove-image',
        options: {
          maxWidth: 900,                    // 継続記録はコンパクトに
          maxHeight: 675,                   // 継続記録はコンパクトに
          quality: 0.9,                     // WebP対応で品質維持
          compressionThreshold: 2 * 1024 * 1024, // 2MB以上で圧縮
          maxFileSize: 3 * 1024 * 1024,     // 最大3MB（継続記録は小さめ）
          onCompressionStart: (file) => {
            const format = handler.getBestImageFormat();
            const formatName = format.replace('image/', '').toUpperCase();
            
            // 継続記録用の圧縮メッセージ表示
            showNoteCompressionMessage(`${formatName}形式で圧縮中...`);
          },
          onCompressionEnd: (original, compressed) => {
            const originalSize = handler.formatFileSize(original.size);
            const compressedSize = handler.formatFileSize(compressed.size);
            const reductionRate = ((original.size - compressed.size) / original.size * 100).toFixed(1);
            const format = handler.getBestImageFormat().replace('image/', '').toUpperCase();
            
            // 継続記録用の完了メッセージ表示
            showNoteCompressionMessage(
              `${format}圧縮完了: ${originalSize} → ${compressedSize} (${reductionRate}% 削減)`, 
              3000
            );
          },
          onError: (message, error) => {
            console.error('継続記録画像エラー:', error);
            showNoteCompressionMessage(`エラー: ${message}`, 4000);
          }
        }
      });
            
    } catch (error) {
      console.error('❌ 継続記録用画像圧縮機能の初期化に失敗:', error);
    }
  } else {
    console.warn('⚠️ 継続記録用画像要素が不足しているため、圧縮機能をスキップします');
  }
  
  // 継続記録用の圧縮メッセージ表示関数
  function showNoteCompressionMessage(message, duration = 0) {
    let messageElement = document.getElementById('note-compression-message');
    
    if (!messageElement) {
      messageElement = document.createElement('div');
      messageElement.id = 'note-compression-message';
      messageElement.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white;
        padding: 10px 16px;
        border-radius: 6px;
        box-shadow: 0 3px 10px rgba(40, 167, 69, 0.3);
        z-index: 9998;
        font-size: 13px;
        display: none;
        animation: noteSlideIn 0.3s ease-out;
        max-width: 280px;
        word-wrap: break-word;
      `;
      
      // 継続記録用アニメーション
      const style = document.createElement('style');
      style.textContent = `
        @keyframes noteSlideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes noteSlideOut {
          from { transform: translateX(0); opacity: 1; }
          to { transform: translateX(100%); opacity: 0; }
        }
      `;
      document.head.appendChild(style);
      
      document.body.appendChild(messageElement);
    }
    
    messageElement.textContent = message;
    messageElement.style.display = 'block';
    
    if (duration > 0) {
      setTimeout(() => {
        messageElement.style.animation = 'noteSlideOut 0.3s ease-in';
        setTimeout(() => {
          messageElement.style.display = 'none';
          messageElement.style.animation = '';
        }, 300);
      }, duration);
    }
  }
});

// ========== 画像モーダル表示機能 ==========
function showImageModal(imageUrl, title) {
  // 既存のモーダルを削除
  const existingModal = document.getElementById('imageModal');
  if (existingModal) {
    existingModal.remove();
  }
  
  // モーダルHTML作成
  const modalHtml = `
    <div class="modal fade" id="imageModal" tabindex="-1" aria-labelledby="imageModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-xl modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="imageModalLabel">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="閉じる"></button>
          </div>
          <div class="modal-body text-center p-0">
            <img src="${imageUrl}" class="img-fluid" alt="${title}" style="max-height: 80vh; object-fit: contain;">
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">閉じる</button>
            <a href="${imageUrl}" class="btn btn-primary" target="_blank">
              <i class="bi bi-download me-1"></i>画像を表示
            </a>
          </div>
        </div>
      </div>
    </div>
  `;
  
  // モーダルをDOMに追加
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  
  // モーダルを表示
  const modal = new bootstrap.Modal(document.getElementById('imageModal'));
  modal.show();
  
  // モーダルが閉じられたらDOMから削除
  document.getElementById('imageModal').addEventListener('hidden.bs.modal', function() {
    this.remove();
  });
}

// モーダル表示機能をグローバルで利用可能にする
window.showImageModal = showImageModal;

// ========== ツールチップ初期化 ==========
document.addEventListener('DOMContentLoaded', function() {
  // Bootstrap tooltipsの初期化
  if (typeof bootstrap !== 'undefined') {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }
});

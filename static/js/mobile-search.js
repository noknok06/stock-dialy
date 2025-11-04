// mobile-search.js - モバイル最適化検索フォーム用JavaScript

document.addEventListener('DOMContentLoaded', function() {
  // 要素の取得
  const advancedToggle = document.getElementById('advancedToggle');
  const advancedPanel = document.getElementById('advancedPanel');
  const mainSearchInput = document.getElementById('mainSearchInput');
  const searchSuggestions = document.getElementById('searchSuggestions');
  const searchForm = document.getElementById('optimizedSearchForm');
  const activeFilters = document.getElementById('activeFilters');
  const searchIndicator = document.getElementById('search-indicator');
  
  // 詳細検索パネルの切り替え
  if (advancedToggle && advancedPanel) {
    advancedToggle.addEventListener('click', function() {
      const isCollapsed = advancedPanel.classList.contains('collapsed');
      
      if (isCollapsed) {
        advancedPanel.classList.remove('collapsed');
        advancedPanel.classList.add('slide-down');
        this.innerHTML = '<i class="bi bi-x"></i>';
        this.setAttribute('aria-expanded', 'true');
        
        // 検索履歴を表示（あれば）
        loadSearchHistory();
      } else {
        advancedPanel.classList.add('collapsed');
        advancedPanel.classList.remove('slide-down');
        this.innerHTML = '<i class="bi bi-sliders"></i>';
        this.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // メイン検索入力のイベント処理
  if (mainSearchInput) {
    // フォーカス時の処理
    mainSearchInput.addEventListener('focus', function() {
      if (this.value.length > 0 && searchSuggestions) {
        searchSuggestions.style.display = 'block';
      }
    });

    // 入力時の処理（HTMXと併用）
    mainSearchInput.addEventListener('input', function() {
      const query = this.value.trim();
      
      // 検索履歴に追加（3文字以上で）
      if (query.length >= 3) {
        addToSearchHistory(query);
      }
      
      // サジェスチョンの表示/非表示制御
      if (query.length > 1) {
        // HTMXが自動的に処理するが、表示制御は手動で行う
        setTimeout(() => {
          if (searchSuggestions && searchSuggestions.children.length > 0) {
            searchSuggestions.style.display = 'block';
          }
        }, 100);
      } else if (searchSuggestions) {
        searchSuggestions.style.display = 'none';
      }
    });

    // Enterキーでの検索実行
    mainSearchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        searchForm.dispatchEvent(new Event('submit'));
      }
      
      // Escapeキーでサジェスチョンを閉じる
      if (e.key === 'Escape' && searchSuggestions) {
        searchSuggestions.style.display = 'none';
        this.blur();
      }
    });
  }

  // 外部クリックでサジェスチョンを閉じる
  document.addEventListener('click', function(e) {
    if (searchSuggestions && !e.target.closest('.main-search-wrapper')) {
      searchSuggestions.style.display = 'none';
    }
  });

  // HTMXのafter-swapイベントでサジェスチョンアイテムのクリックイベントを設定
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'searchSuggestions') {
      setupSuggestionClickHandlers();
    }
  });

  // フォーム送信時の処理
  if (searchForm) {
    searchForm.addEventListener('submit', function(e) {
      // インジケーター表示
      if (searchIndicator) {
        searchIndicator.style.display = 'flex';
      }
      
      // サジェスチョンを閉じる
      if (searchSuggestions) {
        searchSuggestions.style.display = 'none';
      }
      
      // 検索クエリを履歴に追加
      const query = mainSearchInput.value.trim();
      if (query.length >= 2) {
        addToSearchHistory(query);
      }
      
      // アクティブフィルターを更新
      setTimeout(updateActiveFilters, 100);
    });

  // タグクリック時のイベントリスナーを設定
  function setupTagClickHandlers() {
    const tagElements = document.querySelectorAll('.diary-tag');
    
    tagElements.forEach(tag => {
      // 既存のイベントリスナーを削除（重複防止）
      tag.removeEventListener('click', handleTagClick);
      
      // 新しいイベントリスナーを追加
      tag.addEventListener('click', handleTagClick);
      
      // クリック可能であることを示すスタイルを追加
      tag.style.cursor = 'pointer';
      tag.style.transition = 'all 0.2s ease';
      
      // ホバー効果を追加
      tag.addEventListener('mouseenter', function() {
        this.style.transform = 'scale(1.05)';
        this.style.opacity = '0.8';
      });
      
      tag.addEventListener('mouseleave', function() {
        this.style.transform = 'scale(1)';
        this.style.opacity = '1';
      });
    });
  }
  
  // タグクリック時の処理
  function handleTagClick(event) {
    event.preventDefault();
    event.stopPropagation(); // イベントの伝播を防ぐ（カードクリックを防ぐ）
    
    const tagElement = event.currentTarget;
    const tagId = tagElement.getAttribute('data-tag-id');
    const tagName = tagElement.textContent.trim();
    
    if (!tagId) {
      console.warn('タグIDが見つかりません');
      return;
    }
    
    // タグフィルターを適用
    applyTagFilter(tagId, tagName);
  }
  
  // タグフィルターを適用する関数
  function applyTagFilter(tagId, tagName) {
    // セレクトボックスの値を更新
    const tagFilterSelect = document.getElementById('tagFilter');
    if (tagFilterSelect) {
      tagFilterSelect.value = tagId;
    }
    
    // 詳細検索パネルが閉じている場合は開く
    const advancedPanel = document.getElementById('advancedPanel');
    const advancedToggle = document.getElementById('advancedToggle');
    
    if (advancedPanel && advancedPanel.classList.contains('collapsed')) {
      advancedPanel.classList.remove('collapsed');
      advancedPanel.classList.add('slide-down');
      
      if (advancedToggle) {
        advancedToggle.innerHTML = '<i class="bi bi-x"></i>';
        advancedToggle.setAttribute('aria-expanded', 'true');
      }
    }
    
    // 検索フォームを送信
    const searchForm = document.getElementById('optimizedSearchForm');
    if (searchForm) {
      // HTMXで検索を実行
      htmx.trigger(searchForm, 'submit');
      
      // ページ上部にスクロール（スムーズに）
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
      
      // ユーザーへのフィードバック
      showFilterNotification(tagName);
    }
  }
  
  // フィルター適用の通知を表示
  function showFilterNotification(tagName) {
    // 既存の通知を削除
    const existingNotification = document.querySelector('.filter-notification');
    if (existingNotification) {
      existingNotification.remove();
    }
    
    // 新しい通知を作成
    const notification = document.createElement('div');
    notification.className = 'filter-notification';
    notification.innerHTML = `
      <i class="bi bi-tag-fill me-2"></i>
      タグ「${tagName}」でフィルタリング中
    `;
    
    // 通知をページに追加
    document.body.appendChild(notification);
    
    // アニメーションで表示
    setTimeout(() => {
      notification.classList.add('show');
    }, 10);
    
    // 3秒後に非表示
    setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => {
        notification.remove();
      }, 300);
    }, 3000);
  }
  
  // HTMXのafterSwapイベント後にタグクリックハンドラーを再設定
  document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'diary-container') {
      setTimeout(setupTagClickHandlers, 100);
    }
  });
  
  // 初期セットアップ
  setupTagClickHandlers();

// バッジ更新関数を修正（グローバルスコープ）
if (typeof updateFilterBadges !== 'undefined') {
  const originalUpdateFilterBadges = updateFilterBadges;
  
  updateFilterBadges = function() {
    originalUpdateFilterBadges();
    
    // バッジ更新後にタグクリックハンドラーを再設定
    setTimeout(() => {
      const tagElements = document.querySelectorAll('.diary-tag');
      tagElements.forEach(tag => {
        tag.style.cursor = 'pointer';
      });
    }, 50);
  };
}

/* ========== タグクリック用CSS ========== */
const style = document.createElement('style');
style.textContent = `
  .diary-tag {
    cursor: pointer !important;
    user-select: none;
    position: relative;
    overflow: hidden;
  }
  
  .diary-tag::before {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.2);
    opacity: 0;
    transition: opacity 0.2s ease;
  }
  
  .diary-tag:hover::before {
    opacity: 1;
  }
  
  .diary-tag:active {
    transform: scale(0.95);
  }
  
  /* フィルター通知 */
  .filter-notification {
    position: fixed;
    top: 80px;
    right: 20px;
    background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
    color: white;
    padding: 12px 20px;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    z-index: 1050;
    display: flex;
    align-items: center;
    font-size: 0.9rem;
    font-weight: 500;
    opacity: 0;
    transform: translateX(400px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  
  .filter-notification.show {
    opacity: 1;
    transform: translateX(0);
  }
  
  @media (max-width: 768px) {
    .filter-notification {
      top: 70px;
      right: 10px;
      left: 10px;
      font-size: 0.85rem;
      padding: 10px 15px;
    }
  }
  
  /* ダークモード対応 */
  .dark-mode .filter-notification,
  [data-theme="dark"] .filter-notification {
    background: linear-gradient(135deg, var(--dm-primary), var(--dm-primary-hover));
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  }
`;
  document.head.appendChild(style);   

  // フィルター選択時の自動検索
  const filterSelects = document.querySelectorAll('#tagFilter, #statusFilter, #sectorFilter, #dateRange');
  filterSelects.forEach(select => {
    select.addEventListener('change', function() {
      // フォームを自動送信（HTMXが処理）
      const changeEvent = new Event('change', { bubbles: true });
      this.dispatchEvent(changeEvent);
      
      // アクティブフィルターを更新
      setTimeout(updateActiveFilters, 100);
    });
  });

  // 初期化時にアクティブフィルターを設定
  updateActiveFilters();
});

// サジェスチョンアイテムのクリックハンドラーを設定
function setupSuggestionClickHandlers() {
  const suggestionItems = document.querySelectorAll('#searchSuggestions .search-suggestion-item, #searchSuggestions .suggestion-item');
  
  suggestionItems.forEach(item => {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      
      const mainSearchInput = document.getElementById('mainSearchInput');
      const searchSuggestions = document.getElementById('searchSuggestions');
      
      // テキストを取得（複数のフォーマットに対応）
      let text = '';
      const textElement = this.querySelector('.suggestion-text');
      if (textElement) {
        text = textElement.textContent.trim();
      } else {
        text = this.textContent.trim();
      }
      
      if (mainSearchInput && text) {
        mainSearchInput.value = text;
        
        // サジェスチョンを閉じる
        if (searchSuggestions) {
          searchSuggestions.style.display = 'none';
        }
        
        // 検索を実行
        const searchForm = document.getElementById('optimizedSearchForm');
        if (searchForm) {
          // HTMXでフォーム送信
          htmx.trigger(searchForm, 'submit');
        }
      }
    });
  });
}

// フィルターチップの削除機能
function removeFilter(filterType) {
  const form = document.getElementById('optimizedSearchForm');
  if (!form) return;
  
  // 該当するフィルターフィールドをクリア
  const filterElement = form.querySelector(`[name="${filterType}"]`);
  if (filterElement) {
    filterElement.value = '';
    
    // HTMXで更新
    htmx.trigger(form, 'submit');
  }
  
  // アクティブフィルターを更新
  setTimeout(updateActiveFilters, 100);
}

// アクティブフィルターの表示を更新
function updateActiveFilters() {
  const activeFilters = document.getElementById('activeFilters');
  if (!activeFilters) return;
  
  const form = document.getElementById('optimizedSearchForm');
  if (!form) return;
  
  let hasFilters = false;
  const filterContainer = activeFilters;
  
  // 既存のフィルターチップをクリア
  filterContainer.innerHTML = '';
  
  // 各フィルターをチェック
  const filters = [
    { name: 'tag', type: 'select', getLabel: (value) => {
      const option = form.querySelector(`select[name="tag"] option[value="${value}"]`);
      return option ? option.textContent : value;
    }},
    { name: 'status', type: 'select', getLabel: (value) => {
      const labels = {
        'active': '保有中',
        'memo': 'メモのみ'
      };
      return labels[value] || value;
    }},
    { name: 'sector', type: 'select', getLabel: (value) => value },
    { name: 'date_range', type: 'select', getLabel: (value) => {
      const labels = {
        '1w': '過去1週間',
        '1m': '過去1ヶ月',
        '3m': '過去3ヶ月',
        '6m': '過去6ヶ月',
        '1y': '過去1年'
      };
      return labels[value] || value;
    }}
  ];
  
  filters.forEach(filter => {
    const element = form.querySelector(`[name="${filter.name}"]`);
    if (element && element.value) {
      hasFilters = true;
      
      const chip = document.createElement('div');
      chip.className = 'filter-chip';
      chip.setAttribute('data-filter', filter.name);
      chip.setAttribute('data-value', element.value);
      
      chip.innerHTML = `
        <span>${filter.getLabel(element.value)}</span>
        <button type="button" class="filter-chip-remove" onclick="removeFilter('${filter.name}')">
          <i class="bi bi-x"></i>
        </button>
      `;
      
      filterContainer.appendChild(chip);
    }
  });
  
  // アクティブフィルターコンテナの表示/非表示
  activeFilters.style.display = hasFilters ? 'block' : 'none';
}

// 検索履歴の管理
function addToSearchHistory(query) {
  if (!query || query.length < 2) return;
  
  try {
    let history = JSON.parse(localStorage.getItem('search_history') || '[]');
    
    // 重複を除去
    history = history.filter(item => item !== query);
    
    // 先頭に追加
    history.unshift(query);
    
    // 最大10件に制限
    history = history.slice(0, 10);
    
    localStorage.setItem('search_history', JSON.stringify(history));
  } catch (e) {
    console.warn('検索履歴の保存に失敗しました:', e);
  }
}

function loadSearchHistory() {
  const historyContainer = document.getElementById('historyItems');
  const historySection = document.getElementById('searchHistory');
  
  if (!historyContainer || !historySection) return;
  
  try {
    const history = JSON.parse(localStorage.getItem('search_history') || '[]');
    
    if (history.length === 0) {
      historySection.style.display = 'none';
      return;
    }
    
    historyContainer.innerHTML = '';
    
    history.slice(0, 5).forEach(item => {
      const historyItem = document.createElement('div');
      historyItem.className = 'history-item';
      historyItem.textContent = item;
      historyItem.addEventListener('click', function() {
        const mainSearchInput = document.getElementById('mainSearchInput');
        if (mainSearchInput) {
          mainSearchInput.value = item;
          const searchForm = document.getElementById('optimizedSearchForm');
          if (searchForm) {
            htmx.trigger(searchForm, 'submit');
          }
        }
      });
      
      historyContainer.appendChild(historyItem);
    });
    
    historySection.style.display = 'block';
    
  } catch (e) {
    console.warn('検索履歴の読み込みに失敗しました:', e);
    historySection.style.display = 'none';
  }
}

// HTMXイベントのリスナー
document.body.addEventListener('htmx:beforeRequest', function(evt) {
  const searchIndicator = document.getElementById('search-indicator');
  if (searchIndicator && evt.detail.elt.id === 'optimizedSearchForm') {
    searchIndicator.style.display = 'flex';
  }
});

document.body.addEventListener('htmx:afterRequest', function(evt) {
  const searchIndicator = document.getElementById('search-indicator');
  if (searchIndicator && evt.detail.elt.id === 'optimizedSearchForm') {
    searchIndicator.style.display = 'none';
  }
  
  // 検索結果情報を更新
  const resultsInfo = document.getElementById('searchResultsInfo');
  if (resultsInfo) {
    resultsInfo.style.display = 'flex';
  }
});

// エラーハンドリング
document.body.addEventListener('htmx:responseError', function(evt) {
  const searchIndicator = document.getElementById('search-indicator');
  if (searchIndicator) {
    searchIndicator.style.display = 'none';
  }
  
  console.error('検索リクエストエラー:', evt.detail);
});

// 検索フィールドの自動リサイズ（テキストエリアの場合）
function autoResizeTextarea(element) {
  if (element.tagName.toLowerCase() === 'textarea') {
    element.style.height = 'auto';
    element.style.height = (element.scrollHeight) + 'px';
  }
}

// ユーティリティ関数：デバウンス
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// 検索フォームの状態管理
const SearchFormManager = {
  // フォームの状態を保存
  saveState: function() {
    const form = document.getElementById('optimizedSearchForm');
    if (!form) return;
    
    const formData = new FormData(form);
    const state = {};
    
    for (const [key, value] of formData.entries()) {
      if (value) {
        state[key] = value;
      }
    }
    
    try {
      sessionStorage.setItem('search_form_state', JSON.stringify(state));
    } catch (e) {
      console.warn('フォーム状態の保存に失敗しました:', e);
    }
  },
  
  // フォームの状態を復元
  restoreState: function() {
    try {
      const state = JSON.parse(sessionStorage.getItem('search_form_state') || '{}');
      const form = document.getElementById('optimizedSearchForm');
      if (!form) return;
      
      Object.entries(state).forEach(([key, value]) => {
        const element = form.querySelector(`[name="${key}"]`);
        if (element) {
          element.value = value;
        }
      });
      
      updateActiveFilters();
    } catch (e) {
      console.warn('フォーム状態の復元に失敗しました:', e);
    }
  }
};

// ページ読み込み時にフォーム状態を復元
document.addEventListener('DOMContentLoaded', function() {
  SearchFormManager.restoreState();
});

// ページ離脱時にフォーム状態を保存
window.addEventListener('beforeunload', function() {
  SearchFormManager.saveState();
});
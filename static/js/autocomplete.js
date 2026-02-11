/**
 * Autocomplete Component
 * オートコンプリート機能（銘柄検索）
 */

class Autocomplete {
  constructor(inputId, suggestionsId, options = {}) {
    this.input = document.getElementById(inputId);
    this.suggestionsContainer = document.getElementById(suggestionsId);

    if (!this.input || !this.suggestionsContainer) {
      console.warn('Autocomplete: Required elements not found');
      return;
    }

    // オプション
    this.options = {
      minChars: 2,
      debounceDelay: 300,
      maxResults: 5,
      apiUrl: '/stockdiary/api/stock/search/',
      onSelect: null,
      enableKeyboard: true,
      enableHaptics: true,
      ...options
    };

    // 状態
    this.currentIndex = -1;
    this.suggestions = [];
    this.debounceTimer = null;
    this.isLoading = false;

    this.init();
  }

  // ========== 初期化 ==========
  init() {
    // 入力イベント
    this.input.addEventListener('input', (e) => this.onInput(e));

    // フォーカスイベント
    this.input.addEventListener('focus', () => {
      if (this.input.value.length >= this.options.minChars) {
        this.suggestionsContainer.classList.add('active');
      }
    });

    // ブラー時に遅延して閉じる（候補クリックを可能にするため）
    this.input.addEventListener('blur', () => {
      setTimeout(() => {
        this.suggestionsContainer.classList.remove('active');
      }, 200);
    });

    // キーボードナビゲーション
    if (this.options.enableKeyboard) {
      this.input.addEventListener('keydown', (e) => this.onKeyDown(e));
    }
  }

  // ========== 入力ハンドラー ==========
  onInput(e) {
    const query = e.target.value.trim();

    // 最小文字数チェック
    if (query.length < this.options.minChars) {
      this.hideSuggestions();
      return;
    }

    // デバウンス処理
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.search(query);
    }, this.options.debounceDelay);
  }

  // ========== キーボードナビゲーション ==========
  onKeyDown(e) {
    if (!this.suggestionsContainer.classList.contains('active')) {
      return;
    }

    const items = this.suggestionsContainer.querySelectorAll('.suggestion-item');

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.currentIndex = Math.min(this.currentIndex + 1, items.length - 1);
        this.highlightItem(items);
        break;

      case 'ArrowUp':
        e.preventDefault();
        this.currentIndex = Math.max(this.currentIndex - 1, -1);
        this.highlightItem(items);
        break;

      case 'Enter':
        e.preventDefault();
        if (this.currentIndex >= 0 && items[this.currentIndex]) {
          this.selectSuggestion(this.suggestions[this.currentIndex]);
        }
        break;

      case 'Escape':
        e.preventDefault();
        this.hideSuggestions();
        break;
    }
  }

  highlightItem(items) {
    items.forEach((item, index) => {
      if (index === this.currentIndex) {
        item.classList.add('active');
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else {
        item.classList.remove('active');
      }
    });
  }

  // ========== 検索API ==========
  async search(query) {
    this.isLoading = true;
    this.showLoading();

    try {
      const url = new URL(this.options.apiUrl, window.location.origin);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', this.options.maxResults);

      const response = await fetch(url);
      const data = await response.json();

      if (data.success && data.companies) {
        this.suggestions = data.companies;
        this.renderSuggestions(data.companies);
      } else {
        this.showNoResults();
      }
    } catch (error) {
      console.error('Autocomplete search error:', error);
      this.showError();
    } finally {
      this.isLoading = false;
    }
  }

  // ========== 候補の表示 ==========
  renderSuggestions(companies) {
    if (companies.length === 0) {
      this.showNoResults();
      return;
    }

    const listContainer = this.suggestionsContainer.querySelector('.suggestions-list');
    if (!listContainer) {
      console.warn('suggestions-list element not found');
      return;
    }

    listContainer.innerHTML = '';

    companies.forEach((company, index) => {
      const item = document.createElement('div');
      item.className = 'suggestion-item';
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', 'false');
      item.dataset.index = index;

      item.innerHTML = `
        <div class="stock-info">
          <span class="stock-code">${this.escapeHtml(company.code)}</span>
          <span class="stock-name">${this.escapeHtml(company.name)}</span>
        </div>
        <div class="stock-meta">
          <span>${this.escapeHtml(company.industry || '')}</span>
          <span>${this.escapeHtml(company.market || '')}</span>
        </div>
      `;

      // クリックイベント
      item.addEventListener('click', () => {
        this.selectSuggestion(company);
      });

      // マウスオーバーでハイライト
      item.addEventListener('mouseenter', () => {
        this.currentIndex = index;
        this.highlightItem(listContainer.querySelectorAll('.suggestion-item'));
      });

      listContainer.appendChild(item);
    });

    this.suggestionsContainer.classList.add('active');
    this.currentIndex = -1;
  }

  // ========== 候補選択 ==========
  selectSuggestion(company) {
    // 入力欄に値を設定
    this.input.value = `${company.code} ${company.name}`;

    // 触覚フィードバック
    if (this.options.enableHaptics && navigator.vibrate) {
      navigator.vibrate(10);
    }

    // 候補を閉じる
    this.hideSuggestions();

    // コールバック実行
    if (typeof this.options.onSelect === 'function') {
      this.options.onSelect(company);
    }

    // カスタムイベント発火
    const event = new CustomEvent('autocomplete:select', {
      detail: { company }
    });
    this.input.dispatchEvent(event);
  }

  // ========== 表示制御 ==========
  showLoading() {
    const listContainer = this.suggestionsContainer.querySelector('.suggestions-list');
    if (listContainer) {
      listContainer.innerHTML = `
        <div class="suggestion-item text-center text-muted">
          <span class="spinner-border spinner-border-sm me-2"></span>
          検索中...
        </div>
      `;
    }
    this.suggestionsContainer.classList.add('active');
  }

  showNoResults() {
    const listContainer = this.suggestionsContainer.querySelector('.suggestions-list');
    if (listContainer) {
      listContainer.innerHTML = `
        <div class="suggestion-item text-center text-muted">
          <i class="bi bi-search me-2"></i>
          該当する銘柄が見つかりませんでした
        </div>
      `;
    }
    this.suggestionsContainer.classList.add('active');
  }

  showError() {
    const listContainer = this.suggestionsContainer.querySelector('.suggestions-list');
    if (listContainer) {
      listContainer.innerHTML = `
        <div class="suggestion-item text-center text-danger">
          <i class="bi bi-exclamation-triangle me-2"></i>
          検索エラーが発生しました
        </div>
      `;
    }
    this.suggestionsContainer.classList.add('active');
  }

  hideSuggestions() {
    this.suggestionsContainer.classList.remove('active');
    this.currentIndex = -1;
    this.suggestions = [];
  }

  // ========== ユーティリティ ==========
  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text ? String(text).replace(/[&<>"']/g, m => map[m]) : '';
  }

  destroy() {
    // イベントリスナーをクリーンアップ
    clearTimeout(this.debounceTimer);
    // （詳細な実装は省略）
  }
}

// ========== グローバル初期化 ==========

document.addEventListener('DOMContentLoaded', function() {
  // クイック記録フォームのオートコンプリート
  const stockNameInput = document.getElementById('stock_name_quick');
  const suggestionsContainer = document.getElementById('suggestions_quick');

  if (stockNameInput && suggestionsContainer) {
    window.stockAutocomplete = new Autocomplete('stock_name_quick', 'suggestions_quick', {
      minChars: 2,
      debounceDelay: 300,
      maxResults: 5,
      onSelect: function(company) {
        console.log('Selected company:', company);
        // 追加の処理（必要に応じて）
      }
    });
  }
});

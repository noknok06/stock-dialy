/**
 * Autocomplete Component
 * オートコンプリート機能（銘柄検索）
 * 
 * 🆕 修正内容:
 * - 選択時に銘柄コードと名称を隠しフィールドに分けて設定
 * - 業種・市場情報も自動入力
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
      apiUrl: window.location.origin + '/stockdiary/api/stock/search/',
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

    console.log('[Autocomplete] Initialized with API URL:', this.options.apiUrl);

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

    // 🆕 入力が変更されたら隠しフィールドをクリア
    this.clearHiddenFields();

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
      const url = new URL(this.options.apiUrl);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', this.options.maxResults);

      console.log('[Autocomplete] Fetching:', url.toString());

      const response = await fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json',
        }
      });

      console.log('[Autocomplete] Response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[Autocomplete] API Error:', response.status, errorText);
        throw new Error(`APIエラー: ${response.status}`);
      }

      const data = await response.json();
      console.log('[Autocomplete] Response data:', data);

      if (data.success && data.companies) {
        this.suggestions = data.companies;
        this.renderSuggestions(data.companies);
      } else {
        if (data.message) {
          console.warn('[Autocomplete] API message:', data.message);
        }
        this.showNoResults();
      }
    } catch (error) {
      console.error('[Autocomplete] Search error:', error);
      this.showError(error.message);
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
    // 入力欄に値を設定（表示用）
    this.input.value = `${company.code} ${company.name}`;

    // 🆕 銘柄コードと名称を隠しフィールドに分けて設定
    const form = this.input.closest('form');
    if (form) {
      // 銘柄コード用の隠しフィールド
      let stockCodeInput = form.querySelector('input[name="stock_code"]');
      if (!stockCodeInput) {
        stockCodeInput = document.createElement('input');
        stockCodeInput.type = 'hidden';
        stockCodeInput.name = 'stock_code';
        form.appendChild(stockCodeInput);
      }
      stockCodeInput.value = company.code;
      
      // 銘柄名用の隠しフィールド
      let stockNameInput = form.querySelector('input[name="stock_name_hidden"]');
      if (!stockNameInput) {
        stockNameInput = document.createElement('input');
        stockNameInput.type = 'hidden';
        stockNameInput.name = 'stock_name_hidden';
        form.appendChild(stockNameInput);
      }
      stockNameInput.value = company.name;
      
      // 業種情報も設定（あれば）
      if (company.industry) {
        let industryInput = form.querySelector('input[name="industry"]');
        if (!industryInput) {
          industryInput = document.createElement('input');
          industryInput.type = 'hidden';
          industryInput.name = 'industry';
          form.appendChild(industryInput);
        }
        industryInput.value = company.industry;
      }
      
      // 市場情報も設定（あれば）
      if (company.market) {
        let marketInput = form.querySelector('input[name="market"]');
        if (!marketInput) {
          marketInput = document.createElement('input');
          marketInput.type = 'hidden';
          marketInput.name = 'market';
          form.appendChild(marketInput);
        }
        marketInput.value = company.market;
      }
      
      console.log('[Autocomplete] Set hidden fields:', {
        code: company.code,
        name: company.name,
        industry: company.industry,
        market: company.market
      });
    }

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

  // 🆕 隠しフィールドをクリア
  clearHiddenFields() {
    const form = this.input.closest('form');
    if (form) {
      const hiddenFields = ['stock_code', 'stock_name_hidden', 'industry', 'market'];
      hiddenFields.forEach(fieldName => {
        const field = form.querySelector(`input[name="${fieldName}"]`);
        if (field) {
          field.value = '';
        }
      });
    }
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

  showError(errorMessage) {
    const listContainer = this.suggestionsContainer.querySelector('.suggestions-list');
    if (listContainer) {
      listContainer.innerHTML = `
        <div class="suggestion-item text-center text-danger">
          <i class="bi bi-exclamation-triangle me-2"></i>
          検索エラーが発生しました
          ${errorMessage ? `<div class="small mt-1">${this.escapeHtml(errorMessage)}</div>` : ''}
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
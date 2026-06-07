/**
 * hashtag-autocomplete.js
 * EasyMDE (CodeMirror) のエディター内で @ を入力したときに
 * 既存ハッシュタグを補完するクラス。
 *
 * 使用対象:
 *   - reason（投資仮説）テキストエリア — diary_form.html
 *   - content（継続ノート）テキストエリア — detail.html
 *
 * 使い方:
 *   new HashtagMentionAutocomplete(easyMDEInstance.codemirror, apiUrl);
 */

// 軸ごとの色（tag_axis_config.py と同期）
const HASHTAG_AXIS_META = {
  theme:          { color: '#7c3aed' },
  macro:          { color: '#d97706' },
  capital_policy: { color: '#16a34a' },
  business_model: { color: '#0891b2' },
  risk:           { color: '#dc2626' },
  event:          { color: '#6b7280' },
  custom:         { color: '#9333ea', icon: '🏷' },
};

class HashtagMentionAutocomplete {
  /**
   * @param {CodeMirror.Editor} codemirror - EasyMDE の .codemirror プロパティ
   * @param {string}            apiUrl     - /api/hashtags/ の URL
   */
  constructor(codemirror, apiUrl) {
    this.cm         = codemirror;
    this.apiUrl     = apiUrl;
    this.dropdown   = null;
    this.activeQuery = null;   // { query, start:{line,ch}, end:{line,ch} } | null
    this.timer      = null;
    this.currentIdx = -1;

    this._init();
  }

  // =========================================================
  // 初期化
  // =========================================================
  _init() {
    // ドロップダウンを body に fixed 配置
    this.dropdown = this._createDropdown();
    document.body.appendChild(this.dropdown);

    this.cm.on('keyup',  (cm, e) => this._onKeyUp(e));
    this.cm.on('keydown', (cm, e) => this._onKeyDown(e));
    // change イベント: 日本語IMEがEnterで確定した後もここで検知できる
    // (keyupは key:'Enter' でフィルタされ、keyupは composition 中に getLine が空になるため)
    this.cm.on('change', () => this._onTextChange());
    // blur 時は mousedown が先に発火するため 150ms 遅延して非表示
    this.cm.on('blur', () => setTimeout(() => this._hide(), 150));

    // 日本語IME確定の保険: CodeMirror の隠しtextareaに直接 compositionend を張る
    // (環境によっては change より compositionend が確実に発火する)
    try {
      const input = this.cm.getInputField && this.cm.getInputField();
      if (input) {
        input.addEventListener('compositionend', () => {
          setTimeout(() => this._onTextChange(), 0);
        });
      }
    } catch (_) { /* getInputField 非対応環境は無視 */ }

    console.log('[HashtagAC] attached to editor:', this.apiUrl);
  }

  // =========================================================
  // カーソル直前の @xxx パターンを検出
  // =========================================================
  _getMentionAtCursor() {
    const cursor = this.cm.getCursor();
    const line   = this.cm.getLine(cursor.line) || '';
    const before = line.slice(0, cursor.ch);

    // @（日本語・英数字・アンダースコア）が直前にある場合のみ補完
    const match = before.match(
      /@([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF66-\uFF9Fa-zA-Z0-9_]*)$/
    );
    if (!match) return null;

    return {
      query: match[1],
      start: { line: cursor.line, ch: cursor.ch - match[0].length },
      end:   { line: cursor.line, ch: cursor.ch },
    };
  }

  // =========================================================
  // キーボードイベント: ドロップダウン表示の判定
  // =========================================================
  _onKeyUp(e) {
    if (['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(e.key)) return;
    this._trigger('keyup');
  }

  // =========================================================
  // テキスト変更（日本語IMEのEnter確定後にも発火）
  // =========================================================
  _onTextChange() {
    // keyup と同じ debounce タイマーを共有するので二重フェッチにならない
    this._trigger('change');
  }

  // カーソル位置の @xxx を検出してフェッチをスケジュール
  _trigger(source) {
    const mention = this._getMentionAtCursor();
    if (!mention) {
      this._hide();
      return;
    }
    console.log('[HashtagAC] mention detected via', source, '→ query:', JSON.stringify(mention.query));
    this.activeQuery = mention;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this._fetch(mention.query), 200);
  }

  // =========================================================
  // キーボードナビゲーション
  // =========================================================
  _onKeyDown(e) {
    if (!this._isVisible()) return;
    const items = this._getItems();

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this._navigate(+1, items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this._navigate(-1, items);
    } else if (e.key === 'Enter' && this.currentIdx >= 0) {
      e.preventDefault();
      this._insert(items[this.currentIdx].dataset.tag);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      this._hide();
    }
  }

  _navigate(dir, items) {
    if (items.length === 0) return;
    if (this.currentIdx >= 0 && items[this.currentIdx]) {
      items[this.currentIdx].classList.remove('active');
    }
    this.currentIdx = Math.max(0, Math.min(items.length - 1, this.currentIdx + dir));
    items[this.currentIdx].classList.add('active');
    items[this.currentIdx].scrollIntoView({ block: 'nearest' });
  }

  // =========================================================
  // API 呼び出し
  // =========================================================
  async _fetch(query) {
    try {
      const url = `${this.apiUrl}?q=${encodeURIComponent(query)}&limit=8`;
      const res  = await fetch(url, { credentials: 'same-origin' });
      if (!res.ok) {
        console.warn('[HashtagAC] fetch failed:', res.status, url);
        return;
      }
      const data = await res.json();
      const n = (data.hashtags || []).length;
      console.log('[HashtagAC] fetched', n, 'results for', JSON.stringify(query));
      if (data.success && data.hashtags && data.hashtags.length > 0) {
        this._positionDropdown();
        this._show(data.hashtags);
      } else {
        this._hide();
      }
    } catch (err) {
      console.warn('[HashtagAC] fetch error:', err);
      this._hide();
    }
  }

  // =========================================================
  // ドロップダウン表示・位置決め
  // =========================================================
  _positionDropdown() {
    // CodeMirror のカーソル座標（ビューポート基準）を取得
    const coords = this.cm.cursorCoords(null, 'window');
    const dropH  = this.dropdown.offsetHeight || 240;
    const viewH  = window.innerHeight;

    // 下にスペースがあればカーソルの下、なければ上に表示
    if (coords.bottom + dropH + 8 < viewH) {
      this.dropdown.style.top  = `${coords.bottom + 4}px`;
    } else {
      this.dropdown.style.top  = `${coords.top - dropH - 4}px`;
    }
    this.dropdown.style.left = `${coords.left}px`;
  }

  _show(hashtags) {
    this.currentIdx = -1;
    this.dropdown.innerHTML = hashtags.map((h) => {
      const meta = HASHTAG_AXIS_META[h.axis] || { color: '#6b7280' };
      const badge = meta.icon
        ? `<span class="hashtag-axis-dot" style="color:${meta.color};font-size:0.75em;flex-shrink:0;">${meta.icon}</span>`
        : `<span class="hashtag-axis-dot" style="background:${meta.color};" aria-hidden="true"></span>`;
      const countStr = h.count > 0
        ? `<span class="hashtag-count">${h.count}</span>`
        : '';
      return `<div class="hashtag-suggestion-item" data-tag="${this._esc(h.tag)}" role="option">
        ${badge}<span class="hashtag-at">@</span><span class="hashtag-name">${this._esc(h.tag)}</span>
        ${countStr}
      </div>`;
    }).join('');

    this._getItems().forEach((item) => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();   // blur を防いで確実に挿入
        this._insert(item.dataset.tag);
      });
    });

    this.dropdown.style.display = 'block';
  }

  _hide() {
    this.dropdown.style.display = 'none';
    this.currentIdx = -1;
  }

  _isVisible() {
    return this.dropdown.style.display === 'block';
  }

  _getItems() {
    return Array.from(this.dropdown.querySelectorAll('.hashtag-suggestion-item'));
  }

  // =========================================================
  // テキストへの挿入（CodeMirror replaceRange を使用）
  // =========================================================
  _insert(tag) {
    if (!this.activeQuery) return;
    const insertion = `@${tag} `;
    this.cm.replaceRange(insertion, this.activeQuery.start, this.activeQuery.end);
    this.cm.focus();
    this._hide();
    this.activeQuery = null;
  }

  // =========================================================
  // ドロップダウン DOM の生成
  // =========================================================
  _createDropdown() {
    const el = document.createElement('div');
    el.className = 'hashtag-autocomplete-dropdown';
    el.setAttribute('role', 'listbox');
    el.style.display = 'none';
    return el;
  }

  // HTML エスケープ
  _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}

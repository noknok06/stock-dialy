/**
 * hashtag-autocomplete.js
 * エディター内でトリガ文字を入力したときにサジェストを出す補完クラス群。
 *
 *   - MentionAutocomplete        : 共通基底（ドロップダウン・座標・キーボード操作・IME対応）
 *   - HashtagMentionAutocomplete : `@` で既存ハッシュタグを補完（挿入: `@tag `）
 *   - DiaryMentionAutocomplete   : `[[` で自分の日記を補完（挿入: `銘柄名(コード) `）
 *                                  → 既存の言及リンク/関連エッジ基盤にそのまま乗る
 *
 * エディタは EasyMDE(CodeMirror) の .codemirror、または同等APIを実装したアダプタ
 * （クイック記録の TextareaCM）を渡す。
 *
 * 使い方:
 *   new HashtagMentionAutocomplete(cmOrAdapter, "/stockdiary/api/hashtags/");
 *   new DiaryMentionAutocomplete(cmOrAdapter, "/stockdiary/api/diaries/mine/search/");
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


// =========================================================
// 共通基底
// =========================================================
class MentionAutocomplete {
  /**
   * @param {object} codemirror - CodeMirror.Editor または同等アダプタ
   * @param {string} apiUrl     - サジェスト取得API（?q=&limit=8 で問い合わせ）
   */
  constructor(codemirror, apiUrl) {
    this.cm = codemirror;
    this.apiUrl = apiUrl;
    this.dropdown = null;
    this.activeQuery = null;   // { query, start:{line,ch}, end:{line,ch} } | null
    this.timer = null;
    this.currentIdx = -1;
    this._init();
  }

  // --- サブクラスで上書きする3メソッド ---
  // カーソル直前テキストからトリガを検出。{query, length} または null。
  _match(_before) { return null; }
  // API レスポンスから候補配列を取り出す。
  _parse(_data) { return []; }
  // 候補1件を <div data-insert="挿入文字列" ...> として描画する。
  _renderItem(_item) { return ''; }

  _init() {
    this.dropdown = this._createDropdown();
    document.body.appendChild(this.dropdown);

    this.cm.on('keyup', (cm, e) => this._onKeyUp(e));
    this.cm.on('keydown', (cm, e) => this._onKeyDown(e));
    // 日本語IMEのEnter確定後も検知するため change でも発火
    this.cm.on('change', () => this._onTextChange());
    this.cm.on('blur', () => setTimeout(() => this._hide(), 150));

    try {
      const input = this.cm.getInputField && this.cm.getInputField();
      if (input) {
        input.addEventListener('compositionend', () => {
          setTimeout(() => this._onTextChange(), 0);
        });
      }
    } catch (_) { /* getInputField 非対応環境は無視 */ }
  }

  _getMentionAtCursor() {
    const cursor = this.cm.getCursor();
    const line = this.cm.getLine(cursor.line) || '';
    const before = line.slice(0, cursor.ch);
    const m = this._match(before);
    if (!m) return null;
    return {
      query: m.query,
      start: { line: cursor.line, ch: cursor.ch - m.length },
      end:   { line: cursor.line, ch: cursor.ch },
    };
  }

  _onKeyUp(e) {
    if (['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(e.key)) return;
    this._trigger();
  }

  _onTextChange() { this._trigger(); }

  _trigger() {
    const mention = this._getMentionAtCursor();
    if (!mention) { this._hide(); return; }
    this.activeQuery = mention;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this._fetch(mention.query), 200);
  }

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
      this._insert(items[this.currentIdx].dataset.insert);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      this._hide();
    }
  }

  _navigate(dir, items) {
    if (items.length === 0) return;
    if (this.currentIdx >= 0 && items[this.currentIdx]) {
      items[this.currentIdx].classList.remove('active');
      items[this.currentIdx].style.background = '';
    }
    this.currentIdx = Math.max(0, Math.min(items.length - 1, this.currentIdx + dir));
    items[this.currentIdx].classList.add('active');
    items[this.currentIdx].style.background = 'rgba(74,109,167,0.12)';
    items[this.currentIdx].scrollIntoView({ block: 'nearest' });
  }

  async _fetch(query) {
    try {
      const url = `${this.apiUrl}?q=${encodeURIComponent(query)}&limit=8`;
      const res = await fetch(url, { credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      const items = this._parse(data) || [];
      if (items.length > 0) {
        this._positionDropdown();
        this._show(items);
      } else {
        this._hide();
      }
    } catch (err) {
      this._hide();
    }
  }

  _positionDropdown() {
    const coords = this.cm.cursorCoords(null, 'window');
    const dropH = this.dropdown.offsetHeight || 240;
    const viewH = window.innerHeight;
    if (coords.bottom + dropH + 8 < viewH) {
      this.dropdown.style.top = `${coords.bottom + 4}px`;
    } else {
      this.dropdown.style.top = `${coords.top - dropH - 4}px`;
    }
    this.dropdown.style.left = `${coords.left}px`;
  }

  _show(items) {
    this.currentIdx = -1;
    this.dropdown.innerHTML = items.map((it) => this._renderItem(it)).join('');
    this._getItems().forEach((item) => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();   // blur を防いで確実に挿入
        this._insert(item.dataset.insert);
      });
      item.addEventListener('mouseenter', () => { item.style.background = 'rgba(74,109,167,0.12)'; });
      item.addEventListener('mouseleave', () => { item.style.background = ''; });
    });
    this.dropdown.style.display = 'block';
  }

  _hide() {
    this.dropdown.style.display = 'none';
    this.currentIdx = -1;
  }

  _isVisible() { return this.dropdown.style.display === 'block'; }

  _getItems() {
    return Array.from(this.dropdown.querySelectorAll('[data-insert]'));
  }

  _insert(text) {
    if (!this.activeQuery || text == null) return;
    this.cm.replaceRange(text, this.activeQuery.start, this.activeQuery.end);
    this.cm.focus();
    this._hide();
    this.activeQuery = null;
  }

  _createDropdown() {
    const el = document.createElement('div');
    el.className = 'hashtag-autocomplete-dropdown';
    el.setAttribute('role', 'listbox');
    el.style.display = 'none';
    Object.assign(el.style, {
      position:     'fixed',
      zIndex:       '2200',   // クイック記録の全画面オーバーレイ(2000)より前面
      width:        '260px',
      maxHeight:    '240px',
      overflowY:    'auto',
      background:   '#ffffff',
      border:       '1px solid rgba(0,0,0,0.12)',
      borderRadius: '8px',
      boxShadow:    '0 4px 14px rgba(0,0,0,0.18)',
      fontSize:     '0.88rem',
    });
    return el;
  }

  _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}


// =========================================================
// @ ハッシュタグ補完（挙動は従来どおり）
// =========================================================
class HashtagMentionAutocomplete extends MentionAutocomplete {
  _match(before) {
    const m = before.match(
      /@([぀-ゟ゠-ヿ一-鿿ｦ-ﾟa-zA-Z0-9_]*)$/
    );
    return m ? { query: m[1], length: m[0].length } : null;
  }

  _parse(data) {
    return (data && data.success && data.hashtags) ? data.hashtags : [];
  }

  _renderItem(h) {
    const meta = HASHTAG_AXIS_META[h.axis] || { color: '#6b7280' };
    const badge = meta.icon
      ? `<span class="hashtag-axis-dot" style="color:${meta.color};font-size:0.75em;flex-shrink:0;">${meta.icon}</span>`
      : `<span class="hashtag-axis-dot" aria-hidden="true" style="display:inline-block;width:7px;height:7px;border-radius:50%;flex-shrink:0;background:${meta.color};"></span>`;
    const countStr = h.count > 0
      ? `<span class="hashtag-count" style="margin-left:auto;padding-left:8px;font-size:0.72rem;color:#888;flex-shrink:0;">${h.count}</span>`
      : '';
    return `<div class="hashtag-suggestion-item" data-insert="${this._esc('@' + h.tag + ' ')}" role="option"
      style="padding:8px 12px;cursor:pointer;display:flex;align-items:center;gap:4px;color:#1f2328;">
      ${badge}<span class="hashtag-at" style="color:#4a6da7;font-weight:700;">@</span><span class="hashtag-name" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${this._esc(h.tag)}</span>
      ${countStr}
    </div>`;
  }
}


// =========================================================
// [[ 日記メンション補完（挿入: 銘柄名(コード) ）
// =========================================================
class DiaryMentionAutocomplete extends MentionAutocomplete {
  _match(before) {
    // 直前に `[[（任意の文字、改行/角括弧以外）` がある場合のみ
    const m = before.match(/\[\[([^\[\]\n]*)$/);
    return m ? { query: m[1], length: m[0].length } : null;
  }

  _parse(data) {
    // 言及リンクは銘柄コードに依存するため、コードのある日記のみ候補にする
    return (data && data.diaries ? data.diaries : []).filter((d) => d.stock_symbol);
  }

  _renderItem(d) {
    const code = d.stock_symbol ? `(${d.stock_symbol})` : '';
    const raw = `${d.stock_name}${code} `;   // 既存の言及リンク基盤が拾う正規形式
    return `<div class="diary-suggestion-item" data-insert="${this._esc(raw)}" role="option"
      style="padding:8px 12px;cursor:pointer;display:flex;align-items:center;gap:6px;color:#1f2328;">
      <i class="bi bi-journal-text" style="color:#5457e6;flex-shrink:0;"></i>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${this._esc(d.stock_name)}</span>
      <span style="font-size:0.75rem;color:#888;flex-shrink:0;">${this._esc(code)}</span>
    </div>`;
  }
}

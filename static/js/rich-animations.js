/**
 * rich-animations.js
 * リッチUIアニメーション - yui540スタイル
 * スクロール検知・マグネット・数値カウンター・インタラクション強化
 */

(function () {
  'use strict';

  /* =========================================================
   * ① スクロール検知 フェードイン (IntersectionObserver)
   * ======================================================= */
  function initScrollReveal() {
    const targets = document.querySelectorAll('.reveal-on-scroll');
    if (!targets.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: '0px 0px -32px 0px' }
    );

    targets.forEach((el) => observer.observe(el));
  }

  /* =========================================================
   * ② カード 3Dティルト効果 (マウス追従)
   * ======================================================= */
  function initCardTilt() {
    // モバイルタッチデバイスではスキップ
    if (window.matchMedia('(hover: none)').matches) return;
    if (window.matchMedia('(max-width: 767px)').matches) return;

    function applyTilt(card) {
      card.addEventListener('mousemove', onMouseMove);
      card.addEventListener('mouseleave', onMouseLeave);
    }

    function onMouseMove(e) {
      const rect = this.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      const rotX = ((y - cy) / cy) * -4;   // 最大 ±4deg
      const rotY = ((x - cx) / cx) * 4;
      const shine = `radial-gradient(circle at ${x}px ${y}px, rgba(255,255,255,0.07) 0%, transparent 60%)`;

      this.style.transform = `perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateZ(2px)`;
      this.style.transition = 'transform 0.08s linear';
      this.style.backgroundImage = shine;
    }

    function onMouseLeave() {
      this.style.transform = '';
      this.style.backgroundImage = '';
      this.style.transition = 'transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)';
    }

    // 現在のカードに適用
    document.querySelectorAll('.diary-article').forEach(applyTilt);

    // HTMX で追加されたカードにも適用
    document.addEventListener('htmx:afterSwap', function (e) {
      if (e.detail && e.detail.target && e.detail.target.id === 'diary-container') {
        setTimeout(function () {
          e.detail.target.querySelectorAll('.diary-article').forEach(applyTilt);
        }, 50);
      }
    });
  }

  /* =========================================================
   * ③ 数値カウンターアニメーション (損益バッジ)
   * ======================================================= */
  function animateNumber(el, from, to, duration, prefix, suffix, decimals) {
    const start = performance.now();
    const diff = to - from;

    function step(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = from + diff * eased;

      const formatted = Math.round(current).toLocaleString('ja-JP');
      el.textContent = prefix + formatted + suffix;

      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = prefix + Math.round(to).toLocaleString('ja-JP') + suffix;
    }

    requestAnimationFrame(step);
  }

  function initProfitCounters() {
    document.querySelectorAll('[data-profit-value]').forEach(function (el) {
      if (el.dataset.animated) return;
      el.dataset.animated = '1';

      const raw = parseFloat(el.dataset.profitValue);
      if (isNaN(raw)) return;

      const prefix = el.dataset.profitPrefix || '';
      const suffix = el.dataset.profitSuffix || '';
      animateNumber(el, 0, raw, 700, prefix, suffix, 0);
    });
  }

  /* =========================================================
   * ④ カード登場後のスタガーアニメーション再適用
   *    (HTMX で差し替えられた際に再トリガー)
   * ======================================================= */
  function reinitCardAnimations(container) {
    const cards = container ? container.querySelectorAll('.diary-article') : [];

    cards.forEach(function (card, i) {
      // アニメーションをリセットして再実行
      card.style.animation = 'none';
      card.style.opacity = '0';
      // reflow を強制
      void card.offsetHeight;
      card.style.animation = '';
      card.style.animationDelay = Math.min(i * 60, 600) + 'ms';
    });
  }

  /* =========================================================
   * ⑤ リップルエフェクト（ボタン）
   * ======================================================= */
  function createRipple(e) {
    const btn = e.currentTarget;
    const existing = btn.querySelector('.js-ripple');
    if (existing) existing.remove();

    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;

    const ripple = document.createElement('span');
    ripple.className = 'js-ripple';
    ripple.style.cssText = `
      position: absolute;
      width: ${size}px;
      height: ${size}px;
      left: ${x}px;
      top: ${y}px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.35) 0%, rgba(255,255,255,0) 70%);
      pointer-events: none;
      transform: scale(0);
      animation: js-ripple-anim 0.6s ease-out forwards;
    `;

    btn.style.position = 'relative';
    btn.style.overflow = 'hidden';
    btn.appendChild(ripple);

    ripple.addEventListener('animationend', function () {
      ripple.remove();
    });
  }

  // グローバルなキーフレーム定義（1回だけ）
  if (!document.getElementById('js-ripple-style')) {
    const style = document.createElement('style');
    style.id = 'js-ripple-style';
    style.textContent = `
      @keyframes js-ripple-anim {
        to { transform: scale(1); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }

  function initRipples() {
    document.querySelectorAll('.btn, .btn-primary, .btn-filter-apply, .btn-filter-reset').forEach(function (btn) {
      if (btn.dataset.rippleInit) return;
      btn.dataset.rippleInit = '1';
      btn.addEventListener('click', createRipple);
    });
  }

  /* =========================================================
   * ⑥ マグネットボタン効果（速度調整ボタン等）
   * ======================================================= */
  function initMagneticButtons() {
    if (window.matchMedia('(hover: none)').matches) return;

    document.querySelectorAll('.btn-primary, .filter-toggle-btn, .sort-toggle-btn').forEach(function (btn) {
      if (btn.dataset.magnetInit) return;
      btn.dataset.magnetInit = '1';

      btn.addEventListener('mousemove', function (e) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        const strength = 0.3;
        this.style.transform = `translate(${x * strength}px, ${y * strength}px)`;
        this.style.transition = 'transform 0.1s linear';
      });

      btn.addEventListener('mouseleave', function () {
        this.style.transform = '';
        this.style.transition = 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
      });
    });
  }

  /* =========================================================
   * ⑦ 画像ホバー パララックス
   * ======================================================= */
  function initImageParallax() {
    if (window.matchMedia('(hover: none)').matches) return;

    document.querySelectorAll('.diary-figure').forEach(function (fig) {
      if (fig.dataset.parallaxInit) return;
      fig.dataset.parallaxInit = '1';

      const img = fig.querySelector('img');
      if (!img) return;

      fig.addEventListener('mousemove', function (e) {
        const rect = fig.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;
        const moveX = (x - 0.5) * 12;
        const moveY = (y - 0.5) * 8;
        img.style.transform = `scale(1.06) translate(${moveX}px, ${moveY}px)`;
        img.style.transition = 'transform 0.1s linear';
      });

      fig.addEventListener('mouseleave', function () {
        img.style.transform = '';
        img.style.transition = 'transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)';
      });
    });
  }

  /* =========================================================
   * ⑧ フィルターチップ 削除アニメーション
   * ======================================================= */
  function patchFilterChipRemove() {
    // フィルターチップの削除ボタンにアニメーションを追加
    const originalRemoveFilter = window.removeFilter;
    if (!originalRemoveFilter) return;

    window.removeFilter = function (filterName) {
      const chip = document.querySelector(`.filter-chip[data-filter="${filterName}"]`);
      if (chip) {
        chip.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
        chip.style.transform = 'scale(0.7)';
        chip.style.opacity = '0';
        setTimeout(function () {
          originalRemoveFilter(filterName);
        }, 180);
      } else {
        originalRemoveFilter(filterName);
      }
    };
  }

  /* =========================================================
   * ⑨ ページ遷移エフェクト
   * ======================================================= */
  function initPageTransitions() {
    if (!document.startViewTransition) return;

    // ページ内リンクにview transitionを適用
    document.querySelectorAll('a[href]:not([href^="#"]):not([href^="javascript"]):not([target="_blank"])').forEach(function (link) {
      if (link.dataset.noTransition) return;
      link.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript')) return;
        // 外部リンクはスキップ
        if (this.hostname && this.hostname !== window.location.hostname) return;

        // HTMX リンクはスキップ
        if (this.hasAttribute('hx-get') || this.hasAttribute('hx-post')) return;

        e.preventDefault();
        document.startViewTransition(function () {
          window.location.href = href;
        });
      });
    });
  }

  /* =========================================================
   * ⑩ スターバースト（タグクリック時）
   * ======================================================= */
  function createStarburst(x, y, color) {
    const count = 8;
    for (let i = 0; i < count; i++) {
      const dot = document.createElement('div');
      const angle = (i / count) * Math.PI * 2;
      const dist = 30 + Math.random() * 20;
      const tx = Math.cos(angle) * dist;
      const ty = Math.sin(angle) * dist;
      const size = 3 + Math.random() * 3;

      dot.style.cssText = `
        position: fixed;
        left: ${x}px;
        top: ${y}px;
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        background: ${color};
        pointer-events: none;
        z-index: 9999;
        animation: starburst-dot 0.6s ease-out forwards;
        --tx: ${tx}px;
        --ty: ${ty}px;
      `;
      document.body.appendChild(dot);
      dot.addEventListener('animationend', function () { dot.remove(); });
    }
  }

  // スターバースト用CSS（1回だけ）
  if (!document.getElementById('starburst-style')) {
    const style = document.createElement('style');
    style.id = 'starburst-style';
    style.textContent = `
      @keyframes starburst-dot {
        0%   { transform: translate(0, 0) scale(1); opacity: 1; }
        100% { transform: translate(var(--tx), var(--ty)) scale(0); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }

  function initTagStarburst() {
    document.addEventListener('click', function (e) {
      const tag = e.target.closest('.tag-pill');
      if (!tag) return;

      const rect = tag.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      createStarburst(x, y, 'rgba(113, 196, 239, 0.8)');
    });
  }

  /* =========================================================
   * HTMX イベントフック
   * ======================================================= */
  document.addEventListener('htmx:afterSwap', function (e) {
    if (!e.detail || !e.detail.target) return;
    const container = e.detail.target;

    if (container.id === 'diary-container') {
      reinitCardAnimations(container);
      setTimeout(function () {
        initCardTilt();
        initRipples();
        initMagneticButtons();
        initImageParallax();
        initProfitCounters();
        initScrollReveal();
      }, 50);
    }
  });

  /* =========================================================
   * 初期化
   * ======================================================= */
  function init() {
    initScrollReveal();
    initCardTilt();
    initRipples();
    initMagneticButtons();
    initImageParallax();
    initProfitCounters();
    initTagStarburst();
    patchFilterChipRemove();

    // View Transitions API が利用可能な場合のみ
    if (typeof document.startViewTransition === 'function') {
      initPageTransitions();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

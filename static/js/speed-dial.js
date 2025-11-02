/**
 * Enhanced SpeedDial class - improved mobile experience
 * - Better animations
 * - Auto-close timer
 * - Improved accessibility
 * - Mobile gesture support
 */
class SpeedDial {
  constructor(config = {}) {
    this.config = {
      triggerSelector: '.speed-dial-trigger',
      actionsSelector: '.speed-dial-actions',
      overlaySelector: '.speed-dial-overlay',
      containerSelector: '.speed-dial-container',
      useOverlay: true,
      ...config
    };
    
    this.trigger = document.querySelector(this.config.triggerSelector);
    this.actions = document.querySelector(this.config.actionsSelector);
    this.overlay = document.querySelector(this.config.overlaySelector);
    this.container = document.querySelector(this.config.containerSelector);
    
    this.isOpen = false;
    this.singleAction = false; // 単一アクションモードのフラグ
    this.autoCloseTimer = null; // 自動閉じるタイマー
    
    // タッチ操作のための変数
    this.touchStartY = 0;
    this.touchStartTime = 0;
    
    // アクションが1つだけかチェック
    if (this.actions && this.actions.querySelectorAll('.speed-dial-action').length === 1) {
      this.singleAction = true;
      this.setupSingleAction();
    } else if (this.trigger && this.actions) {
      this.init();
    } else {
      console.warn('SpeedDial: 必要な要素が見つかりません');
    }
  }
  
  // 単一アクションモードのセットアップ
  setupSingleAction() {
    // トリガーボタンを非表示にする
    if (this.trigger) {
      this.trigger.style.display = 'none';
    }
    
    // アクションボタンを常に表示
    if (this.actions) {
      this.actions.classList.add('active');
      
      // 単一のアクションボタンを取得
      const actionItem = this.actions.querySelector('.speed-dial-action');
      if (actionItem) {
        // ラベルを非表示
        const label = actionItem.querySelector('.action-label');
        if (label) {
          label.style.display = 'none';
        }
        
        // ボタンを大きく
        const btn = actionItem.querySelector('.speed-dial-btn');
        if (btn) {
          btn.style.width = '56px';
          btn.style.height = '56px';
          
          // ユーザー操作をすぐにトリガーするためにラベルを常に表示
          if (label) {
            label.style.opacity = '1';
            label.style.transform = 'translateX(0)';
          }
        }
      }
    }
    
    // コンテナにクラスを追加
    if (this.container) {
      this.container.classList.add('single-action-mode');
    }
  }
  
  init() {
    // トリガーボタンのクリックイベント
    this.trigger.addEventListener('click', () => {
      this.toggle();
    });
    
    // トリガーボタンのキーボードイベント（アクセシビリティ向上）
    this.trigger.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.toggle();
      }
    });
    
    // オーバーレイのクリックイベント
    if (this.overlay && this.config.useOverlay) {
      this.overlay.addEventListener('click', () => {
        this.close();
      });
    }
    
    // アクションボタンクリック時の処理
    const actionButtons = this.actions.querySelectorAll('.speed-dial-btn');
    actionButtons.forEach(btn => {
      // キーボードアクセシビリティの強化
      btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          btn.click();
        }
      });
    });
    
    // ページ内の他の場所をクリックした時に閉じる
    document.addEventListener('click', (e) => {
      if (this.isOpen && !this.container.contains(e.target)) {
        this.close();
      }
    });
    
    // ESCキーで閉じる
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
    
    // タッチ操作のサポート（スワイプで閉じる）
    if (this.container) {
      this.container.addEventListener('touchstart', (e) => {
        this.touchStartY = e.touches[0].clientY;
        this.touchStartTime = Date.now();
      }, { passive: true });
      
      this.container.addEventListener('touchmove', (e) => {
        if (!this.isOpen) return;
        
        const currentY = e.touches[0].clientY;
        const diffY = currentY - this.touchStartY;
        
        // 上向きのスワイプで閉じる
        if (diffY < -50) {
          this.close();
        }
      }, { passive: true });
    }
    
    // スクロール時に非表示にするための監視
    let lastScrollTop = window.pageYOffset || document.documentElement.scrollTop;
    let scrollTimer = null;
    
    window.addEventListener('scroll', () => {
      // スクロール中は処理をスキップ（パフォーマンス最適化）
      if (scrollTimer !== null) return;
      
      scrollTimer = setTimeout(() => {
        const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
        // スクロール方向の判定
        if (Math.abs(lastScrollTop - currentScrollTop) > 50) {
          if (this.isOpen) {
            this.close();
          }
          lastScrollTop = currentScrollTop;
        }
        scrollTimer = null;
      }, 150);
    }, { passive: true });
  }
  
  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }
  
  open() {
    if (!this.isOpen) {
      // 振動フィードバック（対応デバイスのみ）
      if (navigator.vibrate) {
        navigator.vibrate(5);
      }
      
      this.trigger.classList.add('active');
      this.actions.classList.add('active');
      
      if (this.overlay && this.config.useOverlay) {
        this.overlay.classList.add('active');
      }
      
      // アニメーションのためにタイミングを少しずらす
      this.actions.querySelectorAll('.speed-dial-action').forEach((action, index) => {
        action.style.transitionDelay = `${0.05 * index}s`;
      });
      
      // アクセシビリティ: ARIAステートの更新
      this.trigger.setAttribute('aria-expanded', 'true');
      
      this.isOpen = true;
      
      // 自動で閉じるタイマーを設定
      this.startAutoCloseTimer();
    }
  }
  
  close() {
    if (this.isOpen) {
      this.trigger.classList.remove('active');
      this.actions.classList.remove('active');
      
      if (this.overlay && this.config.useOverlay) {
        this.overlay.classList.remove('active');
      }
      
      // トランジションディレイをリセット
      this.actions.querySelectorAll('.speed-dial-action').forEach(action => {
        action.style.transitionDelay = '';
      });
      
      // アクセシビリティ: ARIAステートの更新
      this.trigger.setAttribute('aria-expanded', 'false');
      
      this.isOpen = false;
      
      // 自動閉じるタイマーをクリア
      this.clearAutoCloseTimer();
    }
  }
  
  // 自動で閉じるタイマーを開始
  startAutoCloseTimer() {
    this.clearAutoCloseTimer();
    
    if (this.config.autoCloseTime > 0) {
      // タイムアウトインジケーターを追加
      this.addTimeoutIndicator();
      
      this.autoCloseTimer = setTimeout(() => {
        this.close();
      }, this.config.autoCloseTime);
    }
  }
  
  // 自動で閉じるタイマーをクリア
  clearAutoCloseTimer() {
    if (this.autoCloseTimer) {
      clearTimeout(this.autoCloseTimer);
      this.autoCloseTimer = null;
      
      // タイムアウトインジケーターを削除
      this.removeTimeoutIndicator();
    }
  }
  
  // タイムアウトインジケーターを追加
  addTimeoutIndicator() {
    // すでに存在するインジケーターを削除
    this.removeTimeoutIndicator();
    
    // アクションボタン周りにタイムアウトインジケーターを追加
    const indicator = document.createElement('div');
    indicator.className = 'timeout-indicator';
    
    // トリガーボタンに追加
    if (this.trigger) {
      this.trigger.appendChild(indicator);
    }
  }
  
  // タイムアウトインジケーターを削除
  removeTimeoutIndicator() {
    const indicators = document.querySelectorAll('.timeout-indicator');
    indicators.forEach(indicator => {
      indicator.remove();
    });
  }
}

/**
 * スピードダイアルを動的に生成する
 * @param {Object} options スピードダイアルの設定オプション
 */
function createSpeedDial(options = {}) {
  const defaults = {
    container: document.body,
    actions: [],
    useOverlay: true,
    triggerIcon: 'bi-plus-lg',
    position: 'bottom-right',
    autoCloseTime: 4000
  };
  
  const config = { ...defaults, ...options };
  
  // アクションをフィルタリング (条件がfalseのものを除外)
  const filteredActions = config.actions.filter(action => action.condition !== false);
  
  // アクションが1つの場合の特別処理
  const singleActionMode = filteredActions.length === 1;
  
  // コンテナを作成
  const container = document.createElement('div');
  container.className = 'speed-dial-container';
  if (singleActionMode) {
    container.classList.add('single-action-mode');
  }
  
  // アクションボタンコンテナを作成
  const actionsContainer = document.createElement('div');
  actionsContainer.className = 'speed-dial-actions';
  actionsContainer.setAttribute('role', 'menu');
  actionsContainer.setAttribute('aria-orientation', 'vertical');
  
  if (singleActionMode) {
    actionsContainer.classList.add('active');
  }
  
  // アクションボタンを生成
  for (const action of filteredActions) {
    const actionItem = document.createElement('div');
    actionItem.className = 'speed-dial-action';
    actionItem.setAttribute('role', 'menuitem');
    
    // アクションラベル
    const label = document.createElement('span');
    label.className = 'action-label';
    label.textContent = action.label || '';
    
    // アクションボタン
    const btn = document.createElement('a');
    btn.href = action.url || '#';
    btn.className = `speed-dial-btn action-${action.type}`;
    btn.setAttribute('role', 'button');
    btn.setAttribute('aria-label', action.aria_label || action.label || '');
    btn.setAttribute('title', action.label || '');
    
    // クリックイベントをdata属性として設定（あとで参照できるように）
    if (action.onclick) {
      btn.setAttribute('data-onclick', action.onclick.toString());
      
      btn.addEventListener('click', (e) => {
        if (!action.url || action.url === '#') {
          e.preventDefault();
        }
        
        try {
          if (typeof action.onclick === 'function') {
            action.onclick(e);
          }
        } catch (err) {
          console.warn('Action onclick error:', err);
        }
      });
    }
    
    const icon = document.createElement('i');
    icon.className = `bi ${action.icon}`;
    btn.appendChild(icon);
    
    // 要素を組み立てる
    actionItem.appendChild(label);
    actionItem.appendChild(btn);
    actionsContainer.appendChild(actionItem);
  }
  
  // トリガーボタンを作成
  const trigger = document.createElement('button');
  trigger.className = 'speed-dial-trigger';
  trigger.type = 'button';
  trigger.setAttribute('aria-haspopup', 'menu');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.setAttribute('aria-label', 'アクションメニュー');
  
  const triggerIcon = document.createElement('i');
  triggerIcon.className = `bi ${config.triggerIcon}`;
  trigger.appendChild(triggerIcon);
  
  // 単一アクションモードではトリガーを非表示
  if (singleActionMode) {
    trigger.style.display = 'none';
  }
  
  // オーバーレイを作成
  let overlay = null;
  if (config.useOverlay && !singleActionMode) {
    overlay = document.createElement('div');
    overlay.className = 'speed-dial-overlay';
    config.container.appendChild(overlay);
  }
  
  // 要素を追加
  container.appendChild(actionsContainer);
  container.appendChild(trigger);
  config.container.appendChild(container);
  
  // スピードダイアルのインスタンスを初期化
  return new SpeedDial({
    triggerSelector: '.speed-dial-trigger',
    actionsSelector: '.speed-dial-actions',
    overlaySelector: '.speed-dial-overlay',
    containerSelector: '.speed-dial-container',
    useOverlay: config.useOverlay,
    autoCloseTime: config.autoCloseTime
  });
}

// グローバル初期化関数
function initializeSpeedDial() {
  // 既存のスピードダイアルを初期化
  const speedDial = new SpeedDial();
  
  // コンソールで呼び出せるようにグローバル変数に保持
  window.speedDialInstance = speedDial;
  
  // スピードダイヤルをDOM内で適切な位置に強制移動
  const speedDialContainer = document.querySelector('.speed-dial-container');
  if (speedDialContainer && speedDialContainer.parentElement !== document.body) {
    document.body.appendChild(speedDialContainer);
    // console.log('スピードダイヤルをbody直下に移動しました');
  }
  
  // ページクリック時にポジションを確認・修正
  document.addEventListener('click', function() {
    const speedDial = document.querySelector('.speed-dial-container');
    if (speedDial && speedDial.parentElement !== document.body) {
      document.body.appendChild(speedDial);
      // console.log('スピードダイヤルの位置を修正しました');
    }
  }, true); // キャプチャリングフェーズで実行

  return speedDial;
}

// DOMContentLoadedイベントでページ内の既存スピードダイアルを初期化
document.addEventListener('DOMContentLoaded', function() {
  // ページに静的なスピードダイアル要素がある場合
  const existingTrigger = document.querySelector('.speed-dial-trigger');
  if (existingTrigger) {
    initializeSpeedDial();
  }
});
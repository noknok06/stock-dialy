/**
 * スピードダイアル（拡張浮動アクションボタン）実装
 * モバイルでの操作性向上のために使用
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
          btn.style.width = '52px';
          btn.style.height = '52px';
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
    
    // オーバーレイのクリックイベント
    if (this.overlay && this.config.useOverlay) {
      this.overlay.addEventListener('click', () => {
        this.close();
      });
    }
    
    // アクションボタンクリック時の処理
    const actionButtons = this.actions.querySelectorAll('.speed-dial-btn');
    actionButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        // ボタンの種類に応じた処理
        // action-quick-add クラスのボタンはデフォルト動作を停止しない
        // それ以外のボタンはダイアログを閉じる
        if (!btn.classList.contains('action-quick-add')) {
          // データ属性にonclickがあれば優先
          const onclickAttr = btn.getAttribute('data-onclick');
          if (onclickAttr) {
            try {
              eval(onclickAttr);
            } catch (err) {
              console.warn('カスタムクリックハンドラーエラー:', err);
            }
          }
          
          // href="#"の場合やURLがない場合はデフォルト動作を停止
          const href = btn.getAttribute('href');
          if (!href || href === '#') {
            e.preventDefault();
          }
          
          // クイック作成以外はスピードダイアルを閉じる
          this.close();
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
      this.trigger.classList.add('active');
      this.actions.classList.add('active');
      
      if (this.overlay && this.config.useOverlay) {
        this.overlay.classList.add('active');
      }
      
      this.isOpen = true;
    }
  }
  
  close() {
    if (this.isOpen) {
      this.trigger.classList.remove('active');
      this.actions.classList.remove('active');
      
      if (this.overlay && this.config.useOverlay) {
        this.overlay.classList.remove('active');
      }
      
      this.isOpen = false;
    }
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
    position: 'bottom-right'
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
  if (singleActionMode) {
    actionsContainer.classList.add('active');
  }
  
  // アクションボタンを生成
  for (const action of filteredActions) {
    const actionItem = document.createElement('div');
    actionItem.className = 'speed-dial-action';
    
    const btn = document.createElement('a');
    btn.href = action.url || '#';
    btn.className = `speed-dial-btn action-${action.type}`;
    
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
    
    // ラベルの作成（単一アクションモードでも念のため作成するが非表示）
    const label = document.createElement('span');
    label.className = 'action-label';
    label.textContent = action.label || '';
    
    if (singleActionMode) {
      label.style.display = 'none';
      btn.style.width = '52px';
      btn.style.height = '52px';
    }
    
    actionItem.appendChild(label);
    actionItem.appendChild(btn);
    actionsContainer.appendChild(actionItem);
  }
  
  // トリガーボタンを作成
  const trigger = document.createElement('button');
  trigger.className = 'speed-dial-trigger';
  trigger.type = 'button';
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
    useOverlay: config.useOverlay
  });
}

// グローバル初期化関数
function initializeSpeedDial() {
  // 既存のスピードダイアルを初期化
  const speedDial = new SpeedDial();
  
  // コンソールで呼び出せるようにグローバル変数に保持
  window.speedDialInstance = speedDial;
  
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
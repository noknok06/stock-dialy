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
      
      if (this.trigger && this.actions) {
        this.init();
      } else {
        console.warn('SpeedDial: 必要な要素が見つかりません');
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
      
      // アクションボタンクリック時に自動でダイアログを閉じる
      const actionButtons = this.actions.querySelectorAll('.speed-dial-btn');
      actionButtons.forEach(btn => {
        btn.addEventListener('click', () => {
          this.close();
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
    
    // コンテナを作成
    const container = document.createElement('div');
    container.className = 'speed-dial-container';
    
    // アクションボタンコンテナを作成
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'speed-dial-actions';
    
    // アクションボタンを生成
    for (const action of config.actions) {
      if (action.condition === false) continue; // 条件がfalseならスキップ
      
      const actionItem = document.createElement('div');
      actionItem.className = 'speed-dial-action';
      
      const btn = document.createElement('a');
      btn.href = action.url || '#';
      btn.className = `speed-dial-btn action-${action.type}`;
      if (action.onclick) {
        btn.addEventListener('click', (e) => {
          if (!action.url || action.url === '#') {
            e.preventDefault();
          }
          action.onclick(e);
        });
      }
      
      const icon = document.createElement('i');
      icon.className = `bi ${action.icon}`;
      btn.appendChild(icon);
      
      const label = document.createElement('span');
      label.className = 'action-label';
      label.textContent = action.label || '';
      
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
    
    // オーバーレイを作成
    let overlay = null;
    if (config.useOverlay) {
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
    // 既存のスピードダイアル要素を初期化
    const speedDial = new SpeedDial();
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
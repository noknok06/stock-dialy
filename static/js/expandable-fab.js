// expandable-fab.js
// 拡張浮動アクションボタン（Expandable FAB）の動作スクリプト

document.addEventListener('DOMContentLoaded', function () {
    // 要素の取得
    const speedDial = document.querySelector('.speed-dial');
    const trigger = document.querySelector('.speed-dial-trigger');
    const overlay = document.querySelector('.speed-dial-overlay');

    if (!speedDial || !trigger) return;

    // FABの表示/非表示を切り替える関数
    function toggleSpeedDial() {
        speedDial.classList.toggle('active');
        trigger.classList.toggle('active');

        // オーバーレイがある場合は切り替える
        if (overlay) {
            overlay.classList.toggle('active');
        }
    }

    // トリガーボタンのクリックイベント
    trigger.addEventListener('click', function (e) {
        e.preventDefault();
        toggleSpeedDial();
    });

    // オーバーレイがある場合のクリックイベント
    if (overlay) {
        overlay.addEventListener('click', function () {
            toggleSpeedDial();
        });
    }

    // 各アクションボタンのクリックイベント
    const actionButtons = document.querySelectorAll('.speed-dial-action');
    actionButtons.forEach(button => {
        // リンクの場合は通常の動作を維持
        if (button.tagName === 'A' && button.hasAttribute('href')) {
            // 何もしない（デフォルトの動作を維持）
        } else {
            // ボタンの場合はクリック時にダイアルを閉じる
            button.addEventListener('click', function () {
                toggleSpeedDial();
            });
        }
    });

    // Escキーでダイアルを閉じる
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && speedDial.classList.contains('active')) {
            toggleSpeedDial();
        }
    });

    // ダイアル外のクリックで閉じる
    document.addEventListener('click', function (e) {
        if (speedDial.classList.contains('active')) {
            // クリックされた要素がダイアル内かどうかをチェック
            let targetElement = e.target;
            let isClickInside = false;

            while (targetElement != null) {
                if (targetElement === speedDial) {
                    isClickInside = true;
                    break;
                }
                targetElement = targetElement.parentElement;
            }

            if (!isClickInside && !e.target.classList.contains('speed-dial-overlay')) {
                toggleSpeedDial();
            }
        }
    });

    // ページスクロール時に自動的に閉じる
    let scrollTimeout;
    window.addEventListener('scroll', function () {
        if (speedDial.classList.contains('active')) {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(function () {
                toggleSpeedDial();
            }, 150);
        }
    }, { passive: true });
});

// 動的にスピードダイアルを生成する関数
function createSpeedDial(options) {
    options = options || {};

    // デフォルトオプション
    const defaults = {
        container: document.body,          // 追加先のコンテナ
        actions: [],                       // アクションボタン配列
        triggerIcon: 'bi-plus-lg',         // トリガーボタンのアイコン
        triggerClass: '',                  // トリガーボタンの追加クラス
        useOverlay: true,                  // オーバーレイを使用するか
        position: { right: '20px', bottom: '70px' } // 位置指定
    };

    // オプションをマージ
    const settings = Object.assign({}, defaults, options);

    // メインコンテナ作成
    const speedDial = document.createElement('div');
    speedDial.className = 'speed-dial';

    // カスタム位置設定
    if (settings.position) {
        Object.keys(settings.position).forEach(prop => {
            speedDial.style[prop] = settings.position[prop];
        });
    }

    // トリガーボタン作成
    const trigger = document.createElement('button');
    trigger.className = `speed-dial-btn speed-dial-trigger ${settings.triggerClass}`;
    trigger.innerHTML = `<i class="bi ${settings.triggerIcon}"></i>`;
    trigger.setAttribute('aria-label', 'アクションメニューを開く');

    // アクションコンテナ作成
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'speed-dial-actions';

    // アクションボタンを追加
    settings.actions.forEach(action => {
        // アクションラッパー作成
        const actionWrapper = document.createElement('div');
        actionWrapper.className = 'speed-dial-action';

        // アクションボタン作成
        const actionElem = document.createElement(action.url ? 'a' : 'button');

        actionElem.className = `speed-dial-btn action-${action.type || 'default'}`;

        if (action.url) {
            actionElem.href = action.url;
        }

        if (action.onClick) {
            actionElem.addEventListener('click', action.onClick);
        }

        if (action.ariaLabel) {
            actionElem.setAttribute('aria-label', action.ariaLabel);
        }

        // アイコン設定
        actionElem.innerHTML = `<i class="bi ${action.icon}"></i>`;

        // ラベル追加（存在する場合）
        if (action.label) {
            const label = document.createElement('span');
            label.className = 'action-label';
            label.textContent = action.label;
            actionWrapper.appendChild(label);
        }

        // ボタンをラッパーに追加
        actionWrapper.appendChild(actionElem);

        // アクションコンテナに追加
        actionsContainer.appendChild(actionWrapper);
    });

    // コンポーネントを組み立て
    speedDial.appendChild(actionsContainer);
    speedDial.appendChild(trigger);

    // オーバーレイを作成（オプション）
    if (settings.useOverlay) {
        const overlay = document.createElement('div');
        overlay.className = 'speed-dial-overlay';
        settings.container.appendChild(overlay);
    }

    // コンテナに追加
    settings.container.appendChild(speedDial);

    // 新しく追加されたspeedDialに対してJSの初期化を実行する
    const script = document.createElement('script');
    script.textContent = `
      (function() {
        const speedDial = document.querySelector('.speed-dial:last-child');
        const trigger = speedDial.querySelector('.speed-dial-trigger');
        const overlay = document.querySelector('.speed-dial-overlay:last-child');
        
        if (!speedDial || !trigger) return;
        
        function toggleSpeedDial() {
          speedDial.classList.toggle('active');
          trigger.classList.toggle('active');
          
          if (overlay) {
            overlay.classList.toggle('active');
          }
        }
        
        trigger.addEventListener('click', function(e) {
          e.preventDefault();
          toggleSpeedDial();
        });
        
        if (overlay) {
          overlay.addEventListener('click', function() {
            toggleSpeedDial();
          });
        }
        
        const actionButtons = speedDial.querySelectorAll('.speed-dial-action');
        actionButtons.forEach(button => {
          if (!button.querySelector('a[href]')) {
            button.addEventListener('click', function() {
              toggleSpeedDial();
            });
          }
        });
      })();
    `;

    document.body.appendChild(script);

    // 作成したspeedDialを返す
    return speedDial;
}
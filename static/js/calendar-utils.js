// static/js/calendar-utils.js

/**
 * カレンダー関連のユーティリティ関数と共通処理
 */
const CalendarUtils = (function() {
    // カレンダーインスタンスを格納
    let desktopCalendarInstance = null;
    let mobileCalendarInstance = null;
    
    // カレンダーのイベントデータ
    let calendarEvents = [];
    
    // 日記データのキャッシュ
    let diaryData = [];
    
    /**
     * カレンダーイベントとデータを初期化する
     * @param {Array} events - イベントデータ
     * @param {Array} diaries - 日記データ
     */
    function initData(events, diaries) {
      calendarEvents = events || [];
      diaryData = diaries || [];
    }
    
    /**
     * デスクトップカレンダーを初期化する
     * @param {string} elementId - カレンダー要素のID
     * @returns {object} カレンダーインスタンス
     */
    function initDesktopCalendar(elementId, options = {}) {
      const element = document.getElementById(elementId);
      if (!element) {
        console.warn(`Element with ID "${elementId}" not found`);
        return null;
      }
      
      // 既存インスタンスを破棄
      if (desktopCalendarInstance) {
        desktopCalendarInstance.destroy();
      }
      
      // デフォルトオプション
      const defaultOptions = {
        initialView: 'dayGridMonth',
        locale: 'ja',
        height: 450,
        headerToolbar: false,
        events: calendarEvents,
        eventDisplay: 'block',
        dayMaxEventRows: 3
      };
      
      // オプションをマージ
      const calendarOptions = Object.assign({}, defaultOptions, options);
      
      // カレンダーインスタンスを作成
      desktopCalendarInstance = new FullCalendar.Calendar(element, calendarOptions);
      desktopCalendarInstance.render();
      
      return desktopCalendarInstance;
    }
    
    /**
     * モバイルカレンダーを初期化する
     * @param {string} elementId - カレンダー要素のID
     * @returns {object} カレンダーインスタンス
     */
    function initMobileCalendar(elementId, options = {}) {
      const element = document.getElementById(elementId);
      if (!element) {
        console.warn(`Element with ID "${elementId}" not found`);
        return null;
      }
      
      // 既存インスタンスを破棄
      if (mobileCalendarInstance) {
        mobileCalendarInstance.destroy();
      }
      
      // デフォルトオプション
      const defaultOptions = {
        initialView: 'dayGridMonth',
        locale: 'ja',
        height: 350,
        headerToolbar: false,
        events: calendarEvents,
        eventDisplay: 'block',
        dayMaxEventRows: 3
      };
      
      // オプションをマージ
      const calendarOptions = Object.assign({}, defaultOptions, options);
      
      // カレンダーインスタンスを作成
      mobileCalendarInstance = new FullCalendar.Calendar(element, calendarOptions);
      
      // レンダリング前にビューポートの可視性を確認
      const isVisible = element.offsetParent !== null;
      mobileCalendarInstance.render();
      
      // 非表示時はリサイズフラグを設定
      if (!isVisible) {
        element.classList.add('needs-resize');
      }
      
      return mobileCalendarInstance;
    }
    
    /**
     * 選択された日付のイベントを表示する
     * @param {string} dateStr - 日付文字列 (YYYY-MM-DD)
     * @param {boolean} isMobile - モバイル表示かどうか
     */
    function showDayEvents(dateStr, isMobile = false) {
      // DOM要素の取得
      const selectedDateEl = document.getElementById(isMobile ? 'mobile-selected-date' : 'desktop-selected-date');
      const dayEventsEl = document.getElementById(isMobile ? 'mobile-day-events' : 'desktop-day-events');
      const eventsCard = document.getElementById(isMobile ? 'mobile-events-card' : 'desktop-events-card');
      
      if (!selectedDateEl || !dayEventsEl) return;
      
      // タイトル更新
      try {
        const dateObj = new Date(dateStr);
        const year = dateObj.getFullYear();
        const month = dateObj.getMonth() + 1;
        const day = dateObj.getDate();
        
        selectedDateEl.textContent = `${year}年${month}月${day}日のイベント`;
      } catch (e) {
        selectedDateEl.textContent = "選択日のイベント";
      }
      
      // その日のイベントを取得
      const dayEvents = calendarEvents.filter(event => event.start === dateStr);
      
      // イベント表示
      if (dayEvents.length === 0) {
        dayEventsEl.innerHTML = '<p class="text-muted">この日のイベントはありません</p>';
      } else {
        let eventsHtml = '';
        
        for (const event of dayEvents) {
          // イベントの日記IDから対応する日記データを検索
          const diary = diaryData.find(d => d.id === event.diaryId);
          if (!diary) continue;
          
          let badgeClass, badgeText, priceInfo;
          
          if (event.eventType === 'memo') {
            badgeClass = 'bg-info';
            badgeText = 'メモ';
            priceInfo = '<div class="small">記録のみ</div>';
          } else if (event.eventType === 'purchase') {
            badgeClass = 'bg-success';
            badgeText = '購入';
            priceInfo = diary.purchasePrice ? 
              `<div class="small">${diary.purchasePrice.toLocaleString()}円 × ${diary.quantity}株</div>` :
              '<div class="small">価格情報なし</div>';
          } else { // sell
            badgeClass = 'bg-danger';
            badgeText = '売却';
            priceInfo = diary.sellPrice ? 
              `<div class="small">${diary.sellPrice.toLocaleString()}円 × ${diary.quantity}株</div>` :
              '<div class="small">価格情報なし</div>';
          }
          
          eventsHtml += `
            <a href="${event.url}" class="calendar-event-item">
              <span class="badge ${badgeClass}">${badgeText}</span>
              <div>
                <div class="fw-bold">${diary.title} (${diary.symbol})</div>
                ${priceInfo}
              </div>
            </a>
          `;
        }
        
        dayEventsEl.innerHTML = eventsHtml;
      }
      
      // モバイルではイベントカードを表示
      if (isMobile && eventsCard) {
        eventsCard.style.display = 'block';
      }
    }
    
    /**
     * 年月表示を更新する
     * @param {Date} date - 日付オブジェクト
     * @param {boolean} isMobile - モバイル表示かどうか
     */
    function updateCurrentYearMonth(date, isMobile) {
      const year = date.getFullYear();
      const month = date.getMonth() + 1;
      const displayText = `${year}年${month}月`;
      
      const element = document.getElementById(
        isMobile ? 'mobile-current-year-month' : 'desktop-current-year-month'
      );
      
      if (element) {
        element.textContent = displayText;
      }
    }
    
    // 公開API
    return {
      initData,
      initDesktopCalendar,
      initMobileCalendar,
      showDayEvents,
      updateCurrentYearMonth,
      get desktopCalendar() { return desktopCalendarInstance; },
      get mobileCalendar() { return mobileCalendarInstance; }
    };
  })();
// diary-theme.js - カレンダーとモバイル最適化のためのスクリプト

document.addEventListener('DOMContentLoaded', function () {
    // カレンダーの初期化
    initializeCalendar();
    
    // フィルターバッジの初期化
    initializeFilterBadges();
    
    // モバイル向けの調整を実行
    optimizeForMobile();
  });
  
  /**
   * カレンダーを初期化する関数
   */
  function initializeCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    // FullCalendarが読み込まれているか確認
    if (typeof FullCalendar === 'undefined') {
      console.warn('FullCalendar is not loaded');
      return;
    }
    
    // イベントデータを解析
    const events = [];
    
    // サーバーからのデータを使用する場合
    if (window.calendarEvents) {
      events.push(...window.calendarEvents);
    } else {
      // 日記要素からイベントを生成する（代替手段）
      document.querySelectorAll('.diary-card').forEach(diaryCard => {
        const diaryId = diaryCard.dataset.diaryId;
        const stockName = diaryCard.querySelector('.diary-title')?.textContent?.trim() || 'No title';
        const dateEl = diaryCard.querySelector('.diary-date');
        let date = '';
        
        if (dateEl) {
          const dateMatch = dateEl.textContent.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/);
          if (dateMatch) {
            date = `${dateMatch[1]}-${dateMatch[2].padStart(2, '0')}-${dateMatch[3].padStart(2, '0')}`;
          }
        }
        
        const isMemo = diaryCard.classList.contains('memo-card');
        const isSold = diaryCard.classList.contains('sold-card');
        
        if (date) {
          // 購入イベント
          events.push({
            title: stockName,
            start: date,
            url: `/stockdiary/${diaryId}/`,
            className: isMemo ? 'memo-event' : 'purchase-event',
            eventType: isMemo ? 'memo' : 'purchase'
          });
          
        }
      });
    }
    
    // カレンダーの設定
    const calendar = new FullCalendar.Calendar(calendarEl, {
      initialView: 'dayGridMonth',
      locale: 'ja',
      height: window.innerWidth < 768 ? 350 : 450,
      headerToolbar: {
        left: 'prev,next today',
        center: 'title',
        right: 'dayGridMonth'
      },
      events: events,
      eventClick: function(info) {
        info.jsEvent.preventDefault();
        window.location.href = info.event.url;
      },
      dateClick: function(info) {
        showDayEvents(info.dateStr);
        
        // クリックされた日付をハイライト
        document.querySelectorAll('.fc-day-clicked').forEach(el => {
          el.classList.remove('fc-day-clicked');
        });
        info.dayEl.classList.add('fc-day-clicked');
        
        // スマホ表示の場合は自動スクロール
        if (window.innerWidth < 992) {
          const eventsContainer = document.querySelector('.calendar-events');
          if (eventsContainer) {
            eventsContainer.scrollIntoView({ behavior: 'smooth' });
          }
        }
      },
      dayMaxEventRows: 3,
      lazyFetching: true
    });
    
    calendar.render();
    
    // ウィンドウサイズ変更時の処理
    window.addEventListener('resize', function() {
      const newHeight = window.innerWidth < 768 ? 350 : 450;
      calendar.setOption('height', newHeight);
    });
    
    // 初期表示として今日の日付のイベントを表示
    showDayEvents(new Date().toISOString().split('T')[0]);
  }
  
  /**
   * 指定された日付のイベントを表示する関数
   * @param {string} dateStr - YYYY-MM-DD形式の日付文字列
   */
  function showDayEvents(dateStr) {
    if (!dateStr) return;
    
    const selectedDateEl = document.getElementById('selected-date');
    const dayEventsEl = document.getElementById('day-events');
    
    if (!selectedDateEl || !dayEventsEl) return;
    
    // タイトルを更新
    try {
      const dateObj = new Date(dateStr);
      const year = dateObj.getFullYear();
      const month = dateObj.getMonth() + 1;
      const day = dateObj.getDate();
      selectedDateEl.textContent = `${year}年${month}月${day}日のイベント`;
    } catch (e) {
      selectedDateEl.textContent = "選択日のイベント";
    }
    
    // イベントをフィルタリング
    const dayEvents = window.calendarEvents ? 
      window.calendarEvents.filter(event => event.start === dateStr) : 
      [];
    
    if (dayEvents.length === 0) {
      dayEventsEl.innerHTML = '<p class="text-muted">この日のイベントはありません</p>';
      return;
    }
    
    // イベント表示HTMLを生成
    let eventsHtml = '';
    const maxEvents = Math.min(dayEvents.length, 10);
    
    for (let i = 0; i < maxEvents; i++) {
      const event = dayEvents[i];
      
      let eventType, badgeClass, badgeText;
      
      if (event.eventType === 'memo') {
        eventType = 'メモ';
        badgeClass = 'bg-info';
        badgeText = 'メモ';
      } else if (event.eventType === 'purchase') {
        eventType = '購入';
        badgeClass = 'bg-success';
        badgeText = '購入';
      } else { // sell
      }
      
      eventsHtml += `
        <a href="${event.url}" class="calendar-event-item">
          <span class="badge ${badgeClass}">${badgeText}</span>
          <div>
            <div class="fw-bold">${event.title}</div>
          </div>
        </a>
      `;
    }
    
    // 表示件数が制限された場合
    if (dayEvents.length > maxEvents) {
      eventsHtml += `<div class="text-center text-muted small mt-2">他 ${dayEvents.length - maxEvents} 件のイベントがあります</div>`;
    }
    
    dayEventsEl.innerHTML = eventsHtml;
  }
  
  /**
   * フィルターバッジの初期化関数
   */
  function initializeFilterBadges() {
    const filterBadges = document.querySelectorAll('.filter-badge');
    if (!filterBadges.length) return;
    
    filterBadges.forEach(badge => {
      badge.addEventListener('click', function() {
        filterBadges.forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        
        // カスタムイベントを発行（フィルタリング処理用）
        const filterEvent = new CustomEvent('diaryFilter', {
          detail: {
            type: this.dataset.filterType || 'all'
          }
        });
        document.dispatchEvent(filterEvent);
      });
    });
  }
  
  /**
   * モバイル表示の最適化関数
   */
  function optimizeForMobile() {
    // 現在の画面幅を取得
    const isMobile = window.innerWidth < 768;
    
    if (isMobile) {
      // モバイル向けのパディング調整
      const containers = document.querySelectorAll('.container');
      containers.forEach(container => {
        container.style.paddingLeft = '10px';
        container.style.paddingRight = '10px';
      });
      
      // カードのパディング調整
      const cardBodies = document.querySelectorAll('.diary-card-body');
      cardBodies.forEach(body => {
        body.style.padding = '1rem 0.75rem';
      });
      
      // info-item の調整
      const infoItems = document.querySelectorAll('.info-item');
      infoItems.forEach(item => {
        item.style.padding = '0.5rem';
        item.style.minWidth = '140px';
      });
      
      // フォントサイズの調整
      const titles = document.querySelectorAll('.diary-title');
      titles.forEach(title => {
        if (parseFloat(window.getComputedStyle(title).fontSize) > 20) {
          title.style.fontSize = '1.2rem';
        }
      });
    }
  }
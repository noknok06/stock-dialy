// static/js/template.js

// 企業決算データを設定するための関数
function setCompanyData(data) {
  console.log('setCompanyData関数を実行:', data);
  
  // 要素のテキスト設定用ヘルパー関数
  function setElementText(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value || '';
    } else {
      console.warn(`要素が見つかりません: ${id}`);
    }
  }
  
  // 要素のHTML設定用ヘルパー関数
  function setElementHTML(id, html) {
    const element = document.getElementById(id);
    if (element) {
      element.innerHTML = html || '';
    } else {
      console.warn(`要素が見つかりません: ${id}`);
    }
  }
  
  // 会社情報を全ページに共通して設定
  function setCompanyInfoForAllPages() {
    const pages = [1, 2, 3];
    
    pages.forEach(page => {
      const logoElement = document.getElementById(page === 1 ? 'company-logo' : `company-logo-page${page}`);
      if (logoElement) {
        logoElement.textContent = data.companyAbbr || '';
        logoElement.style.backgroundColor = data.companyColor || '#1e40af';
      }
      
      const nameElement = document.getElementById(page === 1 ? 'company-name' : `company-name-page${page}`);
      if (nameElement) {
        nameElement.textContent = data.companyName || '';
      }
      
      const codeElement = document.getElementById(page === 1 ? 'company-code' : `company-code-page${page}`);
      if (codeElement) {
        codeElement.textContent = data.companyCode ? `(${data.companyCode})` : '';
      }
      
      const periodElement = document.getElementById(page === 1 ? 'fiscal-period' : `fiscal-period-page${page}`);
      if (periodElement) {
        periodElement.textContent = data.fiscalPeriod || '';
      }
    });
  }
  
  try {
    // 会社情報を設定
    setCompanyInfoForAllPages();
    
    // ページ1のデータを設定
    setElementText('achievement-badge', data.achievementBadge || '');
    setElementText('overall-rating-display', data.overallRating || '0');
    setElementText('overall-rating-text', `総合評価：${data.overallRatingText || ''}`);
    setElementText('overall-summary', data.overallSummary || '');
    setElementText('recommendation-text', data.recommendationText || '');
    setElementText('star-rating', data.starRating || '');
    setElementText('investment-reason', data.investmentReason || '');
    
    // 総合評価の円グラフとメーターに数値を表示して色付け
    enhanceRatingVisuals(data);
    
    // 業績ハイライト
    setElementText('performance-rating-badge', data.performanceRating ? `${data.performanceRating}/10` : '/10');
    setElementText('net-income', data.netIncome || '');
    setElementHTML('net-income-change', `
      <i class="bi bi-graph-up-arrow me-1"></i> ${data.netIncomeChange || ''}
    `);
    setElementText('eps', data.eps || '');
    setElementHTML('eps-change', `
      <i class="bi bi-graph-up-arrow me-1"></i> ${data.epsChange || ''}
    `);
    setElementText('dividend', data.dividend || '');
    setElementHTML('dividend-change', `
      <i class="bi bi-graph-up-arrow me-1"></i> ${data.dividendChange || ''}
    `);
    setElementText('roe', data.roe || '');
    setElementHTML('roe-change', `
      <i class="bi ${data.roeChange && data.roeChange.includes('-') ? 'bi-graph-down-arrow' : 'bi-graph-up-arrow'} me-1"></i> ${data.roeChange || ''}
    `);
    
    // 業績評価
    setElementText('performance-rating-text', data.performanceRating ? `${data.performanceRating}/10` : '/10');
    setElementText('performance-rating-category', data.performanceRatingCategory || '');
    setElementText('performance-point-1', data.performancePoint1 || '');
    setElementText('performance-point-2', data.performancePoint2 || '');
    setElementText('performance-point-3', data.performancePoint3 || '');
    
    // 市場予想比較
    setElementText('sales', data.sales || '');
    setElementText('sales-forecast', data.salesForecast || '');
    setElementText('sales-vs-forecast', data.salesVsForecast || '');
    setElementText('operating-profit', data.operatingProfit || '');
    setElementText('operating-profit-forecast', data.operatingProfitForecast || '');
    setElementText('operating-profit-vs-forecast', data.operatingProfitVsForecast || '');
    setElementText('net-income-table', data.netIncome || '');
    setElementText('net-income-forecast', data.netIncomeForecast || '');
    setElementText('net-income-vs-forecast', data.netIncomeVsForecast || '');
    setElementText('forecast-comparison-rating', data.forecastComparisonRating || '0');
    setElementText('forecast-comparison-category', data.forecastComparisonCategory || '');
    setElementText('forecast-comparison-comment', data.forecastComparisonComment || '');
    
    // 決算ポイント
    setElementText('key-points-rating-badge', `評価: ${data.keyPointsRating || ''}/10`);
    const keyPointsContainer = document.getElementById('key-points');
    if (keyPointsContainer) {
      keyPointsContainer.innerHTML = ''; // 既存のポイントをクリア
      
      if (data.keyPoints && Array.isArray(data.keyPoints)) {
        data.keyPoints.forEach(point => {
          const li = document.createElement('li');
          li.className = 'flex items-start gap-2';
          
          const iconDiv = document.createElement('div');
          iconDiv.className = `flex-shrink-0 h-5 w-5 ${point.positive ? 'bg-green-100' : 'bg-amber-100'} rounded-full flex items-center justify-center mt-0.5`;
          
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('class', `h-3 w-3 ${point.positive ? 'text-green-600' : 'text-amber-600'}`);
          svg.setAttribute('fill', 'none');
          svg.setAttribute('viewBox', '0 0 24 24');
          svg.setAttribute('stroke', 'currentColor');
          
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('stroke-linejoin', 'round');
          path.setAttribute('stroke-width', '2');
          path.setAttribute('d', point.positive ? 'M5 10l7-7m0 0l7 7m-7-7v18' : 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z');
          
          svg.appendChild(path);
          iconDiv.appendChild(svg);
          
          const span = document.createElement('span');
          span.textContent = point.text || '';
          
          li.appendChild(iconDiv);
          li.appendChild(span);
          keyPointsContainer.appendChild(li);
        });
      }
    }
    
    setElementText('key-points-rating-text', data.keyPointsRating ? `${data.keyPointsRating}/10` : '/10');
    setElementText('key-points-rating-category', data.keyPointsRatingCategory || '');
    setElementText('key-points-point-1', data.keyPointsPoint1 || '');
    setElementText('key-points-point-2', data.keyPointsPoint2 || '');
    setElementText('key-points-point-3', data.keyPointsPoint3 || '');
    
    // セグメント評価
    setElementText('segment-rating-badge', `評価: ${data.segmentRating || ''}/10`);
    setElementText('segment-rating-text', data.segmentRating ? `${data.segmentRating}/10` : '/10');
    setElementText('segment-rating-category', data.segmentRatingCategory || '');
    setElementText('segment-point-1', data.segmentPoint1 || '');
    setElementText('segment-point-2', data.segmentPoint2 || '');
    setElementText('segment-point-3', data.segmentPoint3 || '');
    
    // セグメント詳細
    const segmentsContainer = document.getElementById('segments-container');
    if (segmentsContainer) {
      segmentsContainer.innerHTML = ''; // 既存のセグメントをクリア
      
      if (data.segments && Array.isArray(data.segments)) {
        data.segments.forEach(segment => {
          const div = document.createElement('div');
          div.className = `segment-card ${segment.profit ? 'positive' : 'negative'}`;
          
          const titleDiv = document.createElement('div');
          titleDiv.className = `text-sm font-bold ${segment.profit ? 'text-green-800' : 'text-red-800'} mb-1`;
          titleDiv.textContent = segment.name || '';
          
          const valueDiv = document.createElement('div');
          valueDiv.className = 'text-base font-bold mb-1';
          valueDiv.textContent = segment.value || '';
          
          const changeDiv = document.createElement('div');
          changeDiv.className = `change-indicator ${segment.change && segment.change.includes('-') ? 'negative' : 'positive'}`;
          
          const icon = document.createElement('i');
          icon.className = `bi ${segment.change && segment.change.includes('-') ? 'bi-graph-down-arrow' : 'bi-graph-up-arrow'} me-1`;
          
          const span = document.createElement('span');
          span.className = 'font-bold';
          span.textContent = segment.change || '';
          
          changeDiv.appendChild(icon);
          changeDiv.appendChild(span);
          
          const descP = document.createElement('p');
          descP.className = 'text-xs text-gray-600 mt-1';
          descP.textContent = segment.description || '';
          
          div.appendChild(titleDiv);
          div.appendChild(valueDiv);
          div.appendChild(changeDiv);
          div.appendChild(descP);
          
          segmentsContainer.appendChild(div);
        });
      }
    }
    
    // 来期予想
    setElementText('next-fiscal-rating-badge', `評価: ${data.nextFiscalRating || ''}/10`);
    setElementText('next-fiscal-net-income', data.nextFiscalNetIncome || '');
    setElementHTML('next-fiscal-net-income-change', `
      <i class="bi bi-graph-up-arrow me-1"></i> ${data.nextFiscalNetIncomeChange || ''}
    `);
    setElementText('next-fiscal-dividend', data.nextFiscalDividend || '');
    setElementHTML('next-fiscal-dividend-change', `
      <i class="bi bi-graph-up-arrow me-1"></i> ${data.nextFiscalDividendChange || ''}
    `);
    setElementText('next-fiscal-highlight', data.nextFiscalHighlight || '');
    setElementText('next-fiscal-rating-text', data.nextFiscalRating ? `${data.nextFiscalRating}/10` : '/10');
    setElementText('next-fiscal-rating-category', data.nextFiscalRatingCategory || '');
    setElementText('next-fiscal-point-1', data.nextFiscalPoint1 || '');
    setElementText('next-fiscal-point-2', data.nextFiscalPoint2 || '');
    setElementText('next-fiscal-point-3', data.nextFiscalPoint3 || '');
    
    // 財務状態
    // setElementText('financial-rating-badge', `評価: ${data.financialRating || ''}/10`);
    // setElementText('equity-ratio', data.equityRatio || '');
    // setElementHTML('equity-ratio-change', `
    //   <i class="bi bi-graph-up-arrow me-1"></i> ${data.equityRatioChange || ''}
    // `);
    // setElementText('operating-cash-flow', data.operatingCashFlow || '');
    // setElementHTML('operating-cash-flow-change', `
    //   <i class="bi bi-graph-up-arrow me-1"></i> ${data.operatingCashFlowChange || ''}
    // `);
    // setElementText('liquid-assets', data.liquidAssets || '');
    // setElementHTML('liquid-assets-change', `
    //   <i class="bi bi-graph-up-arrow me-1"></i> ${data.liquidAssetsChange || ''}
    // `);
    // setElementText('financial-rating-text', data.financialRating ? `${data.financialRating}/10` : '/10');
    // setElementText('financial-rating-category', data.financialRatingCategory || '');
    // setElementText('financial-point-1', data.financialPoint1 || '');
    // setElementText('financial-point-2', data.financialPoint2 || '');
    // setElementText('financial-point-3', data.financialPoint3 || '');
    
    // // データソース
    // setElementText('data-source', data.dataSource || '');
    
    // ポジティブポイント
    const positivePointsContainer = document.getElementById('positive-points');
    if (positivePointsContainer) {
      positivePointsContainer.innerHTML = ''; // 既存のポイントをクリア
      
      if (data.positivePoints && Array.isArray(data.positivePoints)) {
        data.positivePoints.forEach(point => {
          const li = document.createElement('li');
          li.textContent = point;
          positivePointsContainer.appendChild(li);
        });
      }
    }
    
    // ネガティブポイント
    const negativePointsContainer = document.getElementById('negative-points');
    if (negativePointsContainer) {
      negativePointsContainer.innerHTML = ''; // 既存のポイントをクリア
      
      if (data.negativePoints && Array.isArray(data.negativePoints)) {
        data.negativePoints.forEach(point => {
          const li = document.createElement('li');
          li.textContent = point;
          negativePointsContainer.appendChild(li);
        });
      }
    }
    
    setRatingBarStyles({
      'overview-rating-bar': data.overallRating,
      'performance-rating-meter': data.performanceRating,
      'forecast-comparison-meter': data.forecastComparisonRating,
      'key-points-meter': data.keyPointsRating,
      'next-fiscal-meter': data.nextFiscalRating,
      'segment-rating-meter': data.segmentRating
    });
    
    // 変動インジケーターのスタイル設定
    styleChangeIndicators();
    
    console.log('データ表示完了');
  } catch (error) {
    console.error('データ表示中にエラーが発生しました:', error);
  }
}

// 評価の視覚的な表現を強化する関数
function enhanceRatingVisuals(data) {
  // 評価円に評価値を表示
  const overviewRating = document.getElementById('overview-rating');
  if (overviewRating) {
    overviewRating.textContent = data.overallRating || '0';
    
    // アニメーション用のクラス追加
    overviewRating.classList.add('animate-in');
  }
  
  // 評価円のスタイルを評価に応じて変更
  const ratingCircle = document.querySelector('.rating-circle');
  if (ratingCircle) {
    const rating = parseFloat(data.overallRating) || 0;
    
    // 評価によって円の色を変更
    if (rating >= 7) {
      ratingCircle.style.backgroundColor = 'rgba(16, 185, 129, 0.15)'; // success-light
      ratingCircle.style.boxShadow = '0 0 0 6px rgba(16, 185, 129, 0.1)';
    } else if (rating >= 4) {
      ratingCircle.style.backgroundColor = 'rgba(245, 158, 11, 0.15)'; // warning-light
      ratingCircle.style.boxShadow = '0 0 0 6px rgba(245, 158, 11, 0.1)';
    } else {
      ratingCircle.style.backgroundColor = 'rgba(239, 68, 68, 0.15)'; // danger-light
      ratingCircle.style.boxShadow = '0 0 0 6px rgba(239, 68, 68, 0.1)';
    }
  }
}

// 変動インジケーターのスタイル設定
function styleChangeIndicators() {
  const changeIndicators = document.querySelectorAll('.change-indicator');
  changeIndicators.forEach(indicator => {
    const text = indicator.textContent;
    if (!text) return;
    
    // 既にクラスが設定されている場合はスキップ
    if (indicator.classList.contains('positive') || indicator.classList.contains('negative')) {
      return;
    }
    
    if (text && !text.includes('-')) {
      indicator.classList.add('positive');
    } else if (text) {
      indicator.classList.add('negative');
    }
  });
}

// 評価メーターの更新関数
function updateRatingMeter(meterId, ratingValue) {
  const meter = document.getElementById(meterId);
  if (!meter) {
    console.warn(`メーター要素が見つかりません: ${meterId}`);
    return;
  }
  
  try {
    // 評価値を取得（0-10の範囲）
    const value = parseFloat(ratingValue) || 0;
    const percentage = Math.min(Math.max(value * 10, 0), 100); // 0-100%の範囲に制限
    
    // 評価値に応じてメーターの幅と色を設定
    meter.style.width = '0%'; // 最初は0から始める（アニメーション用）
    
    // トランジションを設定
    meter.style.transition = 'width 1s ease-out, background-color 0.5s ease';
    
    // 少し遅延させてアニメーション効果を出す
    setTimeout(() => {
      meter.style.width = `${percentage}%`;
      
      // 評価に基づいて色を設定
      if (value >= 7) {
        meter.style.backgroundColor = 'var(--success)';
        meter.classList.add('high-rating');
      } else if (value >= 4) {
        meter.style.backgroundColor = 'var(--warning)';
        meter.classList.add('medium-rating');
      } else {
        meter.style.backgroundColor = 'var(--danger)';
        meter.classList.add('low-rating');
      }
      
      // 光沢エフェクトを追加
      addShineEffect(meter);
    }, 100);
  } catch (error) {
    console.error(`メーター「${meterId}」の更新中にエラーが発生しました:`, error);
  }
}
// 評価メーターのスタイルを設定する関数 - アニメーション修正版
function setRatingBarStyles(ratingBars) {
  // スタイルの初期化
  addRatingBarStyles();
  
  // 各メーターを処理
  Object.entries(ratingBars).forEach(([id, ratingValue], index) => {
    const element = document.getElementById(id);
    if (!element) {
      console.warn(`メーター要素が見つかりません: ${id}`);
      return;
    }
    
    // 評価値を解析
    const value = parseFloat(ratingValue) || 0;
    const percentage = (value / 10) * 100;
    
    // 最初にトランジションをオフにして幅を0に設定
    element.style.transition = 'none';
    element.style.width = '0%';
    
    // クラスをリセットして基本クラスを設定
    element.className = 'rating-bar-value';
    
    // アニメーション用のクラスを追加
    element.classList.add('animated-bar');
    
    // 強制的なリフローを発生させてCSSの変更を確定
    element.offsetWidth;
    
    // わずかな遅延を入れて処理を確実に分離
    setTimeout(() => {
      // トランジションをオンにして幅を設定
      element.style.transition = 'width 1s ease-out';
      element.style.width = `${percentage}%`;
    }, 100 + (index * 50));
  });
}

// 評価バーのスタイルをCSSに追加 - アニメーション修正版
function addRatingBarStyles() {
  if (document.getElementById('rating-bar-styles')) return;
  
  const style = document.createElement('style');
  style.id = 'rating-bar-styles';
  style.textContent = `
    .rating-bar-value {
      position: relative;
      overflow: hidden;
      background-color: var(--primary, #3b82f6); /* 常に同じ色を使用 */
      width: 0%; /* 初期幅を0に設定 */
      height: 100%;
      border-radius: 9999px;
    }
    
    .animated-bar::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-image: linear-gradient(
        90deg,
        rgba(255, 255, 255, 0) 0%,
        rgba(255, 255, 255, 0.4) 50%,
        rgba(255, 255, 255, 0) 100%
      );
      background-size: 200% 100%;
      animation: shine 2.5s infinite linear;
      pointer-events: none;
    }
    
    @keyframes shine {
      from { background-position: -100% 0; }
      to { background-position: 200% 0; }
    }
    
    .animate-in {
      animation: scaleIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    
    @keyframes scaleIn {
      0% { transform: scale(0); opacity: 0; }
      70% { transform: scale(1.1); opacity: 1; }
      100% { transform: scale(1); opacity: 1; }
    }
    
    .rating-circle::before {
      content: '';
      position: absolute;
      top: 5px;
      left: 5px;
      right: 5px;
      bottom: 5px;
      border-radius: 50%;
      border: 2px dashed var(--primary, #2563eb);
      border-left-color: transparent;
      border-bottom-color: transparent;
      animation: rotate 8s linear infinite;
    }
    
    @keyframes rotate {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}
// 変動インジケーターのスタイル設定
function styleChangeIndicators() {
  const changeIndicators = document.querySelectorAll('.change-indicator');
  changeIndicators.forEach(indicator => {
    const text = indicator.textContent;
    if (!text) return;
    
    // 既にクラスが設定されている場合はスキップ
    if (indicator.classList.contains('positive') || indicator.classList.contains('negative')) {
      return;
    }
    
    if (text && !text.includes('-')) {
      indicator.classList.add('positive');
    } else if (text) {
      indicator.classList.add('negative');
    }
  });
}

// 光沢エフェクトを追加する関数
function addShineEffect(element) {
  // すでに光沢エフェクトが適用されていたら何もしない
  if (element.classList.contains('has-shine')) return;
  
  element.classList.add('has-shine');
  element.style.position = 'relative';
  element.style.overflow = 'hidden';
  
  // 光沢エフェクト用の疑似要素のスタイルを作成
  if (!document.getElementById('shine-effect-style')) {
    const style = document.createElement('style');
    style.id = 'shine-effect-style';
    style.textContent = `
      .has-shine::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(
          90deg,
          rgba(255, 255, 255, 0) 0%,
          rgba(255, 255, 255, 0.4) 50%,
          rgba(255, 255, 255, 0) 100%
        );
        transform: translateX(-100%);
        animation: shine 2s infinite;
      }
      
      @keyframes shine {
        100% {
          transform: translateX(100%);
        }
      }
      
      .animate-in {
        animation: scaleIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      @keyframes scaleIn {
        0% { transform: scale(0); opacity: 0; }
        70% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(1); opacity: 1; }
      }
      
      .rating-circle::before {
        content: '';
        position: absolute;
        top: 5px;
        left: 5px;
        right: 5px;
        bottom: 5px;
        border-radius: 50%;
        border: 2px dashed var(--primary);
        border-left-color: transparent;
        border-bottom-color: transparent;
        animation: rotate 8s linear infinite;
      }
      
      @keyframes rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
  }
}

// ページ切り替え機能
function goToPage(pageNumber) {
  console.log(`ページ切り替え: ${pageNumber}`);
  
  try {
    // すべてのページを非表示にする
    document.querySelectorAll('.page').forEach(page => {
      page.classList.remove('active');
    });
    
    // 選択したページを表示する
    const selectedPage = document.getElementById(`page${pageNumber}`);
    if (selectedPage) {
      selectedPage.classList.add('active');
      
      // ページインジケーターを更新
      document.querySelectorAll('.page-indicator-dot').forEach((dot, index) => {
        if (index === pageNumber - 1) {
          dot.classList.add('active');
        } else {
          dot.classList.remove('active');
        }
      });
    } else {
      console.warn(`ページが見つかりません: page${pageNumber}`);
    }
  } catch (error) {
    console.error('ページ切り替え中にエラーが発生しました:', error);
  }
}

// タブ切り替え機能を初期化
function initTabs() {
  const tabButtons = document.querySelectorAll('.tab-button');
  const tabContents = document.querySelectorAll('.tab-content');
  const tabIndicator = document.querySelector('.tab-indicator');
  
  function updateTabIndicator(activeTab) {
    if (!tabIndicator) return;
    
    const tabWidth = activeTab.offsetWidth;
    const tabLeft = activeTab.offsetLeft;
    
    tabIndicator.style.width = `${tabWidth}px`;
    tabIndicator.style.left = `${tabLeft}px`;
  }
  
  // 初期インジケーター位置を設定
  const activeTab = document.querySelector('.tab-button.active');
  if (activeTab && tabIndicator) {
    updateTabIndicator(activeTab);
  }
  
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const tabId = button.getAttribute('data-tab');
      
      // アクティブなタブボタンとコンテンツを更新
      tabButtons.forEach(btn => btn.classList.remove('active'));
      tabContents.forEach(content => content.classList.remove('active'));
      
      button.classList.add('active');
      document.getElementById(`tab-${tabId}`).classList.add('active');
      
      // タブインジケーターを更新
      updateTabIndicator(button);
    });
  });
}

// アコーディオン機能を初期化
function initAccordions() {
  const accordionHeaders = document.querySelectorAll('[data-toggle="collapse"]');
  
  accordionHeaders.forEach(header => {
    header.addEventListener('click', () => {
      const targetId = header.getAttribute('data-target');
      const targetElement = document.querySelector(targetId);
      const chevronIcon = header.querySelector('.chevron-icon');
      
      if (targetElement.classList.contains('show')) {
        targetElement.classList.remove('show');
        chevronIcon.classList.remove('rotated');
      } else {
        targetElement.classList.add('show');
        chevronIcon.classList.add('rotated');
      }
    });
  });
}

// template.js の最後の部分だけを修正

// デバッグのためのページ読み込み完了イベントリスナー
document.addEventListener('DOMContentLoaded', function() {
  console.log('template.js: DOMContentLoaded');
  
  // タブ切り替え機能を初期化
  initTabs();
  
  // アコーディオン機能を初期化
  initAccordions();
  
  // レポートデータを処理
  try {
    // データの取得方法を改善
    let reportData;
    
    // 1. window.reportDataからデータを取得（最も優先）
    if (window.reportData && typeof window.reportData === 'object') {
      reportData = window.reportData;
      console.log('window.reportDataからデータを取得しました');
    } 
    // 2. #report-dataスクリプトからデータを取得
    else {
      const dataScript = document.getElementById('report-data');
      if (dataScript) {
        try {
          reportData = JSON.parse(dataScript.textContent);
          console.log('#report-dataからデータを取得しました');
        } catch (e) {
          console.error('JSONパースエラー:', e);
        }
      }
    }
    
    // 3. データが取得できない場合はDOM要素から取得
    if (!reportData || Object.keys(reportData).length === 0) {
      console.log('DOM要素からデータを収集します');
      reportData = {
        companyName: document.getElementById('company-name')?.textContent?.trim() || '',
        companyCode: document.getElementById('company-code')?.textContent?.trim().replace(/[()]/g, '') || '',
        companyAbbr: document.getElementById('company-logo')?.textContent?.trim() || '',
        companyColor: document.getElementById('company-logo')?.style?.backgroundColor || '#3B82F6',
        fiscalPeriod: document.getElementById('fiscal-period')?.textContent?.trim() || '',
        achievementBadge: document.getElementById('achievement-badge')?.textContent?.trim() || '',
        overallRating: document.getElementById('overall-rating-display')?.textContent?.trim() || '0',
        overallSummary: document.getElementById('overall-summary')?.textContent?.trim() || ''
      };
    }
    
    console.log('レポートデータ:', reportData);
    
    // メーターの表示を即時適用（インラインスクリプトと競合を避けるため）
    setupInitialMeters(reportData);
    
    // テンプレートにデータを適用
    if (Object.keys(reportData).length > 0) {
      setCompanyData(reportData);
    } else {
      console.error('データが空のため、setCompanyData関数は実行しません');
    }
  } catch (error) {
    console.error('データ処理中にエラーが発生しました:', error);
  }
});

// メーターの初期表示を設定する関数
function setupInitialMeters(data) {
  // メーター要素のIDリスト
  const meterIds = [
    'overview-rating-bar',
    'performance-rating-meter',
    'forecast-comparison-meter',
    'key-points-meter',
    'next-fiscal-meter',
    'segment-rating-meter'
  ];
  
  // メーターのスタイルを設定
  addRatingBarStyles();
  
  // 各メーターを処理
  meterIds.forEach(id => {
    const element = document.getElementById(id);
    if (!element) return;
    
    // 対応する評価値を取得
    let value;
    switch (id) {
      case 'overview-rating-bar': value = data.overallRating; break;
      case 'performance-rating-meter': value = data.performanceRating; break;
      case 'forecast-comparison-meter': value = data.forecastComparisonRating; break;
      case 'key-points-meter': value = data.keyPointsRating; break;
      case 'next-fiscal-meter': value = data.nextFiscalRating; break;
      case 'segment-rating-meter': value = data.segmentRating; break;
      default: value = 0;
    }
    
    // 数値に変換
    const rating = parseFloat(value) || 0;
    const percentage = (rating / 10) * 100;
    
    // 初期設定
    element.style.transition = 'none';
    element.style.width = '0%';
    element.className = 'rating-bar-value bg-primary';
    
    // 強制的なリフロー
    element.offsetWidth;
    
    // アニメーション
    setTimeout(() => {
      element.style.transition = 'width 1s ease-out';
      element.style.width = `${percentage}%`;
    }, 100);
  });
}
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
    
    // 業績ハイライト
    setElementText('performance-rating-badge', data.performanceRating ? `${data.performanceRating}/10` : '/10');
    setElementText('net-income', data.netIncome || '');
    setElementHTML('net-income-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-2 w-2 mr-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      前年比 ${data.netIncomeChange || ''}
    `);
    setElementText('eps', data.eps || '');
    setElementHTML('eps-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-2 w-2 mr-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      前年比 ${data.epsChange || ''}
    `);
    setElementText('dividend', data.dividend || '');
    setElementHTML('dividend-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-2 w-2 mr-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      前年比 ${data.dividendChange || ''}
    `);
    setElementText('roe', data.roe || '');
    setElementHTML('roe-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-2 w-2 mr-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      ${data.roeChange || ''}
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
          div.className = `bg-gradient-to-br ${segment.profit ? 'from-green-50 to-green-100 border border-green-200' : 'from-red-50 to-red-100 border border-red-200'} rounded-lg p-2`;
          
          const titleDiv = document.createElement('div');
          titleDiv.className = `text-sm font-bold ${segment.profit ? 'text-green-800' : 'text-red-800'} mb-1`;
          titleDiv.textContent = segment.name || '';
          
          const valueDiv = document.createElement('div');
          valueDiv.className = 'text-base font-bold mb-1';
          valueDiv.textContent = segment.value || '';
          
          const changeDiv = document.createElement('div');
          changeDiv.className = `flex items-center ${segment.profit ? 'text-green-600' : 'text-red-600'} text-xs`;
          
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('class', 'h-3 w-3 mr-1');
          svg.setAttribute('fill', 'none');
          svg.setAttribute('viewBox', '0 0 24 24');
          svg.setAttribute('stroke', 'currentColor');
          
          const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('stroke-linecap', 'round');
          path.setAttribute('stroke-linejoin', 'round');
          path.setAttribute('stroke-width', '2');
          path.setAttribute('d', segment.profit ? 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' : 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6');
          
          svg.appendChild(path);
          
          const span = document.createElement('span');
          span.className = 'font-bold';
          span.textContent = segment.change || '';
          
          changeDiv.appendChild(svg);
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
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      前年比 ${data.nextFiscalNetIncomeChange || ''}
    `);
    setElementText('next-fiscal-dividend', data.nextFiscalDividend || '');
    setElementHTML('next-fiscal-dividend-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      ${data.nextFiscalDividendChange || ''}
    `);
    setElementText('next-fiscal-highlight', data.nextFiscalHighlight || '');
    setElementText('next-fiscal-rating-text', data.nextFiscalRating ? `${data.nextFiscalRating}/10` : '/10');
    setElementText('next-fiscal-rating-category', data.nextFiscalRatingCategory || '');
    setElementText('next-fiscal-point-1', data.nextFiscalPoint1 || '');
    setElementText('next-fiscal-point-2', data.nextFiscalPoint2 || '');
    setElementText('next-fiscal-point-3', data.nextFiscalPoint3 || '');
    
    // 財務状態
    setElementText('financial-rating-badge', `評価: ${data.financialRating || ''}/10`);
    setElementText('equity-ratio', data.equityRatio || '');
    setElementHTML('equity-ratio-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      ${data.equityRatioChange || ''}
    `);
    setElementText('operating-cash-flow', data.operatingCashFlow || '');
    setElementHTML('operating-cash-flow-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      ${data.operatingCashFlowChange || ''}
    `);
    setElementText('liquid-assets', data.liquidAssets || '');
    setElementHTML('liquid-assets-change', `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
      </svg>
      ${data.liquidAssetsChange || ''}
    `);
    setElementText('financial-rating-text', data.financialRating ? `${data.financialRating}/10` : '/10');
    setElementText('financial-rating-category', data.financialRatingCategory || '');
    setElementText('financial-point-1', data.financialPoint1 || '');
    setElementText('financial-point-2', data.financialPoint2 || '');
    setElementText('financial-point-3', data.financialPoint3 || '');
    
    // データソース
    setElementText('data-source', data.dataSource || '');
    
    // ポジティブポイント
    const positivePointsContainer = document.getElementById('positive-points');
    if (positivePointsContainer) {
      positivePointsContainer.innerHTML = ''; // 既存のポイントをクリア
      
      if (data.positivePoints && Array.isArray(data.positivePoints)) {
        data.positivePoints.forEach(point => {
          const li = document.createElement('li');
          li.className = 'text-xs';
          li.textContent = `• ${point}`;
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
          li.className = 'text-xs';
          li.textContent = `• ${point}`;
          negativePointsContainer.appendChild(li);
        });
      }
    }
    
    // 評価メーターの更新
    updateRatingMeter('performance-rating-meter', data.performanceRating || 0);
    updateRatingMeter('forecast-comparison-meter', data.forecastComparisonRating || 0);
    updateRatingMeter('key-points-meter', data.keyPointsRating || 0);
    updateRatingMeter('next-fiscal-meter', data.nextFiscalRating || 0);
    updateRatingMeter('segment-rating-meter', data.segmentRating || 0);
    updateRatingMeter('financial-rating-meter', data.financialRating || 0);
    
    console.log('データ表示完了');
  } catch (error) {
    console.error('データ表示中にエラーが発生しました:', error);
  }
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
    meter.style.width = `${percentage}%`;
    
    if (value >= 7) {
      meter.className = 'rating-meter-value bg-green-600';
    } else if (value >= 4) {
      meter.className = 'rating-meter-value bg-yellow-500';
    } else {
      meter.className = 'rating-meter-value bg-red-500';
    }
  } catch (error) {
    console.error(`メーター「${meterId}」の更新中にエラーが発生しました:`, error);
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

// デバッグのためのページ読み込み完了イベントリスナー
document.addEventListener('DOMContentLoaded', function() {
  console.log('template.js: DOMContentLoaded');
  console.log('ページ切り替え機能が利用可能です');
});
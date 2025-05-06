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

// レポートデータ初期化関数
document.addEventListener('DOMContentLoaded', function() {
  console.log('レポート詳細インラインスクリプト実行開始');
  
  try {
    // レポートデータをJSONオブジェクトとして取得
    // Django テンプレートから渡されたデータがある場合はそれを使用
    let reportData;
    
    // Django テンプレートからのデータがある場合（実際の環境で使用）
    if (typeof djangoReportData !== 'undefined') {
      reportData = djangoReportData;
    } else {
      // テスト用データ（テンプレートからデータが渡されない場合）
      reportData = {'companyAbbr': 'MRB', 'companyColor': '#E60012', 'companyName': '丸紅株式会社', 'companyCode': '8002', 'fiscalPeriod': '2025年3月期 決算サマリー', 'achievementBadge': '過去2番目の高水準達成', 'overallRating': '8.5', 'overallRatingText': '優秀（7-9点）', 'overallSummary': '前期比6.7%増益となる5,030億円の純利益を計上し、従来見通しを上回る好業績。非資源分野は過去最高の3,230億円の実態純利益を達成。積極的な資本配分と株主還元も強化し、総合的に良好な決算内容。', 'recommendationText': '買い推奨', 'starRating': '★★★★☆', 'investmentReason': '非資源事業の安定的な収益拡大と積極的な株主還元策が評価でき、PER8.4倍と割安感もある。中期経営戦略で掲げる時価総額10兆円目標に向けた成長期待も投資魅力。', 'performanceRating': '8', 'netIncome': '5,030億円', 'netIncomeChange': '+316億円 (+6.7%)', 'eps': '302.78円', 'epsChange': '+23.16円 (+8.3%)', 'dividend': '95円', 'dividendChange': '+10円 (+11.8%)', 'roe': '14.2%', 'roeChange': '-1.0pt', 'performanceRatingCategory': '優秀', 'performancePoint1': '純利益5,030億円は従来見通しの5,000億円を上回り、過去2番目の高水準を達成', 'performancePoint2': '非資源分野の実態純利益は3,230億円と過去最高を更新（資源分野は1,300億円で減益）', 'performancePoint3': '年間配当は95円（中間45円、期末50円）と増配、自己株式取得も800億円規模で実施', 'sales': '7兆7,902億円', 'salesForecast': '7兆2,505億円', 'salesVsForecast': '+7.4%', 'operatingProfit': '2,723億円', 'operatingProfitForecast': '2,763億円', 'operatingProfitVsForecast': '-1.5%', 'netIncomeForecast': '4,714億円', 'netIncomeVsForecast': '+6.7%', 'forecastComparisonRating': '7', 'forecastComparisonCategory': '良好', 'forecastComparisonComment': '売上高と純利益は市場予想を上回り、営業利益は微減も全体として市場期待を上回る結果。特に非資源分野の好調が予想を上回る要因。', 'keyPointsRating': '8', 'keyPoints': [{'positive': true, 'text': '既存事業領域の強化により、年間4,500億円超の収益基盤を確立'}, {'positive': true, 'text': '基礎営業キャッシュフローは+6,066億円と過去最高を達成（前年度比+586億円）'}, {'positive': true, 'text': '戦略プラットフォーム型事業を中心とした非資源分野の利益成長が増益を牽引'}, {'positive': false, 'text': '資源分野の原料炭事業・石油ガス開発事業は市況下落等により減益（-160億円）'}], 'keyPointsRatingCategory': '優秀', 'keyPointsPoint1': '非資源分野の実態純利益が3,230億円と過去最高を達成し、ポートフォリオバランスの改善が進展', 'keyPointsPoint2': '基礎営業CFも+6,066億円と順調に成長（GC2021開始以降のCAGR8%）し、財務基盤が強化', 'keyPointsPoint3': '資源分野は市況下落の影響を受け1,300億円（-240億円）と減益も、全体をカバーする非資源の成長', 'nextFiscalRating': '7', 'nextFiscalNetIncome': '5,100億円', 'nextFiscalNetIncomeChange': '+70億円 (+1.4%)', 'nextFiscalDividend': '100円（予想）', 'nextFiscalDividendChange': '+5円', 'nextFiscalHighlight': '2期連続の高水準利益を目指す', 'nextFiscalRatingCategory': '良好', 'nextFiscalPoint1': '為替・市況前提を足元水準に見直し、2024年度実績対比で▲460億円の影響を見込む', 'nextFiscalPoint2': '既存事業の磨き込み、成長投資の利益貢献により、+550億円の増益を見込む', 'nextFiscalPoint3': '実態純利益は4,600億円（+90億円）と増益見通し、非資源分野が3,360億円（+130億円）と牽引', 'segmentRating': '8', 'segments': [{'name': 'ライフスタイル', 'value': '84億円', 'change': '-15億円', 'description': 'タイヤ関連事業等の減益', 'profit': true}, {'name': 'フォレストプロダクツ', 'value': '152億円', 'change': '+294億円', 'description': 'パルプ市況・販売数量増', 'profit': true}, {'name': 'アグリ事業', 'value': '457億円', 'change': '+42億円', 'description': '米国肥料卸売事業の増益', 'profit': true}, {'name': '金属', 'value': '1,235億円', 'change': '-400億円', 'description': '豪州鉄鉱石・原料炭の減益', 'profit': true}, {'name': 'エネルギー', 'value': '693億円', 'change': '+301億円', 'description': '為替換算調整勘定の実現益', 'profit': true}, {'name': '電力', 'value': '660億円', 'change': '+187億円', 'description': '海外電力IPP事業の売却益', 'profit': true}], 'segmentRatingCategory': '優秀', 'segmentPoint1': '多様な事業ポートフォリオを活かし、資源分野の下落をフォレストプロダクツ(+294億円)やエネルギー(+301億円)等でカバー', 'segmentPoint2': '食料・アグリ関連が全体として安定的に利益成長し、ポートフォリオの柱として機能', 'segmentPoint3': '次世代事業開発は先行投資段階であるが、将来的な成長領域を着実に構築中', 'financialRating': '8', 'equityRatio': '39.4%', 'equityRatioChange': '+0.6pt', 'operatingCashFlow': '+5,979億円', 'operatingCashFlowChange': '+1,555億円', 'liquidAssets': '5,691億円', 'liquidAssetsChange': '+629億円', 'financialRatingCategory': '優秀', 'financialPoint1': '親会社の所有者に帰属する持分比率が39.4%（+0.6pt）と着実に上昇し、財務安定性が向上', 'financialPoint2': '営業活動によるキャッシュフローが+5,979億円（+1,555億円）と大幅に増加し、投資余力が拡大', 'financialPoint3': 'ネットDEレシオが0.54倍（-0.01pt）と改善継続。財務健全性とリターンのバランスが良好', 'investmentDecisionText': '買い推奨', 'investmentStars': '★★★★☆', 'investmentDecisionReason': 'PER8.4倍・PBR1.13倍と割安感があり、配当利回り3.76%と株主還元も魅力的。2031年3月期までに時価総額10兆円超を目指す成長戦略も期待できる。', 'positivePoints': ['非資源分野の実態純利益が過去最高を達成し、事業ポートフォリオの安定性向上', '基礎営業キャッシュフローが過去最高を記録し、投資と株主還元の両立が可能に', '総還元性向を40%程度に引き上げ、積極的な株主還元策を継続', '年間配当を95円→100円に増配し、自己株取得も継続する株主還元の強化', 'PER8.4倍・PBR1.13倍と割安なバリュエーションで投資妙味が高い'], 'negativePoints': ['資源分野は市況下落の影響を受け減益となり、市況変動リスクが残存', '米ドル/円レートの想定が152.58円から140円へと円高前提となり、為替変動リスクあり', 'ROEが14.2%と前年度比-1.0ptの低下、資本効率のさらなる向上が課題', '世界経済の減速懸念や地政学リスクによる事業環境の不確実性が高まっている'], 'dataSource': '丸紅株式会社 2025年3月期決算IR資料（2025年5月2日公表）'};
    }
    
    console.log('レポートデータ取得:', reportData);
    
    // データ不足があれば基本情報で補完
    const defaults = {
      companyName: "丸紅株式会社",
      companyCode: "8002",
      companyAbbr: "MRB",
      companyColor: "#E60012",
      fiscalPeriod: "2025年3月期 決算サマリー",
      achievementBadge: "過去2番目の高水準達成",
      overallRating: "8.5",
      positivePoints: [],
      negativePoints: []
    };
    
    console.log('デフォルト値:', defaults);
    
    // デフォルト値でデータを補完
    for (const [key, value] of Object.entries(defaults)) {
      if (!reportData[key] && value) {
        reportData[key] = value;
      }
    }
    
    console.log('補完後データ:', reportData);
    
    // テンプレートにデータを適用
    if (Object.keys(reportData).length > 0) {
      setCompanyData(reportData);
      console.log('setCompanyData関数実行完了');
    } else {
      console.error('データが空のため、setCompanyData関数は実行しません');
    }
  } catch (error) {
    console.error('データ処理中にエラーが発生しました:', error);
  }
});
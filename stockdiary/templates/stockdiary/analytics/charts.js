// stockdiary/templates/stockdiary/analytics/charts.js

document.addEventListener('DOMContentLoaded', function() {
    // 共通の色パレット
    const CHART_COLORS = {
      primary: {
        main: 'rgb(79, 70, 229)',
        light: 'rgba(79, 70, 229, 0.7)',
        veryLight: 'rgba(79, 70, 229, 0.1)'
      },
      success: {
        main: 'rgb(16, 185, 129)',
        light: 'rgba(16, 185, 129, 0.7)'
      },
      warning: {
        main: 'rgb(245, 158, 11)',
        light: 'rgba(245, 158, 11, 0.7)'
      },
      danger: {
        main: 'rgb(239, 68, 68)',
        light: 'rgba(239, 68, 68, 0.7)'
      }
    };
  
    // 共通のチャートオプション
    const CHART_DEFAULT_OPTIONS = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true
        }
      }
    };
  
    // チャートを初期化する共通関数
    function initChart(elementId, type, data, customOptions = {}) {
      const ctx = document.getElementById(elementId);
      if (!ctx) return null;
      
      // オプションをマージ
      const options = Object.assign({}, CHART_DEFAULT_OPTIONS, customOptions);
      
      return new Chart(ctx, {
        type: type,
        data: data,
        options: options
      });
    }
  
    // データの有効性をチェックする共通関数
    function isValidData(data) {
      if (!data) return false;
      if (Array.isArray(data) && data.length === 0) return false;
      return true;
    }
  
    // すべてのチャート初期化関数を呼び出し
    const chartsToInitialize = [
      initializeMonthlyRecordsChart,
      initializeDayOfWeekChart,
      initializeContentLengthChart,
      initializeTagFrequencyChart,
      initializeTagTimelineChart,
      initializeChecklistCompletionChart,
      initializeChecklistTimelineChart,
      initializeHoldingsChart,
      initializeSectorDistributionChart,
      initializeHoldingPeriodChart,
      initializeProfitRateChart,
      initializeSectorChart,
      initializeMonthlyInvestmentChart
    ];
    
    chartsToInitialize.forEach(initFn => {
      try {
        initFn();
      } catch (err) {
        console.error(`Error initializing chart: ${err.message}`);
      }
    });
  
    // 月別記録数チャート
    function initializeMonthlyRecordsChart() {
      const labels = {{ monthly_labels|safe|default:"[]" }};
      const counts = {{ monthly_counts|safe|default:"[]" }};
      
      if (!isValidData(labels) || !isValidData(counts)) return;
      
      initChart('monthlyRecordsChart', 'line', {
        labels: labels,
        datasets: [{
          label: '記録数',
          data: counts,
          borderColor: CHART_COLORS.primary.main,
          backgroundColor: CHART_COLORS.primary.veryLight,
          borderWidth: 2,
          fill: true,
          tension: 0.4
        }]
      });
    }
    
    // 曜日別記録数チャート
    function initializeDayOfWeekChart() {
      const dayOfWeekCounts = {{ day_of_week_counts|safe|default:"[]" }};
      
      if (!isValidData(dayOfWeekCounts)) return;
      
      initChart('dayOfWeekChart', 'bar', {
        labels: ['日曜日', '月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日'],
        datasets: [{
          label: '記録数',
          data: dayOfWeekCounts,
          backgroundColor: CHART_COLORS.primary.light,
          borderColor: CHART_COLORS.primary.main,
          borderWidth: 1
        }]
      });
    }
    
    // 以下、他のチャート初期化関数も同様に変換...
  });
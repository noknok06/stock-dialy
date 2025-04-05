// static/js/chart-utils.js

/**
 * チャート関連のユーティリティ関数と共通設定
 */
const ChartUtils = (function() {
    // 共通の色パレット
    const COLORS = {
      primary: {
        main: 'rgb(79, 70, 229)',
        light: 'rgba(79, 70, 229, 0.7)',
        veryLight: 'rgba(79, 70, 229, 0.1)'
      },
      success: {
        main: 'rgb(16, 185, 129)',
        light: 'rgba(16, 185, 129, 0.7)',
        veryLight: 'rgba(16, 185, 129, 0.1)'
      },
      warning: {
        main: 'rgb(245, 158, 11)',
        light: 'rgba(245, 158, 11, 0.7)',
        veryLight: 'rgba(245, 158, 11, 0.1)'
      },
      danger: {
        main: 'rgb(239, 68, 68)',
        light: 'rgba(239, 68, 68, 0.7)',
        veryLight: 'rgba(239, 68, 68, 0.1)'
      },
      info: {
        main: 'rgb(59, 130, 246)',
        light: 'rgba(59, 130, 246, 0.7)',
        veryLight: 'rgba(59, 130, 246, 0.1)'
      },
      gray: {
        main: 'rgb(75, 85, 99)',
        light: 'rgba(75, 85, 99, 0.7)',
        veryLight: 'rgba(75, 85, 99, 0.1)'
      }
    };
  
    // 共通のチャートオプション
    const DEFAULT_OPTIONS = {
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
  
    /**
     * データの有効性をチェックする
     * @param {*} data - チェックするデータ
     * @returns {boolean} データが有効かどうか
     */
    function isValidData(data) {
      if (data === null || data === undefined) return false;
      if (Array.isArray(data) && data.length === 0) return false;
      return true;
    }
  
    /**
     * チャートを初期化する
     * @param {string} elementId - チャート要素のID
     * @param {string} type - チャートタイプ ('line', 'bar', 'pie'など)
     * @param {object} data - チャートデータ
     * @param {object} customOptions - カスタムオプション (省略可)
     * @returns {Chart|null} チャートインスタンスまたはnull
     */
    function initChart(elementId, type, data, customOptions = {}) {
      const ctx = document.getElementById(elementId);
      if (!ctx) {
        console.warn(`Element with ID "${elementId}" not found`);
        return null;
      }
      
      // デフォルトオプションとカスタムオプションをマージ
      const options = Object.assign({}, DEFAULT_OPTIONS, customOptions);
      
      // Chart.jsインスタンスを作成して返す
      return new Chart(ctx, {
        type: type,
        data: data,
        options: options
      });
    }
  
    /**
     * ラインチャートを初期化する
     * @param {string} elementId - チャート要素のID
     * @param {Array} labels - ラベル配列
     * @param {Array} data - データ配列
     * @param {object} options - カスタムオプション (省略可)
     * @returns {Chart|null} チャートインスタンスまたはnull
     */
    function createLineChart(elementId, labels, data, options = {}) {
      if (!isValidData(labels) || !isValidData(data)) {
        console.warn(`Invalid data for chart "${elementId}"`);
        return null;
      }
      
      const chartData = {
        labels: labels,
        datasets: [{
          label: options.label || 'データ',
          data: data,
          borderColor: options.borderColor || COLORS.primary.main,
          backgroundColor: options.backgroundColor || COLORS.primary.veryLight,
          borderWidth: options.borderWidth || 2,
          fill: options.fill !== undefined ? options.fill : true,
          tension: options.tension || 0.4
        }]
      };
      
      return initChart(elementId, 'line', chartData, options);
    }
  
    /**
     * 棒グラフを初期化する
     * @param {string} elementId - チャート要素のID
     * @param {Array} labels - ラベル配列
     * @param {Array} data - データ配列
     * @param {object} options - カスタムオプション (省略可)
     * @returns {Chart|null} チャートインスタンスまたはnull
     */
    function createBarChart(elementId, labels, data, options = {}) {
      if (!isValidData(labels) || !isValidData(data)) {
        console.warn(`Invalid data for chart "${elementId}"`);
        return null;
      }
      
      // 条件付きの色設定のサポート
      let backgroundColor, borderColor;
      
      if (typeof options.getBackgroundColor === 'function') {
        backgroundColor = (context) => options.getBackgroundColor(context, COLORS);
      } else {
        backgroundColor = options.backgroundColor || COLORS.primary.light;
      }
      
      if (typeof options.getBorderColor === 'function') {
        borderColor = (context) => options.getBorderColor(context, COLORS);
      } else {
        borderColor = options.borderColor || COLORS.primary.main;
      }
      
      const chartData = {
        labels: labels,
        datasets: [{
          label: options.label || 'データ',
          data: data,
          backgroundColor: backgroundColor,
          borderColor: borderColor,
          borderWidth: options.borderWidth || 1
        }]
      };
      
      return initChart(elementId, 'bar', chartData, options);
    }
  
    /**
     * 円グラフ/ドーナツチャートを初期化する
     * @param {string} elementId - チャート要素のID
     * @param {Array} labels - ラベル配列
     * @param {Array} data - データ配列
     * @param {object} options - カスタムオプション (省略可)
     * @returns {Chart|null} チャートインスタンスまたはnull
     */
    function createPieChart(elementId, labels, data, options = {}) {
      if (!isValidData(labels) || !isValidData(data)) {
        console.warn(`Invalid data for chart "${elementId}"`);
        return null;
      }
      
      // 色の配列を作成（データの長さに合わせて）
      const colorArray = [
        COLORS.primary.light,
        COLORS.success.light,
        COLORS.warning.light,
        COLORS.danger.light,
        COLORS.info.light,
        COLORS.gray.light
      ];
      
      // データの長さに応じて色を動的に生成
      while (colorArray.length < data.length) {
        const r = Math.floor(Math.random() * 200) + 50;
        const g = Math.floor(Math.random() * 200) + 50;
        const b = Math.floor(Math.random() * 200) + 50;
        colorArray.push(`rgba(${r}, ${g}, ${b}, 0.7)`);
      }
      
      const chartData = {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: options.backgroundColor || colorArray.slice(0, data.length),
          borderWidth: options.borderWidth || 1
        }]
      };
      
      // ドーナツオプションの追加
      const chartOptions = Object.assign({}, options);
      if (options.doughnut) {
        chartOptions.cutout = options.cutoutPercentage || '50%';
        return initChart(elementId, 'doughnut', chartData, chartOptions);
      }
      
      return initChart(elementId, 'pie', chartData, chartOptions);
    }

  /**
   * アプリケーション固有の円グラフスタイル設定を適用した円グラフを作成
   * @param {string} elementId - チャート要素のID
   * @param {Array} labels - ラベル配列
   * @param {Array} data - データ配列
   * @param {Function} colorGenerator - 色生成関数（省略可）
   * @param {object} customOptions - 追加オプション（省略可）
   * @returns {Chart|null} チャートインスタンス
   */
  function createStyledPieChart(elementId, labels, data, colorGenerator = null, customOptions = {}) {
    // データの検証
    if (!isValidData(labels) || !isValidData(data)) { // this. を削除
      const ctx = document.getElementById(elementId);
      if (ctx) {
        ctx.parentElement.innerHTML = '<div class="alert alert-info p-3 h-100 d-flex align-items-center justify-content-center">データがありません</div>';
      }
      return null;
    }
    
    // 色の生成（カスタム関数または内部配列を使用）
    let colors;
    if (typeof colorGenerator === 'function') {
      colors = colorGenerator(labels.length);
    } else {
      // デフォルトの色配列
      colors = [
        COLORS.primary.light, // this. を削除
        COLORS.success.light,
        COLORS.warning.light,
        COLORS.danger.light,
        COLORS.info.light,
        COLORS.gray.light
      ];
      
      // データに合わせて色を生成
      while (colors.length < data.length) {
        const r = Math.floor(Math.random() * 200) + 50;
        const g = Math.floor(Math.random() * 200) + 50;
        const b = Math.floor(Math.random() * 200) + 50;
        colors.push(`rgba(${r}, ${g}, ${b}, 0.7)`);
      }
    }
      
    
    // アプリケーション固有のデフォルト設定
    const defaultOptions = {
      plugins: {
        legend: {
          display: true,
          position: 'right',
          align: 'left',
          labels: {
            boxWidth: 14,
            usePointStyle: true,
            padding: 10,
            font: {
              size: 10
            }
          }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = context.raw || 0;
              const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
              const percentage = Math.round((value / total) * 100);
              return `${label}: ${value} (${percentage}%)`;
            }
          }
        }
      }
    };
    
    // カスタムオプションとデフォルトオプションをマージ
    const mergedOptions = _deepMerge(defaultOptions, customOptions);

    // 円グラフを作成して返す
    return createPieChart(elementId, labels, data, {
      scales: {
        y: {
          ticks: {
            display: false // Y軸の数値ラベルを非表示
          }
        }
      },
      backgroundColor: colors.slice(0, data.length),
      ...mergedOptions
    });
  }

  function _deepMerge(target, source) {
    const output = Object.assign({}, target);
    if (isObject(target) && isObject(source)) { // this. を削除
      Object.keys(source).forEach(key => {
        if (isObject(source[key])) { // this. を削除
          if (!(key in target)) {
            Object.assign(output, { [key]: source[key] });
          } else {
            output[key] = _deepMerge(target[key], source[key]); // this. を削除
          }
        } else {
          Object.assign(output, { [key]: source[key] });
        }
      });
    }
    return output;
  }
  
  /**
   * 値がオブジェクトかどうかを確認
   * @private
   */
  function isObject(item) { // function キーワードを追加
    return (item && typeof item === 'object' && !Array.isArray(item));
  }

// 戻り値に新しい関数を追加
return {
  COLORS,
  DEFAULT_OPTIONS,
  isValidData,
  initChart,
  createLineChart,
  createBarChart,
  createPieChart,
  createStyledPieChart, // 新しい関数を追加
  _deepMerge,
  isObject
};
})();
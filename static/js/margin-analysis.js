// static/js/margin-analysis.js（両面解釈重視版）
// 根拠明示・バランスの取れた分析表示

class MarginAnalysisManager {
    constructor(diaryId, currentSymbol = null) {
        this.diaryId = diaryId;
        this.currentSymbol = currentSymbol;
        this.analysisData = null;
        this.isLoading = false;
        this.isMobile = this.detectMobile();
        this.retryCount = 0;
        this.maxRetries = 3;
        
        this.init();
    }
    
    detectMobile() {
        return window.innerWidth <= 768 || 
               /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }
    
    init() {
        this.initEventListeners();
        this.loadAnalysisData();
    }
    
    initEventListeners() {
        // 更新ボタン
        const refreshBtn = document.getElementById('refreshAnalysisBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshAnalysis());
        }
        
        // 期間選択ボタン
        const periodButtons = document.querySelectorAll('input[name="chartPeriod"]');
        periodButtons.forEach(button => {
            button.addEventListener('change', (e) => {
                if (e.target.checked && this.analysisData) {
                    this.updateRatioChart(this.analysisData);
                }
            });
        });
        
        // タブ切り替えイベント（チャート表示調整用）
        const chartTab = document.getElementById('chart-tab');
        if (chartTab) {
            chartTab.addEventListener('shown.bs.tab', () => {
                // チャートタブが表示されたときにチャートをリサイズ
                if (this.ratioChart) {
                    setTimeout(() => {
                        this.ratioChart.resize();
                    }, 100);
                } else if (this.analysisData) {
                    // チャートがまだ作成されていない場合は作成
                    this.updateRatioChart(this.analysisData);
                }
            });
        }
    }
    
    async loadAnalysisData() {
        if (this.isLoading) return;
        
        this.showLoading();
        this.isLoading = true;
        
        try {
            const response = await fetch(`/stockdiary/api/margin-analysis/${this.diaryId}/`, {
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                if (response.status === 500) {
                    throw new Error('サーバーエラーが発生しました。しばらく後に再試行してください');
                } else if (response.status === 404) {
                    throw new Error('この銘柄の分析データは現在利用できません');
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }
            
            const data = await response.json();
            
            if (data.status === 'error') {
                throw new Error(data.message || '分析データの取得に失敗しました');
            }
            
            if (data.status === 'no_data') {
                this.showNoDataState(data.message);
                return;
            }
            
            this.analysisData = data;
            this.displayAnalysisResults();
            this.retryCount = 0;
            
        } catch (error) {
            console.error('Analysis data loading error:', error);
            this.showError(error.message, true);
            
            // リトライロジック
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                console.log(`Retrying analysis data load (attempt ${this.retryCount}/${this.maxRetries})`);
                setTimeout(() => {
                    this.loadAnalysisData();
                }, 2000 * this.retryCount);
            }
            
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    displayAnalysisResults() {
        if (!this.analysisData) return;
        
        this.updateCurrentRatio(this.analysisData);
        this.updatePositiveFactors(this.analysisData);
        this.updateNegativeFactors(this.analysisData);
        this.updateJudgmentPoints(this.analysisData);
        this.updateHistoricalContext(this.analysisData);
        this.updateSectorContext(this.analysisData.sector_comparison);
        this.updateMarketContext(this.analysisData);
        
        // チャートタブがアクティブな場合のみチャートを初期化
        const chartTab = document.getElementById('chart-tab');
        if (chartTab && chartTab.classList.contains('active')) {
            // 少し遅延させてDOMの描画が完了してから初期化
            setTimeout(() => {
                this.updateRatioChart(this.analysisData);
            }, 100);
        }
    }
    
    updateCurrentRatio(analysisData) {
        const container = document.getElementById('currentRatioDisplay');
        if (!container || !analysisData) return;
        
        // 信用倍率の計算と表示
        let ratioValue = 0;
        let ratioClass = 'ratio-medium';
        let levelClass = 'level-medium';
        let ratioText = '均衡';
        let description = '需給バランスは標準的な水準';
        
        // level_analysis から水準を判定
        if (analysisData.level_analysis && analysisData.current_ratio) {
            ratioValue = analysisData.current_ratio;
            const level = analysisData.level_analysis.level;
            description = analysisData.level_analysis.description;
            
            switch (level) {
                case 'very_high':
                    ratioClass = 'ratio-very-high';
                    levelClass = 'level-very-high';
                    ratioText = '極めて高水準';
                    break;
                case 'high':
                    ratioClass = 'ratio-high';
                    levelClass = 'level-high';
                    ratioText = '高水準';
                    break;
                case 'medium_high':
                    ratioClass = 'ratio-medium-high';
                    levelClass = 'level-medium-high';
                    ratioText = 'やや高水準';
                    break;
                case 'very_low':
                    ratioClass = 'ratio-very-low';
                    levelClass = 'level-very-low';
                    ratioText = '極めて低水準';
                    break;
                case 'low':
                    ratioClass = 'ratio-low';
                    levelClass = 'level-low';
                    ratioText = '低水準';
                    break;
                default:
                    ratioClass = 'ratio-medium';
                    levelClass = 'level-medium';
                    ratioText = '標準水準';
            }
        }
        
        container.innerHTML = `
            <div class="ratio-display">
                <div class="ratio-value ${ratioClass}">
                    ${ratioValue.toFixed(2)}
                    <span class="ratio-unit">倍</span>
                </div>
                <div class="ratio-status">
                    <span class="ratio-level ${levelClass}">${ratioText}</span>
                </div>
                <div class="ratio-description">
                    ${description}
                </div>
            </div>
            <div class="ratio-meta mt-3">
                <small class="text-muted">
                    更新日: ${this.formatDate(analysisData.analysis_date)}
                    ${analysisData.company_name ? ` | ${analysisData.company_name}` : ''}
                </small>
            </div>
        `;
    }
    
    async updateRatioChart(analysisData) {
        const canvas = document.getElementById('mainRatioChart');
        if (!canvas) return;
        
        try {
            // 選択された期間を取得
            const selectedPeriod = document.querySelector('input[name="chartPeriod"]:checked')?.value || '3';
            
            // チャートデータを取得
            const response = await fetch(`/stockdiary/api/margin-chart-data/${this.diaryId}/?period=${selectedPeriod}`, {
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error('チャートデータの取得に失敗しました');
            }
            
            const chartData = await response.json();
            
            if (chartData.error) {
                throw new Error(chartData.error);
            }
            
            // Chart.jsでチャートを描画
            this.renderRatioChart(canvas, chartData);
            this.updateChartStats(chartData.stats);
            
        } catch (error) {
            console.error('Chart update error:', error);
            const chartContainer = canvas.parentElement;
            chartContainer.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-exclamation-triangle"></i>
                    <p class="mt-2 mb-0 small">チャートの表示に失敗しました</p>
                </div>
            `;
        }
    }
    
    renderRatioChart(canvas, chartData) {
        const ctx = canvas.getContext('2d');
        
        // 既存のチャートがあれば破棄
        if (this.ratioChart) {
            this.ratioChart.destroy();
        }
        
        // Chart.jsが読み込まれているかチェック
        if (typeof Chart === 'undefined') {
            console.error('Chart.js is not loaded');
            return;
        }
        
        this.ratioChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.chart_data.labels,
                datasets: [{
                    label: '信用倍率',
                    data: chartData.chart_data.datasets[0].data,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#0d6efd',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toFixed(2) + '倍';
                            },
                            font: {
                                size: 11
                            },
                            color: '#6c757d'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            font: {
                                size: 11
                            },
                            color: '#6c757d',
                            maxRotation: 45
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#0d6efd',
                        borderWidth: 1,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                return '信用倍率: ' + context.parsed.y.toFixed(2) + '倍';
                            }
                        }
                    }
                },
                elements: {
                    point: {
                        hoverRadius: 8
                    }
                }
            }
        });
        
        // チャート作成後、少し待ってからリサイズ
        setTimeout(() => {
            if (this.ratioChart) {
                this.ratioChart.resize();
            }
        }, 50);
    }
    
    updateChartStats(stats) {
        if (!stats) return;
        
        // 統計情報を更新
        const currentRatio = document.getElementById('currentRatio');
        const avgRatio = document.getElementById('avgRatio');
        const maxRatio = document.getElementById('maxRatio');
        const minRatio = document.getElementById('minRatio');
        
        if (currentRatio) currentRatio.textContent = stats.current?.toFixed(2) + '倍' || '-';
        if (avgRatio) avgRatio.textContent = stats.average?.toFixed(2) + '倍' || '-';
        if (maxRatio) maxRatio.textContent = stats.max?.toFixed(2) + '倍' || '-';
        if (minRatio) minRatio.textContent = stats.min?.toFixed(2) + '倍' || '-';
    }
    
    updatePositiveFactors(analysisData) {
        const container = document.getElementById('positiveFactors');
        if (!container) return;
        
        const factorBody = container.querySelector('.factor-body');
        if (!factorBody) return;
        
        // ポジティブ要因を抽出・生成
        const positiveFactors = this.generatePositiveFactors(analysisData);
        
        if (positiveFactors.length === 0) {
            factorBody.innerHTML = `
                <div class="text-muted text-center py-2">
                    <small>現在の状況では明確なポジティブ要因が見つかりません</small>
                </div>
            `;
            return;
        }
        
        let html = '<ul class="factor-list">';
        positiveFactors.forEach(factor => {
            html += `
                <li class="factor-item">
                    <i class="factor-icon bi-plus-circle text-success"></i>
                    <div class="factor-text">
                        <div class="factor-title">${factor.title}</div>
                        <div class="factor-description">${factor.description}</div>
                    </div>
                </li>
            `;
        });
        html += '</ul>';
        
        factorBody.innerHTML = html;
    }
    
    updateNegativeFactors(analysisData) {
        const container = document.getElementById('negativeFactors');
        if (!container) return;
        
        const factorBody = container.querySelector('.factor-body');
        if (!factorBody) return;
        
        // リスク要因を抽出・生成
        const negativeFactors = this.generateNegativeFactors(analysisData);
        
        if (negativeFactors.length === 0) {
            factorBody.innerHTML = `
                <div class="text-muted text-center py-2">
                    <small>現在の状況では重大なリスク要因は見つかりません</small>
                </div>
            `;
            return;
        }
        
        let html = '<ul class="factor-list">';
        negativeFactors.forEach(factor => {
            html += `
                <li class="factor-item">
                    <i class="factor-icon bi-exclamation-triangle text-warning"></i>
                    <div class="factor-text">
                        <div class="factor-title">${factor.title}</div>
                        <div class="factor-description">${factor.description}</div>
                    </div>
                </li>
            `;
        });
        html += '</ul>';
        
        factorBody.innerHTML = html;
    }
    
    updateJudgmentPoints(analysisData) {
        const container = document.getElementById('judgmentPoints');
        if (!container) return;
        
        const pointsBody = container.querySelector('.points-body');
        if (!pointsBody) return;
        
        // 判断ポイントを生成
        const judgmentPoints = this.generateJudgmentPoints(analysisData);
        
        let html = '<ul class="points-list">';
        judgmentPoints.forEach((point, index) => {
            html += `
                <li class="point-item">
                    <div class="point-number">${index + 1}</div>
                    <div class="point-text">${point}</div>
                </li>
            `;
        });
        html += '</ul>';
        
        pointsBody.innerHTML = html;
    }
    
    updateHistoricalContext(analysisData) {
        const container = document.getElementById('historicalContext');
        if (!container) return;
        
        const contextBody = container.querySelector('.context-body');
        if (!contextBody) return;
        
        // 過去との比較データを生成
        let html = '';
        
        if (analysisData.trend_analysis) {
            const trend = analysisData.trend_analysis;
            let trendClass = 'text-muted';
            let trendText = '変化なし';
            
            switch (trend.trend) {
                case 'strong_upward':
                case 'upward':
                    trendClass = 'text-success';
                    trendText = '上昇傾向';
                    break;
                case 'strong_downward':
                case 'downward':
                    trendClass = 'text-danger';
                    trendText = '下降傾向';
                    break;
                default:
                    trendClass = 'text-primary';
                    trendText = '安定推移';
            }
            
            html += `
                <div class="comparison-result">
                    <span class="comparison-label">過去4週間との比較</span>
                    <span class="comparison-value ${trendClass}">${trendText}</span>
                </div>
                <div class="context-detail">
                    <small class="text-muted">${trend.description}</small>
                </div>
            `;
        }
        
        contextBody.innerHTML = html || `
            <div class="text-muted text-center py-2">
                <small>過去データとの比較情報が不足しています</small>
            </div>
        `;
    }
    
    updateSectorContext(sectorData) {
        const container = document.getElementById('sectorContext');
        if (!container) return;
        
        const contextBody = container.querySelector('.context-body');
        if (!contextBody) return;
        
        if (!sectorData || sectorData.status !== 'success') {
            contextBody.innerHTML = `
                <div class="text-muted text-center py-2">
                    <small>同業種比較データが利用できません</small>
                </div>
            `;
            return;
        }
        
        const percentile = sectorData.percentile || 50;
        let rankingClass = 'text-muted';
        let rankingText = '平均的';
        
        if (percentile >= 80) {
            rankingClass = 'text-success';
            rankingText = '上位グループ';
        } else if (percentile >= 60) {
            rankingClass = 'text-info';
            rankingText = '平均以上';
        } else if (percentile <= 20) {
            rankingClass = 'text-warning';
            rankingText = '下位グループ';
        }
        
        contextBody.innerHTML = `
            <div class="comparison-result">
                <span class="comparison-label">${sectorData.sector_name}内での位置</span>
                <span class="comparison-value ${rankingClass}">${rankingText}</span>
            </div>
            <div class="comparison-result">
                <span class="comparison-label">分析対象企業数</span>
                <span class="comparison-value">${sectorData.sector_companies_count}社</span>
            </div>
            <div class="context-detail mt-2">
                <small class="text-muted">${sectorData.assessment}</small>
            </div>
        `;
    }
    
    updateMarketContext(analysisData) {
        const container = document.getElementById('marketContext');
        if (!container) return;
        
        const contextBody = container.querySelector('.context-body');
        if (!contextBody) return;
        
        // 市場全体の傾向を分析（簡易版）
        let marketTrend = '標準的な水準';
        let trendClass = 'text-primary';
        
        if (analysisData.volatility_analysis) {
            const volatility = analysisData.volatility_analysis.volatility;
            
            switch (volatility) {
                case 'high':
                    marketTrend = '市場全体で変動が大きい時期';
                    trendClass = 'text-warning';
                    break;
                case 'low':
                    marketTrend = '市場全体で安定している時期';
                    trendClass = 'text-success';
                    break;
                default:
                    marketTrend = '市場全体で標準的な変動';
                    trendClass = 'text-primary';
            }
        }
        
        contextBody.innerHTML = `
            <div class="comparison-result">
                <span class="comparison-label">市場全体の傾向</span>
                <span class="comparison-value ${trendClass}">${marketTrend}</span>
            </div>
            <div class="context-detail mt-2">
                <small class="text-muted">
                    信用取引全体の動向を踏まえると、個別銘柄の判断においても市場環境を考慮することが重要です。
                </small>
            </div>
        `;
    }
    
    generatePositiveFactors(analysisData) {
        const factors = [];
        
        if (analysisData.level_analysis) {
            const level = analysisData.level_analysis.level;
            
            if (level === 'high' || level === 'very_high') {
                factors.push({
                    title: '買い需要が優勢',
                    description: '信用取引で買いポジションが売りを上回っており、投資家の上昇期待が強い状況'
                });
            }
            
            if (level === 'low' || level === 'very_low') {
                factors.push({
                    title: '売り枯れによる反発期待',
                    description: '売りポジションが多い状況は、売り枯れ後の反発上昇の可能性を示唆'
                });
            }
        }
        
        if (analysisData.trend_analysis) {
            const trend = analysisData.trend_analysis.trend;
            
            if (trend === 'upward' || trend === 'strong_upward') {
                factors.push({
                    title: '需給改善トレンド',
                    description: '過去数週間で買い需要が徐々に増加しており、需給環境が改善している'
                });
            }
        }
        
        if (analysisData.volatility_analysis) {
            const volatility = analysisData.volatility_analysis.volatility;
            
            if (volatility === 'low') {
                factors.push({
                    title: '安定した需給環境',
                    description: '需給バランスが安定しており、急激な変動リスクが低い状況'
                });
            }
        }
        
        return factors;
    }
    
    generateNegativeFactors(analysisData) {
        const factors = [];
        
        if (analysisData.level_analysis) {
            const level = analysisData.level_analysis.level;
            
            if (level === 'very_high') {
                factors.push({
                    title: '過度な買い偏重リスク',
                    description: '信用買いが非常に多い状況は、将来的な売り圧力や調整リスクを含む'
                });
            }
            
            if (level === 'high') {
                factors.push({
                    title: '利益確定売りの可能性',
                    description: '買いポジションが多い状況では、株価上昇後の利益確定売りが出やすい'
                });
            }
            
            if (level === 'very_low' || level === 'low') {
                factors.push({
                    title: '売り圧力の継続懸念',
                    description: '売りポジションが多い状況は、さらなる下落圧力として作用する可能性'
                });
            }
        }
        
        if (analysisData.trend_analysis) {
            const trend = analysisData.trend_analysis.trend;
            
            if (trend === 'downward' || trend === 'strong_downward') {
                factors.push({
                    title: '需給悪化トレンド',
                    description: '過去数週間で売り圧力が増加しており、需給環境が悪化している'
                });
            }
        }
        
        if (analysisData.volatility_analysis) {
            const volatility = analysisData.volatility_analysis.volatility;
            
            if (volatility === 'high') {
                factors.push({
                    title: '不安定な需給環境',
                    description: '需給バランスが不安定で、急激な価格変動が起こりやすい状況'
                });
            }
        }
        
        return factors;
    }
    
    generateJudgmentPoints(analysisData) {
        const points = [];
        
        points.push('信用倍率は需給の一つの指標ですが、業績や技術的要因も総合的に検討しましょう');
        
        if (analysisData.level_analysis) {
            const level = analysisData.level_analysis.level;
            
            if (level === 'very_high' || level === 'high') {
                points.push('買い優勢の状況では、利益確定のタイミングや追加買いのリスクを慎重に評価してください');
            }
            
            if (level === 'very_low' || level === 'low') {
                points.push('売り優勢の状況では、底値圏での投資機会と下落継続リスクの両方を検討してください');
            }
        }
        
        if (analysisData.sector_comparison && analysisData.sector_comparison.status === 'success') {
            points.push(`同業他社（${analysisData.sector_comparison.sector_name}）との比較も投資判断の重要な要素です`);
        }
        
        points.push('過去の推移パターンと現在の市場環境を照らし合わせて判断することが重要です');
        
        points.push('信用倍率の変化だけでなく、その変化の理由や背景も考慮してください');
        
        return points;
    }
    
    showLoading() {
        const containers = [
            'currentRatioDisplay',
            { id: 'positiveFactors', selector: '.factor-body' },
            { id: 'negativeFactors', selector: '.factor-body' },
            { id: 'judgmentPoints', selector: '.points-body' },
            { id: 'historicalContext', selector: '.context-body' },
            { id: 'sectorContext', selector: '.context-body' },
            { id: 'marketContext', selector: '.context-body' }
        ];
        
        containers.forEach(item => {
            let container;
            if (typeof item === 'string') {
                container = document.getElementById(item);
            } else {
                const parent = document.getElementById(item.id);
                container = parent ? parent.querySelector(item.selector) : null;
            }
            
            if (container) {
                container.innerHTML = `
                    <div class="loading-state">
                        <div class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <span class="ms-2 small">分析中...</span>
                    </div>
                `;
            }
        });
        
        // チャート統計の初期化
        this.resetChartStats();
    }
    
    showNoDataState(message) {
        const containers = ['currentRatioDisplay'];
        
        containers.forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="bi bi-info-circle" style="font-size: 1.5rem;"></i>
                        <p class="mt-2 mb-2">${message}</p>
                        <button class="btn btn-outline-primary btn-sm" 
                                onclick="window.marginAnalysisController?.refreshAnalysis()">
                            <i class="bi bi-arrow-clockwise me-1"></i>再試行
                        </button>
                    </div>
                `;
            }
        });
    }
    
    showError(message, showRetry = false) {
        this.showToast(message, 'danger', 8000);
        
        if (showRetry) {
            const container = document.getElementById('currentRatioDisplay');
            if (container) {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="bi bi-exclamation-triangle text-warning" style="font-size: 1.5rem;"></i>
                        <p class="mt-2 mb-2">${message}</p>
                        <button class="btn btn-outline-primary btn-sm" 
                                onclick="window.marginAnalysisController?.refreshAnalysis()">
                            <i class="bi bi-arrow-clockwise me-1"></i>再試行
                        </button>
                    </div>
                `;
            }
        }
    }
    
    resetChartStats() {
        const statElements = ['currentRatio', 'avgRatio', 'maxRatio', 'minRatio'];
        statElements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = '-';
            }
        });
    }
    
    // クリーンアップ処理
    destroy() {
        if (this.ratioChart) {
            this.ratioChart.destroy();
            this.ratioChart = null;
        }
    }
    
    showToast(message, type = 'info', duration = 3000) {
        // Bootstrap Toast を表示
        const toastId = `toast-${Date.now()}`;
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0 position-fixed top-0 end-0 m-3" 
                 role="alert" style="z-index: 9999;">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        const toastContainer = document.createElement('div');
        toastContainer.innerHTML = toastHtml;
        document.body.appendChild(toastContainer);
        
        const toastElement = toastContainer.querySelector('.toast');
        
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = new bootstrap.Toast(toastElement, {
                autohide: true,
                delay: duration
            });
            toast.show();
            
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastContainer.remove();
            });
        } else {
            setTimeout(() => {
                toastContainer.remove();
            }, duration);
        }
    }
    
    refreshAnalysis() {
        if (this.isLoading) return;
        
        this.retryCount = 0;
        this.loadAnalysisData();
        this.showToast('分析データを更新しています...', 'info', 2000);
    }
    
    formatDate(dateString) {
        if (!dateString) return '不明';
        
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('ja-JP', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        } catch (error) {
            return '不明';
        }
    }
}

// グローバル変数
window.marginAnalysisController = null;

// 初期化関数
function initializeMarginAnalysis(diaryId, currentSymbol = null) {
    window.marginAnalysisController = new MarginAnalysisManager(diaryId, currentSymbol);
    return window.marginAnalysisController;
}

// DOMContentLoaded で自動初期化
document.addEventListener('DOMContentLoaded', function() {
    const container = document.querySelector('.margin-analysis-container');
    if (container) {
        const diaryId = container.dataset.diaryId;
        const currentSymbol = container.dataset.currentSymbol;
        
        if (diaryId) {
            initializeMarginAnalysis(parseInt(diaryId), currentSymbol);
            console.log('✅ Margin Analysis Controller (Balanced Interpretation) initialized');
        }
    }
});

console.log('✅ Margin Analysis Manager (Balanced Interpretation) loaded successfully');
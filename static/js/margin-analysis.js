// static/js/margin-analysis.js（利用規約準拠版）

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
        
        this.updateTrendAnalysis(this.analysisData.trend_analysis);
        this.updateLevelAnalysis(this.analysisData.level_analysis);
        this.updateInvestmentInsights(this.analysisData.investment_insight);
        this.updateVolatilityAnalysis(this.analysisData.volatility_analysis);
        this.updateSectorComparison(this.analysisData.sector_comparison);
        this.updateAlerts(this.analysisData.alerts);
    }
    
    updateTrendAnalysis(trendData) {
        const container = document.getElementById('trendAnalysis');
        if (!container || !trendData) return;
        
        const trendIcons = {
            'strong_upward': '<i class="bi bi-arrow-up-circle text-success"></i>',
            'upward': '<i class="bi bi-arrow-up text-success"></i>',
            'stable': '<i class="bi bi-arrow-right text-primary"></i>',
            'downward': '<i class="bi bi-arrow-down text-warning"></i>',
            'strong_downward': '<i class="bi bi-arrow-down-circle text-danger"></i>'
        };
        
        container.innerHTML = `
            <div class="trend-indicator d-flex align-items-center">
                ${trendIcons[trendData.trend] || '<i class="bi bi-question-circle text-muted"></i>'}
                <span class="trend-description ms-2">${trendData.description}</span>
            </div>
            <div class="trend-details mt-2">
                <small class="text-muted">
                    ${trendData.period}: ${trendData.change_rate > 0 ? '+' : ''}${trendData.change_rate}%
                </small>
            </div>
        `;
    }
    
    updateLevelAnalysis(levelData) {
        const container = document.getElementById('levelAnalysis');
        if (!container || !levelData) return;
        
        const levelClasses = {
            'very_high': 'text-danger',
            'high': 'text-warning',
            'medium': 'text-primary',
            'low': 'text-info',
            'very_low': 'text-secondary'
        };
        
        container.innerHTML = `
            <div class="level-indicator text-center">
                <div class="level-text ${levelClasses[levelData.level]} fs-5 fw-bold">${levelData.level_text}</div>
                <div class="level-suggestion mt-2">
                    <small class="text-dark">${levelData.suggestion}</small>
                </div>
                <div class="level-context mt-2">
                    <small class="text-muted">${levelData.vs_average}</small>
                </div>
            </div>
        `;
    }
    
    updateInvestmentInsights(insightData) {
        const container = document.getElementById('investmentInsights');
        if (!container || !insightData) return;
        
        if (!insightData.insights || insightData.insights.length === 0) {
            container.innerHTML = '<p class="text-muted mb-0">現時点で特別な注意点はありません</p>';
            return;
        }
        
        let html = '';
        insightData.insights.forEach((insight) => {
            const iconClass = {
                'caution': 'bi-exclamation-triangle text-warning',
                'opportunity': 'bi-lightbulb text-success',
                'trend_alert': 'bi-activity text-info'
            }[insight.type] || 'bi-info-circle text-primary';
            
            html += `
                <div class="insight-item mb-3">
                    <div class="d-flex align-items-start">
                        <i class="${iconClass} me-3 mt-1" style="font-size: 1.2em;"></i>
                        <div class="flex-grow-1">
                            <div class="insight-message fw-medium mb-1">${insight.message}</div>
                            <small class="insight-suggestion text-muted">${insight.suggestion}</small>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    updateVolatilityAnalysis(volatilityData) {
        const container = document.getElementById('volatilityAnalysis');
        if (!container || !volatilityData) return;
        
        const volatilityIcons = {
            'high': '<i class="bi bi-activity text-danger"></i>',
            'medium': '<i class="bi bi-graph-up text-primary"></i>',
            'low': '<i class="bi bi-minus-square text-success"></i>'
        };
        
        container.innerHTML = `
            <div class="volatility-indicator d-flex align-items-center">
                ${volatilityIcons[volatilityData.volatility]}
                <span class="ms-2">${volatilityData.description}</span>
            </div>
        `;
    }
    
    updateSectorComparison(sectorData) {
        const container = document.getElementById('sectorComparison');
        if (!container) return;
        
        if (!sectorData || sectorData.status !== 'success') {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-building" style="font-size: 2rem;"></i>
                    <p class="mt-2 mb-0">業種比較データがありません</p>
                </div>
            `;
            return;
        }
        
        const percentile = sectorData.percentile;
        const progressWidth = Math.max(5, percentile);
        const progressColor = percentile >= 70 ? 'bg-success' : 
                             percentile >= 30 ? 'bg-primary' : 'bg-warning';
        
        container.innerHTML = `
            <div class="sector-ranking mb-3">
                <div class="ranking-header d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0 fw-bold">${sectorData.sector_name}</h6>
                    <span class="badge bg-secondary">${sectorData.sector_companies_count}社</span>
                </div>
                <div class="ranking-progress">
                    <div class="progress mb-2" style="height: 12px;">
                        <div class="progress-bar ${progressColor}" 
                             style="width: ${progressWidth}%" 
                             role="progressbar">
                        </div>
                    </div>
                    <div class="d-flex justify-content-between">
                        <small class="text-muted">低位</small>
                        <small class="fw-bold text-primary">${sectorData.ranking_description}</small>
                        <small class="text-muted">高位</small>
                    </div>
                </div>
            </div>
        `;
    }
    
    updateAlerts(alerts) {
        const container = document.getElementById('marginAlerts');
        if (!container) return;
        
        if (!alerts || alerts.length === 0) {
            container.innerHTML = '';
            return;
        }
        
        let html = '';
        alerts.forEach((alert) => {
            const alertClass = {
                'warning': 'alert-warning',
                'info': 'alert-info',
                'success': 'alert-success',
                'danger': 'alert-danger'
            }[alert.level] || 'alert-info';
            
            const iconClass = {
                'warning': 'bi-exclamation-triangle',
                'info': 'bi-info-circle',
                'success': 'bi-check-circle',
                'danger': 'bi-x-circle'
            }[alert.level] || 'bi-info-circle';
            
            html += `
                <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                    <i class="${iconClass} me-2"></i>
                    <strong>${alert.message}</strong><br>
                    <small>${alert.action}</small>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    showLoading() {
        const containers = ['trendAnalysis', 'levelAnalysis'];
        containers.forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = `
                    <div class="text-center py-3">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-2 mb-0 small text-muted">分析中...</p>
                    </div>
                `;
            }
        });
    }
    
    hideLoading() {
        // ローディング表示を隠す処理は displayAnalysisResults で上書きされる
    }
    
    showNoDataState(message) {
        const containers = [
            'trendAnalysis', 
            'levelAnalysis', 
            'investmentInsights', 
            'volatilityAnalysis',
            'sectorComparison'
        ];
        
        containers.forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = `
                    <div class="text-center text-muted py-4">
                        <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
                        <p class="mt-2 mb-0">${message}</p>
                        <button class="btn btn-outline-primary btn-sm mt-2" 
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
            const containers = ['trendAnalysis', 'levelAnalysis'];
            containers.forEach(id => {
                const container = document.getElementById(id);
                if (container) {
                    container.innerHTML = `
                        <div class="text-center text-muted py-3">
                            <i class="bi bi-exclamation-triangle text-warning" style="font-size: 2rem;"></i>
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
            console.log('✅ Margin Analysis Controller initialized');
        }
    }
});

console.log('✅ Margin Analysis Manager loaded successfully');
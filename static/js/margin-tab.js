// stockdiary/static/stockdiary/js/margin-tab.js

class MarginTabManager {
    constructor(diaryId, issueId) {
        this.diaryId = diaryId;
        this.issueId = String(issueId)+'0';
        this.chart = null;
        this.compareChart = null;
        this.compareSymbols = [];
        
        this.init();
    }
    
    init() {
        this.initEventListeners();
        this.loadChartData();
        this.loadSectorData();
    }
    
    initEventListeners() {
        // タブ切り替え
        document.querySelectorAll('#marginTabsNav button').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const targetId = e.target.getAttribute('data-bs-target');
                this.onTabSwitch(targetId);
            });
        });
        
        // チャート期間変更
        document.querySelectorAll('input[name="chartPeriod"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.loadChartData(e.target.value);
            });
        });
        
        // 比較銘柄追加
        const addBtn = document.getElementById('addCompareBtn');
        const input = document.getElementById('compareSymbolInput');
        
        if (addBtn && input) {
            addBtn.addEventListener('click', () => this.addCompareSymbol());
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.addCompareSymbol();
                }
            });
            
            // 入力中の提案表示
            input.addEventListener('input', debounce(() => {
                this.showSymbolSuggestions(input.value);
            }, 300));
        }
        
        // リセットボタン
        const resetBtn = document.getElementById('resetCompareBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetComparison());
        }
    }
    
    onTabSwitch(targetId) {
        switch(targetId) {
            case '#chart-content':
                // チャートの再描画（リサイズ対応）
                if (this.chart) {
                    setTimeout(() => this.chart.resize(), 100);
                }
                break;
                
            case '#compare-content':
                // 比較チャートの再描画
                if (this.compareChart) {
                    setTimeout(() => this.compareChart.resize(), 100);
                }
                break;
                
            case '#data-content':
                // データテーブルは静的なので特に処理なし
                break;
        }
    }
    
    async loadChartData(period = '3') {
        const loadingEl = document.getElementById('chartLoading');
        if (loadingEl) loadingEl.classList.remove('d-none');
        
        try {
            const response = await fetch(`/stockdiary/api/margin-chart/${this.diaryId}/?period=${period}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'データ取得に失敗しました');
            }
            
            this.renderChart(data.chart_data);
            this.updateStats(data.stats);
            this.showAlerts(data.alerts);
            
        } catch (error) {
            console.error('Chart data loading error:', error);
            this.showError('チャートデータの読み込みに失敗しました: ' + error.message);
        } finally {
            if (loadingEl) loadingEl.classList.add('d-none');
        }
    }
    
    renderChart(chartData) {
        const ctx = document.getElementById('marginChart');
        if (!ctx) return;
        
        // 既存のチャートを破棄
        if (this.chart) {
            this.chart.destroy();
        }
        
        // Chart.jsの設定
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: window.innerWidth < 768 ? 10 : 20
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;
                                
                                if (label.includes('信用倍率')) {
                                    return `${label}: ${value}倍`;
                                } else {
                                    return `${label}: ${value.toLocaleString()}株`;
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: window.innerWidth >= 768,
                            text: '日付'
                        },
                        ticks: {
                            maxTicksLimit: window.innerWidth < 768 ? 5 : 8
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: window.innerWidth >= 768,
                            text: '信用倍率'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '倍';
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: window.innerWidth >= 768,
                        position: 'right',
                        title: {
                            display: true,
                            text: '残高(株)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        };
        
        this.chart = new Chart(ctx, config);
    }
    
    updateStats(stats) {
        const avgEl = document.getElementById('avgRatio');
        const volEl = document.getElementById('volatility');
        
        if (avgEl) avgEl.textContent = `${stats.average}倍`;
        if (volEl) volEl.textContent = `${stats.volatility}`;
    }
    
    showAlerts(alerts) {
        const alertContainer = document.getElementById('marginAlerts');
        if (!alertContainer) return;
        
        alertContainer.innerHTML = '';
        
        alerts.forEach(alert => {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${alert.type} alert-dismissible fade show`;
            alertDiv.innerHTML = `
                <i class="bi bi-info-circle me-2"></i>
                ${alert.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            alertContainer.appendChild(alertDiv);
        });
    }
    
    async addCompareSymbol() {
        const input = document.getElementById('compareSymbolInput');
        const symbol = input.value.trim();
        
        if (!symbol || this.compareSymbols.includes(symbol) || this.compareSymbols.length >= 4) {
            return;
        }
        
        this.compareSymbols.push(symbol);
        input.value = '';
        
        this.updateSelectedSymbols();
        this.loadCompareData();
    }
    
    removeCompareSymbol(symbol) {
        const index = this.compareSymbols.indexOf(symbol);
        if (index > -1) {
            this.compareSymbols.splice(index, 1);
            this.updateSelectedSymbols();
            
            if (this.compareSymbols.length > 0) {
                this.loadCompareData();
            } else {
                this.hideCompareChart();
            }
        }
    }
    
    updateSelectedSymbols() {
        const container = document.getElementById('selectedSymbols');
        if (!container) return;
        
        if (this.compareSymbols.length === 0) {
            container.innerHTML = '<p class="text-muted small">比較銘柄を追加してください（最大4銘柄）</p>';
            return;
        }
        
        const symbolsHtml = this.compareSymbols.map(symbol => `
            <span class="badge bg-primary me-2 mb-2 p-2">
                ${symbol}
                <button type="button" class="btn-close btn-close-white ms-2" 
                        style="font-size: 0.7em;" 
                        onclick="window.MarginTabController.removeCompareSymbol('${symbol}')">
                </button>
            </span>
        `).join('');
        
        container.innerHTML = `<div class="mb-2">${symbolsHtml}</div>`;
    }
    
    async loadCompareData() {
        if (this.compareSymbols.length === 0) return;
        
        try {
            const symbolsParam = this.compareSymbols.join(',');
            const response = await fetch(`/stockdiary/api/margin-compare/${this.diaryId}/?symbols=${symbolsParam}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'データ取得に失敗しました');
            }
            
            this.renderCompareChart(data.chart_data);
            this.showCompareChart();
            
        } catch (error) {
            console.error('Compare data loading error:', error);
            this.showError('比較データの読み込みに失敗しました: ' + error.message);
        }
    }
    
    renderCompareChart(chartData) {
        const ctx = document.getElementById('compareChart');
        if (!ctx) return;
        
        if (this.compareChart) {
            this.compareChart.destroy();
        }
        
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: window.innerWidth < 768 ? 'bottom' : 'top',
                        labels: {
                            usePointStyle: true,
                            padding: window.innerWidth < 768 ? 5 : 15,
                            font: {
                                size: window.innerWidth < 768 ? 10 : 12
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${context.dataset.label}: ${context.parsed.y}倍`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        ticks: {
                            maxTicksLimit: window.innerWidth < 768 ? 4 : 6
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: window.innerWidth >= 768,
                            text: '信用倍率'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '倍';
                            }
                        }
                    }
                }
            }
        };
        
        this.compareChart = new Chart(ctx, config);
    }
    
    showCompareChart() {
        const container = document.getElementById('compareChartContainer');
        if (container) {
            container.style.display = 'block';
        }
    }
    
    hideCompareChart() {
        const container = document.getElementById('compareChartContainer');
        if (container) {
            container.style.display = 'none';
        }
    }
    
    resetComparison() {
        this.compareSymbols = [];
        this.updateSelectedSymbols();
        this.hideCompareChart();
        
        if (this.compareChart) {
            this.compareChart.destroy();
            this.compareChart = null;
        }
    }
    
    async loadSectorData() {
        try {
            const response = await fetch(`/stockdiary/api/margin-sector/${this.diaryId}/`);
            const data = await response.json();
            
            if (!response.ok) {
                if (data.suggestions) {
                    this.displaySectorSuggestions(data.suggestions);
                }
                return;
            }
            
            this.displaySectorStats(data.sector_stats);
            this.displaySectorSuggestions(data.suggestions);
            
        } catch (error) {
            console.error('Sector data loading error:', error);
        }
    }
    
    displaySectorStats(stats) {
        const container = document.getElementById('sectorStats');
        if (!container || !stats) return;
        
        const ranking = stats.current_ranking ? 
            `${stats.current_ranking}位 / ${stats.company_count}社` : '不明';
        
        container.innerHTML = `
            <div class="card border-0 bg-light">
                <div class="card-body p-2 p-sm-3">
                    <h6 class="mb-2">
                        <i class="bi bi-building"></i> 
                        ${stats.sector_name}業種分析
                    </h6>
                    <div class="row g-2">
                        <div class="col-6 col-md-3">
                            <div class="text-center">
                                <div class="small text-muted">業種平均</div>
                                <div class="fw-semibold">${stats.average_ratio}倍</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="text-center">
                                <div class="small text-muted">業種順位</div>
                                <div class="fw-semibold">${ranking}</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="text-center">
                                <div class="small text-muted">最高値</div>
                                <div class="fw-semibold">${stats.max_ratio}倍</div>
                            </div>
                        </div>
                        <div class="col-6 col-md-3">
                            <div class="text-center">
                                <div class="small text-muted">最低値</div>
                                <div class="fw-semibold">${stats.min_ratio}倍</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    displaySectorSuggestions(suggestions) {
        const container = document.getElementById('suggestedSymbols');
        if (!container || !suggestions || suggestions.length === 0) {
            if (container) {
                container.innerHTML = '<small class="text-muted">推奨銘柄なし</small>';
            }
            return;
        }
        
        const suggestionsHtml = suggestions.slice(0, 3).map(item => `
            <button class="btn btn-outline-secondary btn-sm me-1 mb-1" 
                    onclick="document.getElementById('compareSymbolInput').value='${item.symbol}'; window.MarginTabController.addCompareSymbol();">
                ${item.symbol} (${item.ratio})
            </button>
        `).join('');
        
        container.innerHTML = suggestionsHtml;
    }
    
    showError(message) {
        // Bootstrap toastまたはalertでエラー表示
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show mt-2';
        alertDiv.innerHTML = `
            <i class="bi bi-exclamation-triangle me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.margin-tab-container');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
        }
    }
    
    showSymbolSuggestions(query) {
        // 実装は省略（既存の検索サジェスト機能を活用）
    }
}

// ユーティリティ関数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
console.log('✅ margin-tab.js loaded successfully');

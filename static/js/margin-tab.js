// stockdiary/static/stockdiary/js/margin-tab.js

class MarginTabManager {
    constructor(diaryId, issueId, currentSymbol = null) {
        this.diaryId = diaryId;
        this.issueId = String(issueId);
        this.currentSymbol = currentSymbol;
        this.chart = null;
        this.compareChart = null;
        this.compareSymbols = [];
        this.sectorSuggestions = [];
        this.compareTabInitialized = false; // 比較タブ初期化フラグ
        
        this.init();
    }
    
    init() {
        this.initEventListeners();
        this.loadChartData();
        this.loadSectorSuggestions(); // 業種別候補を先に読み込み
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
                    e.preventDefault();
                    this.addCompareSymbol();
                }
            });
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
                if (this.chart) {
                    setTimeout(() => {
                        this.chart.resize();
                        this.chart.update('none');
                    }, 100);
                }
                break;
                
            case '#compare-content':
                // 比較タブ初回表示時に現在の銘柄を自動追加
                if (!this.compareTabInitialized && this.currentSymbol) {
                    this.initializeCompareTab();
                    this.compareTabInitialized = true;
                }
                
                if (this.compareChart) {
                    setTimeout(() => {
                        this.compareChart.resize();
                        this.compareChart.update('none');
                    }, 100);
                } else if (this.compareSymbols.length > 0) {
                    // 比較データがある場合は再描画
                    this.loadCompareData();
                }
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
        
        // Chart.jsの設定（修正版）
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false, // 重要：アスペクト比を維持しない
                layout: {
                    padding: {
                        top: 10,
                        bottom: 10
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: window.innerWidth < 768 ? 10 : 20,
                            font: {
                                size: window.innerWidth < 768 ? 11 : 13
                            }
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
                        },
                        beginAtZero: false
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
                        beginAtZero: true
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
        if (volEl) volEl.textContent = `±${stats.volatility}`;
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
    
    async loadSectorSuggestions() {
        const loadingEl = document.getElementById('suggestionsLoading');
        if (loadingEl) loadingEl.classList.remove('d-none');
        
        try {
            const response = await fetch(`/stockdiary/api/margin-sector-suggestions/${this.diaryId}/`);
            const data = await response.json();
            
            this.sectorSuggestions = data.suggestions || [];
            this.sectorInfo = {
                name: data.sector,
                type: data.sector_type || '業種',
                totalCompanies: data.total_companies || 0,
                filteredCount: data.filtered_count || 0,
                priorityMethod: data.priority_method || '17業種優先'
            };
            
            this.displaySectorSuggestions();
            
        } catch (error) {
            console.error('Sector suggestions loading error:', error);
            this.sectorSuggestions = [];
            this.sectorInfo = null;
        } finally {
            if (loadingEl) loadingEl.classList.add('d-none');
        }
    }
    
    initializeCompareTab() {
        /**
         * 比較タブ初期化：現在の銘柄を自動追加
         */
        if (this.currentSymbol && !this.compareSymbols.includes(this.currentSymbol)) {
            // 現在の銘柄を最初に追加（特別表示）
            this.compareSymbols.push(this.currentSymbol);
            this.updateSelectedSymbols();
            
            // 初期データをロード
            setTimeout(() => {
                this.loadCompareData();
            }, 100);
            
            console.log(`✅ 初期銘柄 ${this.currentSymbol} を比較に追加しました`);
        }
    }
    
    displaySectorSuggestions() {
        const container = document.getElementById('suggestedSymbols');
        if (!container) return;
        
        // 業種情報がない場合
        if (!this.sectorInfo) {
            container.innerHTML = '<small class="text-muted">業種情報を取得できませんでした</small>';
            return;
        }
        
        // 推奨銘柄がない場合
        if (this.sectorSuggestions.length === 0) {
            container.innerHTML = `
                <small class="text-muted">
                    ${this.sectorInfo.name}（${this.sectorInfo.type}）の推奨銘柄がありません
                </small>
            `;
            return;
        }
        
        // 現在の銘柄と既に選択済みの銘柄を除外
        const availableSuggestions = this.sectorSuggestions.filter(item => 
            item.symbol !== this.currentSymbol && !this.compareSymbols.includes(item.symbol)
        );
        
        if (availableSuggestions.length === 0) {
            container.innerHTML = `
                <small class="text-muted">
                    ${this.sectorInfo.name}（${this.sectorInfo.type}）で追加可能な銘柄がありません
                </small>
            `;
            return;
        }
        
        // 業種情報ヘッダー
        let headerHtml = `
            <div class="d-flex align-items-center justify-content-between mb-2">
                <small class="text-primary fw-medium">
                    <i class="bi bi-building me-1"></i>
                    ${this.sectorInfo.name}（${this.sectorInfo.type}）
                </small>
                <small class="text-muted">
                    ${this.sectorInfo.filteredCount}/${this.sectorInfo.totalCompanies}社
                </small>
            </div>
        `;
        
        // 推奨銘柄ボタン
        const suggestionsHtml = availableSuggestions.slice(0, 6).map(item => {
            const isBalanced = item.is_balanced;
            const buttonClass = isBalanced ? 'btn-outline-success' : 'btn-outline-secondary';
            const ratioText = isBalanced ? `${item.ratio}★` : item.ratio;
            
            return `
                <button type="button" class="btn ${buttonClass} btn-sm me-1 mb-1" 
                        onclick="window.MarginTabController.addSuggestion('${item.symbol}', '${item.name}'); return false;"
                        title="${item.name}&#10;倍率: ${item.ratio} ${isBalanced ? '(適正範囲)' : ''}&#10;市場: ${item.market}&#10;規模: ${item.scale}">
                    ${item.name}
                </button>
            `;
        }).join('');
        
        container.innerHTML = headerHtml + suggestionsHtml;
    }
    
    addSuggestion(symbol, name) {
        const input = document.getElementById('compareSymbolInput');
        if (input) {
            input.value = symbol;
            this.addCompareSymbol();
            
            // 推奨銘柄リストを即座に更新
            setTimeout(() => {
                this.displaySectorSuggestions();
            }, 100);
        }
    }
    
    async addCompareSymbol() {
        const input = document.getElementById('compareSymbolInput');
        const symbol = input.value.trim();
        
        if (!symbol) {
            this.showError('証券コードを入力してください');
            return;
        }
        
        if (this.compareSymbols.includes(symbol)) {
            this.showError('この銘柄は既に追加されています');
            return;
        }
        
        if (this.compareSymbols.length >= 4) {
            this.showError('比較銘柄は最大4つまでです');
            return;
        }
        
        this.compareSymbols.push(symbol);
        input.value = '';
        
        this.updateSelectedSymbols();
        this.displaySectorSuggestions(); // 推奨銘柄も更新
        this.loadCompareData();
    }
    
    removeCompareSymbol(symbol) {
        const index = this.compareSymbols.indexOf(symbol);
        if (index > -1) {
            this.compareSymbols.splice(index, 1);
            this.updateSelectedSymbols();
            this.displaySectorSuggestions(); // 推奨銘柄も更新
            
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
        
        const symbolsHtml = this.compareSymbols.map(symbol => {
            const isCurrentSymbol = symbol === this.currentSymbol;
            const badgeClass = isCurrentSymbol ? 'bg-success' : 'bg-primary';
            const symbolLabel = isCurrentSymbol ? `${symbol} (現在)` : symbol;
            
            return `
                <span class="badge ${badgeClass} me-2 mb-2 p-2">
                    <i class="bi ${isCurrentSymbol ? 'bi-star-fill' : 'bi-building'} me-1"></i>
                    ${symbolLabel}
                    <button type="button" class="btn-close btn-close-white ms-2" 
                            style="font-size: 0.7em;" 
                            onclick="window.MarginTabController.removeCompareSymbol('${symbol}'); return false;"
                            title="削除">
                    </button>
                </span>
            `;
        }).join('');
        
        const countText = this.compareSymbols.length < 4 ? 
            `(${this.compareSymbols.length}/4銘柄)` : 
            '(上限に達しました)';
        
        container.innerHTML = `
            <div class="d-flex align-items-center justify-content-between mb-2">
                <small class="text-muted">選択済み銘柄 ${countText}</small>
                ${this.compareSymbols.length > 1 ? `
                    <button type="button" class="btn btn-outline-secondary btn-sm" 
                            onclick="window.MarginTabController.resetComparison(); return false;">
                        <i class="bi bi-arrow-counterclockwise me-1"></i>リセット
                    </button>
                ` : ''}
            </div>
            <div class="mb-2">${symbolsHtml}</div>
        `;
    }
    
    async loadCompareData() {
        if (this.compareSymbols.length === 0) return;
        
        const loadingEl = document.getElementById('compareChartLoading');
        if (loadingEl) loadingEl.classList.remove('d-none');
        
        try {
            const symbolsParam = this.compareSymbols.join(',');
            const response = await fetch(`/stockdiary/api/margin-compare/${this.diaryId}/?symbols=${symbolsParam}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || '比較データの取得に失敗しました');
            }
            
            this.renderCompareChart(data.chart_data);
            this.displayCompareStats(data.compare_data);
            this.showCompareChart();
            
        } catch (error) {
            console.error('Compare data loading error:', error);
            this.showError('比較データの読み込みに失敗しました: ' + error.message);
        } finally {
            if (loadingEl) loadingEl.classList.add('d-none');
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
                maintainAspectRatio: false, // 重要：アスペクト比を維持しない
                layout: {
                    padding: {
                        top: 10,
                        bottom: 10
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: window.innerWidth < 768 ? 'bottom' : 'top',
                        labels: {
                            usePointStyle: true,
                            padding: window.innerWidth < 768 ? 8 : 15,
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
                            maxTicksLimit: window.innerWidth < 768 ? 4 : 6,
                            font: {
                                size: window.innerWidth < 768 ? 10 : 12
                            }
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
                            },
                            font: {
                                size: window.innerWidth < 768 ? 10 : 12
                            }
                        },
                        beginAtZero: false
                    }
                }
            }
        };
        
        this.compareChart = new Chart(ctx, config);
    }
    
    displayCompareStats(compareData) {
        const container = document.getElementById('compareStats');
        if (!container || !compareData.length) return;
        
        let statsHtml = '<div class="row g-2">';
        
        compareData.forEach(data => {
            const ratioClass = this.getRatioClass(data.current_ratio);
            
            statsHtml += `
                <div class="col-6 col-md-3">
                    <div class="card border-0 bg-light">
                        <div class="card-body p-2 text-center">
                            <div class="small text-muted">${data.name}</div>
                            <div class="fw-semibold ${ratioClass}">${data.current_ratio}倍</div>
                            <div class="small text-muted">平均: ${data.average_ratio}倍</div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        statsHtml += '</div>';
        container.innerHTML = statsHtml;
    }
    
    getRatioClass(ratio) {
        if (ratio > 2) return 'text-success';
        if (ratio > 1) return 'text-primary';
        return 'text-danger';
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
        
        // 統計も隠す
        const statsContainer = document.getElementById('compareStats');
        if (statsContainer) {
            statsContainer.innerHTML = '';
        }
    }
    
    resetComparison() {
        this.compareSymbols = [];
        
        // 現在の銘柄を再追加
        if (this.currentSymbol) {
            this.compareSymbols.push(this.currentSymbol);
        }
        
        this.updateSelectedSymbols();
        this.displaySectorSuggestions();
        
        if (this.compareSymbols.length > 0) {
            this.loadCompareData();
        } else {
            this.hideCompareChart();
        }
        
        if (this.compareChart) {
            this.compareChart.destroy();
            this.compareChart = null;
        }
    }
    
    showError(message) {
        // Toast通知でエラー表示
        const toastHtml = `
            <div class="toast align-items-center text-white bg-danger border-0 position-fixed top-0 end-0 m-3" 
                 role="alert" aria-live="assertive" aria-atomic="true" style="z-index: 9999;">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                            data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        const toastContainer = document.createElement('div');
        toastContainer.innerHTML = toastHtml;
        document.body.appendChild(toastContainer);
        
        const toastElement = toastContainer.querySelector('.toast');
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: 5000
        });
        
        toast.show();
        
        // Toast終了後に要素を削除
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastContainer.remove();
        });
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

console.log('✅ margin-tab.js loaded successfully (fixed version)');
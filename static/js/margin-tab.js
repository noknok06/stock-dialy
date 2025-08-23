// ===== スマホ最適化版 margin-tab.js =====

class MarginTabManager {
    constructor(diaryId, issueId, currentSymbol = null) {
        this.diaryId = diaryId;
        this.issueId = String(issueId);
        this.currentSymbol = currentSymbol;
        this.chart = null;
        this.compareChart = null;
        this.compareSymbols = [];
        this.sectorSuggestions = [];
        this.compareTabInitialized = false;
        this.isLoading = false;
        this.isMobile = this.detectMobile();
        
        this.init();
    }
    
    detectMobile() {
        return window.innerWidth <= 768 || 
               /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }
    
    init() {
        this.initEventListeners();
        this.loadChartData();
        this.loadSectorSuggestions();
        this.setupTouchOptimization();
    }
    
    setupTouchOptimization() {
        // タッチデバイス用の最適化
        if (this.isMobile) {
            // スクロール時のチャートリサイズ防止
            let scrollTimeout;
            window.addEventListener('scroll', () => {
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    this.resizeCharts();
                }, 150);
            });
            
            // オリエンテーション変更対応
            window.addEventListener('orientationchange', () => {
                setTimeout(() => {
                    this.resizeCharts();
                }, 300);
            });
            
            // タッチフレンドリーなツールチップ
            this.setupMobileTooltips();
        }
    }
    
    setupMobileTooltips() {
        // モバイルでのツールチップ改善
        const tooltipOptions = {
            trigger: this.isMobile ? 'click' : 'hover',
            delay: this.isMobile ? { show: 100, hide: 200 } : { show: 500, hide: 100 }
        };
        
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
            new bootstrap.Tooltip(el, tooltipOptions);
        });
    }
    
    initEventListeners() {
        // タブ切り替え（タッチ最適化）
        document.querySelectorAll('#marginTabsNav button').forEach(tab => {
            // タッチイベント追加でレスポンスを向上
            tab.addEventListener('touchstart', () => {}, { passive: true });
            
            tab.addEventListener('shown.bs.tab', (e) => {
                const targetId = e.target.getAttribute('data-bs-target');
                this.onTabSwitch(targetId);
            });
        });
        
        // チャート期間変更（改善されたレスポンス）
        document.querySelectorAll('input[name="chartPeriod"]').forEach(radio => {
            radio.addEventListener('change', this.debounce((e) => {
                this.loadChartData(e.target.value);
                this.hapticFeedback(); // タッチフィードバック
            }, 300));
        });
        
        // 比較銘柄追加（エラーハンドリング強化）
        const addBtn = document.getElementById('addCompareBtn');
        const input = document.getElementById('compareSymbolInput');
        
        if (addBtn && input) {
            addBtn.addEventListener('click', () => this.addCompareSymbol());
            addBtn.addEventListener('touchstart', () => {}, { passive: true });
            
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.addCompareSymbol();
                }
            });
            
            // リアルタイム入力validation
            input.addEventListener('input', this.debounce((e) => {
                this.validateSymbolInput(e.target.value);
            }, 300));
        }
        
        // リセットボタン（確認ダイアログ追加）
        const resetBtn = document.getElementById('resetCompareBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.confirmReset());
        }
        
        // スワイプジェスチャー（モバイル用）
        if (this.isMobile) {
            this.initSwipeGestures();
        }
    }
    
    initSwipeGestures() {
        let startX = 0;
        let startY = 0;
        
        const container = document.querySelector('.margin-tab-content');
        if (!container) return;
        
        container.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }, { passive: true });
        
        container.addEventListener('touchmove', (e) => {
            if (Math.abs(e.touches[0].clientY - startY) > 50) {
                return; // 縦スクロールの場合は無視
            }
        }, { passive: true });
        
        container.addEventListener('touchend', (e) => {
            const endX = e.changedTouches[0].clientX;
            const endY = e.changedTouches[0].clientY;
            
            const diffX = startX - endX;
            const diffY = Math.abs(startY - endY);
            
            // 縦スクロールの場合は無視
            if (diffY > 50) return;
            
            // スワイプ距離が十分でない場合は無視
            if (Math.abs(diffX) < 50) return;
            
            const currentTab = document.querySelector('#marginTabsNav .nav-link.active');
            let nextTab = null;
            
            if (diffX > 0) { // 左スワイプ（次のタブ）
                nextTab = currentTab.parentElement.nextElementSibling?.querySelector('.nav-link');
            } else { // 右スワイプ（前のタブ）
                nextTab = currentTab.parentElement.previousElementSibling?.querySelector('.nav-link');
            }
            
            if (nextTab) {
                nextTab.click();
                this.hapticFeedback();
            }
        });
    }
    
    validateSymbolInput(value) {
        const input = document.getElementById('compareSymbolInput');
        if (!input) return;
        
        const cleanValue = value.trim().toUpperCase();
        
        // 数字のみで4桁チェック
        if (cleanValue && !/^\d{4}$/.test(cleanValue)) {
            input.classList.add('is-invalid');
            this.showInputFeedback(input, '4桁の証券コードを入力してください', 'invalid');
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            this.clearInputFeedback(input);
        }
    }
    
    showInputFeedback(input, message, type) {
        this.clearInputFeedback(input);
        
        const feedback = document.createElement('div');
        feedback.className = `${type}-feedback d-block small`;
        feedback.textContent = message;
        feedback.id = 'input-feedback';
        
        input.parentNode.appendChild(feedback);
        
        // 3秒後に自動削除
        setTimeout(() => {
            this.clearInputFeedback(input);
        }, 3000);
    }
    
    clearInputFeedback(input) {
        const existing = document.getElementById('input-feedback');
        if (existing) {
            existing.remove();
        }
    }
    
    hapticFeedback() {
        // タッチデバイスでの触覚フィードバック
        if (navigator.vibrate && this.isMobile) {
            navigator.vibrate(50);
        }
    }
    
    confirmReset() {
        if (this.compareSymbols.length <= 1) {
            this.resetComparison();
            return;
        }
        
        const confirmed = confirm('比較設定をリセットしますか？');
        if (confirmed) {
            this.resetComparison();
            this.hapticFeedback();
        }
    }
    
    onTabSwitch(targetId) {
        // ローディング中は切り替えを無視
        if (this.isLoading) return;
        
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
                    this.loadCompareData();
                }
                break;
                
            case '#data-content':
                // データタブの最適化
                this.optimizeDataTable();
                break;
        }
    }
    
    optimizeDataTable() {
        const table = document.querySelector('.data-table');
        if (!table || !this.isMobile) return;
        
        // モバイルでのテーブル最適化
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.addEventListener('click', () => {
                row.classList.toggle('table-active');
            });
        });
    }
    
    async loadChartData(period = '3') {
        if (this.isLoading) return;
        
        const loadingEl = document.getElementById('chartLoading');
        if (loadingEl) loadingEl.classList.remove('d-none');
        
        this.isLoading = true;
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10秒タイムアウト
            
            const response = await fetch(`/stockdiary/api/margin-chart/${this.diaryId}/?period=${period}`, {
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            this.renderChart(data.chart_data);
            this.updateStats(data.stats);
            this.showAlerts(data.alerts);
            
        } catch (error) {
            console.error('Chart data loading error:', error);
            
            if (error.name === 'AbortError') {
                this.showError('通信がタイムアウトしました。再度お試しください。');
            } else {
                this.showError(`チャートデータの読み込みに失敗: ${error.message}`);
            }
        } finally {
            this.isLoading = false;
            if (loadingEl) loadingEl.classList.add('d-none');
        }
    }
    
    renderChart(chartData) {
        const ctx = document.getElementById('marginChart');
        if (!ctx) return;
        
        if (this.chart) {
            this.chart.destroy();
        }
        
        // モバイル用チャート設定
        const config = {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                devicePixelRatio: window.devicePixelRatio || 1,
                animation: {
                    duration: this.isMobile ? 300 : 800 // モバイルでは短いアニメーション
                },
                layout: {
                    padding: {
                        top: this.isMobile ? 8 : 10,
                        bottom: this.isMobile ? 8 : 10,
                        left: this.isMobile ? 4 : 8,
                        right: this.isMobile ? 4 : 8
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
                            padding: this.isMobile ? 8 : 15,
                            font: {
                                size: this.isMobile ? 10 : 12
                            },
                            boxWidth: this.isMobile ? 10 : 12,
                            boxHeight: this.isMobile ? 10 : 12
                        }
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: true,
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
                            display: !this.isMobile,
                            text: '日付',
                            font: {
                                size: 11
                            }
                        },
                        ticks: {
                            maxTicksLimit: this.isMobile ? 4 : 6,
                            font: {
                                size: this.isMobile ? 9 : 10
                            }
                        },
                        grid: {
                            display: !this.isMobile
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: !this.isMobile,
                            text: '信用倍率',
                            font: {
                                size: 11
                            }
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '倍';
                            },
                            font: {
                                size: this.isMobile ? 9 : 10
                            }
                        },
                        grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        beginAtZero: false
                    },
                    y1: {
                        type: 'linear',
                        display: !this.isMobile, // モバイルでは非表示
                        position: 'right',
                        title: {
                            display: false
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString();
                            },
                            font: {
                                size: 9
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
        
        if (avgEl) {
            avgEl.textContent = `${stats.average}倍`;
            avgEl.classList.add('updated');
            setTimeout(() => avgEl.classList.remove('updated'), 1000);
        }
        
        if (volEl) {
            volEl.textContent = `±${stats.volatility}`;
            volEl.classList.add('updated');
            setTimeout(() => volEl.classList.remove('updated'), 1000);
        }
    }
    
    showAlerts(alerts) {
        const alertContainer = document.getElementById('marginAlerts');
        if (!alertContainer) return;
        
        alertContainer.innerHTML = '';
        
        alerts.forEach((alert, index) => {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${alert.type} alert-dismissible fade show`;
            alertDiv.style.animationDelay = `${index * 100}ms`;
            alertDiv.innerHTML = `
                <i class="bi bi-info-circle me-2"></i>
                ${alert.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="閉じる"></button>
            `;
            alertContainer.appendChild(alertDiv);
            
            // 自動削除（モバイルでは早めに）
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    const bsAlert = new bootstrap.Alert(alertDiv);
                    bsAlert.close();
                }
            }, this.isMobile ? 5000 : 8000);
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
    
    displaySectorSuggestions() {
        const container = document.getElementById('suggestedSymbols');
        if (!container) return;
        
        if (!this.sectorInfo) {
            container.innerHTML = '<small class="text-muted">業種情報を取得中...</small>';
            return;
        }
        
        if (this.sectorSuggestions.length === 0) {
            container.innerHTML = `
                <small class="text-muted">
                    ${this.sectorInfo.name}（${this.sectorInfo.type}）の推奨銘柄がありません
                </small>
            `;
            return;
        }
        
        const availableSuggestions = this.sectorSuggestions.filter(item => 
            item.symbol !== this.currentSymbol && !this.compareSymbols.includes(item.symbol)
        );
        
        if (availableSuggestions.length === 0) {
            container.innerHTML = `
                <small class="text-muted">
                    ${this.sectorInfo.name}で追加可能な銘柄がありません
                </small>
            `;
            return;
        }
        
        // 業種情報とカウント
        let headerHtml = `
            <div class="d-flex align-items-center justify-content-between mb-2">
                <small class="sector-info">
                    <i class="bi bi-building me-1"></i>
                    ${this.sectorInfo.name}
                </small>
                <small class="text-muted">
                    ${this.sectorInfo.filteredCount}/${this.sectorInfo.totalCompanies}社
                </small>
            </div>
        `;
        
        // 推奨銘柄ボタン（モバイル最適化）
        const maxSuggestions = this.isMobile ? 4 : 6;
        const suggestionsHtml = availableSuggestions.slice(0, maxSuggestions).map(item => {
            const isBalanced = item.is_balanced;
            const buttonClass = isBalanced ? 'btn-outline-success' : 'btn-outline-secondary';
            
            return `
                <button type="button" class="btn ${buttonClass} btn-sm suggestion-btn" 
                        onclick="window.MarginTabController.addSuggestion('${item.symbol}', '${item.name}'); return false;"
                        title="${item.name} - 倍率: ${item.ratio}${isBalanced ? ' (適正)' : ''}">
                    ${item.name}${isBalanced ? ' ★' : ''}
                </button>
            `;
        }).join('');
        
        container.innerHTML = headerHtml + '<div class="suggestions-grid">' + suggestionsHtml + '</div>';
    }
    
    addSuggestion(symbol, name) {
        const input = document.getElementById('compareSymbolInput');
        if (input) {
            input.value = symbol;
            this.addCompareSymbol();
            this.hapticFeedback();
            
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
            input.focus();
            return;
        }
        
        if (this.compareSymbols.includes(symbol)) {
            this.showError('この銘柄は既に追加されています');
            input.focus();
            return;
        }
        
        if (this.compareSymbols.length >= 4) {
            this.showError('比較銘柄は最大4つまでです');
            return;
        }
        
        // 入力値のvalidation
        if (!/^\d{4}$/.test(symbol)) {
            this.showError('4桁の証券コードを入力してください');
            input.focus();
            return;
        }
        
        this.compareSymbols.push(symbol);
        input.value = '';
        input.classList.remove('is-valid', 'is-invalid');
        this.clearInputFeedback(input);
        
        this.updateSelectedSymbols();
        this.displaySectorSuggestions();
        this.loadCompareData();
        this.hapticFeedback();
        
        // 成功フィードバック
        this.showSuccessToast(`${symbol} を比較に追加しました`);
    }
    
    removeCompareSymbol(symbol) {
        const index = this.compareSymbols.indexOf(symbol);
        if (index > -1) {
            this.compareSymbols.splice(index, 1);
            this.updateSelectedSymbols();
            this.displaySectorSuggestions();
            this.hapticFeedback();
            
            if (this.compareSymbols.length > 0) {
                this.loadCompareData();
            } else {
                this.hideCompareChart();
            }
            
            this.showSuccessToast(`${symbol} を比較から削除しました`);
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
                <span class="badge ${badgeClass} me-2 mb-2 p-2 symbol-badge">
                    <i class="bi ${isCurrentSymbol ? 'bi-star-fill' : 'bi-building'} me-1"></i>
                    ${symbolLabel}
                    <button type="button" class="btn-close btn-close-white ms-2" 
                            style="font-size: 0.7em;" 
                            onclick="window.MarginTabController.removeCompareSymbol('${symbol}'); return false;"
                            aria-label="削除">
                    </button>
                </span>
            `;
        }).join('');
        
        const countText = this.compareSymbols.length < 4 ? 
            `(${this.compareSymbols.length}/4銘柄)` : 
            '(上限)';
        
        container.innerHTML = `
            <div class="d-flex align-items-center justify-content-between mb-2">
                <small class="text-muted">選択済み銘柄 ${countText}</small>
                ${this.compareSymbols.length > 1 ? `
                    <button type="button" class="btn btn-outline-secondary btn-sm reset-btn" 
                            onclick="window.MarginTabController.confirmReset(); return false;">
                        <i class="bi bi-arrow-counterclockwise me-1"></i>リセット
                    </button>
                ` : ''}
            </div>
            <div class="selected-symbols-container">${symbolsHtml}</div>
        `;
    }
    
    resizeCharts() {
        if (this.chart && this.chart.canvas) {
            this.chart.resize();
        }
        
        if (this.compareChart && this.compareChart.canvas) {
            this.compareChart.resize();
        }
    }
    
    initializeCompareTab() {
        if (this.currentSymbol && !this.compareSymbols.includes(this.currentSymbol)) {
            this.compareSymbols.push(this.currentSymbol);
            this.updateSelectedSymbols();
            
            setTimeout(() => {
                this.loadCompareData();
            }, 100);
            
            console.log(`✅ 初期銘柄 ${this.currentSymbol} を比較に追加`);
        }
    }
    
    showSuccessToast(message) {
        this.showToast(message, 'success');
    }
    
    showError(message) {
        this.showToast(message, 'danger', 5000);
    }
    
    showToast(message, type = 'info', duration = 3000) {
        const toastId = `toast-${Date.now()}`;
        const iconClass = type === 'success' ? 'bi-check-circle' : 
                         type === 'danger' ? 'bi-exclamation-triangle' : 'bi-info-circle';
        
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0 position-fixed ${this.isMobile ? 'bottom-0 start-50 translate-middle-x mb-3' : 'top-0 end-0 m-3'}" 
                 role="alert" aria-live="assertive" aria-atomic="true" style="z-index: 9999;">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi ${iconClass} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                            data-bs-dismiss="toast" aria-label="閉じる"></button>
                </div>
            </div>
        `;
        
        const toastContainer = document.createElement('div');
        toastContainer.innerHTML = toastHtml;
        document.body.appendChild(toastContainer);
        
        const toastElement = toastContainer.querySelector('.toast');
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: duration
        });
        
        toast.show();
        
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastContainer.remove();
        });
        
        return toast;
    }
    
    // その他のメソッドは元のファイルから継承...
    // （loadCompareData, renderCompareChart, displayCompareStats, resetComparison等）
    
    async loadCompareData() {
        if (this.compareSymbols.length === 0 || this.isLoading) return;
        
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
            this.showError('比較データの読み込みに失敗: ' + error.message);
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
                maintainAspectRatio: false,
                animation: {
                    duration: this.isMobile ? 300 : 600
                },
                layout: {
                    padding: {
                        top: this.isMobile ? 8 : 10,
                        bottom: this.isMobile ? 8 : 10,
                        left: this.isMobile ? 4 : 8,
                        right: this.isMobile ? 4 : 8
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: this.isMobile ? 'bottom' : 'top',
                        labels: {
                            usePointStyle: true,
                            padding: this.isMobile ? 6 : 12,
                            font: {
                                size: this.isMobile ? 9 : 11
                            },
                            boxWidth: this.isMobile ? 8 : 10,
                            boxHeight: this.isMobile ? 8 : 10
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
                            maxTicksLimit: this.isMobile ? 3 : 5,
                            font: {
                                size: this.isMobile ? 8 : 10
                            }
                        },
                        grid: {
                            display: !this.isMobile
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: !this.isMobile,
                            text: '信用倍率'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '倍';
                            },
                            font: {
                                size: this.isMobile ? 8 : 10
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
                <div class="${this.isMobile ? 'col-6' : 'col-6 col-md-3'}">
                    <div class="card border-0 bg-light compare-stat-card">
                        <div class="card-body p-2 text-center">
                            <div class="small text-muted mb-1">${this.truncateText(data.name, 8)}</div>
                            <div class="fw-semibold ${ratioClass} fs-6">${data.current_ratio}倍</div>
                            <div class="small text-muted">平均: ${data.average_ratio}倍</div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        statsHtml += '</div>';
        container.innerHTML = statsHtml;
    }
    
    truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
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
        
        const statsContainer = document.getElementById('compareStats');
        if (statsContainer) {
            statsContainer.innerHTML = '';
        }
    }
    
    resetComparison() {
        this.compareSymbols = [];
        
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
    
    // デバウンス関数
    debounce(func, wait) {
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
}

// グローバル関数（テンプレートから呼び出し用）
window.MarginTabController = null;

// ユーティリティ関数
function isMobileDevice() {
    return window.innerWidth <= 768 || 
           /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// パフォーマンス監視
if (typeof performance !== 'undefined') {
    performance.mark('margin-tab-js-loaded');
}

console.log('✅ margin-tab.js (スマホ最適化版) loaded successfully');
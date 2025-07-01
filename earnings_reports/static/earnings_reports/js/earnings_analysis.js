/**
 * earnings_reports/static/earnings_reports/js/earnings_analysis.js
 * 決算分析システム用JavaScript
 */

class EarningsAnalysisApp {
    constructor() {
        this.init();
        this.bindEvents();
        this.startAutoUpdates();
    }

    init() {
        // 設定
        this.config = {
            statusUpdateInterval: 3000, // 3秒
            chartUpdateInterval: 10000, // 10秒
            maxRetries: 5,
            csrfToken: this.getCsrfToken()
        };

        // 状態管理
        this.state = {
            activePolling: false,
            selectedDocuments: new Set(),
            charts: {},
            retryCount: 0
        };

        // DOM要素のキャッシュ
        this.elements = {
            documentCheckboxes: document.querySelectorAll('input[name="selected_documents"]'),
            analysisStatusTable: document.getElementById('analysis-table-body'),
            progressBar: document.getElementById('overall-progress'),
            startButton: document.getElementById('start-analysis-btn'),
            statusSummary: document.getElementById('selected-summary')
        };

        console.log('決算分析システム初期化完了');
    }

    bindEvents() {
        // 書類選択チェックボックス
        if (this.elements.documentCheckboxes) {
            this.elements.documentCheckboxes.forEach(checkbox => {
                checkbox.addEventListener('change', (e) => {
                    this.handleDocumentSelection(e);
                });
            });
        }

        // 分析開始ボタン
        if (this.elements.startButton) {
            this.elements.startButton.addEventListener('click', (e) => {
                this.handleAnalysisStart(e);
            });
        }

        // グローバルエラーハンドリング
        window.addEventListener('error', (e) => {
            this.handleGlobalError(e);
        });

        // ページ離脱前の確認
        window.addEventListener('beforeunload', (e) => {
            if (this.state.activePolling) {
                e.preventDefault();
                e.returnValue = '分析が実行中です。ページを離れますか？';
            }
        });
    }

    startAutoUpdates() {
        // 分析状況ページでの自動更新
        if (window.location.pathname.includes('/analysis/status/')) {
            this.startStatusPolling();
        }

        // チャートの自動更新
        if (document.querySelector('canvas')) {
            this.scheduleChartUpdates();
        }
    }

    // ========================================
    // 書類選択関連
    // ========================================

    handleDocumentSelection(event) {
        const checkbox = event.target;
        const documentId = checkbox.value;

        if (checkbox.checked) {
            this.state.selectedDocuments.add(documentId);
        } else {
            this.state.selectedDocuments.delete(documentId);
        }

        this.updateSelectionSummary();
        this.updateStartButton();
    }

    updateSelectionSummary() {
        const count = this.state.selectedDocuments.size;
        const summaryElement = this.elements.statusSummary;

        if (summaryElement) {
            if (count > 0) {
                summaryElement.textContent = `${count}件の書類が選択されています`;
                summaryElement.className = 'text-success';
            } else {
                summaryElement.textContent = '書類を選択してください';
                summaryElement.className = 'text-muted';
            }
        }
    }

    updateStartButton() {
        const count = this.state.selectedDocuments.size;
        const button = this.elements.startButton;

        if (button) {
            if (count > 0) {
                button.disabled = false;
                button.innerHTML = `<i class="fas fa-play me-2"></i>${count}件の書類を分析`;
            } else {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-play me-2"></i>分析を開始';
            }
        }
    }

    // クイック選択機能
    selectDocumentsByType(docType) {
        this.state.selectedDocuments.clear();
        
        this.elements.documentCheckboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            const badge = row?.querySelector('.badge');
            
            if (badge && this.getDocTypeFromBadge(badge.textContent) === docType) {
                checkbox.checked = true;
                this.state.selectedDocuments.add(checkbox.value);
            } else {
                checkbox.checked = false;
            }
        });

        this.updateSelectionSummary();
        this.updateStartButton();
    }

    selectLatestDocuments(count) {
        this.state.selectedDocuments.clear();
        
        const checkboxes = Array.from(this.elements.documentCheckboxes);
        checkboxes.slice(0, count).forEach(checkbox => {
            checkbox.checked = true;
            this.state.selectedDocuments.add(checkbox.value);
        });
        
        checkboxes.slice(count).forEach(checkbox => {
            checkbox.checked = false;
        });

        this.updateSelectionSummary();
        this.updateStartButton();
    }

    selectAllDocuments() {
        this.state.selectedDocuments.clear();
        
        this.elements.documentCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
            this.state.selectedDocuments.add(checkbox.value);
        });

        this.updateSelectionSummary();
        this.updateStartButton();
    }

    clearSelection() {
        this.state.selectedDocuments.clear();
        
        this.elements.documentCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });

        this.updateSelectionSummary();
        this.updateStartButton();
    }

    // ========================================
    // 分析実行関連
    // ========================================

    handleAnalysisStart(event) {
        event.preventDefault();

        if (this.state.selectedDocuments.size === 0) {
            this.showAlert('分析する書類を選択してください。', 'warning');
            return;
        }

        const confirmMessage = 
            `${this.state.selectedDocuments.size}件の書類を分析します。\n\n` +
            '分析には数分かかる場合があります。\n' +
            '実行しますか？';

        if (!confirm(confirmMessage)) {
            return;
        }

        this.disableStartButton();
        this.submitAnalysisForm();
    }

    disableStartButton() {
        const button = this.elements.startButton;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>分析を開始しています...';
        }
    }

    submitAnalysisForm() {
        const form = document.querySelector('form');
        if (form) {
            // フォームデータの検証
            const formData = new FormData(form);
            
            // 選択された書類がフォームに含まれているかチェック
            const selectedDocs = formData.getAll('selected_documents');
            if (selectedDocs.length === 0) {
                this.showAlert('書類の選択に失敗しました。ページを再読み込みしてください。', 'error');
                return;
            }

            form.submit();
        }
    }

    // ========================================
    // 分析状況監視
    // ========================================

    startStatusPolling() {
        if (this.state.activePolling) return;

        this.state.activePolling = true;
        this.pollAnalysisStatus();
    }

    stopStatusPolling() {
        this.state.activePolling = false;
        this.state.retryCount = 0;
    }

    async pollAnalysisStatus() {
        if (!this.state.activePolling) return;

        try {
            const response = await fetch(window.location.href, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.config.csrfToken
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.updateAnalysisStatus(data);

            // 完了チェック
            if (data.all_completed) {
                this.handleAnalysisCompletion();
                return;
            }

            // 次回のポーリングをスケジュール
            setTimeout(() => {
                this.pollAnalysisStatus();
            }, this.config.statusUpdateInterval);

            // リトライカウンターリセット
            this.state.retryCount = 0;

        } catch (error) {
            console.error('Status polling error:', error);
            this.handlePollingError(error);
        }
    }

    updateAnalysisStatus(data) {
        if (!data.analyses) return;

        data.analyses.forEach(analysis => {
            this.updateAnalysisRow(analysis);
        });

        this.updateStatusSummary(data.analyses);
        this.updateOverallProgress(data.analyses);
        this.updateLastUpdateTime();
    }

    updateAnalysisRow(analysis) {
        const row = document.querySelector(`tr[data-analysis-id="${analysis.id}"]`);
        if (!row) return;

        // ステータス更新
        const statusBadge = row.querySelector('.status-badge');
        if (statusBadge) {
            statusBadge.className = `status-badge analysis-status-${analysis.status}`;
            statusBadge.innerHTML = this.getStatusIcon(analysis.status);
        }

        // 進行度更新
        const progressBar = row.querySelector('.progress-bar');
        if (progressBar) {
            const percentage = analysis.progress_percentage || 0;
            progressBar.style.width = `${percentage}%`;
            progressBar.className = this.getProgressBarClass(analysis.status);
        }

        // スコア更新
        if (analysis.overall_score !== null) {
            const scoreCell = row.querySelector('.score-cell');
            if (scoreCell) {
                const badgeClass = this.getScoreBadgeClass(analysis.overall_score);
                scoreCell.innerHTML = 
                    `<span class="badge score-badge ${badgeClass}">${analysis.overall_score.toFixed(1)}</span>`;
            }
        }

        // 処理時間更新
        if (analysis.processing_time) {
            const timeCell = row.querySelector('.time-cell');
            if (timeCell) {
                timeCell.textContent = `${analysis.processing_time.toFixed(1)}秒`;
            }
        }

        // アクションボタン更新
        this.updateActionButton(row, analysis);
    }

    updateActionButton(row, analysis) {
        const actionCell = row.querySelector('.action-cell');
        if (!actionCell) return;

        if (analysis.status === 'completed') {
            actionCell.innerHTML = `
                <a href="/earnings/analysis/${analysis.id}/" class="btn btn-outline-primary btn-sm">
                    <i class="fas fa-eye me-1"></i>詳細
                </a>
            `;
        } else if (analysis.status === 'failed') {
            actionCell.innerHTML = `
                <button type="button" class="btn btn-outline-warning btn-sm" 
                        onclick="app.retryAnalysis(${analysis.id})" title="再実行">
                    <i class="fas fa-redo"></i>
                </button>
            `;
        }
    }

    updateStatusSummary(analyses) {
        const counts = {
            total: analyses.length,
            completed: 0,
            processing: 0,
            failed: 0
        };

        analyses.forEach(analysis => {
            switch (analysis.status) {
                case 'completed':
                    counts.completed++;
                    break;
                case 'processing':
                case 'pending':
                    counts.processing++;
                    break;
                case 'failed':
                    counts.failed++;
                    break;
            }
        });

        // DOM更新
        this.updateElement('total-count', counts.total);
        this.updateElement('completed-count', counts.completed);
        this.updateElement('processing-count', counts.processing);
        this.updateElement('failed-count', counts.failed);
    }

    updateOverallProgress(analyses) {
        let totalProgress = 0;
        const validAnalyses = analyses.length;

        analyses.forEach(analysis => {
            if (analysis.status === 'completed') {
                totalProgress += 100;
            } else if (analysis.status === 'processing') {
                totalProgress += (analysis.progress_percentage || 50);
            }
        });

        const overallPercentage = validAnalyses > 0 ? 
            Math.round(totalProgress / validAnalyses) : 0;

        // 進行状況バー更新
        if (this.elements.progressBar) {
            this.elements.progressBar.style.width = `${overallPercentage}%`;
            
            if (overallPercentage === 100) {
                this.elements.progressBar.className = 'progress-bar bg-success';
            }
        }

        // パーセンテージ表示更新
        this.updateElement('overall-percentage', `${overallPercentage}%`);

        // プログレスメッセージ更新
        const messageElement = document.getElementById('progress-message');
        if (messageElement) {
            if (overallPercentage === 100) {
                messageElement.textContent = '全ての分析が完了しました！';
            } else if (overallPercentage > 0) {
                messageElement.textContent = '分析を実行中...';
            } else {
                messageElement.textContent = '分析を開始しています...';
            }
        }
    }

    updateLastUpdateTime() {
        const element = document.getElementById('last-update');
        if (element) {
            const now = new Date();
            element.textContent = `最終更新: ${now.toLocaleTimeString('ja-JP')}`;
        }
    }

    handleAnalysisCompletion() {
        this.stopStatusPolling();
        
        // 完了メッセージ表示
        this.showAlert('すべての分析が完了しました！', 'success');
        
        // 2秒後にページリロード（完了状態を表示するため）
        setTimeout(() => {
            window.location.reload();
        }, 2000);
    }

    handlePollingError(error) {
        this.state.retryCount++;
        
        if (this.state.retryCount >= this.config.maxRetries) {
            this.stopStatusPolling();
            this.showAlert('状況の取得に失敗しました。ページを再読み込みしてください。', 'error');
            return;
        }

        // リトライ間隔を延長
        const retryDelay = this.config.statusUpdateInterval * this.state.retryCount;
        setTimeout(() => {
            this.pollAnalysisStatus();
        }, retryDelay);
    }

    // ========================================
    // 分析再実行
    // ========================================

    async retryAnalysis(analysisId) {
        if (!confirm('この分析を再実行しますか？')) {
            return;
        }

        try {
            const response = await fetch(`/earnings/api/analysis/${analysisId}/retry/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.config.csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.showAlert('分析を再実行しています...', 'info');
                
                // ポーリングを再開
                if (!this.state.activePolling) {
                    this.startStatusPolling();
                }
            } else {
                this.showAlert(`再実行に失敗しました: ${data.error}`, 'error');
            }

        } catch (error) {
            console.error('Retry error:', error);
            this.showAlert('エラーが発生しました。', 'error');
        }
    }

    // ========================================
    // チャート関連
    // ========================================

    initializeCharts() {
        // 感情分析円グラフ
        this.initSentimentChart();
        
        // キャッシュフロー棒グラフ
        this.initCashflowChart();
        
        // トレンドライングラフ
        this.initTrendChart();
    }

    initSentimentChart() {
        const ctx = document.getElementById('sentimentPieChart');
        if (!ctx || !window.sentimentData) return;

        this.state.charts.sentiment = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['ポジティブ', 'ネガティブ', 'ニュートラル'],
                datasets: [{
                    data: [
                        window.sentimentData.positive_score,
                        window.sentimentData.negative_score,
                        window.sentimentData.neutral_score
                    ],
                    backgroundColor: ['#28a745', '#dc3545', '#6c757d'],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.parsed.toFixed(1)}%`;
                            }
                        }
                    }
                }
            }
        });
    }

    initCashflowChart() {
        const ctx = document.getElementById('cashflowBarChart');
        if (!ctx || !window.cashflowData) return;

        this.state.charts.cashflow = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['営業CF', '投資CF', '財務CF', 'フリーCF'],
                datasets: [{
                    data: [
                        window.cashflowData.operating_cf || 0,
                        window.cashflowData.investing_cf || 0,
                        window.cashflowData.financing_cf || 0,
                        window.cashflowData.free_cf || 0
                    ],
                    backgroundColor: function(context) {
                        const value = context.parsed.y;
                        return value >= 0 ? '#28a745' : '#dc3545';
                    },
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.parsed.y.toLocaleString()}百万円`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString() + '百万円';
                            }
                        }
                    }
                }
            }
        });
    }

    scheduleChartUpdates() {
        setInterval(() => {
            this.updateCharts();
        }, this.config.chartUpdateInterval);
    }

    updateCharts() {
        // 必要に応じてチャートデータを更新
        Object.values(this.state.charts).forEach(chart => {
            if (chart && typeof chart.update === 'function') {
                chart.update('none'); // アニメーションなしで更新
            }
        });
    }

    // ========================================
    // ユーティリティ関数
    // ========================================

    getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return decodeURIComponent(value);
            }
        }
        return '';
    }

    updateElement(id, content) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = content;
        }
    }

    showAlert(message, type = 'info') {
        // Bootstrap Toast または Alert を使用
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // ページ上部に表示
        const container = document.querySelector('.container-fluid') || document.body;
        container.insertBefore(alertDiv, container.firstChild);

        // 5秒後に自動削除
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    getStatusIcon(status) {
        switch (status) {
            case 'pending':
                return '<i class="fas fa-clock me-1"></i>待機中';
            case 'processing':
                return '<i class="fas fa-spinner fa-spin me-1"></i>処理中';
            case 'completed':
                return '<i class="fas fa-check-circle me-1"></i>完了';
            case 'failed':
                return '<i class="fas fa-exclamation-triangle me-1"></i>失敗';
            default:
                return status;
        }
    }

    getProgressBarClass(status) {
        switch (status) {
            case 'completed':
                return 'progress-bar bg-success';
            case 'failed':
                return 'progress-bar bg-danger';
            case 'processing':
                return 'progress-bar progress-bar-striped progress-bar-animated';
            default:
                return 'progress-bar';
        }
    }

    getScoreBadgeClass(score) {
        if (score >= 80) return 'score-excellent';
        if (score >= 60) return 'score-good';
        if (score >= 40) return 'score-fair';
        if (score >= 0) return 'score-poor';
        return 'score-negative';
    }

    getDocTypeFromBadge(text) {
        const typeMap = {
            '有価証券報告書': '120',
            '四半期報告書': '130',
            '半期報告書': '140',
            '決算短信': '350'
        };
        return typeMap[text] || '';
    }

    handleGlobalError(event) {
        console.error('Global error:', event.error);
        
        // 重要なエラーの場合のみユーザーに通知
        if (event.error.name === 'ChunkLoadError' || 
            event.message.includes('Loading chunk')) {
            this.showAlert('リソースの読み込みに失敗しました。ページを再読み込みしてください。', 'warning');
        }
    }
}

// ========================================
// グローバル関数（テンプレートから呼び出し用）
// ========================================

function getScoreBadgeClass(score) {
    if (score >= 80) return 'score-excellent';
    if (score >= 60) return 'score-good';
    if (score >= 40) return 'score-fair';
    if (score >= 0) return 'score-poor';
    return 'score-negative';
}

function selectByType(docType) {
    if (window.app) {
        window.app.selectDocumentsByType(docType);
    }
}

function selectLatest(count) {
    if (window.app) {
        window.app.selectLatestDocuments(count);
    }
}

function selectAll() {
    if (window.app) {
        window.app.selectAllDocuments();
    }
}

function clearSelection() {
    if (window.app) {
        window.app.clearSelection();
    }
}

function retryAnalysis(analysisId) {
    if (window.app) {
        window.app.retryAnalysis(analysisId);
    }
}

// ========================================
// 初期化
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    // アプリケーション初期化
    window.app = new EarningsAnalysisApp();
    
    // チャート初期化
    if (typeof Chart !== 'undefined') {
        window.app.initializeCharts();
    }
    
    // ツールチップ初期化
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    console.log('決算分析システム JavaScript 初期化完了');
});
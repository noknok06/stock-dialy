// ===== 信用倍率タブ用ユーティリティ =====

/**
 * パフォーマンス監視クラス
 * チャート描画やAPI呼び出しのパフォーマンスを追跡
 */
class PerformanceMonitor {
    constructor() {
        this.metrics = new Map();
        this.thresholds = {
            apiCall: 3000,      // API呼び出し：3秒
            chartRender: 1000,  // チャート描画：1秒
            tabSwitch: 300      // タブ切り替え：300ms
        };
    }
    
    start(operation) {
        const startTime = performance.now();
        this.metrics.set(operation, { startTime, endTime: null, duration: null });
        return operation;
    }
    
    end(operation) {
        const metric = this.metrics.get(operation);
        if (!metric) return null;
        
        metric.endTime = performance.now();
        metric.duration = metric.endTime - metric.startTime;
        
        // 閾値チェック
        const threshold = this.thresholds[operation] || 1000;
        if (metric.duration > threshold) {
            console.warn(`⚠️ Performance warning: ${operation} took ${metric.duration.toFixed(2)}ms (threshold: ${threshold}ms)`);
            
            // 必要に応じてメトリクス送信
            this.reportSlowOperation(operation, metric.duration, threshold);
        }
        
        return metric.duration;
    }
    
    reportSlowOperation(operation, duration, threshold) {
        // 本番環境では分析サービスに送信
        if (typeof gtag !== 'undefined') {
            gtag('event', 'performance_warning', {
                event_category: 'margin_tab',
                event_label: operation,
                value: Math.round(duration),
                custom_map: {
                    threshold: threshold
                }
            });
        }
    }
    
    getMetrics() {
        const result = {};
        for (const [operation, metric] of this.metrics) {
            if (metric.duration !== null) {
                result[operation] = metric.duration;
            }
        }
        return result;
    }
    
    clear() {
        this.metrics.clear();
    }
}

/**
 * エラー追跡クラス
 * API エラーやチャート描画エラーを追跡・分類
 */
class ErrorTracker {
    constructor() {
        this.errors = [];
        this.maxErrors = 50; // 最大保存エラー数
        this.errorCounts = new Map();
        
        // グローバルエラーハンドラー設定
        this.setupGlobalHandlers();
    }
    
    setupGlobalHandlers() {
        // 未処理のエラーをキャッチ
        window.addEventListener('error', (e) => {
            if (e.filename && e.filename.includes('margin-tab')) {
                this.track('javascript_error', e.error || e.message, {
                    filename: e.filename,
                    lineno: e.lineno,
                    colno: e.colno
                });
            }
        });
        
        // Promise の rejection をキャッチ
        window.addEventListener('unhandledrejection', (e) => {
            if (e.reason && e.reason.stack && e.reason.stack.includes('margin')) {
                this.track('promise_rejection', e.reason.message || e.reason, {
                    stack: e.reason.stack
                });
            }
        });
    }
    
    track(type, message, metadata = {}) {
        const error = {
            type,
            message: String(message),
            metadata,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            stackTrace: this.getStackTrace()
        };
        
        this.errors.unshift(error);
        
        // 最大数を超えた場合は古いエラーを削除
        if (this.errors.length > this.maxErrors) {
            this.errors.pop();
        }
        
        // エラー回数をカウント
        const errorKey = `${type}:${message}`;
        this.errorCounts.set(errorKey, (this.errorCounts.get(errorKey) || 0) + 1);
        
        // コンソールに出力
        console.error(`🚨 MarginTab Error [${type}]:`, message, metadata);
        
        // 重要なエラーは即座に報告
        if (this.isCriticalError(type, message)) {
            this.reportError(error);
        }
        
        return error;
    }
    
    isCriticalError(type, message) {
        const criticalPatterns = [
            'network',
            'api_failure',
            'chart_render_failure',
            'data_corruption'
        ];
        
        return criticalPatterns.some(pattern => 
            type.includes(pattern) || message.toLowerCase().includes(pattern)
        );
    }
    
    reportError(error) {
        // 本番環境では監視サービスに送信
        if (typeof gtag !== 'undefined') {
            gtag('event', 'error', {
                event_category: 'margin_tab',
                event_label: error.type,
                description: error.message
            });
        }
        
        // 開発環境では詳細をコンソールに表示
        if (window.location.hostname === 'localhost' || window.location.hostname.includes('dev')) {
            console.group('🚨 Critical Error Details');
            console.error('Type:', error.type);
            console.error('Message:', error.message);
            console.error('Metadata:', error.metadata);
            console.error('Stack:', error.stackTrace);
            console.groupEnd();
        }
    }
    
    getStackTrace() {
        try {
            throw new Error();
        } catch (e) {
            return e.stack;
        }
    }
    
    getErrors(type = null) {
        if (type) {
            return this.errors.filter(error => error.type === type);
        }
        return [...this.errors];
    }
    
    getErrorSummary() {
        const summary = {};
        for (const [key, count] of this.errorCounts) {
            const [type] = key.split(':', 1);
            summary[type] = (summary[type] || 0) + count;
        }
        return summary;
    }
    
    clear() {
        this.errors = [];
        this.errorCounts.clear();
    }
}

/**
 * ネットワーク監視クラス
 * API呼び出しの成功率と応答時間を監視
 */
class NetworkMonitor {
    constructor() {
        this.requests = [];
        this.maxRequests = 100;
        this.setupInterceptors();
    }
    
    setupInterceptors() {
        // fetch API をインターセプト
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const [url, options] = args;
            
            // マージンタブ関連のAPIのみ監視
            if (typeof url === 'string' && url.includes('/api/margin')) {
                return this.monitoredFetch(originalFetch, ...args);
            }
            
            return originalFetch(...args);
        };
    }
    
    async monitoredFetch(originalFetch, ...args) {
        const [url] = args;
        const startTime = performance.now();
        
        try {
            const response = await originalFetch(...args);
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            this.recordRequest({
                url,
                method: args[1]?.method || 'GET',
                status: response.status,
                duration,
                success: response.ok,
                timestamp: new Date().toISOString()
            });
            
            // 遅いリクエストを警告
            if (duration > 5000) {
                console.warn(`🐌 Slow API request: ${url} took ${duration.toFixed(0)}ms`);
            }
            
            return response;
            
        } catch (error) {
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            this.recordRequest({
                url,
                method: args[1]?.method || 'GET',
                status: 0,
                duration,
                success: false,
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            // エラートラッカーに報告
            if (window.marginErrorTracker) {
                window.marginErrorTracker.track('api_failure', `Failed to fetch ${url}: ${error.message}`, {
                    url,
                    duration
                });
            }
            
            throw error;
        }
    }
    
    recordRequest(request) {
        this.requests.unshift(request);
        
        if (this.requests.length > this.maxRequests) {
            this.requests.pop();
        }
    }
    
    getStats() {
        if (this.requests.length === 0) {
            return null;
        }
        
        const successful = this.requests.filter(r => r.success).length;
        const failed = this.requests.length - successful;
        const avgDuration = this.requests.reduce((sum, r) => sum + r.duration, 0) / this.requests.length;
        
        return {
            total: this.requests.length,
            successful,
            failed,
            successRate: (successful / this.requests.length) * 100,
            averageDuration: avgDuration,
            slowRequests: this.requests.filter(r => r.duration > 3000).length
        };
    }
    
    getRecentRequests(count = 10) {
        return this.requests.slice(0, count);
    }
}

/**
 * デバイス情報収集クラス
 * パフォーマンス問題の原因分析用
 */
class DeviceProfiler {
    constructor() {
        this.profile = this.generateProfile();
    }
    
    generateProfile() {
        const profile = {
            // 基本情報
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            
            // 画面情報
            screenWidth: screen.width,
            screenHeight: screen.height,
            screenDensity: window.devicePixelRatio || 1,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            
            // デバイス判定
            isMobile: this.isMobileDevice(),
            isTablet: this.isTabletDevice(),
            isTouch: 'ontouchstart' in window,
            
            // ネットワーク情報
            connection: this.getConnectionInfo(),
            
            // パフォーマンス指標
            memory: this.getMemoryInfo(),
            
            // ブラウザ機能
            supports: {
                webGL: this.supportsWebGL(),
                canvas: !!document.createElement('canvas').getContext,
                localStorage: this.supportsLocalStorage(),
                webWorkers: typeof Worker !== 'undefined',
                intersectionObserver: 'IntersectionObserver' in window
            }
        };
        
        return profile;
    }
    
    isMobileDevice() {
        return /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               window.innerWidth <= 768;
    }
    
    isTabletDevice() {
        return /iPad|Android(?!.*Mobile)/i.test(navigator.userAgent) ||
               (window.innerWidth > 768 && window.innerWidth <= 1024);
    }
    
    getConnectionInfo() {
        if ('connection' in navigator) {
            const conn = navigator.connection;
            return {
                effectiveType: conn.effectiveType,
                downlink: conn.downlink,
                rtt: conn.rtt,
                saveData: conn.saveData
            };
        }
        return null;
    }
    
    getMemoryInfo() {
        if ('memory' in performance) {
            return {
                jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
                totalJSHeapSize: performance.memory.totalJSHeapSize,
                usedJSHeapSize: performance.memory.usedJSHeapSize
            };
        }
        return null;
    }
    
    supportsWebGL() {
        try {
            const canvas = document.createElement('canvas');
            return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
        } catch (e) {
            return false;
        }
    }
    
    supportsLocalStorage() {
        try {
            localStorage.setItem('test', 'test');
            localStorage.removeItem('test');
            return true;
        } catch (e) {
            return false;
        }
    }
    
    getProfile() {
        return { ...this.profile };
    }
    
    isLowEndDevice() {
        const profile = this.profile;
        
        // メモリが少ない
        if (profile.memory && profile.memory.jsHeapSizeLimit < 1000000000) { // 1GB未満
            return true;
        }
        
        // 古いデバイス（推定）
        if (profile.screenDensity < 2 && profile.screenWidth < 1200) {
            return true;
        }
        
        // 低速ネットワーク
        if (profile.connection && profile.connection.effectiveType === '2g') {
            return true;
        }
        
        return false;
    }
}

/**
 * ユーザビリティ監視クラス
 * ユーザーの操作パターンを分析してUX改善のインサイトを収集
 */
class UsabilityMonitor {
    constructor() {
        this.interactions = [];
        this.maxInteractions = 200;
        this.setupEventListeners();
        this.startTime = Date.now();
    }
    
    setupEventListeners() {
        // タブ切り替えの追跡
        document.addEventListener('click', (e) => {
            if (e.target.closest('#marginTabsNav .nav-link')) {
                const tabId = e.target.closest('.nav-link').getAttribute('data-bs-target');
                this.recordInteraction('tab_switch', { target: tabId });
            }
        });
        
        // チャート期間変更の追跡
        document.addEventListener('change', (e) => {
            if (e.target.name === 'chartPeriod') {
                this.recordInteraction('chart_period_change', { period: e.target.value });
            }
        });
        
        // 比較銘柄追加の追跡
        document.addEventListener('click', (e) => {
            if (e.target.id === 'addCompareBtn') {
                const input = document.getElementById('compareSymbolInput');
                this.recordInteraction('compare_symbol_add', { 
                    symbolLength: input ? input.value.length : 0 
                });
            }
        });
        
        // エラー発生時の追跡
        document.addEventListener('error', (e) => {
            this.recordInteraction('error_encountered', {
                source: e.target.tagName,
                message: e.message
            });
        });
    }
    
    recordInteraction(type, data = {}) {
        const interaction = {
            type,
            data,
            timestamp: Date.now(),
            sessionTime: Date.now() - this.startTime,
            url: window.location.href,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        };
        
        this.interactions.unshift(interaction);
        
        if (this.interactions.length > this.maxInteractions) {
            this.interactions.pop();
        }
    }
    
    getUsageStats() {
        const stats = {
            totalInteractions: this.interactions.length,
            sessionDuration: Date.now() - this.startTime,
            interactionTypes: {},
            averageTimePerInteraction: 0
        };
        
        // 操作種別ごとのカウント
        this.interactions.forEach(interaction => {
            stats.interactionTypes[interaction.type] = 
                (stats.interactionTypes[interaction.type] || 0) + 1;
        });
        
        // 平均操作間隔
        if (this.interactions.length > 1) {
            const intervals = [];
            for (let i = 0; i < this.interactions.length - 1; i++) {
                intervals.push(this.interactions[i].timestamp - this.interactions[i + 1].timestamp);
            }
            stats.averageTimePerInteraction = intervals.reduce((a, b) => a + b, 0) / intervals.length;
        }
        
        return stats;
    }
    
    getMostUsedFeatures(limit = 5) {
        const counts = {};
        this.interactions.forEach(interaction => {
            counts[interaction.type] = (counts[interaction.type] || 0) + 1;
        });
        
        return Object.entries(counts)
            .sort(([,a], [,b]) => b - a)
            .slice(0, limit)
            .map(([feature, count]) => ({ feature, count }));
    }
    
    getSessionReport() {
        return {
            duration: Date.now() - this.startTime,
            interactions: this.getUsageStats(),
            mostUsed: this.getMostUsedFeatures(),
            deviceProfile: window.marginDeviceProfiler?.getProfile() || null,
            performance: window.marginPerformanceMonitor?.getMetrics() || null,
            errors: window.marginErrorTracker?.getErrorSummary() || null
        };
    }
}

// グローバルインスタンスの作成
window.marginPerformanceMonitor = new PerformanceMonitor();
window.marginErrorTracker = new ErrorTracker();
window.marginNetworkMonitor = new NetworkMonitor();
window.marginDeviceProfiler = new DeviceProfiler();
window.marginUsabilityMonitor = new UsabilityMonitor();

// デバッグ用のグローバル関数
window.getMarginDebugInfo = () => {
    return {
        performance: window.marginPerformanceMonitor.getMetrics(),
        errors: window.marginErrorTracker.getErrorSummary(),
        network: window.marginNetworkMonitor.getStats(),
        device: window.marginDeviceProfiler.getProfile(),
        usability: window.marginUsabilityMonitor.getUsageStats()
    };
};

// 定期的なヘルスチェック（5分間隔）
setInterval(() => {
    const stats = window.marginNetworkMonitor.getStats();
    if (stats && stats.successRate < 80) {
        console.warn('🚨 Network success rate is low:', stats.successRate.toFixed(1) + '%');
    }
}, 5 * 60 * 1000);

console.log('✅ Margin tab utilities loaded successfully');
console.log('📱 Device profile:', window.marginDeviceProfiler.getProfile());

// 低スペックデバイスの場合は警告
if (window.marginDeviceProfiler.isLowEndDevice()) {
    console.warn('⚡ Low-end device detected. Performance optimizations will be applied.');
}
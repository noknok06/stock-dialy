// static/js/common-utils.js

/**
 * Cookieから値を取得
 * @param {string} name - Cookie名
 * @returns {string|null} Cookie値
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * CSRFトークンを複数の方法で取得
 * @returns {string|null} CSRFトークン
 */
function getCSRFToken() {
    // 方法1: Cookieから取得
    let token = getCookie('csrftoken');
    
    // 方法2: hiddenフィールドから取得
    if (!token) {
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) {
            token = csrfInput.value;
            console.log('✅ CSRFトークンをhiddenフィールドから取得');
        }
    }
    
    // 方法3: metaタグから取得
    if (!token) {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            token = csrfMeta.content;
            console.log('✅ CSRFトークンをmetaタグから取得');
        }
    }
    
    if (!token) {
        console.warn('⚠️ CSRFトークンが見つかりません');
    } else {
        console.log('✅ CSRFトークンが見つかりました');
    }
    
    return token;
}

/**
 * トースト通知を表示（showToast関数がない場合はalertにフォールバック）
 * @param {string} message - 表示メッセージ
 * @param {string} type - メッセージタイプ (success, danger, warning, info)
 */
function showToastOrAlert(message, type) {
    if (typeof showToast === 'function') {
        showToast(message, type);
    } else {
        alert(message);
    }
}

/**
 * 日付をフォーマット（YYYY年MM月DD日形式）
 * @param {Date|string} date - 日付オブジェクトまたはISO文字列
 * @returns {string} フォーマット済み日付文字列
 */
function formatDateJP(date) {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

/**
 * 日時をフォーマット（YYYY年MM月DD日 HH:MM形式）
 * @param {Date|string} datetime - 日時オブジェクトまたはISO文字列
 * @returns {string} フォーマット済み日時文字列
 */
function formatDateTimeJP(datetime) {
    const d = typeof datetime === 'string' ? new Date(datetime) : datetime;
    return d.toLocaleString('ja-JP', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * 数値をカンマ区切りにフォーマット
 * @param {number} num - 数値
 * @param {number} decimals - 小数点以下の桁数（デフォルト: 0）
 * @returns {string} フォーマット済み数値文字列
 */
function formatNumber(num, decimals = 0) {
    if (num === null || num === undefined) return '-';
    return Number(num).toLocaleString('ja-JP', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// グローバルスコープに公開
window.getCookie = getCookie;
window.getCSRFToken = getCSRFToken;
window.showToastOrAlert = showToastOrAlert;
window.formatDateJP = formatDateJP;
window.formatDateTimeJP = formatDateTimeJP;
window.formatNumber = formatNumber;
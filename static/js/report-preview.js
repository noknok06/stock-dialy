// static/js/report-preview.js

// レポートデータをプレビュー表示する関数
function setPreviewData(data) {
    // console.log('プレビューデータを設定:', data);
    
    // 要素のテキスト設定用ヘルパー関数
    function setElementText(id, value) {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = value || '';
      }
    }
    
    // 要素のHTML設定用ヘルパー関数
    function setElementHTML(id, html) {
      const element = document.getElementById(id);
      if (element) {
        element.innerHTML = html || '';
      }
    }
    
    try {
      // プレビュー用のHTMLを作成
      const previewHTML = `
        <div class="card">
          <div class="card-header bg-white">
            <div class="d-flex align-items-center">
              <div style="width:48px;height:48px;border-radius:12px;background-color:${data.companyColor || '#3B82F6'};display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;">
                ${data.companyAbbr || ''}
              </div>
              <div class="ms-3">
                <h5 class="card-title mb-0 fw-bold">${data.companyName || ''} (${data.companyCode || ''})</h5>
                <p class="text-muted small mb-0">${data.fiscalPeriod || ''}</p>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <span class="badge ${parseFloat(data.overallRating) >= 7 ? 'bg-success' : parseFloat(data.overallRating) >= 4 ? 'bg-warning' : 'bg-danger'}">
                評価: ${data.overallRating || '0'}
              </span>
              <span class="badge bg-light">${data.achievementBadge || ''}</span>
            </div>
            
            <p class="mb-3">${data.overallSummary || ''}</p>
            
            <div class="p-3 rounded bg-light">
              <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-bold">投資判断:</span>
                <span class="badge ${data.recommendationText === '買い推奨' ? 'bg-success' : data.recommendationText === '売り推奨' ? 'bg-danger' : 'bg-warning'}">
                  ${data.recommendationText || ''}
                </span>
              </div>
              <div class="text-center">
                <span style="color:#f59e0b;font-size:1.25rem;">${data.starRating || '★★★☆☆'}</span>
              </div>
            </div>
            
            <hr />
            
            <h6 class="fw-bold mt-4">ポジティブ要素</h6>
            <ul id="preview-positive-points" class="mb-4">
              ${(data.positivePoints || []).map(point => `<li>${point}</li>`).join('')}
            </ul>
            
            <h6 class="fw-bold">注意すべき要素</h6>
            <ul id="preview-negative-points">
              ${(data.negativePoints || []).map(point => `<li>${point}</li>`).join('')}
            </ul>
          </div>
          <div class="card-footer bg-white text-center text-muted">
            プレビュー表示
          </div>
        </div>
      `;
      
      // プレビューコンテナにHTMLを設定
      const previewContainer = document.getElementById('preview-container');
      if (previewContainer) {
        previewContainer.innerHTML = previewHTML;
      }
      
      // console.log('プレビュー表示完了');
    } catch (error) {
      console.error('プレビュー表示中にエラーが発生しました:', error);
    }
  }
// プレビュー用の簡易実装
function setPreviewData(data) {
    console.log('プレビューデータ:', data);
    
    // プレビューコンテナを取得
    const previewContainer = document.getElementById('preview-container');
    if (!previewContainer) {
      console.error('プレビューコンテナが見つかりません');
      return;
    }
    
    // ポジティブポイントHTML生成
    let positivePointsHTML = '';
    if (data.positivePoints && Array.isArray(data.positivePoints)) {
      positivePointsHTML = data.positivePoints.map(point => `<li>${point}</li>`).join('');
    }
    
    // ネガティブポイントHTML生成
    let negativePointsHTML = '';
    if (data.negativePoints && Array.isArray(data.negativePoints)) {
      negativePointsHTML = data.negativePoints.map(point => `<li>${point}</li>`).join('');
    }
    
    // レーティングの色を決定
    const getRatingColor = (rating) => {
      rating = parseFloat(rating) || 0;
      if (rating >= 7) return 'success';
      if (rating >= 4) return 'warning';
      return 'danger';
    };
    
    const ratingColor = getRatingColor(data.overallRating);
    
    // プレビュー内容を生成
    let previewHTML = `
      <div class="p-4">
        <div class="mb-4 d-flex justify-content-between">
          <div class="d-flex align-items-center">
            <div style="width: 60px; height: 60px; background-color: ${data.companyColor || '#3B82F6'}; color: white; display: flex; align-items: center; justify-content: center; border-radius: 12px; font-weight: bold; margin-right: 15px;">
              ${data.companyAbbr || ''}
            </div>
            <div>
              <h3 class="mb-0">${data.companyName || ''} <small class="text-muted">${data.companyCode || ''}</small></h3>
              <p class="text-muted mb-0">${data.fiscalPeriod || ''}</p>
            </div>
          </div>
          <div class="text-end">
            <span class="badge bg-primary mb-2 d-inline-block">${data.achievementBadge || ''}</span>
            <div class="d-flex align-items-baseline justify-content-end">
              <span class="h3 text-${ratingColor} fw-bold mb-0">${data.overallRating || '0'}</span>
              <span class="text-muted ms-1">/10</span>
            </div>
          </div>
        </div>
        
        <div class="card mb-4">
          <div class="card-header bg-light">
            <h4 class="mb-0">総合評価</h4>
          </div>
          <div class="card-body">
            <div class="mb-2">${data.overallRatingText || ''}</div>
            <p>${data.overallSummary || ''}</p>
            
            <div class="p-3 bg-light rounded mb-3">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <h5 class="mb-0">投資判断</h5>
                <span class="badge ${data.recommendationText && data.recommendationText.includes('買い') ? 'bg-success' : data.recommendationText && data.recommendationText.includes('売り') ? 'bg-danger' : 'bg-warning'}">
                  ${data.recommendationText || '未評価'}
                </span>
              </div>
              <div class="text-center text-warning mb-2">${data.starRating || ''}</div>
              <p class="mb-0">${data.investmentReason || ''}</p>
            </div>
          </div>
        </div>
        
        <div class="row mb-4">
          <div class="col-md-6 mb-3">
            <div class="card h-100">
              <div class="card-header bg-success bg-opacity-10">
                <h5 class="mb-0 text-success">ポジティブ要素</h5>
              </div>
              <div class="card-body">
                <ul class="mb-0">
                  ${positivePointsHTML}
                </ul>
              </div>
            </div>
          </div>
          <div class="col-md-6 mb-3">
            <div class="card h-100">
              <div class="card-header bg-danger bg-opacity-10">
                <h5 class="mb-0 text-danger">注意すべき要素</h5>
              </div>
              <div class="card-body">
                <ul class="mb-0">
                  ${negativePointsHTML}
                </ul>
              </div>
            </div>
          </div>
        </div>
        
        <div class="mb-4">
          <h4>業績ハイライト</h4>
          <div class="row">
            <div class="col-md-3 mb-3">
              <div class="card">
                <div class="card-body">
                  <h6 class="text-muted">当期純利益</h6>
                  <div class="h5">${data.netIncome || ''}</div>
                  <div class="small ${data.netIncomeChange && data.netIncomeChange.includes('-') ? 'text-danger' : 'text-success'}">
                    ${data.netIncomeChange || ''}
                  </div>
                </div>
              </div>
            </div>
            <div class="col-md-3 mb-3">
              <div class="card">
                <div class="card-body">
                  <h6 class="text-muted">EPS</h6>
                  <div class="h5">${data.eps || ''}</div>
                  <div class="small ${data.epsChange && data.epsChange.includes('-') ? 'text-danger' : 'text-success'}">
                    ${data.epsChange || ''}
                  </div>
                </div>
              </div>
            </div>
            <div class="col-md-3 mb-3">
              <div class="card">
                <div class="card-body">
                  <h6 class="text-muted">配当</h6>
                  <div class="h5">${data.dividend || ''}</div>
                  <div class="small ${data.dividendChange && data.dividendChange.includes('-') ? 'text-danger' : 'text-success'}">
                    ${data.dividendChange || ''}
                  </div>
                </div>
              </div>
            </div>
            <div class="col-md-3 mb-3">
              <div class="card">
                <div class="card-body">
                  <h6 class="text-muted">ROE</h6>
                  <div class="h5">${data.roe || ''}</div>
                  <div class="small ${data.roeChange && data.roeChange.includes('-') ? 'text-danger' : 'text-success'}">
                    ${data.roeChange || ''}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="alert alert-info">
          <strong>注意:</strong> これは簡易的なプレビューです。実際の表示にはより詳細なデータが必要な場合があります。
        </div>
      </div>
    `;
    
    // プレビューを表示
    previewContainer.innerHTML = previewHTML;
  }
// static/js/ad_preview.js
function openAdPreview(adUnitId) {
    // ポップアップウィンドウを開く
    var popupWindow = window.open('', 'AdPreview', 'width=800,height=600,resizable=yes');
    
    // APIからデータを取得
    fetch('/ads/api/preview/' + adUnitId + '/')
      .then(response => response.json())
      .then(data => {
        // ポップアップにプレビューコンテンツを表示
        popupWindow.document.write(`
          <!DOCTYPE html>
          <html>
          <head>
            <title>広告プレビュー - ${data.name}</title>
            <style>
              body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
              h1 { font-size: 18px; margin-bottom: 20px; }
              .preview-box { 
                padding: 20px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-bottom: 20px;
              }
              .code-box {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                padding: 15px;
                border-radius: 4px;
                font-family: monospace;
                white-space: pre-wrap;
                margin-bottom: 20px;
              }
              .info-table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
              }
              .info-table th, .info-table td {
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
              }
              .info-table th {
                background-color: #f2f2f2;
                font-weight: bold;
              }
            </style>
          </head>
          <body>
            <h1>${data.name} - 広告プレビュー</h1>
            
            <h2>広告情報</h2>
            <table class="info-table">
              <tr>
                <th>配置場所</th>
                <td>${data.placement}</td>
              </tr>
              <tr>
                <th>クライアントID</th>
                <td>${data.ad_client}</td>
              </tr>
              <tr>
                <th>スロットID</th>
                <td>${data.ad_slot}</td>
              </tr>
              <tr>
                <th>フォーマット</th>
                <td>${data.ad_format}${data.is_fluid ? ' (fluid)' : ''}</td>
              </tr>
              ${data.template_type ? `<tr><th>テンプレートタイプ</th><td>${data.template_type}</td></tr>` : ''}
              ${data.ad_layout ? `<tr><th>レイアウト</th><td>${data.ad_layout}</td></tr>` : ''}
              ${data.ad_layout_key ? `<tr><th>レイアウトキー</th><td>${data.ad_layout_key}</td></tr>` : ''}
            </table>
            
            <h2>HTMLコード</h2>
            <div class="code-box">${data.html_code}</div>
            
            <h2>表示イメージ</h2>
            <div class="preview-box">
              <div style="border: 2px dashed #4CAF50; padding: 15px; text-align: center;">
                <strong>広告サイズ: </strong>
                ${data.width && data.height ? `${data.width}×${data.height}px` : 'レスポンシブ'}<br>
                <div style="margin-top: 15px; padding: 30px 15px; background: #fff; border: 1px solid #ddd;">
                  <strong>ここに広告が表示されます</strong><br>
                  <small>(実際の広告は表示されません)</small>
                </div>
              </div>
            </div>
          </body>
          </html>
        `);
      })
      .catch(error => {
        popupWindow.document.write(`
          <html><body>
            <h1>エラー</h1>
            <p>広告情報の取得中にエラーが発生しました。</p>
            <p>${error}</p>
          </body></html>
        `);
      });
  }
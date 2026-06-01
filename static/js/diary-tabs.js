// タブ切り替え処理
document.addEventListener('click', function(e) {
  const tabBtn = e.target.closest('.tab-btn');
  if (!tabBtn) return;

  const targetId = tabBtn.getAttribute('data-tab');
  const article = tabBtn.closest('.diary-article');
  const diaryId = tabBtn.getAttribute('data-diary-id');
  const isLoaded = tabBtn.getAttribute('data-loaded') === 'true';

  // すべてのタブとパネルを非アクティブ化
  article.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
    btn.setAttribute('aria-selected', 'false');
  });

  article.querySelectorAll('.tab-panel').forEach(panel => {
    panel.style.display = 'none';
  });

  // 選択されたタブとパネルをアクティブ化
  tabBtn.classList.add('active');
  tabBtn.setAttribute('aria-selected', 'true');

  // 取引・継続タブでは画像を折りたたんで表示領域を最大化
  const figure = article.querySelector('.diary-figure');
  if (figure) {
    const isContentTab = targetId.includes('notes') || targetId.includes('transactions');
    figure.classList.toggle('figure-collapsed', isContentTab);
    // モバイルでは CSS max-height トランジションが
    // overflow:hidden 親との組み合わせで不安定なため display で確実に制御
    if (window.matchMedia('(max-width: 767px)').matches) {
      figure.style.display = isContentTab ? 'none' : '';
    }
  }

  // すべてのパネルのスクロールクラスをリセット
  article.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.remove('panel-scrollable');
  });

  const targetPanel = document.getElementById(targetId);
  if (targetPanel) {
    targetPanel.style.display = 'block';

    // 継続・取引タブではパネルをスクロール可能に
    const isContentTab = targetId.includes('notes') || targetId.includes('transactions');
    if (isContentTab) {
      targetPanel.classList.add('panel-scrollable');
    }

    // 遅延ロード（HTMXが利用可能な場合）
    if (!isLoaded && diaryId && typeof htmx !== 'undefined') {
      const tabType = targetId.includes('notes') ? 'notes' : 'details';

      htmx.ajax('GET', `/stockdiary/tab-content/${diaryId}/${tabType}/`, {
        target: `#${targetId}`,
        swap: 'innerHTML'
      }).then(() => {
        tabBtn.setAttribute('data-loaded', 'true');
      });
    }
  }
});
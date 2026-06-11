/**
 * EasyMDE のツールバーを Bootstrap Icons で構成するヘルパー。
 *
 * 本アプリは FontAwesome を読み込んでいないため、EasyMDE デフォルトの
 * 文字列指定ツールバー（fa クラス前提）ではアイコンが表示されず
 * 空ボタンの列になる。読み込み済みの Bootstrap Icons を icon プロパティ
 * （カスタムHTML）で指定して置き換える。
 *
 * 使い方:
 *   toolbar: easymdeBiToolbar(['bold', 'italic', '|', 'preview'])
 */
function easymdeBiToolbar(names) {
  var defs = {
    'bold':           { action: EasyMDE.toggleBold,          bi: 'bi-type-bold',         title: '太字' },
    'italic':         { action: EasyMDE.toggleItalic,        bi: 'bi-type-italic',       title: '斜体' },
    'heading':        { action: EasyMDE.toggleHeadingSmaller, bi: 'bi-type-h2',          title: '見出し' },
    'unordered-list': { action: EasyMDE.toggleUnorderedList, bi: 'bi-list-ul',           title: '箇条書き' },
    'ordered-list':   { action: EasyMDE.toggleOrderedList,   bi: 'bi-list-ol',           title: '番号付きリスト' },
    'link':           { action: EasyMDE.drawLink,            bi: 'bi-link-45deg',        title: 'リンク' },
    'quote':          { action: EasyMDE.toggleBlockquote,    bi: 'bi-quote',             title: '引用' },
    'code':           { action: EasyMDE.toggleCodeBlock,     bi: 'bi-code',              title: 'コード' },
    'preview':        { action: EasyMDE.togglePreview,       bi: 'bi-eye',               title: 'プレビュー', noDisable: true },
    'side-by-side':   { action: EasyMDE.toggleSideBySide,    bi: 'bi-layout-split',      title: '分割表示', noDisable: true, noMobile: true },
    'fullscreen':     { action: EasyMDE.toggleFullScreen,    bi: 'bi-arrows-fullscreen', title: '全画面', noDisable: true, noMobile: true },
    'guide':          { action: 'https://www.markdownguide.org/basic-syntax/', bi: 'bi-question-circle', title: 'Markdownガイド' },
  };

  return names.map(function (n) {
    if (n === '|') return '|';
    var d = defs[n];
    if (!d) return n; // 未定義名はそのまま渡す（EasyMDE側のデフォルト動作）
    var item = {
      name: n,
      action: d.action,
      icon: '<i class="bi ' + d.bi + '"></i>',
      title: d.title,
    };
    if (d.noDisable) item.noDisable = true;
    if (d.noMobile) item.noMobile = true;
    return item;
  });
}

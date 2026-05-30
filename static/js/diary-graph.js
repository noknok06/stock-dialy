/**
 * diary-graph.js  v2
 * 日記関連グラフ可視化モジュール
 * D3.js v7 を使用した force-directed graph
 *
 * 新機能:
 *   - 接続モード: manual / tag / sector / hashtag
 *   - タグハブノード（六角形）・業種ハブノード（角丸四角）・@ハッシュタグノード（三角）
 *   - グラフ内検索（銘柄名・コードでハイライト）
 *   - カラーモード: status / sector / profit
 *   - クリック時サイドパネル
 */
(function () {
  'use strict';

  // ==============================
  // 定数
  // ==============================
  const NODE_RADIUS_MIN   = 8;
  const NODE_RADIUS_MAX   = 26;
  const HUB_RADIUS_MIN    = 14;
  const HUB_RADIUS_MAX    = 36;

  const FORCE_LINK_DISTANCE_DEFAULT  = 120;
  const FORCE_LINK_DISTANCE_HUB      = 160;
  const FORCE_CHARGE       = -320;
  const FORCE_COLLISION_MULT = 1.6;

  // エッジ色
  const EDGE_COLOR = {
    manual:  '#94a3b8',
    tag:     '#a78bfa',
    sector:  '#fb923c',
    hashtag: '#a78bfa',  // タグと統合（同色）
    mention: '#f59e0b',
  };

  // ハブノード色
  const HUB_COLOR = {
    tag:     '#7c3aed',
    sector:  '#d97706',
    hashtag: '#7c3aed',  // タグと統合（同色）
  };

  // セクター色パレット
  const SECTOR_PALETTE = [
    '#6366f1','#8b5cf6','#ec4899','#f43f5e','#f97316',
    '#eab308','#22c55e','#14b8a6','#06b6d4','#3b82f6',
    '#84cc16','#a855f7',
  ];

  // ==============================
  // DiaryGraph クラス
  // ==============================
  class DiaryGraph {
    constructor(config) {
      this.apiUrl    = config.apiUrl;
      this.svgEl     = document.getElementById('diary-graph-svg');
      this.loadingEl = document.getElementById('graph-loading');
      this.emptyEl   = document.getElementById('graph-empty');
      this.tooltipEl = document.getElementById('graph-tooltip');
      this.statsEl   = document.getElementById('graph-stats');
      this.sidePanel = document.getElementById('graph-side-panel');
      this.sidePanelBody  = document.getElementById('side-panel-body');
      this.sidePanelTitle = document.getElementById('side-panel-title');

      this.allNodes  = [];
      this.allEdges  = [];
      this.simulation = null;
      this.svg        = null;
      this.gRoot      = null;
      this.zoomBehavior = null;

      this.currentStatus    = 'all';
      this.currentTag       = '';
      this.currentEdgeModes = new Set(config.defaultEdgeModes || ['tag']);
      this.currentColorMode = 'status';
      this.showLabels       = true;
      this.searchQuery      = '';
      this.sectorColorMap   = {};
      this.focusNodeId      = null;
      this.focusNeighborIds = new Set();
      this._searchMatchIds  = [];

      this._init();
    }

    // ==============================
    // 初期化
    // ==============================
    _init() {
      this._bindControls();
      this._syncEdgeModeCheckboxes();
      this._fetchAndRender();
    }

    _syncEdgeModeCheckboxes() {
      document.querySelectorAll('.edge-mode-check').forEach(cb => {
        cb.checked = this.currentEdgeModes.has(cb.value);
      });
      const unifiedTagCb = document.getElementById('mode-tag-unified');
      if (unifiedTagCb) {
        unifiedTagCb.checked = this.currentEdgeModes.has('tag') || this.currentEdgeModes.has('hashtag');
      }
    }

    // ==============================
    // コントロールイベントバインド
    // ==============================
    _bindControls() {
      document.querySelectorAll('input[name="statusFilter"]').forEach(radio => {
        radio.addEventListener('change', e => {
          this.currentStatus = e.target.value;
          this._fetchAndRender();
        });
      });

      const tagSel = document.getElementById('tagFilter');
      if (tagSel) {
        tagSel.addEventListener('change', e => {
          this.currentTag = e.target.value;
          this._fetchAndRender();
        });
      }

      // タグ統合ボタン（tag + hashtag を同時制御）
      const unifiedTagCb = document.getElementById('mode-tag-unified');
      if (unifiedTagCb) {
        unifiedTagCb.addEventListener('change', () => {
          if (unifiedTagCb.checked) {
            this.currentEdgeModes.add('tag');
            this.currentEdgeModes.add('hashtag');
          } else {
            const otherModes = ['manual', 'sector', 'mention'];
            const hasOther = otherModes.some(m => this.currentEdgeModes.has(m));
            if (!hasOther) { unifiedTagCb.checked = true; return; }
            this.currentEdgeModes.delete('tag');
            this.currentEdgeModes.delete('hashtag');
          }
          this._updateLegend();
          this._fetchAndRender();
        });
      }

      // その他のエッジモード（手動・業種・コード参照）
      document.querySelectorAll('.edge-mode-check').forEach(cb => {
        cb.addEventListener('change', () => {
          const checked = [...document.querySelectorAll('.edge-mode-check')].filter(c => c.checked);
          const tagUnifiedOn = unifiedTagCb && unifiedTagCb.checked;
          if (checked.length === 0 && !tagUnifiedOn) {
            cb.checked = true;
            return;
          }
          this.currentEdgeModes = new Set(checked.map(c => c.value));
          if (tagUnifiedOn) {
            this.currentEdgeModes.add('tag');
            this.currentEdgeModes.add('hashtag');
          }
          this._updateLegend();
          this._fetchAndRender();
        });
      });

      const searchInput = document.getElementById('graphSearch');
      if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', e => {
          clearTimeout(debounceTimer);
          debounceTimer = setTimeout(() => {
            this.searchQuery = e.target.value.trim().toLowerCase();
            this._applySearch();
          }, 200);
        });
      }

      const searchClear = document.getElementById('graphSearchClear');
      if (searchClear) {
        searchClear.addEventListener('click', () => {
          const inp = document.getElementById('graphSearch');
          if (inp) inp.value = '';
          this.searchQuery = '';
          this._applySearch();
        });
      }

      const colorSel = document.getElementById('colorModeSelect');
      if (colorSel) {
        colorSel.addEventListener('change', e => {
          this.currentColorMode = e.target.value;
          this._applyColorMode();
        });
      }

      const labelToggle = document.getElementById('showLabels');
      if (labelToggle) {
        labelToggle.addEventListener('change', e => {
          this.showLabels = e.target.checked;
          this._toggleLabels();
        });
      }

      const resetBtn = document.getElementById('resetZoom');
      if (resetBtn) {
        resetBtn.addEventListener('click', () => this._resetZoom());
      }

      const closeBtn = document.getElementById('side-panel-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => this._closeSidePanel());
      }

      const fsBtn = document.getElementById('toggleFullscreen');
      if (fsBtn) {
        fsBtn.addEventListener('click', () => this._toggleFullscreen());
      }
      const exitFsBtn = document.getElementById('exitFullscreen');
      if (exitFsBtn) {
        exitFsBtn.addEventListener('click', () => this._toggleFullscreen(false));
      }
      document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
          if (this._isFullscreen) this._toggleFullscreen(false);
          if (this.focusNodeId) this._exitFocusMode();
        }
      });

      const focusExitBtn = document.getElementById('focus-banner-exit');
      if (focusExitBtn) {
        focusExitBtn.addEventListener('click', () => this._exitFocusMode());
      }

      const searchFocusBtn = document.getElementById('search-focus-btn');
      if (searchFocusBtn) {
        searchFocusBtn.addEventListener('click', () => {
          if (this._searchMatchIds && this._searchMatchIds.length > 0) {
            const ids = [...this._searchMatchIds];
            const inp = document.getElementById('graphSearch');
            if (inp) inp.value = '';
            this.searchQuery = '';
            this._applySearch();
            this._enterMultiFocusMode(ids);
          }
        });
      }
      // ウィンドウリサイズ時（端末回転など）はセンター追従のみ。手動 zoom/pan は維持
      window.addEventListener('resize', () => {
        if (this._resizeTimer) clearTimeout(this._resizeTimer);
        this._resizeTimer = setTimeout(() => this._handleResize(false), 150);
      });
    }

    // ==============================
    // データ取得 → 描画
    // ==============================
    async _fetchAndRender() {
      this._showLoading();
      this._closeSidePanel();
      this.focusNodeId = null;
      this.focusNeighborIds = new Set();
      this._hideFocusBanner();

      const params = new URLSearchParams();
      if (this.currentStatus && this.currentStatus !== 'all') {
        params.set('status', this.currentStatus);
      }
      if (this.currentTag) {
        params.set('tag', this.currentTag);
      }
      params.set('edge_modes', [...this.currentEdgeModes].join(','));

      try {
        const resp = await fetch(`${this.apiUrl}?${params.toString()}`, {
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        this.allNodes = data.nodes || [];
        this.allEdges = data.edges || [];

        // 孤立ノード（どのエッジにも接続していない）を除外
        const connectedIds = new Set();
        this.allEdges.forEach(e => {
          connectedIds.add(String(e.source));
          connectedIds.add(String(e.target));
        });
        this.allNodes = this.allNodes.filter(n => connectedIds.has(String(n.id)));

        if (this.allEdges.length === 0 || this.allNodes.length === 0) {
          this._showEmpty();
          return;
        }

        this._buildSectorColorMap();
        this._renderGraph();
        this._updateStats(data.meta);
        this._updateLegend();
      } catch (err) {
        console.error('グラフデータ取得エラー:', err);
        this._showError(err.message);
      }
    }

    // ==============================
    // セクターカラーマップ構築
    // ==============================
    _buildSectorColorMap() {
      const sectors = [...new Set(
        this.allNodes
          .filter(n => n.node_type === 'diary')
          .map(n => n.sector || '未分類')
      )];
      this.sectorColorMap = {};
      sectors.forEach((s, i) => {
        this.sectorColorMap[s] = SECTOR_PALETTE[i % SECTOR_PALETTE.length];
      });
    }

    _edgeWidth(d)   { return 1.5; }
    _edgeOpacity(d) { return 0.55; }

    // ==============================
    // D3 グラフ描画
    // ==============================
    _renderGraph() {
      if (this.simulation) {
        this.simulation.stop();
        this.simulation = null;
      }
      this.svgEl.innerHTML = '';

      const svgEl = this.svgEl;
      const width  = svgEl.clientWidth || svgEl.parentElement.clientWidth || 800;
      const height = svgEl.clientHeight || 600;

      const diaryNodes = this.allNodes.filter(n => n.node_type === 'diary');
      const maxLinks = Math.max(...diaryNodes.map(n => n.link_count || 0), 1);
      const radiusScale = d3.scaleSqrt()
        .domain([0, maxLinks])
        .range([NODE_RADIUS_MIN, NODE_RADIUS_MAX]);

      const hubNodes = this.allNodes.filter(n => n.node_type !== 'diary');
      const hubMaxLinks = Math.max(...hubNodes.map(n => n.link_count || 0), 1);
      const hubRadiusScale = d3.scaleSqrt()
        .domain([0, hubMaxLinks])
        .range([HUB_RADIUS_MIN, HUB_RADIUS_MAX]);

      const svg = d3.select(svgEl);
      this.svg = svg;

      const g = svg.append('g').attr('class', 'graph-root');
      this.gRoot = g;

      // ユーザーが手動でズーム・パン操作したかを記録するフラグ
      this._userHasInteracted = false;
      // 自動フィットを一度だけ実行するためのフラグ（多重フィットによる「ガクつき」防止）
      this._hasAutoFitted = false;

      this.zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 6])
        .on('zoom', event => {
          g.attr('transform', event.transform);
          // sourceEvent がある = ユーザー操作（プログラム制御の transform 変更は除外）
          if (event.sourceEvent) this._userHasInteracted = true;
        });
      svg.call(this.zoomBehavior);

      // パン・スクロールと単純クリックを区別（mouse / touch 両対応）
      let _ptrStart = null;
      svg.on('pointerdown.clickguard', event => {
        _ptrStart = [event.clientX, event.clientY];
      });
      svg.on('pointercancel.clickguard', () => {
        // ブラウザがページスクロールを引き継いだ場合 → 次の click でパネルを閉じない
        if (_ptrStart) _ptrStart = [-9999, -9999];
      });
      svg.on('click', event => {
        // pointerdown から 4px 以上動いていたら移動操作 → パネルを閉じない
        const moved = _ptrStart && (
          Math.abs(event.clientX - _ptrStart[0]) > 4 ||
          Math.abs(event.clientY - _ptrStart[1]) > 4
        );
        _ptrStart = null;
        if (moved) return;
        this._hideTooltip();
        this._closeSidePanel();
        if (this.focusNodeId) this._exitFocusMode();
      });

      // ノードは間引かない（ハブも全表示）。d3 が x/y や source/target を
      // 書き換えるため、元データを汚さないようコピーを渡す。
      const nodes = this.allNodes.map(d => ({ ...d }));
      const edges = this.allEdges.map(d => ({ ...d }));

      const hasHubMode = this.currentEdgeModes.has('tag') || this.currentEdgeModes.has('sector') || this.currentEdgeModes.has('hashtag');
      const linkDist  = hasHubMode ? FORCE_LINK_DISTANCE_HUB : FORCE_LINK_DISTANCE_DEFAULT;

      this.simulation = d3.forceSimulation(nodes)
        .force('link',
          d3.forceLink(edges).id(d => d.id).distance(linkDist)
        )
        .force('charge', d3.forceManyBody().strength(FORCE_CHARGE))
        .force('center',  d3.forceCenter(width / 2, height / 2))
        // 中央への弱い引力。レイアウトが横長・縦長に広がりすぎるのを抑え、
        // 自動フィット時にノードが豆粒化しないよう全体をまとめる。
        // 縦は画面が短いので少し強めに引く。
        .force('x', d3.forceX(width / 2).strength(0.05))
        .force('y', d3.forceY(height / 2).strength(0.08))
        .force('collision',
          d3.forceCollide().radius(d => {
            if (d.node_type !== 'diary') {
              return hubRadiusScale(d.link_count || 0) * 1.4;
            }
            return radiusScale(d.link_count || 0) * FORCE_COLLISION_MULT;
          })
        );

      // エッジ。希少な関連を太く濃く（_edgeWidth/_edgeOpacity 参照）
      const linkSel = g.append('g').attr('class', 'links')
        .selectAll('line')
        .data(edges)
        .join('line')
          .attr('class', d => `graph-link edge-${d.edge_type || 'manual'}`)
          .attr('stroke', d => EDGE_COLOR[d.edge_type] || EDGE_COLOR.manual)
          .attr('stroke-width',   d => this._edgeWidth(d))
          .attr('stroke-opacity', d => this._edgeOpacity(d));
      // トグル変更時に再描画せず強調度だけ更新するため保持
      this.linkSel = linkSel;

      // ノードグループ
      const self = this;
      const nodeSel = g.append('g').attr('class', 'nodes')
        .selectAll('g')
        .data(nodes)
        .join('g')
          .attr('class', d => {
            if (d.node_type === 'tag')     return 'graph-node node-hub node-tag';
            if (d.node_type === 'sector')  return 'graph-node node-hub node-sector';
            if (d.node_type === 'hashtag') return 'graph-node node-hub node-hashtag';
            return `graph-node status-${d.status}`;
          })
          .attr('data-id',   d => String(d.id))
          .attr('data-name', d => (d.stock_name || d.tag_name || d.sector_name || '').toLowerCase())
          .call(
            d3.drag()
              .on('start', (event, d) => {
                if (!event.active) self.simulation.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
              })
              .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
              .on('end',  (event, d) => {
                if (!event.active) self.simulation.alphaTarget(0);
                // ドラッグ位置にピン留め。クラスで固定中を示す
                d3.select(event.sourceEvent.target.closest('.graph-node')).classed('pinned', true);
              })
          );

      // 形状描画
      nodeSel.each(function(d) {
        const el = d3.select(this);
        if (d.node_type === 'diary') {
          el.append('circle')
            .attr('r', radiusScale(d.link_count || 0))
            .classed('secondary-node', !d.is_primary);
        } else if (d.node_type === 'tag') {
          const r = hubRadiusScale(d.link_count || 0);
          el.append('polygon')
            .attr('points', _hexPoints(r))
            .attr('fill', HUB_COLOR.tag)
            .attr('stroke', 'white')
            .attr('stroke-width', 2);
        } else if (d.node_type === 'sector') {
          const r  = hubRadiusScale(d.link_count || 0);
          const s  = r * 1.5;
          el.append('rect')
            .attr('x', -s / 2).attr('y', -s / 2)
            .attr('width', s).attr('height', s)
            .attr('rx', 5).attr('ry', 5)
            .attr('fill', HUB_COLOR.sector)
            .attr('stroke', 'white')
            .attr('stroke-width', 2);
        } else if (d.node_type === 'hashtag') {
          const r = hubRadiusScale(d.link_count || 0);
          el.append('polygon')
            .attr('points', _hexPoints(r))
            .attr('fill', HUB_COLOR.hashtag)
            .attr('stroke', 'white')
            .attr('stroke-width', 2);
        }
      });

      // ラベル
      nodeSel.append('text')
        .attr('dy', d => {
          if (d.node_type !== 'diary') return hubRadiusScale(d.link_count || 0) + 14;
          return radiusScale(d.link_count || 0) + 13;
        })
        .attr('text-anchor', 'middle')
        .attr('class', 'graph-label')
        .text(d => {
          if (d.node_type === 'hashtag') {
            const n = d.tag_name || '';
            return '@' + (n.length > 7 ? n.substring(0, 7) + '…' : n);
          }
          if (d.node_type === 'tag') {
            const n = d.tag_name || '';
            return n.length > 8 ? n.substring(0, 8) + '…' : n;
          }
          if (d.node_type === 'sector') {
            const n = d.sector_name || '';
            return n.length > 8 ? n.substring(0, 8) + '…' : n;
          }
          const name = d.stock_name || '';
          return name.length > 8 ? name.substring(0, 8) + '…' : name;
        });

      // ホバー時の隣接ハイライト用マップを構築
      const neighborMap = new Map();
      nodes.forEach(n => neighborMap.set(String(n.id), new Set()));
      edges.forEach(e => {
        const s = String(typeof e.source === 'object' ? e.source.id : e.source);
        const t = String(typeof e.target === 'object' ? e.target.id : e.target);
        if (neighborMap.has(s)) neighborMap.get(s).add(t);
        if (neighborMap.has(t)) neighborMap.get(t).add(s);
      });

      // イベント
      nodeSel
        .on('mouseenter', (event, d) => {
          this._showTooltip(event, d);
          const id = String(d.id);
          const neighbors = neighborMap.get(id) || new Set();
          // 隣接ノードをハイライト、それ以外を薄く
          nodeSel.classed('neighbor-dim', n => {
            const nid = String(n.id);
            return nid !== id && !neighbors.has(nid);
          });
          nodeSel.classed('neighbor-highlight', n => {
            const nid = String(n.id);
            return nid !== id && neighbors.has(nid);
          });
          // 接続エッジをハイライト
          linkSel.classed('highlighted', e => {
            const s = String(typeof e.source === 'object' ? e.source.id : e.source);
            const t = String(typeof e.target === 'object' ? e.target.id : e.target);
            return s === id || t === id;
          });
          linkSel.classed('dimmed', e => {
            const s = String(typeof e.source === 'object' ? e.source.id : e.source);
            const t = String(typeof e.target === 'object' ? e.target.id : e.target);
            return s !== id && t !== id;
          });
        })
        .on('mousemove', event => { this._moveTooltip(event); })
        .on('mouseleave', () => {
          this._hideTooltip();
          nodeSel.classed('neighbor-dim', false).classed('neighbor-highlight', false);
          linkSel.classed('highlighted', false).classed('dimmed', false);
        })
        .on('dblclick', (event, d) => {
          // ダブルクリックでピン留め解除
          event.stopPropagation();
          d.fx = null; d.fy = null;
          d3.select(event.currentTarget).classed('pinned', false);
          self.simulation.alphaTarget(0.1).restart();
          setTimeout(() => self.simulation.alphaTarget(0), 500);
        })
        .on('click', (event, d) => {
          event.stopPropagation();
          this._openSidePanel(d);
        });

      // tick
      this.simulation.on('tick', () => {
        linkSel
          .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);

        // レイアウトがほぼ安定したら（end を待たず）一度だけ滑らかにフィット。
        // end まで待つと数秒かかり、その間に瞬間的な縮小が起きて見づらいため。
        if (!this._hasAutoFitted && !this._userHasInteracted
            && this.simulation.alpha() < 0.06) {
          this._hasAutoFitted = true;
          this._fitToView(true);
        }
      });

      this._applyColorMode();
      this._toggleLabels();
      this._applySearch();
      this._showGraph();
      this._applyHubGlow();

      // シミュレーション安定後の自動フィット（tick で未実行だった場合の保険）。
      // すでに tick 内でフィット済み、または手動操作済みなら何もしない。
      this.simulation.on('end', () => {
        if (!this._userHasInteracted && !this._hasAutoFitted) {
          this._hasAutoFitted = true;
          this._fitToView(true);
        }
      });
      // 4秒後にもフィット（tick も end も発火しないケースの最終保険）
      setTimeout(() => {
        if (this.svg && !this._userHasInteracted && !this._hasAutoFitted) {
          this._hasAutoFitted = true;
          this._fitToView(true);
        }
      }, 4000);
    }

    // ==============================
    // ラベル表示切り替え
    // ==============================
    _toggleLabels() {
      document.querySelectorAll('.graph-label').forEach(el => {
        el.style.display = this.showLabels ? '' : 'none';
      });
    }

    // ==============================
    // グラフ内検索
    // ==============================
    _applySearch() {
      const q = this.searchQuery;
      const matchIds = [];

      document.querySelectorAll('.graph-node').forEach(el => {
        if (!q) {
          el.classList.remove('highlighted', 'dimmed');
          return;
        }
        const name = (el.dataset.name || '').toLowerCase();
        if (name.includes(q)) {
          el.classList.add('highlighted');
          el.classList.remove('dimmed');
          matchIds.push(el.dataset.id);
        } else {
          el.classList.remove('highlighted');
          el.classList.add('dimmed');
        }
      });

      this._searchMatchIds = matchIds;
      this._updateSearchFocusButton();
    }

    // ==============================
    // カラーモード
    // ==============================
    _applyColorMode() {
      const mode = this.currentColorMode;
      document.querySelectorAll('.graph-node').forEach(el => {
        const id   = el.dataset.id;
        const node = this.allNodes.find(n => String(n.id) === id);
        if (!node || node.node_type !== 'diary') return;
        const circle = el.querySelector('circle');
        if (!circle) return;
        if (mode === 'status') {
          circle.style.fill = '';
        } else if (mode === 'sector') {
          circle.style.fill = this.sectorColorMap[node.sector] || '#9ca3af';
        } else if (mode === 'profit') {
          const p = node.realized_profit || 0;
          circle.style.fill = p > 0 ? '#10b981' : p < 0 ? '#ef4444' : '#9ca3af';
        }
      });
    }

    // ==============================
    // 凡例更新
    // ==============================
    _updateLegend() {
      const modes  = this.currentEdgeModes;
      const tagLeg  = document.getElementById('legend-tag-node');
      const secLeg  = document.getElementById('legend-sector-node');
      const hubWrap = document.getElementById('legend-hubs');
      const mentionLeg = document.getElementById('legend-mention-edge');

      const toggle = (el, show) => el && el.classList.toggle('legend-hidden', !show);
      const hasTag = modes.has('tag') || modes.has('hashtag');
      toggle(tagLeg,  hasTag);
      toggle(secLeg,  modes.has('sector'));
      const hasHub = hasTag || modes.has('sector');
      toggle(hubWrap, hasHub);
      toggle(mentionLeg, modes.has('mention'));
    }

    // ==============================
    // ズームリセット（全ノードをビューに収める）
    // ==============================
    _resetZoom() {
      this._fitToView(true);
    }

    _fitToView(animate) {
      if (!this.svg || !this.zoomBehavior || !this.gRoot) return;
      const svgEl = this.svgEl;
      const width  = svgEl.clientWidth  || svgEl.parentElement.clientWidth  || 800;
      const height = svgEl.clientHeight || 600;
      try {
        const bbox = this.gRoot.node().getBBox();
        if (!bbox || bbox.width === 0 || bbox.height === 0) return;
        const padding = 48;
        // 全体が収まる縮尺
        const fitScale = Math.min(
          (width  - padding * 2) / bbox.width,
          (height - padding * 2) / bbox.height
        );
        // ノードが豆粒化しない下限と、少数ノード時に寄りすぎない上限でクランプ。
        // 全体が下限縮尺で収まらない場合は中央付近を表示し、パン/ピンチで全体を辿れる。
        const MIN_READABLE_SCALE = 0.5;
        const MAX_SCALE = 1.6;
        const scale = Math.max(MIN_READABLE_SCALE, Math.min(fitScale, MAX_SCALE));
        const tx = width  / 2 - scale * (bbox.x + bbox.width  / 2);
        const ty = height / 2 - scale * (bbox.y + bbox.height / 2);
        const t = d3.zoomIdentity.translate(tx, ty).scale(scale);
        const sel = animate ? this.svg.transition().duration(500) : this.svg;
        sel.call(this.zoomBehavior.transform, t);
      } catch (_) { /* getBBox が利用できない環境では無視 */ }
    }

    // ==============================
    // 全画面モード切替（スマホでノードが見えづらい問題対応）
    // ==============================
    _toggleFullscreen(force) {
      const stage = document.getElementById('graph-stage');
      if (!stage) return;
      const next = (typeof force === 'boolean')
        ? force
        : !stage.classList.contains('is-fullscreen');

      stage.classList.toggle('is-fullscreen', next);
      document.body.classList.toggle('graph-fullscreen-active', next);
      this._isFullscreen = next;

      const btn = document.getElementById('toggleFullscreen');
      if (btn) {
        const icon = btn.querySelector('i');
        if (icon) {
          icon.className = next ? 'bi bi-fullscreen-exit' : 'bi bi-arrows-fullscreen';
        }
        btn.setAttribute('title', next ? '全画面を終了' : '全画面表示');
        btn.setAttribute('aria-pressed', next ? 'true' : 'false');
      }

      // CSS のレイアウト変更が反映されてから再センター + フィット（明示操作なので強制フィット）
      this._handleResize(true);
    }

    // ==============================
    // 描画領域サイズ変更時の再センター/フィット
    //   forceFit=true: 全体が見える位置に強制リフィット（全画面トグル時）
    //   forceFit=false: シミュレーション中心のみ更新、ユーザーの zoom/pan は維持
    // ==============================
    _handleResize(forceFit) {
      if (!this.svg || !this.simulation) return;
      requestAnimationFrame(() => {
        const svgEl = this.svgEl;
        const w = svgEl.clientWidth  || svgEl.parentElement.clientWidth  || 800;
        const h = svgEl.clientHeight || svgEl.parentElement.clientHeight || 600;
        const centerForce = this.simulation.force('center');
        if (centerForce) {
          centerForce.x(w / 2).y(h / 2);
        }
        this.simulation.alpha(0.2).restart();
        if (forceFit) {
          this._userHasInteracted = false;
          this._fitToView(true);
        }
      });
    }

    // ==============================
    // ツールチップ（ホバー）
    // ==============================
    _showTooltip(event, d) {
      let html = '';
      if (d.node_type === 'tag') {
        html = `
          <div class="tt-name"><i class="bi bi-tag-fill me-1" style="color:#7c3aed;"></i>${_esc(d.tag_name)}</div>
          <div class="tt-meta">タグ &nbsp;|&nbsp; 接続銘柄: ${d.diary_count || 0}件</div>
          <div class="tt-hint">クリックで詳細パネル</div>`;
      } else if (d.node_type === 'sector') {
        html = `
          <div class="tt-name"><i class="bi bi-building me-1" style="color:#d97706;"></i>${_esc(d.sector_name)}</div>
          <div class="tt-meta">業種 &nbsp;|&nbsp; 接続銘柄: ${d.diary_count || 0}件</div>
          <div class="tt-hint">クリックで詳細パネル</div>`;
      } else if (d.node_type === 'hashtag') {
        html = `
          <div class="tt-name"><i class="bi bi-hash me-1" style="color:#0ea5e9;"></i>${_esc(d.tag_name)}</div>
          <div class="tt-meta">@ハッシュタグ &nbsp;|&nbsp; 接続銘柄: ${d.diary_count || 0}件</div>
          <div class="tt-hint">クリックで詳細パネル</div>`;
      } else {
        const profit = d.realized_profit || 0;
        const sign   = profit > 0 ? '+' : '';
        const pStr   = profit === 0 ? '-' : sign + profit.toLocaleString('ja-JP') + '円';
        const pClass = profit > 0 ? 'positive' : profit < 0 ? 'negative' : '';
        const statusMap = {
          holding: '<span style="color:#10b981;">●</span> 保有中',
          sold:    '<span style="color:#ef4444;">●</span> 売却済み',
          memo:    '<span style="color:#9ca3af;">●</span> メモ',
        };
        html = `
          <div class="tt-name">${_esc(d.stock_name)}</div>
          <div class="tt-symbol">${_esc(d.stock_symbol || '-')} &nbsp;/&nbsp; ${_esc(d.sector)}</div>
          <div class="tt-profit ${pClass}">実現損益: ${pStr}</div>
          <div class="tt-meta">${statusMap[d.status] || d.status} &nbsp;|&nbsp; 接続: ${d.link_count}本</div>
          <div class="tt-hint">クリックで詳細パネル</div>`;
      }
      this.tooltipEl.innerHTML = html;
      this.tooltipEl.style.display = 'block';
      this._moveTooltip(event);
    }

    _moveTooltip(event) {
      const padding = 14;
      const ttw = this.tooltipEl.offsetWidth  || 200;
      const tth = this.tooltipEl.offsetHeight || 90;
      let x = event.clientX + padding;
      let y = event.clientY - 10;
      if (x + ttw > window.innerWidth  - 8) x = event.clientX - ttw - padding;
      if (y + tth > window.innerHeight - 8) y = window.innerHeight - tth - 8;
      this.tooltipEl.style.left = x + 'px';
      this.tooltipEl.style.top  = y + 'px';
    }

    _hideTooltip() {
      this.tooltipEl.style.display = 'none';
    }

    // ==============================
    // サイドパネル
    // ==============================
    _openSidePanel(d) {
      this._hideTooltip();
      let title = '';
      let html  = '';

      if (d.node_type === 'tag') {
        title = `<i class="bi bi-tag-fill me-1" style="color:#7c3aed;"></i>${_esc(d.tag_name)}`;
        html  = `
          <div class="side-panel-section">
            <div class="side-panel-label">種別</div><div>タグ（ハブノード）</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">接続銘柄数</div><div>${d.diary_count || 0} 件</div>
          </div>`;
      } else if (d.node_type === 'sector') {
        title = `<i class="bi bi-building me-1" style="color:#d97706;"></i>${_esc(d.sector_name)}`;
        html  = `
          <div class="side-panel-section">
            <div class="side-panel-label">種別</div><div>業種（ハブノード）</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">接続銘柄数</div><div>${d.diary_count || 0} 件</div>
          </div>`;
      } else if (d.node_type === 'hashtag') {
        title = `<i class="bi bi-hash me-1" style="color:#0ea5e9;"></i>@${_esc(d.tag_name)}`;
        html  = `
          <div class="side-panel-section">
            <div class="side-panel-label">種別</div><div>@ハッシュタグ（ハブノード）</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">接続銘柄数</div><div>${d.diary_count || 0} 件</div>
          </div>`;
      } else {
        const profit  = d.realized_profit || 0;
        const sign    = profit > 0 ? '+' : '';
        const pStr    = profit === 0 ? '-' : sign + profit.toLocaleString('ja-JP') + '円';
        const pColor  = profit > 0 ? 'text-success' : profit < 0 ? 'text-danger' : 'text-muted';
        const badgeMap = {
          holding: '<span class="badge bg-success">保有中</span>',
          sold:    '<span class="badge bg-danger">売却済み</span>',
          memo:    '<span class="badge bg-secondary">メモ</span>',
        };
        title = _esc(d.stock_name || '-');
        html  = `
          <div class="side-panel-section">
            <div class="side-panel-label">銘柄コード</div><div>${_esc(d.stock_symbol || '-')}</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">業種</div><div>${_esc(d.sector || '未分類')}</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">ステータス</div><div>${badgeMap[d.status] || d.status}</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">実現損益</div>
            <div class="${pColor} fw-semibold">${pStr}</div>
          </div>
          <div class="side-panel-section">
            <div class="side-panel-label">接続数</div><div>${d.link_count || 0} 本</div>
          </div>
          <div class="side-panel-footer mt-3">
            <a href="${_esc(d.url)}" class="btn btn-primary btn-sm w-100">
              <i class="bi bi-journal-text me-1"></i>日記の詳細を見る
            </a>
          </div>`;
      }

      html += `
        <div class="side-panel-section mt-2">
          <button class="btn btn-outline-primary btn-sm w-100" id="focus-mode-btn"
                  data-node-id="${_esc(String(d.id))}">
            <i class="bi bi-crosshair me-1"></i>この関連のみ表示
          </button>
        </div>`;

      this.sidePanelTitle.innerHTML = title;
      this.sidePanelBody.innerHTML  = html;
      this.sidePanel.classList.add('open');
      document.getElementById('graph-wrapper').classList.add('panel-open');

      const focusBtn = document.getElementById('focus-mode-btn');
      if (focusBtn) {
        focusBtn.addEventListener('click', () => {
          const nid = focusBtn.dataset.nodeId;
          this._closeSidePanel();
          this._enterFocusMode(nid);
        });
      }
    }

    _closeSidePanel() {
      if (this.sidePanel)  this.sidePanel.classList.remove('open');
      const wrapper = document.getElementById('graph-wrapper');
      if (wrapper) wrapper.classList.remove('panel-open');
    }

    // ==============================
    // 統計バッジ更新
    // ==============================
    _updateStats(meta) {
      if (!meta || !this.statsEl) return;
      document.getElementById('stats-nodes').textContent = `${meta.total_nodes} ノード`;
      document.getElementById('stats-edges').textContent = `${meta.total_edges} 接続`;
      this.statsEl.style.display = 'block';
    }

    // ==============================
    // フォーカスモード
    // ==============================
    _enterFocusMode(nodeId) {
      const nid = String(nodeId);
      const neighbors = new Set();
      this.allEdges.forEach(e => {
        const s = String(typeof e.source === 'object' ? e.source.id : e.source);
        const t = String(typeof e.target === 'object' ? e.target.id : e.target);
        if (s === nid) neighbors.add(t);
        if (t === nid) neighbors.add(s);
      });

      this.focusNodeId = nid;
      this.focusNeighborIds = neighbors;
      const visibleIds = new Set([nid, ...neighbors]);

      document.querySelectorAll('.graph-node').forEach(el => {
        const id = el.dataset.id;
        if (visibleIds.has(id)) {
          el.classList.remove('focus-hidden');
          el.classList.add('focus-visible');
        } else {
          el.classList.add('focus-hidden');
          el.classList.remove('focus-visible');
        }
      });

      if (this.linkSel) {
        this.linkSel.classed('focus-hidden', e => {
          const s = String(typeof e.source === 'object' ? e.source.id : e.source);
          const t = String(typeof e.target === 'object' ? e.target.id : e.target);
          return !(visibleIds.has(s) && visibleIds.has(t));
        });
      }

      this._showFocusBanner(visibleIds.size);

      const nodesEl = document.getElementById('stats-nodes');
      const edgesEl = document.getElementById('stats-edges');
      const focusedEdgeCount = this.allEdges.filter(e => {
        const s = String(typeof e.source === 'object' ? e.source.id : e.source);
        const t = String(typeof e.target === 'object' ? e.target.id : e.target);
        return visibleIds.has(s) && visibleIds.has(t);
      }).length;
      if (nodesEl) nodesEl.textContent = `${visibleIds.size} ノード (フォーカス)`;
      if (edgesEl) edgesEl.textContent = `${focusedEdgeCount} 接続`;
    }

    _exitFocusMode() {
      this.focusNodeId = null;
      this.focusNeighborIds = new Set();

      document.querySelectorAll('.graph-node').forEach(el => {
        el.classList.remove('focus-hidden', 'focus-visible');
      });

      if (this.linkSel) {
        this.linkSel.classed('focus-hidden', false);
      }

      this._hideFocusBanner();

      const nodesEl = document.getElementById('stats-nodes');
      const edgesEl = document.getElementById('stats-edges');
      if (nodesEl) nodesEl.textContent = `${this.allNodes.length} ノード`;
      if (edgesEl) edgesEl.textContent = `${this.allEdges.length} 接続`;

      this._applySearch();
    }

    _showFocusBanner(nodeCount) {
      const banner = document.getElementById('focus-mode-banner');
      if (!banner) return;
      const node = this.allNodes.find(n => String(n.id) === this.focusNodeId);
      const label = node
        ? (node.stock_name || node.tag_name || node.sector_name || 'ノード')
        : 'ノード';
      const labelEl = banner.querySelector('#focus-banner-label');
      const countEl = banner.querySelector('#focus-banner-count');
      if (labelEl) labelEl.textContent = label;
      if (countEl) countEl.textContent = `${nodeCount} ノード表示中`;
      banner.style.display = 'flex';
    }

    _hideFocusBanner() {
      const banner = document.getElementById('focus-mode-banner');
      if (banner) banner.style.display = 'none';
    }

    _enterMultiFocusMode(nodeIds) {
      if (nodeIds.length === 0) return;
      if (nodeIds.length === 1) { this._enterFocusMode(nodeIds[0]); return; }

      const focusSet = new Set(nodeIds.map(String));
      const neighborUnion = new Set();
      this.allEdges.forEach(e => {
        const s = String(typeof e.source === 'object' ? e.source.id : e.source);
        const t = String(typeof e.target === 'object' ? e.target.id : e.target);
        if (focusSet.has(s)) neighborUnion.add(t);
        if (focusSet.has(t)) neighborUnion.add(s);
      });

      this.focusNodeId = '__multi__';
      this.focusNeighborIds = neighborUnion;
      const visibleIds = new Set([...focusSet, ...neighborUnion]);

      document.querySelectorAll('.graph-node').forEach(el => {
        const id = el.dataset.id;
        if (visibleIds.has(id)) {
          el.classList.remove('focus-hidden');
          el.classList.add('focus-visible');
        } else {
          el.classList.add('focus-hidden');
          el.classList.remove('focus-visible');
        }
      });

      if (this.linkSel) {
        this.linkSel.classed('focus-hidden', e => {
          const s = String(typeof e.source === 'object' ? e.source.id : e.source);
          const t = String(typeof e.target === 'object' ? e.target.id : e.target);
          return !(visibleIds.has(s) && visibleIds.has(t));
        });
      }

      const banner = document.getElementById('focus-mode-banner');
      if (banner) {
        const labelEl = banner.querySelector('#focus-banner-label');
        const countEl = banner.querySelector('#focus-banner-count');
        if (labelEl) labelEl.textContent = `${nodeIds.length} 件の検索結果`;
        if (countEl) countEl.textContent = `${visibleIds.size} ノード表示中`;
        banner.style.display = 'flex';
      }

      const nodesEl = document.getElementById('stats-nodes');
      const edgesEl = document.getElementById('stats-edges');
      const focusedEdgeCount = this.allEdges.filter(e => {
        const s = String(typeof e.source === 'object' ? e.source.id : e.source);
        const t = String(typeof e.target === 'object' ? e.target.id : e.target);
        return visibleIds.has(s) && visibleIds.has(t);
      }).length;
      if (nodesEl) nodesEl.textContent = `${visibleIds.size} ノード (フォーカス)`;
      if (edgesEl) edgesEl.textContent = `${focusedEdgeCount} 接続`;

      const sfBtn = document.getElementById('search-focus-btn');
      if (sfBtn) sfBtn.style.display = 'none';
    }

    _updateSearchFocusButton() {
      const btn = document.getElementById('search-focus-btn');
      if (!btn) return;
      if (!this.searchQuery || this.focusNodeId || this._searchMatchIds.length === 0) {
        btn.style.display = 'none'; return;
      }
      const count = this._searchMatchIds.length;
      if (count === 1) {
        const node = this.allNodes.find(n => String(n.id) === this._searchMatchIds[0]);
        const label = node ? (node.stock_name || node.tag_name || node.sector_name || '') : '';
        btn.innerHTML = `<i class="bi bi-crosshair me-1"></i>${_esc(label)} の関連のみ表示`;
      } else {
        btn.innerHTML = `<i class="bi bi-crosshair me-1"></i>一致した ${count} 件を中心に表示`;
      }
      btn.style.display = 'inline-flex';
    }

    // ==============================
    // ハブノードのグロー強調
    // ==============================
    _applyHubGlow() {
      if (!this.svg) return;

      let defs = this.svg.select('defs');
      if (defs.empty()) defs = this.svg.insert('defs', ':first-child');
      defs.selectAll('filter.hub-glow-filter').remove();

      const TOP_N = 5;
      const glowColorMap = { tag: '#a78bfa', sector: '#fb923c', hashtag: '#a78bfa' };

      const hubNodes = this.allNodes
        .filter(n => ['tag', 'sector', 'hashtag'].includes(n.node_type))
        .sort((a, b) => (b.link_count || 0) - (a.link_count || 0))
        .slice(0, TOP_N);

      if (hubNodes.length === 0) return;

      hubNodes.forEach((node, rank) => {
        const filterId = `hub-glow-${String(node.id).replace(/[^a-z0-9]/gi, '_')}`;
        const glowColor = glowColorMap[node.node_type] || '#a78bfa';
        const stdDev  = 4 - (rank / Math.max(TOP_N - 1, 1)) * 2.5;
        const opacity = 0.85 - (rank / Math.max(TOP_N - 1, 1)) * 0.5;

        const filter = defs.append('filter')
          .attr('id', filterId)
          .attr('class', 'hub-glow-filter')
          .attr('x', '-50%').attr('y', '-50%')
          .attr('width', '200%').attr('height', '200%');
        filter.append('feFlood')
          .attr('flood-color', glowColor)
          .attr('flood-opacity', opacity)
          .attr('result', 'color');
        filter.append('feComposite')
          .attr('in', 'color').attr('in2', 'SourceGraphic')
          .attr('operator', 'in').attr('result', 'coloredSource');
        filter.append('feGaussianBlur')
          .attr('in', 'coloredSource')
          .attr('stdDeviation', stdDev)
          .attr('result', 'blur');
        const merge = filter.append('feMerge');
        merge.append('feMergeNode').attr('in', 'blur');
        merge.append('feMergeNode').attr('in', 'SourceGraphic');

        this.svg.select(`.graph-node[data-id="${String(node.id)}"]`)
          .attr('filter', `url(#${filterId})`);
      });
    }

    // ==============================
    // 表示状態切り替え
    // ==============================
    _showLoading() {
      this.loadingEl.style.display = 'flex';
      this.svgEl.style.display     = 'none';
      this.emptyEl.style.display   = 'none';
      if (this.statsEl) this.statsEl.style.display = 'none';
    }
    _showGraph() {
      this.loadingEl.style.display = 'none';
      this.svgEl.style.display     = 'block';
      this.emptyEl.style.display   = 'none';
    }
    _showEmpty() {
      this.loadingEl.style.display = 'none';
      this.svgEl.style.display     = 'none';
      this.emptyEl.style.display   = 'flex';
      if (this.statsEl) this.statsEl.style.display = 'none';
    }
    _showError(msg) {
      this.loadingEl.innerHTML = `
        <div class="text-center py-4">
          <i class="bi bi-exclamation-triangle text-danger" style="font-size:2.5rem;"></i>
          <p class="mt-2 text-danger">グラフデータの読み込みに失敗しました。</p>
          <small class="text-muted">${_esc(msg)}</small><br>
          <button class="btn btn-outline-secondary btn-sm mt-3" onclick="location.reload()">
            <i class="bi bi-arrow-clockwise me-1"></i>再試行
          </button>
        </div>`;
      this.loadingEl.style.display = 'flex';
    }
  }

  // ==============================
  // ユーティリティ
  // ==============================
  function _hexPoints(r) {
    const pts = [];
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i - Math.PI / 6;
      pts.push(`${(r * Math.cos(angle)).toFixed(2)},${(r * Math.sin(angle)).toFixed(2)}`);
    }
    return pts.join(' ');
  }

  function _triPoints(r) {
    return `0,${-r} ${(r * 0.866).toFixed(2)},${(r * 0.5).toFixed(2)} ${(-r * 0.866).toFixed(2)},${(r * 0.5).toFixed(2)}`;
  }

  function _esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ==============================
  // エントリポイント
  // ==============================
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof GRAPH_CONFIG === 'undefined') return;
    new DiaryGraph(GRAPH_CONFIG);
  });

})();

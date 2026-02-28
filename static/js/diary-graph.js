/**
 * diary-graph.js
 * 日記関連グラフ可視化モジュール
 * D3.js v7 を使用した force-directed graph
 */
(function () {
  'use strict';

  // ==============================
  // 定数
  // ==============================
  const NODE_RADIUS_MIN = 8;
  const NODE_RADIUS_MAX = 26;

  const FORCE_LINK_DISTANCE = 120;
  const FORCE_CHARGE = -280;
  const FORCE_COLLISION_MULT = 1.6;

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

      this.allNodes  = [];
      this.allEdges  = [];
      this.simulation = null;
      this.svg        = null;
      this.gRoot      = null;
      this.zoomBehavior = null;

      this.currentStatus  = 'all';
      this.currentTag     = '';
      this.showLabels     = true;
      this.pinnedNodeId   = null;   // ピン留め中のノードID

      this._init();
    }

    // ==============================
    // 初期化
    // ==============================
    _init() {
      this._bindControls();
      this._fetchAndRender();
    }

    // ==============================
    // コントロールイベントバインド
    // ==============================
    _bindControls() {
      // ステータスフィルター
      document.querySelectorAll('input[name="statusFilter"]').forEach(radio => {
        radio.addEventListener('change', e => {
          this.currentStatus = e.target.value;
          this._fetchAndRender();
        });
      });

      // タグフィルター
      const tagSel = document.getElementById('tagFilter');
      if (tagSel) {
        tagSel.addEventListener('change', e => {
          this.currentTag = e.target.value;
          this._fetchAndRender();
        });
      }

      // ラベルトグル
      const labelToggle = document.getElementById('showLabels');
      if (labelToggle) {
        labelToggle.addEventListener('change', e => {
          this.showLabels = e.target.checked;
          this._toggleLabels();
        });
      }

      // ズームリセット
      const resetBtn = document.getElementById('resetZoom');
      if (resetBtn) {
        resetBtn.addEventListener('click', () => this._resetZoom());
      }
    }

    // ==============================
    // データ取得 → 描画
    // ==============================
    async _fetchAndRender() {
      this._showLoading();

      const params = new URLSearchParams();
      if (this.currentStatus && this.currentStatus !== 'all') {
        params.set('status', this.currentStatus);
      }
      if (this.currentTag) {
        params.set('tag', this.currentTag);
      }

      try {
        const resp = await fetch(`${this.apiUrl}?${params.toString()}`, {
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        this.allNodes = data.nodes || [];
        this.allEdges = data.edges || [];

        // エッジが1本もなければ空状態
        if (this.allEdges.length === 0) {
          this._showEmpty();
          return;
        }

        this._renderGraph();
        this._updateStats(data.meta);
      } catch (err) {
        console.error('グラフデータ取得エラー:', err);
        this._showError(err.message);
      }
    }

    // ==============================
    // D3 グラフ描画
    // ==============================
    _renderGraph() {
      // 既存SVGをクリア・シミュレーション停止
      if (this.simulation) {
        this.simulation.stop();
        this.simulation = null;
      }
      this.svgEl.innerHTML = '';
      this.pinnedNodeId = null;

      const svgEl = this.svgEl;
      const width  = svgEl.clientWidth || svgEl.parentElement.clientWidth || 800;
      const height = svgEl.clientHeight || 600;

      // ノード半径スケール (link_count に比例)
      const maxLinks = Math.max(...this.allNodes.map(n => n.link_count), 1);
      const radiusScale = d3.scaleSqrt()
        .domain([0, maxLinks])
        .range([NODE_RADIUS_MIN, NODE_RADIUS_MAX]);

      const svg = d3.select(svgEl);
      this.svg = svg;

      // ズーム設定
      const g = svg.append('g').attr('class', 'graph-root');
      this.gRoot = g;

      this.zoomBehavior = d3.zoom()
        .scaleExtent([0.15, 5])
        .on('zoom', event => g.attr('transform', event.transform));
      svg.call(this.zoomBehavior);

      // SVG背景クリック → ピン解除
      svg.on('click', () => {
        this.pinnedNodeId = null;
        this._hideTooltip();
      });

      // ノード・エッジデータをコピー（D3がmutateするため）
      const nodes = this.allNodes.map(d => ({ ...d }));
      const edges = this.allEdges.map(d => ({ ...d }));

      // フォースシミュレーション
      this.simulation = d3.forceSimulation(nodes)
        .force('link',
          d3.forceLink(edges)
            .id(d => d.id)
            .distance(FORCE_LINK_DISTANCE)
        )
        .force('charge',
          d3.forceManyBody().strength(FORCE_CHARGE)
        )
        .force('center',
          d3.forceCenter(width / 2, height / 2)
        )
        .force('collision',
          d3.forceCollide().radius(d => radiusScale(d.link_count) * FORCE_COLLISION_MULT)
        );

      // エッジ描画
      const linkSel = g.append('g').attr('class', 'links')
        .selectAll('line')
        .data(edges)
        .join('line')
          .attr('class', 'graph-link');

      // ノードグループ
      const nodeSel = g.append('g').attr('class', 'nodes')
        .selectAll('g')
        .data(nodes)
        .join('g')
          .attr('class', d => `graph-node status-${d.status}`)
          .attr('data-id',   d => String(d.id))
          .attr('data-name', d => (d.stock_name || '').toLowerCase())
          .call(
            d3.drag()
              .on('start', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
              })
              .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
              })
              .on('end', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
              })
          );

      // circle 追加（secondary ノードはやや薄く）
      nodeSel.append('circle')
        .attr('r', d => radiusScale(d.link_count))
        .classed('secondary-node', d => !d.is_primary);

      // ラベル追加
      nodeSel.append('text')
        .attr('dy', d => radiusScale(d.link_count) + 13)
        .attr('text-anchor', 'middle')
        .attr('class', 'graph-label')
        .text(d => {
          const name = d.stock_name || '';
          return name.length > 8 ? name.substring(0, 8) + '…' : name;
        });

      // イベント:
      //   mouseenter/move/leave → ホバーツールチップ（ピン中は固定）
      //   click → ピン留めツールチップ（詳細リンク付き）
      nodeSel
        .on('mouseenter', (event, d) => {
          if (this.pinnedNodeId === null) {
            this._showTooltip(event, d, false);
          }
        })
        .on('mousemove', event => {
          if (this.pinnedNodeId === null) this._moveTooltip(event);
        })
        .on('mouseleave', () => {
          if (this.pinnedNodeId === null) this._hideTooltip();
        })
        .on('click', (event, d) => {
          event.stopPropagation();
          this.pinnedNodeId = d.id;
          this._showTooltip(event, d, true);
        });

      // tick 更新
      this.simulation.on('tick', () => {
        linkSel
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);

        nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
      });

      // ラベル表示状態を反映
      this._toggleLabels();

      // SVGを表示
      this._showGraph();
    }

    // ==============================
    // ラベル表示切り替え
    // ==============================
    _toggleLabels() {
      const labels = document.querySelectorAll('.graph-label');
      labels.forEach(el => {
        el.style.display = this.showLabels ? '' : 'none';
      });
    }

    // ==============================
    // ズームリセット
    // ==============================
    _resetZoom() {
      if (!this.svg || !this.zoomBehavior) return;
      this.svg
        .transition()
        .duration(400)
        .call(this.zoomBehavior.transform, d3.zoomIdentity);
    }

    // ==============================
    // ツールチップ
    // ==============================
    /**
     * @param {MouseEvent} event
     * @param {Object} d - ノードデータ
     * @param {boolean} pinned - true のとき「詳細を見る」リンクを表示
     */
    _showTooltip(event, d, pinned) {
      const profit = d.realized_profit || 0;
      const sign   = profit > 0 ? '+' : '';
      const profitStr = profit === 0
        ? '-'
        : sign + profit.toLocaleString('ja-JP') + '円';
      const profitClass = profit > 0 ? 'positive' : profit < 0 ? 'negative' : '';

      const statusMap = {
        holding: '<span style="color:#10b981;">●</span> 保有中',
        sold:    '<span style="color:#ef4444;">●</span> 売却済み',
        memo:    '<span style="color:#9ca3af;">●</span> メモ',
      };
      const statusLabel = statusMap[d.status] || d.status;

      const linkHtml = pinned
        ? `<div class="tt-link-row">
             <a href="${d.url}" class="tt-detail-link">
               詳細を見る <i class="bi bi-arrow-right-short"></i>
             </a>
           </div>`
        : '';

      this.tooltipEl.innerHTML = `
        <div class="tt-name">${_esc(d.stock_name)}</div>
        <div class="tt-symbol">${_esc(d.stock_symbol || '-')} &nbsp;/&nbsp; ${_esc(d.sector)}</div>
        <div class="tt-profit ${profitClass}">実現損益: ${profitStr}</div>
        <div class="tt-meta">${statusLabel} &nbsp;|&nbsp; 接続: ${d.link_count}本</div>
        ${linkHtml}
      `;
      this.tooltipEl.classList.toggle('pinned', pinned);
      this.tooltipEl.style.display = 'block';
      this._moveTooltip(event);
    }

    _moveTooltip(event) {
      const padding = 14;
      const ttw = this.tooltipEl.offsetWidth || 200;
      const tth = this.tooltipEl.offsetHeight || 90;
      let x = event.clientX + padding;
      let y = event.clientY - 10;

      // 画面右端に収める
      if (x + ttw > window.innerWidth - 8) {
        x = event.clientX - ttw - padding;
      }
      // 画面下端に収める
      if (y + tth > window.innerHeight - 8) {
        y = window.innerHeight - tth - 8;
      }

      this.tooltipEl.style.left = x + 'px';
      this.tooltipEl.style.top  = y + 'px';
    }

    _hideTooltip() {
      this.tooltipEl.style.display = 'none';
      this.tooltipEl.classList.remove('pinned');
    }

    // ==============================
    // 統計バッジ更新
    // ==============================
    _updateStats(meta) {
      if (!meta || !this.statsEl) return;
      document.getElementById('stats-nodes').textContent = `${meta.total_nodes} 銘柄`;
      document.getElementById('stats-edges').textContent = `${meta.total_edges} 関連`;
      this.statsEl.style.display = 'block';
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
          <button class="btn btn-outline-secondary btn-sm mt-3"
                  onclick="location.reload()">
            <i class="bi bi-arrow-clockwise me-1"></i>再試行
          </button>
        </div>
      `;
      this.loadingEl.style.display = 'flex';
    }
  }

  // ==============================
  // ユーティリティ
  // ==============================
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

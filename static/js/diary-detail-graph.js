/**
 * diary-detail-graph.js
 * 日記詳細画面用：D3.js force-directed 埋め込みグラフ
 *
 * 使い方:
 *   window.DIARY_DETAIL_GRAPH_API = "/stockdiary/api/diary/<id>/graph/";
 *   window.DIARY_FOCAL_ID = <id>;
 */

(function () {
  'use strict';

  // ── カラー定数（diary-graph.js と同じ値） ──────────────────────────
  const STATUS_COLOR = {
    holding: '#10b981',
    sold:    '#ef4444',
    memo:    '#9ca3af',
  };
  const HUB_COLOR = {
    tag:     '#7c3aed',
    sector:  '#d97706',
    hashtag: '#0ea5e9',
  };
  const EDGE_COLOR = {
    manual:  '#94a3b8',
    tag:     '#a78bfa',
    sector:  '#fb923c',
    hashtag: '#38bdf8',
    mention: '#f59e0b',
  };

  // ── ノード半径 ────────────────────────────────────────────────────────
  function nodeRadius(node, isFocal) {
    if (isFocal) return 22;
    if (node.node_type !== 'diary') return 12;
    return Math.max(8, Math.min(18, 8 + (node.link_count || 0) * 1.5));
  }

  // ── メインクラス ─────────────────────────────────────────────────────
  class DiaryDetailGraph {
    constructor(apiUrl, focalId) {
      this.apiUrl  = apiUrl;
      this.focalId = focalId;

      this.svg        = d3.select('#detail-graph-svg');
      this.loading    = document.getElementById('detail-graph-loading');
      this.emptyMsg   = document.getElementById('detail-graph-empty');
      this.tooltip    = document.getElementById('detail-graph-tooltip');
      this.container  = document.getElementById('detail-graph-container');

      this.simulation = null;

      this._bindEdgeModeControls();
      this._fetchAndRender(this._getEdgeModes());
    }

    // ── エッジモードチェックボックスを取得 ─────────────────────────────
    _getEdgeModes() {
      const checked = document.querySelectorAll('.detail-edge-check:checked');
      const modes = Array.from(checked).map(el => el.value);
      return modes.length ? modes : ['manual', 'tag', 'sector', 'hashtag', 'mention'];
    }

    // ── チェックボックスのイベント登録 ────────────────────────────────
    _bindEdgeModeControls() {
      document.querySelectorAll('.detail-edge-check').forEach(el => {
        el.addEventListener('change', () => {
          if (this.simulation) this.simulation.stop();
          this._fetchAndRender(this._getEdgeModes());
        });
      });
    }

    // ── API 呼び出し & 描画 ────────────────────────────────────────────
    _fetchAndRender(edgeModes) {
      this._showLoading(true);
      // 前回の描画をクリア
      this.svg.selectAll('*').remove();

      const url = `${this.apiUrl}?edge_modes=${edgeModes.join(',')}`;
      fetch(url, { credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
          this._showLoading(false);
          if (!data.nodes || data.nodes.length === 0) {
            this._showEmpty(true);
            return;
          }
          this._showEmpty(false);
          this._render(data);
        })
        .catch(() => {
          this._showLoading(false);
          this._showEmpty(true);
        });
    }

    // ── D3 グラフ描画 ─────────────────────────────────────────────────
    _render(data) {
      const width  = this.container.clientWidth  || 400;
      const height = this.container.clientHeight || 280;

      // SVG に zoom レイヤーを設定
      const zoom = d3.zoom()
        .scaleExtent([0.3, 4])
        .on('zoom', (event) => g.attr('transform', event.transform));

      this.svg
        .attr('width', width)
        .attr('height', height)
        .call(zoom);

      const g = this.svg.append('g');

      // ノード・エッジをコピー（D3 がプロパティを付加するため）
      const nodes = data.nodes.map(d => ({ ...d }));
      const edges = data.edges.map(d => ({ ...d }));

      // ── force simulation ────────────────────────────────────────────
      const sim = d3.forceSimulation(nodes)
        .force('link',
          d3.forceLink(edges)
            .id(d => d.id)
            .distance(d => (d.edge_type === 'manual' ? 90 : 110))
        )
        .force('charge', d3.forceManyBody().strength(-220))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision',
          d3.forceCollide(d =>
            nodeRadius(d, d.id === this.focalId) * 1.8
          )
        );

      this.simulation = sim;

      // フォーカルノードを初期位置で中心に固定（後でリリース）
      const focalNode = nodes.find(n => n.id === this.focalId);
      if (focalNode) {
        focalNode.fx = width / 2;
        focalNode.fy = height / 2;
        // 少し落ち着いたら固定を外す
        setTimeout(() => {
          if (focalNode) { focalNode.fx = null; focalNode.fy = null; }
          sim.alpha(0.3).restart();
        }, 800);
      }

      // ── エッジ描画 ─────────────────────────────────────────────────
      const link = g.append('g').attr('class', 'detail-graph-links')
        .selectAll('line')
        .data(edges)
        .join('line')
          .attr('stroke', d => EDGE_COLOR[d.edge_type] || '#aaa')
          .attr('stroke-width', 1.5)
          .attr('stroke-opacity', 0.65);

      // ── ノード描画 ─────────────────────────────────────────────────
      const node = g.append('g').attr('class', 'detail-graph-nodes')
        .selectAll('g')
        .data(nodes)
        .join('g')
          .attr('class', d =>
            'detail-graph-node' + (d.id === this.focalId ? ' focal-node' : '')
          )
          .style('cursor', d =>
            d.id === this.focalId ? 'default' : (d.node_type === 'diary' ? 'pointer' : 'default')
          )
          .call(
            d3.drag()
              .on('start', (event, d) => {
                if (!event.active) sim.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
              })
              .on('drag', (event, d) => {
                d.fx = event.x; d.fy = event.y;
              })
              .on('end', (event, d) => {
                if (!event.active) sim.alphaTarget(0);
                // ダブルクリックで固定解除（通常ドラッグは固定のまま）
              })
          );

      // 円（全ノード共通）
      node.append('circle')
        .attr('r', d => nodeRadius(d, d.id === this.focalId))
        .attr('fill', d => {
          if (d.node_type !== 'diary') return HUB_COLOR[d.node_type] || '#999';
          return STATUS_COLOR[d.status] || '#9ca3af';
        })
        .attr('stroke', d => d.id === this.focalId ? '#f59e0b' : 'rgba(255,255,255,0.5)')
        .attr('stroke-width', d => d.id === this.focalId ? 3 : 1);

      // フォーカルノードに外枠リング
      node.filter(d => d.id === this.focalId)
        .append('circle')
          .attr('r', d => nodeRadius(d, true) + 5)
          .attr('fill', 'none')
          .attr('stroke', '#f59e0b')
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '4,2')
          .attr('stroke-opacity', 0.8);

      // ラベル（銘柄コードまたはハブ名）
      node.append('text')
        .attr('dy', d => nodeRadius(d, d.id === this.focalId) + 10)
        .attr('text-anchor', 'middle')
        .attr('font-size', d => d.id === this.focalId ? '11px' : '9px')
        .attr('font-weight', d => d.id === this.focalId ? 'bold' : 'normal')
        .attr('fill', 'var(--bs-body-color, #333)')
        .attr('pointer-events', 'none')
        .text(d => {
          if (d.node_type !== 'diary') return d.tag_name || '';
          return d.stock_symbol || d.stock_name || '';
        });

      // ── インタラクション ────────────────────────────────────────────
      node
        .on('mouseover', (event, d) => this._showTooltip(event, d))
        .on('mousemove', (event) => this._moveTooltip(event))
        .on('mouseout',  () => this._hideTooltip())
        .on('click', (event, d) => {
          if (d.node_type === 'diary' && d.id !== this.focalId && d.url) {
            window.location.href = d.url;
          }
        });

      // ダブルクリックで固定解除
      node.on('dblclick', (event, d) => {
        d.fx = null; d.fy = null;
        sim.alpha(0.3).restart();
      });

      // ── tick ────────────────────────────────────────────────────────
      sim.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
    }

    // ── ツールチップ ────────────────────────────────────────────────
    _showTooltip(event, d) {
      let html = '';
      if (d.node_type === 'diary') {
        const isFocal = d.id === this.focalId;
        const statusLabel = { holding: '保有中', sold: '売却済', memo: 'メモ' };
        const statusColor = STATUS_COLOR[d.status] || '#aaa';
        html = `
          <div style="font-weight:bold;margin-bottom:2px;">
            ${isFocal ? '★ ' : ''}${d.stock_name || ''}
          </div>
          ${d.stock_symbol ? `<div style="color:#aaa;font-size:0.68rem;">${d.stock_symbol}</div>` : ''}
          <div style="margin-top:3px;">
            <span style="background:${statusColor};border-radius:3px;padding:1px 5px;font-size:0.68rem;">
              ${statusLabel[d.status] || d.status}
            </span>
          </div>
          ${d.realized_profit !== undefined
            ? `<div style="margin-top:3px;color:${d.realized_profit >= 0 ? '#6ee7b7' : '#fca5a5'};">
                損益: ${d.realized_profit >= 0 ? '+' : ''}${d.realized_profit.toLocaleString()}円
              </div>`
            : ''
          }`;
      } else {
        const typeLabel = { tag: 'タグ', sector: '業種', hashtag: 'ハッシュタグ' };
        html = `
          <div style="font-weight:bold;">${d.tag_name || ''}</div>
          <div style="color:#aaa;font-size:0.68rem;">${typeLabel[d.node_type] || d.node_type}</div>`;
      }

      this.tooltip.innerHTML = html;
      this.tooltip.style.display = 'block';
      this._moveTooltip(event);
    }

    _moveTooltip(event) {
      const x = event.clientX + 12;
      const y = event.clientY - 10;
      const tw = this.tooltip.offsetWidth;
      const th = this.tooltip.offsetHeight;
      this.tooltip.style.left = (x + tw > window.innerWidth  ? x - tw - 20 : x) + 'px';
      this.tooltip.style.top  = (y + th > window.innerHeight ? y - th      : y) + 'px';
    }

    _hideTooltip() {
      this.tooltip.style.display = 'none';
    }

    // ── ローディング/空表示 ─────────────────────────────────────────
    _showLoading(show) {
      this.loading.style.display = show ? 'flex' : 'none';
    }

    _showEmpty(show) {
      this.emptyMsg.style.display = show ? 'flex' : 'none';
    }
  }

  // ── 初期化 ────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    const apiUrl  = window.DIARY_DETAIL_GRAPH_API;
    const focalId = window.DIARY_FOCAL_ID;
    if (apiUrl && focalId !== undefined && typeof d3 !== 'undefined') {
      new DiaryDetailGraph(apiUrl, focalId);
    }
  });
})();

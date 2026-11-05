(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const state = {
    config: null,
    templates: [],
    strategies: [],
    currentId: null,
    dirty: false,
    running: false,
    result: null,
    hover: -1,
    chartGeo: null,
  };

  const COLORS = {
    strategy: '#35d0b4',
    benchmark: '#7a8b9f',
    grid: 'rgba(255,255,255,0.055)',
    axis: '#5d6d80',
    drawdown: '#ff6262',
  };

  // ---------------- 工具 ----------------

  const escapeHtml = (value) =>
    String(value ?? '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]));

  const fmtPct = (v, digits = 2) => `${(v * 100).toFixed(digits)}%`;
  const fmtSignedPct = (v, digits = 2) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`;
  const fmtNum = (v, digits = 2) => Number(v).toFixed(digits);
  const fmtMoney = (v) => Math.round(v).toLocaleString('zh-CN');
  const fmtInt = (v) => Math.round(v).toLocaleString('zh-CN');

  let toastTimer = null;
  function toast(message, isError = false) {
    const el = $('#toast');
    el.textContent = message;
    el.classList.toggle('err', isError);
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* ignore */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || `请求失败（HTTP ${res.status}）`);
      err.payload = data;
      throw err;
    }
    return data;
  }

  // ---------------- 初始化 ----------------

  async function init() {
    bindEvents();
    bindEditor();
    bindCharts();
    try {
      const [config, templates, strategies] = await Promise.all([
        api('/api/config'),
        api('/api/templates'),
        api('/api/strategies'),
      ]);
      state.config = config;
      state.templates = templates.templates || [];
      state.strategies = strategies.strategies || [];
      applyConfig(config);
      renderTemplates();
      renderStrategyList();
      const first = state.strategies[0];
      if (first) {
        await openStrategy(first.id, true);
      } else {
        newStrategy();
      }
    } catch (err) {
      toast(`无法连接本地服务：${err.message}`, true);
    }
  }

  function applyConfig(config) {
    const { defaults, date_range, benchmarks, universe } = config;
    $('#startDate').min = date_range.start;
    $('#startDate').max = date_range.end;
    $('#endDate').min = date_range.start;
    $('#endDate').max = date_range.end;
    $('#startDate').value = defaults.start;
    $('#endDate').value = defaults.end;
    $('#cashInput').value = defaults.cash;
    $('#benchmarkSelect').innerHTML = benchmarks
      .map((b) => `<option value="${b.code}">${escapeHtml(b.name)}</option>`)
      .join('');
    $('#benchmarkSelect').value = defaults.benchmark;
    $('#dataRange').textContent = `${date_range.start.slice(2)} ~ ${date_range.end.slice(2)}`;
    $('#dataCount').textContent = `${universe.length} 只`;
    $('#universeList').innerHTML = universe
      .map((s) => `<li><span>${escapeHtml(s.name)}</span><span>${s.code}</span></li>`)
      .join('');
  }

  function renderTemplates() {
    $('#templateSelect').innerHTML = '<option value="">载入示例策略…</option>' +
      state.templates.map((t) => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
  }

  function renderStrategyList() {
    const list = $('#strategyList');
    list.innerHTML = '';
    if (!state.strategies.length) {
      list.innerHTML = '<p style="font-size:.72rem;color:var(--faint);padding:8px 4px;">还没有保存的策略</p>';
    }
    state.strategies.forEach((s) => {
      const el = document.createElement('div');
      el.className = `strategy-item${s.id === state.currentId ? ' on' : ''}`;
      el.innerHTML = `
        <span class="s-doc"></span>
        <span class="s-main">
          <span class="s-name">${escapeHtml(s.name)}</span>
          <span class="s-date">${escapeHtml((s.updated_at || '').replace('T', ' ').slice(0, 16))}</span>
        </span>
        <button class="s-del" title="删除">×</button>`;
      el.addEventListener('click', () => openStrategy(s.id, true));
      el.querySelector('.s-del').addEventListener('click', (ev) => {
        ev.stopPropagation();
        deleteStrategy(s);
      });
      list.appendChild(el);
    });
    $('#strategyCount').textContent = state.strategies.length ? `${state.strategies.length} 个` : '';
  }

  async function loadStrategies() {
    const data = await api('/api/strategies');
    state.strategies = data.strategies || [];
    renderStrategyList();
  }

  async function openStrategy(id, autorun = false) {
    if (state.dirty && !confirm('当前策略有未保存的修改，切换后会丢失，确定继续吗？')) return;
    try {
      const data = await api(`/api/strategies/${id}`);
      const strategy = data.strategy;
      state.currentId = strategy.id;
      $('#strategyName').value = strategy.name;
      setEditorCode(strategy.code);
      setDirty(false);
      renderStrategyList();
      switchTab('code');
      closeSidebar();
      if (autorun) await runBacktest();
    } catch (err) {
      toast(err.message, true);
    }
  }

  function newStrategy() {
    if (state.dirty && !confirm('当前策略有未保存的修改，新建后会丢失，确定继续吗？')) return;
    const blank = state.templates.find((t) => t.id === 'blank') || state.templates[0];
    state.currentId = null;
    $('#strategyName').value = '未命名策略';
    setEditorCode(blank ? blank.code : '# 在这里编写策略\n');
    setDirty(true);
    renderStrategyList();
    switchTab('code');
    closeSidebar();
    const nameInput = $('#strategyName');
    nameInput.focus();
    nameInput.select();
  }

  async function saveStrategy() {
    const code = $('#editor').value;
    if (!code.trim()) { toast('策略代码为空', true); return; }
    const name = $('#strategyName').value.trim() || '未命名策略';
    try {
      const data = await api('/api/strategies', {
        method: 'POST',
        body: JSON.stringify({ id: state.currentId, name, code }),
      });
      state.currentId = data.strategy.id;
      $('#strategyName').value = data.strategy.name;
      setDirty(false);
      await loadStrategies();
      toast('策略已保存');
    } catch (err) {
      toast(err.message, true);
    }
  }

  async function deleteStrategy(strategy) {
    if (!confirm(`确定删除策略「${strategy.name}」？此操作不可恢复。`)) return;
    try {
      await api(`/api/strategies/${strategy.id}`, { method: 'DELETE' });
      if (state.currentId === strategy.id) {
        state.currentId = null;
        state.dirty = false;
      }
      await loadStrategies();
      const next = state.strategies[0];
      if (next) await openStrategy(next.id, true);
      else newStrategy();
      toast('已删除');
    } catch (err) {
      toast(err.message, true);
    }
  }

  // ---------------- 回测 ----------------

  function setRunning(running) {
    state.running = running;
    const btn = $('#runBtn');
    btn.disabled = running;
    btn.querySelector('.run-text').textContent = running ? '回测中…' : '运行回测';
  }

  async function runBacktest() {
    if (state.running) return;
    const code = $('#editor').value;
    if (!code.trim()) { toast('请先编写策略代码', true); return; }
    const start = $('#startDate').value;
    const end = $('#endDate').value;
    if (start > end) { toast('开始日期不能晚于结束日期', true); return; }

    setRunning(true);
    try {
      const data = await api('/api/backtest', {
        method: 'POST',
        body: JSON.stringify({
          code,
          start,
          end,
          cash: Number($('#cashInput').value) || 1000000,
          benchmark: $('#benchmarkSelect').value,
        }),
      });
      state.result = data.result;
      state.hover = -1;
      $('#chartTip').hidden = true;
      renderResult(data.result);
      switchTab('result');
      requestAnimationFrame(redrawCharts);
      toast(`回测完成 · ${data.result.meta.elapsed_ms} ms`);
      $('#runHint').textContent = `最近回测 ${data.result.meta.elapsed_ms} ms · ${data.result.meta.trading_days} 个交易日`;
    } catch (err) {
      const logs = (err.payload && err.payload.logs) || [];
      renderLogs(logs, err.message);
      switchTab('logs');
      toast(err.message, true);
    } finally {
      setRunning(false);
    }
  }

  // ---------------- 结果渲染 ----------------

  function renderResult(result) {
    $('#resultEmpty').hidden = true;
    $('#resultBody').hidden = false;
    renderMetrics(result);
    renderPositions(result.positions);
    renderMeta(result);
    renderMonthly(result.monthly);
    renderTrades(result.trades, result.rejected);
    renderLogs(result.logs, null);
    $('#legendBenchmark').textContent = result.meta.benchmark_name;
    const m = result.metrics;
    const range = m.drawdown_start && m.drawdown_end ? ` · ${m.drawdown_start} → ${m.drawdown_end}` : '';
    $('#mddLabel').textContent = `${fmtPct(m.max_drawdown)}${range}`;
  }

  function renderMetrics(result) {
    const m = result.metrics;
    const meta = result.meta;
    const items = [
      { label: '总收益', value: fmtSignedPct(m.total_return), tone: m.total_return >= 0 ? 'pos' : 'neg' },
      { label: '年化收益', value: fmtSignedPct(m.annual_return), tone: m.annual_return >= 0 ? 'pos' : 'neg' },
      { label: '最大回撤', value: fmtPct(m.max_drawdown), tone: 'neg' },
      { label: '夏普比率', value: fmtNum(m.sharpe), tone: '' },
      { label: '年化波动', value: fmtPct(m.volatility), tone: '' },
      { label: '卡玛比率', value: fmtNum(m.calmar), tone: '' },
      { label: '日胜率', value: fmtPct(m.win_rate, 1), tone: '' },
      { label: '基准收益', value: fmtSignedPct(m.benchmark_return), tone: m.benchmark_return >= 0 ? 'pos' : 'neg' },
      { label: '超额收益', value: fmtSignedPct(m.excess_return), tone: m.excess_return >= 0 ? 'pos' : 'neg' },
      { label: '年化换手', value: fmtPct(m.turnover), tone: '' },
      { label: '期末资产', value: fmtMoney(m.final_value), sub: '元', tone: '' },
      { label: '成交笔数', value: fmtInt(meta.trade_count), sub: `${meta.rejected_count} 笔未成交`, tone: '' },
    ];
    $('#metrics').innerHTML = items.map((it) => `
      <div class="metric ${it.tone}">
        <div class="k">${it.label}</div>
        <div class="v">${escapeHtml(it.value)}</div>
        ${it.sub ? `<div class="sub">${escapeHtml(it.sub)}</div>` : ''}
      </div>`).join('');
  }

  function renderMonthly(monthly) {
    const wrap = $('#monthlyHeatmap');
    if (!monthly || !monthly.length) { wrap.innerHTML = '<p class="card-note">暂无数据</p>'; return; }
    const byYear = {};
    let maxAbs = 0.01;
    monthly.forEach((item) => {
      byYear[item.year] = byYear[item.year] || {};
      byYear[item.year][item.month] = item.ret;
      maxAbs = Math.max(maxAbs, Math.abs(item.ret));
    });
    const years = Object.keys(byYear).sort();
    const head = `<tr><th class="year">年份</th>${Array.from({ length: 12 }, (_, i) => `<th>${i + 1}月</th>`).join('')}</tr>`;
    const rows = years.map((year) => {
      const cells = Array.from({ length: 12 }, (_, i) => {
        const ret = byYear[year][i + 1];
        if (ret === undefined) return '<td class="empty"></td>';
        const alpha = Math.min(0.5, 0.1 + (Math.abs(ret) / maxAbs) * 0.42);
        const bg = ret >= 0 ? `rgba(255,98,98,${alpha.toFixed(3)})` : `rgba(46,204,143,${alpha.toFixed(3)})`;
        const cls = ret >= 0 ? 'pos' : 'neg';
        return `<td class="${cls}" style="background:${bg}" title="${year}-${String(i + 1).padStart(2, '0')} ${fmtSignedPct(ret)}">${(ret * 100).toFixed(1)}</td>`;
      }).join('');
      return `<tr><th class="year">${year}</th>${cells}</tr>`;
    }).join('');
    wrap.innerHTML = `<table>${head}${rows}</table>`;
  }

  function renderPositions(positions) {
    const wrap = $('#positionsWrap');
    if (!positions || !positions.length) {
      wrap.innerHTML = '<p class="card-note">回测结束时为空仓。可以在策略中通过 order_target_percent 建仓。</p>';
      return;
    }
    const rows = positions.map((p) => `
      <tr>
        <td>${escapeHtml(p.name)}<br><span style="color:var(--faint);font-size:.64rem">${p.security}</span></td>
        <td>${fmtInt(p.amount)}</td>
        <td>${fmtNum(p.avg_cost, 2)}</td>
        <td>${fmtNum(p.price, 2)}</td>
        <td>${fmtMoney(p.value)}</td>
        <td class="${p.pnl >= 0 ? 'buy' : 'sell'}">${p.pnl >= 0 ? '+' : ''}${fmtMoney(p.pnl)}</td>
      </tr>`).join('');
    wrap.innerHTML = `<div class="table-wrap" style="max-height:300px">
      <table class="data">
        <thead><tr><th>标的</th><th>持仓</th><th>成本</th><th>现价</th><th>市值</th><th>浮动盈亏</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>`;
  }

  function renderMeta(result) {
    const m = result.meta;
    const items = [
      ['回测区间', `${m.start} ~ ${m.end}`],
      ['交易日', `${m.trading_days} 天`],
      ['业绩基准', `${m.benchmark_name}（${m.benchmark}）`],
      ['初始资金', `${fmtMoney(m.initial_cash)} 元`],
      ['期末资产', `${fmtMoney(result.metrics.final_value)} 元`],
      ['成交 / 未成交', `${m.trade_count} / ${m.rejected_count} 笔`],
      ['计算耗时', `${m.elapsed_ms} ms`],
      ['数据来源', '内置模拟日线'],
    ];
    $('#runMeta').innerHTML = items.map(([k, v]) => `
      <div class="meta-item"><div class="k">${k}</div><div class="v">${escapeHtml(v)}</div></div>`).join('');
  }

  function renderTrades(trades, rejected) {
    const hasTrades = trades && trades.length;
    $('#tradesEmpty').hidden = !!hasTrades;
    $('#tradesBody').hidden = !hasTrades;
    $('#tradeCount').textContent = hasTrades ? `${trades.length} 笔` : '';

    if (hasTrades) {
      const rows = trades.map((t) => `
        <tr>
          <td>${t.date}</td>
          <td class="name">${escapeHtml(t.name)}</td>
          <td class="${t.side === '买入' ? 'buy' : 'sell'}">${t.side}</td>
          <td>${fmtInt(t.amount)}</td>
          <td>${fmtNum(t.price, 2)}</td>
          <td>${fmtMoney(t.value)}</td>
          <td>${fmtNum(t.fee, 2)}</td>
          <td>${fmtMoney(t.cash)}</td>
        </tr>`).join('');
      $('#tradesTable').innerHTML = `<table class="data">
        <thead><tr><th>日期</th><th>标的</th><th>方向</th><th>数量</th><th>成交价</th><th>金额</th><th>费用</th><th>现金余额</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    }

    if (rejected && rejected.length) {
      $('#rejectedCard').hidden = false;
      $('#rejectedCount').textContent = `${rejected.length} 笔`;
      $('#rejectedTable').innerHTML = `<table class="data">
        <thead><tr><th>日期</th><th>标的</th><th>方向</th><th>数量</th><th>原因</th></tr></thead>
        <tbody>${rejected.map((r) => `<tr>
          <td>${r.date}</td><td class="name">${escapeHtml(r.name)}</td>
          <td class="${r.side === '买入' ? 'buy' : 'sell'}">${r.side}</td>
          <td>${fmtInt(r.amount)}</td><td class="name">${escapeHtml(r.reason)}</td></tr>`).join('')}</tbody></table>`;
    } else {
      $('#rejectedCard').hidden = true;
    }
  }

  function renderLogs(logs, errorMessage) {
    const hasLogs = (logs && logs.length) || errorMessage;
    $('#logsEmpty').hidden = !!hasLogs;
    $('#logsBody').hidden = !hasLogs;
    if (!hasLogs) return;
    const items = [];
    if (errorMessage) items.push({ date: '', level: 'error', message: `回测失败：${errorMessage}` });
    (logs || []).forEach((l) => items.push(l));
    $('#logCount').textContent = `${items.length} 条`;
    $('#logList').innerHTML = items.map((l) => `
      <div class="log-line ${l.level || 'info'}">
        <span class="d">${escapeHtml(l.date || '')}</span>
        <span class="m">${escapeHtml(l.message)}</span>
      </div>`).join('');
  }

  // ---------------- 图表 ----------------

  function prepCanvas(canvas) {
    const box = canvas.parentElement;
    const w = Math.max(280, box.clientWidth);
    const h = Math.max(120, box.clientHeight);
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  function niceDate(day) {
    return day ? `${day.slice(0, 4)}-${day.slice(5, 7)}` : '';
  }

  function drawEquity(hover = -1) {
    if (!state.result) return;
    const canvas = $('#equityChart');
    const { ctx, w, h } = prepCanvas(canvas);
    const { dates, strategy, benchmark } = state.result.equity;
    const n = dates.length;
    if (!n) return;
    const pad = { l: 56, r: 16, t: 16, b: 26 };
    let min = Infinity;
    let max = -Infinity;
    for (const arr of [strategy, benchmark]) {
      for (const v of arr) { if (v < min) min = v; if (v > max) max = v; }
    }
    const span = Math.max(max - min, 0.02);
    min -= span * 0.08;
    max += span * 0.08;
    const plotW = w - pad.l - pad.r;
    const plotH = h - pad.t - pad.b;
    const X = (i) => pad.l + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const Y = (v) => pad.t + (1 - (v - min) / (max - min)) * plotH;

    ctx.clearRect(0, 0, w, h);
    ctx.font = '10px ui-monospace, Menlo, monospace';
    ctx.textBaseline = 'middle';

    // 网格与 Y 轴
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i += 1) {
      const v = min + (max - min) * (i / 4);
      const y = Math.round(Y(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(w - pad.r, y);
      ctx.stroke();
      ctx.fillStyle = COLORS.axis;
      ctx.textAlign = 'right';
      ctx.fillText(`${((v - 1) * 100).toFixed(1)}%`, pad.l - 8, y);
    }

    // X 轴日期
    const ticks = 6;
    ctx.textAlign = 'center';
    ctx.fillStyle = COLORS.axis;
    for (let i = 0; i < ticks; i += 1) {
      const idx = Math.round((i / (ticks - 1)) * (n - 1));
      const x = X(idx);
      if (i === 0) ctx.textAlign = 'left';
      else if (i === ticks - 1) ctx.textAlign = 'right';
      else ctx.textAlign = 'center';
      ctx.fillText(niceDate(dates[idx]), x, h - 10);
    }

    // 策略面积
    const grad = ctx.createLinearGradient(0, pad.t, 0, h - pad.b);
    grad.addColorStop(0, 'rgba(53,208,180,0.18)');
    grad.addColorStop(1, 'rgba(53,208,180,0)');
    ctx.beginPath();
    ctx.moveTo(X(0), Y(strategy[0]));
    for (let i = 1; i < n; i += 1) ctx.lineTo(X(i), Y(strategy[i]));
    ctx.lineTo(X(n - 1), h - pad.b);
    ctx.lineTo(X(0), h - pad.b);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // 基准线
    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = COLORS.benchmark;
    ctx.lineWidth = 1.2;
    for (let i = 0; i < n; i += 1) {
      const x = X(i); const y = Y(benchmark[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // 策略线
    ctx.beginPath();
    ctx.strokeStyle = COLORS.strategy;
    ctx.lineWidth = 1.7;
    ctx.lineJoin = 'round';
    for (let i = 0; i < n; i += 1) {
      const x = X(i); const y = Y(strategy[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    state.chartGeo = { X, Y, n, pad, w, h };

    if (hover >= 0 && hover < n) {
      const x = X(hover);
      ctx.strokeStyle = 'rgba(255,255,255,0.2)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, pad.t);
      ctx.lineTo(x, h - pad.b);
      ctx.stroke();
      [[strategy[hover], COLORS.strategy], [benchmark[hover], COLORS.benchmark]].forEach(([v, color]) => {
        ctx.beginPath();
        ctx.fillStyle = color;
        ctx.arc(x, Y(v), 3.2, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  }

  function drawDrawdown() {
    if (!state.result) return;
    const canvas = $('#drawdownChart');
    const { ctx, w, h } = prepCanvas(canvas);
    const { dates, drawdown } = state.result.equity;
    const n = dates.length;
    if (!n) return;
    const pad = { l: 56, r: 16, t: 12, b: 22 };
    const plotW = w - pad.l - pad.r;
    const plotH = h - pad.t - pad.b;
    const min = Math.min(...drawdown, -0.005) * 1.12;
    const X = (i) => pad.l + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const Y = (v) => pad.t + (1 - (v - min) / (0 - min)) * plotH;

    ctx.clearRect(0, 0, w, h);
    ctx.font = '10px ui-monospace, Menlo, monospace';
    ctx.textBaseline = 'middle';

    ctx.strokeStyle = COLORS.grid;
    for (let i = 0; i <= 2; i += 1) {
      const v = min * (i / 2);
      const y = Math.round(Y(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(w - pad.r, y);
      ctx.stroke();
      ctx.fillStyle = COLORS.axis;
      ctx.textAlign = 'right';
      ctx.fillText(`${(v * 100).toFixed(1)}%`, pad.l - 8, y);
    }

    ctx.beginPath();
    ctx.moveTo(X(0), Y(0));
    for (let i = 0; i < n; i += 1) ctx.lineTo(X(i), Y(drawdown[i]));
    ctx.lineTo(X(n - 1), Y(0));
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, pad.t, 0, h - pad.b);
    grad.addColorStop(0, 'rgba(255,98,98,0.03)');
    grad.addColorStop(1, 'rgba(255,98,98,0.28)');
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    ctx.strokeStyle = COLORS.drawdown;
    ctx.lineWidth = 1.3;
    for (let i = 0; i < n; i += 1) {
      const x = X(i); const y = Y(drawdown[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.fillStyle = COLORS.axis;
    ctx.textAlign = 'left';
    ctx.fillText(niceDate(dates[0]), pad.l, h - 7);
    ctx.textAlign = 'right';
    ctx.fillText(niceDate(dates[n - 1]), w - pad.r, h - 7);
  }

  function redrawCharts() {
    if (!state.result) return;
    const box = $('#equityBox');
    if (!box.clientWidth) return;
    drawEquity(state.hover);
    drawDrawdown();
  }

  function bindCharts() {
    const box = $('#equityBox');
    const tip = $('#chartTip');
    box.addEventListener('mousemove', (ev) => {
      if (!state.result || !state.chartGeo) return;
      const geo = state.chartGeo;
      const rect = box.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const ratio = (x - geo.pad.l) / Math.max(1, geo.w - geo.pad.l - geo.pad.r);
      const idx = Math.max(0, Math.min(geo.n - 1, Math.round(ratio * (geo.n - 1))));
      state.hover = idx;
      drawEquity(idx);

      const { dates, strategy, benchmark, drawdown } = state.result.equity;
      const sx = geo.X(idx);
      const sy = geo.Y(strategy[idx]);
      tip.innerHTML = `
        <div class="tip-date">${dates[idx]}</div>
        <div class="tip-row"><span>策略</span><b style="color:${COLORS.strategy}">${fmtSignedPct(strategy[idx] - 1)}</b></div>
        <div class="tip-row"><span>基准</span><b style="color:#9aabbf">${fmtSignedPct(benchmark[idx] - 1)}</b></div>
        <div class="tip-row"><span>回撤</span><b style="color:${COLORS.drawdown}">${fmtPct(drawdown[idx])}</b></div>`;
      tip.hidden = false;
      const tipW = tip.offsetWidth || 150;
      const left = sx + 14 + tipW > geo.w ? sx - tipW - 14 : sx + 14;
      const top = Math.max(4, Math.min(sy - 20, geo.h - (tip.offsetHeight || 90) - 6));
      tip.style.left = `${left}px`;
      tip.style.top = `${top}px`;
    });
    box.addEventListener('mouseleave', () => {
      state.hover = -1;
      tip.hidden = true;
      drawEquity(-1);
    });

    const observer = new ResizeObserver(() => {
      if (state.result) requestAnimationFrame(redrawCharts);
    });
    observer.observe(box);
  }

  // ---------------- 编辑器 ----------------

  function setEditorCode(code) {
    $('#editor').value = code;
    updateGutter();
    updateCursor();
    $('#editor').scrollTop = 0;
    $('#gutter').scrollTop = 0;
  }

  function updateGutter() {
    const editor = $('#editor');
    const count = editor.value.split('\n').length;
    $('#gutter').textContent = Array.from({ length: Math.max(count, 1) }, (_, i) => i + 1).join('\n');
  }

  function updateCursor() {
    const editor = $('#editor');
    const pos = editor.selectionStart;
    const line = editor.value.slice(0, pos).split('\n').length;
    $('#cursorPos').textContent = `第 ${line} 行`;
  }

  function setDirty(dirty) {
    state.dirty = dirty;
    $('#dirtyDot').classList.toggle('on', dirty);
  }

  function bindEditor() {
    const editor = $('#editor');
    editor.addEventListener('input', () => {
      updateGutter();
      updateCursor();
      setDirty(true);
    });
    editor.addEventListener('scroll', () => {
      $('#gutter').scrollTop = editor.scrollTop;
    });
    editor.addEventListener('click', updateCursor);
    editor.addEventListener('keyup', updateCursor);
    editor.addEventListener('keydown', (ev) => {
      if (ev.key === 'Tab') {
        ev.preventDefault();
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        editor.setRangeText('    ', start, end, 'end');
        updateGutter();
        setDirty(true);
      }
    });
    $('#strategyName').addEventListener('input', () => setDirty(true));
  }

  // ---------------- 交互 ----------------

  function switchTab(name) {
    $$('.tab').forEach((btn) => btn.classList.toggle('on', btn.dataset.tab === name));
    $$('.tab-panel').forEach((panel) => panel.classList.toggle('on', panel.id === `tab-${name}`));
    if (name === 'result') requestAnimationFrame(redrawCharts);
  }

  function openSidebar() {
    $('#sidebar').classList.add('open');
    $('#scrim').classList.add('on');
  }

  function closeSidebar() {
    $('#sidebar').classList.remove('open');
    $('#scrim').classList.remove('on');
  }

  function bindEvents() {
    $$('.tab').forEach((btn) => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));
    $('#runBtn').addEventListener('click', runBacktest);
    $('#saveBtn').addEventListener('click', saveStrategy);
    $('#newStrategyBtn').addEventListener('click', newStrategy);
    $('#menuBtn').addEventListener('click', openSidebar);
    $('#closeSidebar').addEventListener('click', closeSidebar);
    $('#scrim').addEventListener('click', closeSidebar);

    $('#templateSelect').addEventListener('change', (ev) => {
      const tpl = state.templates.find((t) => t.id === ev.target.value);
      ev.target.value = '';
      if (!tpl) return;
      if (state.dirty && !confirm('载入示例会覆盖当前编辑器内容，确定继续吗？')) return;
      setEditorCode(tpl.code);
      setDirty(true);
      switchTab('code');
      toast(`已载入示例：${tpl.name}`);
    });

    $('#apiBtn').addEventListener('click', () => { $('#apiModal').hidden = false; });
    $('#closeApi').addEventListener('click', () => { $('#apiModal').hidden = true; });
    $('#apiModal').addEventListener('click', (ev) => {
      if (ev.target.id === 'apiModal') $('#apiModal').hidden = true;
    });

    document.addEventListener('keydown', (ev) => {
      const cmd = ev.metaKey || ev.ctrlKey;
      if (cmd && ev.key === 'Enter') {
        ev.preventDefault();
        runBacktest();
      } else if (cmd && ev.key.toLowerCase() === 's') {
        ev.preventDefault();
        saveStrategy();
      } else if (ev.key === 'Escape') {
        $('#apiModal').hidden = true;
        closeSidebar();
      }
    });

    window.addEventListener('beforeunload', (ev) => {
      if (!state.dirty) return;
      ev.preventDefault();
      ev.returnValue = '';
    });

    window.addEventListener('resize', () => {
      if (state.result) requestAnimationFrame(redrawCharts);
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();

/* ═══════════════════════════════════════════════════════════════════════════
   Stratzy Algo Scanner — Frontend App
═══════════════════════════════════════════════════════════════════════════ */

const API = '';  // same origin

// Categories to show in the scanner (edit this list to add/remove)
const DEFAULT_CATEGORIES = ['Option Buying', 'Credit Spread', 'Short Strangle', 'Short Straddle'];

// Categories hidden from the picker entirely
const EXCLUDED_CATEGORIES = ['Investing', 'Swing', 'Intraday Cash', 'Index Strategies', 'futures buying', 'Ratio Spread', 'Iron Condor', 'Batman Spread'];

let state = {
  username: '',
  algos: [],
  scanResults: [],
  filteredResults: [],
  watchlist: JSON.parse(localStorage.getItem('stratzy_watchlist') || '[]'),
  selectedCategories: [...DEFAULT_CATEGORIES],
  sortCol: 'score',
  sortDir: 'desc',
  scanInterval: null,
  dhan: {
    analytics: null,
    trades: [],
    filteredTrades: [],
    activeTab: 'csv',
    connected: false,
  },
  overlapData: null,
  selectedOverlapTimeframe: '1M',
  institutionalTopPicks: [],
};

/* ══════════════════════════════════════════════════════════════════════════
   AUTH
══════════════════════════════════════════════════════════════════════════ */
async function doLogin() {
  const cookie = document.getElementById('cookie-input').value.trim();
  const errorEl = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');

  if (!cookie) {
    showError(errorEl, 'Please paste your session cookie.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="btn-text">Connecting...</span>';
  errorEl.classList.add('hidden');

  try {
    const res = await fetch(`${API}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookie }),
    });
    const data = await res.json();

    if (data.success) {
      state.username = data.name || 'User';
      document.getElementById('user-name').textContent = state.username;
      document.getElementById('user-avatar').textContent = state.username[0].toUpperCase();
      showApp();
      loadAlgos();
    } else {
      showError(errorEl, data.message || 'Login failed.');
    }
  } catch (e) {
    showError(errorEl, 'Could not connect to the scanner server. Make sure server.py is running on port 5050.');
  }

  btn.disabled = false;
  btn.innerHTML = '<span class="btn-text">Connect to Stratzy</span><svg class="btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
}

async function doLogout() {
  await fetch(`${API}/api/logout`, { method: 'POST' });
  document.getElementById('app-screen').classList.remove('active');
  document.getElementById('login-screen').classList.add('active');
  document.getElementById('cookie-input').value = '';
  state.algos = [];
  state.scanResults = [];
}

function showApp() {
  document.getElementById('login-screen').classList.remove('active');
  document.getElementById('app-screen').classList.add('active');
  // Pre-warm institutional top picks and portfolio trade overlap analysis
  loadInstitutionalTopPicks();
  loadOverlapAnalysis(state.selectedOverlapTimeframe || '1M');
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove('hidden');
}

/* ══════════════════════════════════════════════════════════════════════════
   VIEWS
══════════════════════════════════════════════════════════════════════════ */
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`view-${name}`)?.classList.add('active');
  document.querySelector(`[data-view="${name}"]`)?.classList.add('active');

  if (name === 'results') {
    if (!state.institutionalTopPicks || state.institutionalTopPicks.length === 0) {
      loadInstitutionalTopPicks();
    }
    if (!state.overlapData) {
      loadOverlapAnalysis(state.selectedOverlapTimeframe || '1M');
    }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   LOAD ALGOS
══════════════════════════════════════════════════════════════════════════ */
async function loadAlgos() {
  const btn = document.getElementById('load-algos-btn');
  btn.disabled = true;
  btn.textContent = 'Loading...';

  try {
    const res = await fetch(`${API}/api/algos`);
    const data = await res.json();

    if (data.success) {
      state.algos = data.algos;
      renderCategoryChips(state.algos);
      // Update count for default selection
      const defLower = DEFAULT_CATEGORIES.map(c => c.toLowerCase());
      const defaultCount = data.algos.filter(a =>
        defLower.includes(((a.displayCategory || a.category || '')).trim().toLowerCase())
      ).length;
      document.getElementById('algo-count-text').textContent =
        `${defaultCount} algos selected (${DEFAULT_CATEGORIES.join(', ')})  ·  ${data.count} total`;
    }
  } catch (e) {
    document.getElementById('algo-count-text').textContent = 'Failed to load algos';
  }

  btn.disabled = false;
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.63"/></svg> Refresh Algos`;
}

function renderCategoryChips(algos) {
  const catCounts = {};
  const excLower = EXCLUDED_CATEGORIES.map(c => c.toLowerCase());
  algos.forEach(a => {
    const cat = a.displayCategory || a.category || 'Other';
    // Skip excluded categories entirely
    if (!excLower.includes(cat.trim().toLowerCase())) {
      catCounts[cat] = (catCounts[cat] || 0) + 1;
    }
  });

  const container = document.getElementById('category-chips');
  container.innerHTML = '';

  const selLower = state.selectedCategories.map(c => c.toLowerCase());
  // Render chips — default selection is the 4 preferred categories
  Object.entries(catCounts).sort((a, b) => b[1] - a[1]).forEach(([cat, count]) => {
    const chip = document.createElement('div');
    const isSelected = selLower.includes(cat.trim().toLowerCase());
    chip.className = `chip${isSelected ? ' selected' : ''}`;
    chip.dataset.cat = cat;
    chip.innerHTML = `${cat} <span class="chip-count">${count}</span>`;
    chip.onclick = () => toggleCategory(cat);
    container.appendChild(chip);
  });

  // Also populate the cat filter dropdown in results (only non-excluded)
  const catFilter = document.getElementById('cat-filter');
  catFilter.innerHTML = '<option value="">All Categories</option>';
  Object.keys(catCounts).sort().forEach(cat => {
    catFilter.innerHTML += `<option value="${cat}">${cat}</option>`;
  });
}

function toggleCategory(cat) {
  const chips = document.querySelectorAll('.chip');

  const catLower = cat.trim().toLowerCase();
  const idx = state.selectedCategories.findIndex(c => c.trim().toLowerCase() === catLower);
  if (idx >= 0) {
    state.selectedCategories.splice(idx, 1);
  } else {
    state.selectedCategories.push(cat);
  }

  const currentSelLower = state.selectedCategories.map(c => c.toLowerCase());
  chips.forEach(c => {
    c.classList.toggle('selected', currentSelLower.includes(c.dataset.cat.trim().toLowerCase()));
  });

  // Update count
  let relevant = state.algos;
  if (state.selectedCategories.length > 0) {
    relevant = state.algos.filter(a =>
      currentSelLower.includes(((a.displayCategory || a.category || '')).trim().toLowerCase())
    );
  }
  document.getElementById('algo-count-text').textContent =
    `${relevant.length} algos selected for scan`;
}

/* ══════════════════════════════════════════════════════════════════════════
   SCAN
══════════════════════════════════════════════════════════════════════════ */
async function startScan() {
  const btn = document.getElementById('start-scan-btn');
  const cancelBtn = document.getElementById('cancel-scan-btn');

  btn.disabled = true;
  cancelBtn.classList.remove('hidden');

  document.getElementById('progress-section').classList.remove('hidden');
  document.getElementById('scan-status-pill').classList.remove('hidden');

  const body = {};
  if (state.selectedCategories.length > 0) {
    body.categories = state.selectedCategories;
  }

  try {
    const res = await fetch(`${API}/api/scan/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (data.success) {
      state.scanInterval = setInterval(pollScanStatus, 1000);
    } else {
      alert(data.message || 'Failed to start scan');
      btn.disabled = false;
      cancelBtn.classList.add('hidden');
    }
  } catch (e) {
    alert('Error starting scan: ' + e.message);
    btn.disabled = false;
    cancelBtn.classList.add('hidden');
  }
}

async function cancelScan() {
  await fetch(`${API}/api/scan/cancel`, { method: 'POST' });
  clearInterval(state.scanInterval);
  resetScanUI();
}

function resetScanUI() {
  document.getElementById('start-scan-btn').disabled = false;
  document.getElementById('cancel-scan-btn').classList.add('hidden');
  document.getElementById('scan-status-pill').classList.add('hidden');
}

async function pollScanStatus() {
  try {
    const res = await fetch(`${API}/api/scan/status`);
    const data = await res.json();

    const pct = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;

    document.getElementById('progress-bar').style.width = `${pct}%`;
    document.getElementById('progress-pct').textContent = `${pct}%`;
    document.getElementById('progress-count').textContent = `${data.progress} / ${data.total}`;
    document.getElementById('scan-status-text').textContent = `Scanning ${data.progress}/${data.total}...`;

    const logEl = document.getElementById('progress-log');
    if (data.log && data.log.length > 0) {
      logEl.textContent = data.log.join('\n');
      logEl.scrollTop = logEl.scrollHeight;
    }

    if (data.status === 'done' || data.status === 'cancelled') {
      clearInterval(state.scanInterval);
      resetScanUI();
      document.getElementById('scan-status-pill').classList.add('hidden');

      // Fetch results
      await loadResults();
      showView('results');
    }
  } catch (e) {
    console.error('Poll error:', e);
  }
}

async function loadResults() {
  try {
    const res = await fetch(`${API}/api/scan/results`);
    const data = await res.json();

    if (data.success && data.results.length > 0) {
      state.scanResults = data.results;
      state.filteredResults = [...data.results];

      renderResults(state.filteredResults);
      renderTopPicks(state.filteredResults);

      const badge = document.getElementById('results-badge');
      badge.textContent = data.count;
      badge.style.display = 'inline-block';

      const lastScan = data.lastScan ? new Date(data.lastScan).toLocaleString('en-IN') : '';
      document.getElementById('results-subtitle').textContent =
        `${data.count} strategies scanned${lastScan ? ` · Last scan: ${lastScan}` : ''}`;

      document.getElementById('export-btn').style.display = 'inline-flex';
    }
  } catch (e) {
    console.error('Load results error:', e);
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   RESULTS RENDERING
══════════════════════════════════════════════════════════════════════════ */
function getAlgoScore(algo) {
  if (typeof algo.institutionalScore === 'number') return algo.institutionalScore;
  if (algo.institutionalScore !== undefined && algo.institutionalScore !== null) {
    const parsed = parseFloat(algo.institutionalScore);
    if (!isNaN(parsed)) return parsed;
  }
  if (typeof algo.algoScore === 'number') return algo.algoScore;
  if (algo.algoScore !== undefined && algo.algoScore !== null) {
    const parsed = parseFloat(algo.algoScore);
    if (!isNaN(parsed)) return parsed;
  }
  return 0;
}

function get1MReturn(algo) {
  return algo.metrics?.['1M']?.booksizeReturn ?? algo.oneMonthPnl ?? null;
}
function get3MReturn(algo) {
  return algo.metrics?.['3M']?.booksizeReturn ?? algo.threeMonthPnl ?? null;
}
function get6MReturn(algo) {
  return algo.metrics?.['6M']?.booksizeReturn ?? algo.sixMonthPnl ?? null;
}
function get1YReturn(algo) {
  return algo.metrics?.['1Y']?.booksizeReturn ?? algo.oneYearPnl ?? null;
}
function getWinRatio(algo) {
  return algo.metrics?.['1Y']?.winRatio ?? algo.winRatio ?? null;
}
function getSharpe(algo) {
  const qs = algo.quantStats;
  if (qs?.['Sharpe Ratio']) {
    return parseFloat(qs['Sharpe Ratio']);
  }
  return algo.sharpeRatio ?? null;
}
function getDrawdown(algo) {
  const ps = algo.performanceSummary;
  if (ps?.['Max Drawdown']) {
    return parseFloat(ps['Max Drawdown'].replace('%', ''));
  }
  return algo.maxDrawdown ?? algo.drawDown ?? null;
}
function getRisk(algo) {
  return algo.performanceSummary?.['Risk'] ?? algo.risk ?? '';
}

function fmtPct(val) {
  if (val === null || val === undefined) return '<span class="val-neu">—</span>';
  const n = parseFloat(val);
  const cls = n > 0 ? 'val-pos' : n < 0 ? 'val-neg' : 'val-neu';
  return `<span class="${cls}">${n > 0 ? '+' : ''}${n.toFixed(1)}%</span>`;
}

function fmtNum(val, decimals = 2) {
  if (val === null || val === undefined) return '<span class="val-neu">—</span>';
  const n = parseFloat(val);
  return `<span class="val-neu">${n.toFixed(decimals)}</span>`;
}

function scoreClass(s) {
  const n = parseFloat(s);
  if (n >= 7) return 'score-high';
  if (n >= 4) return 'score-mid';
  return 'score-low';
}

function riskClass(r) {
  if (!r) return '';
  const map = { 'Low': 'risk-low', 'Medium': 'risk-medium', 'High': 'risk-high', 'Very High': 'risk-very-high' };
  return map[r] || '';
}

function rankBadge(i) {
  if (i === 0) return '<span class="rank-badge rank-1">1</span>';
  if (i === 1) return '<span class="rank-badge rank-2">2</span>';
  if (i === 2) return '<span class="rank-badge rank-3">3</span>';
  return `<span class="rank-badge rank-n">${i + 1}</span>`;
}

function applyFiltersAndSort(results) {
  const search = (document.getElementById('results-search')?.value || '').toLowerCase();
  const catF = document.getElementById('cat-filter')?.value || '';
  const riskF = document.getElementById('risk-filter')?.value || '';
  const minWR = parseFloat(document.getElementById('min-win-ratio')?.value);
  const minSharpe = parseFloat(document.getElementById('min-sharpe')?.value);
  const maxDD = parseFloat(document.getElementById('max-drawdown')?.value);
  const min1M = parseFloat(document.getElementById('min-1m-return')?.value);

  let filtered = results.filter(a => {
    if (search && !a.name?.toLowerCase().includes(search)) return false;
    const cat = a.displayCategory || a.category || '';
    if (catF && cat !== catF) return false;
    if (riskF && getRisk(a) !== riskF) return false;
    if (!isNaN(minWR) && (getWinRatio(a) ?? 0) < minWR) return false;
    if (!isNaN(minSharpe) && (getSharpe(a) ?? 0) < minSharpe) return false;
    if (!isNaN(maxDD)) {
      const dd = getDrawdown(a);
      if (dd !== null && dd < maxDD) return false;
    }
    if (!isNaN(min1M) && (get1MReturn(a) ?? -999) < min1M) return false;
    return true;
  });

  // Sort
  const col = state.sortCol;
  const dir = state.sortDir === 'desc' ? -1 : 1;
  filtered.sort((a, b) => {
    let va, vb;
    switch (col) {
      case 'name': va = a.name || ''; vb = b.name || ''; return dir * va.localeCompare(vb);
      case 'score': va = getAlgoScore(a) ?? 0; vb = getAlgoScore(b) ?? 0; break;
      case '1m': va = get1MReturn(a) ?? -999; vb = get1MReturn(b) ?? -999; break;
      case '3m': va = get3MReturn(a) ?? -999; vb = get3MReturn(b) ?? -999; break;
      case '6m': va = get6MReturn(a) ?? -999; vb = get6MReturn(b) ?? -999; break;
      case '1y': va = get1YReturn(a) ?? -999; vb = get1YReturn(b) ?? -999; break;
      case 'winRatio': va = getWinRatio(a) ?? 0; vb = getWinRatio(b) ?? 0; break;
      case 'sharpe': va = getSharpe(a) ?? 0; vb = getSharpe(b) ?? 0; break;
      case 'drawdown': va = getDrawdown(a) ?? -999; vb = getDrawdown(b) ?? -999; break;
      default: va = 0; vb = 0;
    }
    return dir * (va - vb);
  });

  return filtered;
}

function renderResults(results) {
  const filtered = applyFiltersAndSort(results);
  state.filteredResults = filtered;

  const tbody = document.getElementById('results-tbody');
  if (filtered.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="13">
      <div class="empty-state"><div class="empty-icon">🔍</div><p>No strategies match your filters</p></div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((algo, i) => {
    const score = getAlgoScore(algo);
    const cat = algo.displayCategory || algo.category || '—';
    const risk = getRisk(algo);
    const isStarred = state.watchlist.some(w => w._id === algo._id);

    return `<tr>
      <td>${rankBadge(i)}</td>
      <td class="algo-name" title="${algo.name}">
        <a href="https://stratzy.in/algo-trading-strategies/${(algo.shareLink || '').split('/').pop() || algo._id}" target="_blank">${algo.name}</a>
      </td>
      <td><span class="cat-tag">${cat}</span></td>
      <td><span class="score-pill ${scoreClass(score)}">${score !== null ? parseFloat(score).toFixed(1) : '—'}</span></td>
      <td>${fmtPct(get1MReturn(algo))}</td>
      <td>${fmtPct(get3MReturn(algo))}</td>
      <td>${fmtPct(get6MReturn(algo))}</td>
      <td>${fmtPct(get1YReturn(algo))}</td>
      <td>${getWinRatio(algo) !== null ? `<span class="val-neu">${parseFloat(getWinRatio(algo)).toFixed(1)}%</span>` : '<span class="val-neu">—</span>'}</td>
      <td>${fmtNum(getSharpe(algo))}</td>
      <td>${fmtPct(getDrawdown(algo))}</td>
      <td><span class="risk-badge ${riskClass(risk)}">${risk || '—'}</span></td>
      <td>
        <div class="action-btns">
          <button class="icon-btn ${isStarred ? 'starred' : ''}" title="Add to watchlist" onclick="toggleWatchlist('${algo._id}', this)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="${isStarred ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          </button>
          <button class="icon-btn" title="View details" onclick="openDetail('${algo._id}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          </button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function filterResults() {
  renderResults(state.scanResults);
  renderTopPicks(state.filteredResults);
}

function sortTable(col) {
  if (state.sortCol === col) {
    state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
  } else {
    state.sortCol = col;
    state.sortDir = 'desc';
  }
  renderResults(state.scanResults);
}

/* ══════════════════════════════════════════════════════════════════════════
   TOP PICKS
══════════════════════════════════════════════════════════════════════════ */
/* ══════════════════════════════════════════════════════════════════════════
   INSTITUTIONAL TOP PICKS (25-PARAMETER ENGINE)
══════════════════════════════════════════════════════════════════════════ */
async function loadInstitutionalTopPicks() {
  try {
    const res = await fetch(`${API}/api/algo/top-picks`);
    const data = await res.json();
    if (data.success && data.selectedAlgos && data.selectedAlgos.length > 0) {
      state.institutionalTopPicks = data.selectedAlgos;
      renderInstitutionalTopPicks(data.selectedAlgos);
      return;
    }
  } catch (e) {
    console.warn('Failed to load institutional top picks from API:', e);
  }

  // Fallback to local scan results if API fails
  if (state.scanResults && state.scanResults.length > 0) {
    renderTopPicksFallback(state.scanResults);
  }
}

function renderInstitutionalTopPicks(algos) {
  const section = document.getElementById('top-picks');
  const grid = document.getElementById('top-picks-grid');
  if (!section || !grid) return;

  if (!algos || algos.length === 0) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');

  grid.innerHTML = algos.map((algo, i) => {
    const rank = algo.rank || (i + 1);
    const sharpe = algo.sharpe !== undefined ? algo.sharpe.toFixed(2) : '—';
    const sortino = algo.sortino !== undefined ? algo.sortino.toFixed(2) : '—';
    const calmar = algo.calmar !== undefined ? algo.calmar.toFixed(2) : '—';
    const maxDdNum = algo.maxDrawdown !== undefined ? Math.abs(algo.maxDrawdown) : 0;
    const trades3M = algo.trades3M || 0;
    const winMonth = algo.winMonth ? algo.winMonth.toFixed(0) + '%' : '—';
    const overlapTrades = algo.heldOverlapTrades !== undefined ? algo.heldOverlapTrades : 0;
    const overlapBadge = overlapTrades === 0
      ? '<span style="color:#10b981; font-weight:700;">🟢 0 Held Overlap</span>'
      : `<span style="color:#f59e0b; font-weight:700;">🟡 ${overlapTrades} Overlap</span>`;
    const calmarWarn = algo.calmar !== undefined && algo.calmar < 2.0;
    const ddWarn = maxDdNum >= 20.0;

    const pnlVals = [['3M', algo.pnl3M], ['6M', algo.pnl6M], ['1Y', algo.pnl1Y]];
    const pnlRow = pnlVals.map(([period, val]) => {
      const num = val !== undefined && val !== null ? Number(val) : null;
      const fmt = num !== null ? (num >= 0 ? '+' : '') + num.toFixed(1) + '%' : '—';
      const color = num !== null ? (num > 0 ? '#10b981' : num < 0 ? '#ef4444' : '#9ca3af') : '#6b7280';
      return `<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:5px 6px;text-align:center;"><div style="color:${color};font-size:12px;font-weight:700;">${fmt}</div><div style="color:#6b7280;font-size:10px;">${period} PnL</div></div>`;
    }).join('');

    return `
      <div class="pick-card" onclick="openDetail('${algo.id}')">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div class="pick-rank">⭐ Rank #${rank} Pick</div>
          <span class="pick-inst-score-tag">🏆 ${algo.institutionalScore}/100</span>
        </div>
        <div class="pick-name" style="margin-top:8px;">${algo.name}</div>
        <div class="pick-cat">${algo.category} &middot; ${algo.familyGroup || 'Diversifier'} &middot; <strong style="color:#10b981;">₹${(algo.minCapital || 100000).toLocaleString('en-IN')} Cap</strong></div>

        <!-- 4-Stat Pillar Grid -->
        <div class="pick-stats" style="grid-template-columns: repeat(4, 1fr); margin-top:12px;">
          <div class="pick-stat-item">
            <div class="pick-stat-val ${algo.sharpe >= 1.5 ? 'val-pos' : 'val-neu'}">${sharpe}</div>
            <div class="pick-stat-label">Sharpe</div>
          </div>
          <div class="pick-stat-item">
            <div class="pick-stat-val val-pos">${sortino}</div>
            <div class="pick-stat-label">Sortino</div>
          </div>
          <div class="pick-stat-item">
            <div class="pick-stat-val ${algo.calmar >= 2 ? 'val-pos' : 'val-neu'}">${calmar}${calmarWarn ? ' ⚠️' : ''}</div>
            <div class="pick-stat-label">Calmar</div>
          </div>
          <div class="pick-stat-item">
            <div class="pick-stat-val ${ddWarn ? 'val-neu' : 'val-pos'}">${maxDdNum.toFixed(1)}%${ddWarn ? ' ⚠️' : ''}</div>
            <div class="pick-stat-label">Max DD</div>
          </div>
        </div>

        <!-- PnL Consistency Row (Rule 10: all 3 must be positive) -->
        <div style="margin-top:10px; display:grid; grid-template-columns:repeat(3,1fr); gap:6px;">
          ${pnlRow}
        </div>

        <!-- Consistency & Sample Size Strip -->
        <div style="margin-top:8px; padding:8px 10px; background:rgba(255,255,255,0.03); border-radius:6px; font-size:11px; display:flex; justify-content:space-between; align-items:center; border:1px solid rgba(255,255,255,0.05);">
          <span>📊 <strong>${trades3M}</strong> 3M Trades${trades3M < 20 ? ' ⚠️' : ''}</span>
          <span>🎯 <strong>${winMonth}</strong> Win-M</span>
          <span>${overlapBadge}</span>
        </div>

        <!-- View 25-Parameter Due Diligence Button -->
        <button class="pick-checklist-btn" onclick="event.stopPropagation(); openInstitutionalModal('${algo.id}')">
          📋 25-Parameter Scorecard (${algo.passCount}/25 Passed) &rarr;
        </button>
      </div>
    `;
  }).join('');
}

function renderTopPicks(results) {
  if (state.institutionalTopPicks && state.institutionalTopPicks.length > 0) {
    renderInstitutionalTopPicks(state.institutionalTopPicks);
  } else {
    loadInstitutionalTopPicks();
  }
}

function openInstitutionalModal(algoId) {
  const modal = document.getElementById('institutional-modal');
  if (!modal) return;

  const algo = (state.institutionalTopPicks || []).find(a => a.id === algoId) || (state.institutionalTopPicks || [])[0];
  if (!algo) return;

  document.getElementById('inst-algo-name').textContent = algo.name;
  document.getElementById('inst-algo-cat').textContent = `${algo.category} · Strategy Family: ${algo.familyGroup || algo.category}`;
  document.getElementById('inst-score-badge').textContent = `🏆 ${algo.institutionalScore} / 100 Quality Score`;
  document.getElementById('inst-pass-sub').textContent = `${algo.passCount} Passed · ${algo.cautionCount} Caution · ${algo.failCount} Failed out of 25 Parameters`;

  const container = document.getElementById('inst-checklist-container');
  if (!container) return;

  // Group checklist items by Pillar
  const pillars = {};
  (algo.checklist || []).forEach(item => {
    pillars[item.pillar] = pillars[item.pillar] || [];
    pillars[item.pillar].push(item);
  });

  const pillarIcons = {
    'Return and Risk Quality': '📈',
    'Consistency': '🎯',
    'Reliability of the Numbers': '🔬',
    'Fit for Your Account': '💼',
    'Portfolio Fit': '🔀'
  };

  let html = '';
  Object.keys(pillars).forEach(pName => {
    const items = pillars[pName];
    const passPillar = items.filter(x => x.status === 'PASS').length;
    const icon = pillarIcons[pName] || '📌';

    html += `
      <div class="inst-pillar-section">
        <div class="inst-pillar-header">
          <div class="inst-pillar-title">
            <span>${icon}</span>
            <span>${pName}</span>
          </div>
          <span class="inst-pillar-badge">${passPillar} / ${items.length} Passed</span>
        </div>
        <table class="inst-check-table">
          <thead>
            <tr>
              <th style="width:40px;">#</th>
              <th style="width:200px;">Parameter</th>
              <th style="width:160px;">Institutional Benchmark</th>
              <th style="width:140px;">Strategy Metric</th>
              <th style="width:90px;">Verdict</th>
              <th>Due Diligence Finding</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(it => {
              const pillClass = it.status.toLowerCase();
              return `
                <tr>
                  <td style="color:var(--text-muted); font-weight:700;">${it.id}</td>
                  <td style="font-weight:700; color:var(--text-primary);">${it.name}</td>
                  <td style="color:var(--text-secondary); font-size:11px;">${it.benchmark}</td>
                  <td style="font-family:'JetBrains Mono', monospace; font-weight:700; color:var(--text-primary);">${it.value}</td>
                  <td><span class="inst-status-pill ${pillClass}">${it.status}</span></td>
                  <td style="color:var(--text-secondary); font-size:11px;">${it.note}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;
  });

  container.innerHTML = html;
  modal.classList.remove('hidden');
}

function openFrameworkExplainerModal() {
  if (state.institutionalTopPicks && state.institutionalTopPicks.length > 0) {
    openInstitutionalModal(state.institutionalTopPicks[0].id);
  } else {
    loadInstitutionalTopPicks().then(() => {
      if (state.institutionalTopPicks && state.institutionalTopPicks.length > 0) {
        openInstitutionalModal(state.institutionalTopPicks[0].id);
      }
    });
  }
}

function closeInstitutionalModal(e) {
  if (e.target.id === 'institutional-modal') {
    closeInstitutionalModalDirect();
  }
}

function closeInstitutionalModalDirect() {
  const modal = document.getElementById('institutional-modal');
  if (modal) modal.classList.add('hidden');
}

function buildRecommendation(algo) {
  const parts = [];
  const ret1m = get1MReturn(algo);
  const wr = getWinRatio(algo);
  const sharpe = getSharpe(algo);
  const dd = getDrawdown(algo);

  if (ret1m !== null && ret1m > 10) parts.push(`<strong>Strong 1M momentum</strong> (+${parseFloat(ret1m).toFixed(1)}%)`);
  else if (ret1m !== null && ret1m > 0) parts.push(`Positive 1M return (+${parseFloat(ret1m).toFixed(1)}%)`);

  if (wr !== null && wr > 55) parts.push(`<strong>High win rate</strong> (${parseFloat(wr).toFixed(0)}%)`);

  if (sharpe !== null && sharpe > 2) parts.push(`<strong>Excellent Sharpe</strong> (${parseFloat(sharpe).toFixed(2)})`);
  else if (sharpe !== null && sharpe > 1) parts.push(`Good risk-adjusted returns (Sharpe ${parseFloat(sharpe).toFixed(2)})`);

  if (dd !== null && dd > -15) parts.push('Low drawdown risk');

  return parts.length > 0
    ? '✅ ' + parts.join(' · ')
    : 'Review detailed metrics before deploying capital';
}

/* ══════════════════════════════════════════════════════════════════════════
   PORTFOLIO TRADE OVERLAP ANALYZER (3-STRATEGY RUNTIME ENGINE)
══════════════════════════════════════════════════════════════════════════ */
async function loadOverlapCatalog() {
  if (state.overlapCatalog && state.overlapCatalog.length > 0) {
    return state.overlapCatalog;
  }
  try {
    const res = await fetch(`${API}/api/algo/catalog-options`);
    const json = await res.json();
    if (json.success && Array.isArray(json.data)) {
      state.overlapCatalog = json.data;
      return json.data;
    }
  } catch (err) {
    console.error('Failed to load algo catalog options:', err);
  }
  return [];
}

async function populate3StrategyDropdowns() {
  const sel1 = document.getElementById('overlap-algo-1');
  const sel2 = document.getElementById('overlap-algo-2');
  const sel3 = document.getElementById('overlap-algo-3');
  if (!sel1 || !sel2 || !sel3) return;

  const catalog = await loadOverlapCatalog();
  if (!catalog || catalog.length === 0) return;

  // Separate held and categorize others
  const heldAlgos = catalog.filter(a => a.isHeld);
  const creditSpread = catalog.filter(a => a.category === 'Credit Spread');
  const straddle = catalog.filter(a => a.category === 'Short Straddle');
  const strangle = catalog.filter(a => a.category === 'Short Strangle');
  const optionBuying = catalog.filter(a => a.category === 'Option Buying');

  const renderOpts = (list) => list.map(a => `<option value="${a.id}">${a.isHeld ? '💼 [Held] ' : ''}${a.name}</option>`).join('');

  const fullHtml = `
    <optgroup label="💼 Active Portfolio / Held Strategies (${heldAlgos.length})">
      ${renderOpts(heldAlgos)}
    </optgroup>
    <optgroup label="📈 Credit Spread Strategies (${creditSpread.length})">
      ${renderOpts(creditSpread)}
    </optgroup>
    <optgroup label="🎯 Short Straddle Strategies (${straddle.length})">
      ${renderOpts(straddle)}
    </optgroup>
    <optgroup label="⚡ Short Strangle Strategies (${strangle.length})">
      ${renderOpts(strangle)}
    </optgroup>
    <optgroup label="🚀 Option Buying Strategies (${optionBuying.length})">
      ${renderOpts(optionBuying)}
    </optgroup>
  `;

  const curr1 = sel1.value;
  const curr2 = sel2.value;
  const curr3 = sel3.value;

  sel1.innerHTML = fullHtml;
  sel2.innerHTML = fullHtml;
  sel3.innerHTML = fullHtml;

  // Defaults:
  // Strategy A: Zen Credit Spread Overnight (or first held)
  // Strategy B: IV-Imbalance Credit Spread Overnight (or second held)
  // Strategy C: Damper Credit Spread (or third held)
  const zen = catalog.find(a => a.name.toLowerCase().includes('zen')) || catalog[0];
  const iv  = catalog.find(a => a.name.toLowerCase().includes('iv-imbalance')) || (catalog.length > 1 ? catalog[1] : catalog[0]);
  const damper = catalog.find(a => a.name.toLowerCase().includes('damper')) || (catalog.length > 2 ? catalog[2] : catalog[0]);

  if (curr1 && sel1.querySelector(`option[value="${curr1}"]`)) {
    sel1.value = curr1;
  } else if (zen) {
    sel1.value = zen.id;
  }

  if (curr2 && sel2.querySelector(`option[value="${curr2}"]`)) {
    sel2.value = curr2;
  } else if (iv) {
    sel2.value = iv.id;
  }

  if (curr3 && sel3.querySelector(`option[value="${curr3}"]`)) {
    sel3.value = curr3;
  } else if (damper) {
    sel3.value = damper.id;
  }

  updateCategoryBadges();
}

function updateCategoryBadges() {
  const sel1 = document.getElementById('overlap-algo-1');
  const sel2 = document.getElementById('overlap-algo-2');
  const sel3 = document.getElementById('overlap-algo-3');
  const b1 = document.getElementById('algo-1-cat-badge');
  const b2 = document.getElementById('algo-2-cat-badge');
  const b3 = document.getElementById('algo-3-cat-badge');

  if (!state.overlapCatalog) return;
  const map = {};
  state.overlapCatalog.forEach(a => { map[a.id] = a; });

  if (b1 && sel1 && map[sel1.value]) b1.textContent = map[sel1.value].category;
  if (b2 && sel2 && map[sel2.value]) b2.textContent = map[sel2.value].category;
  if (b3 && sel3 && map[sel3.value]) b3.textContent = map[sel3.value].category;
}

async function loadOverlapAnalysis(timeframe = '1M') {
  const section = document.getElementById('overlap-analyzer-section');
  if (!section) return;

  const tfSelect = document.getElementById('overlap-timeframe-select');
  if (tfSelect) tfSelect.value = timeframe;
  state.selectedOverlapTimeframe = timeframe;

  // Ensure dropdowns are populated
  const sel1 = document.getElementById('overlap-algo-1');
  const sel2 = document.getElementById('overlap-algo-2');
  const sel3 = document.getElementById('overlap-algo-3');

  if (!sel1 || !sel1.options || sel1.options.length === 0) {
    await populate3StrategyDropdowns();
  }

  const id1 = sel1 ? sel1.value : '68596cd26aa2cba24bbb67da';
  const id2 = sel2 ? sel2.value : '687d0a309107a80e07401e5d';
  const id3 = sel3 ? sel3.value : '68c9b755c7ed8fff5c5de9af';

  updateCategoryBadges();

  // Indicate loading state in UI
  const countEl = document.getElementById('inspector-overlap-count');
  const badgeEl = document.getElementById('inspector-risk-badge');
  const daysEl = document.getElementById('inspector-coincide-text');
  if (countEl) countEl.textContent = '...';
  if (badgeEl) {
    badgeEl.textContent = 'Calculating live overlap...';
    badgeEl.className = 'verdict-badge verdict-caution';
  }
  if (daysEl) daysEl.textContent = 'Fetching official Stratzy advice signals at runtime...';

  try {
    const url = `${API}/api/algo/overlap?algoA=${encodeURIComponent(id1)}&algoB=${encodeURIComponent(id2)}&algoC=${encodeURIComponent(id3)}&timeframe=${encodeURIComponent(timeframe)}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.success) {
      console.warn('Overlap fetch error:', data.message);
      return;
    }

    state.overlapData = data;

    // Render inspector card according to active tab
    renderInspectorCard();

    // Render 3x3 Matrix Table
    renderOverlapMatrix(data);
  } catch (err) {
    console.error('Failed to load overlap analysis:', err);
    if (badgeEl) badgeEl.textContent = 'Calculation Error';
  }
}

function onStrategyDropdownChange() {
  updateCategoryBadges();
  const tf = state.selectedOverlapTimeframe || '1M';
  loadOverlapAnalysis(tf);
}

function onOverlapTimeframeChange(val) {
  loadOverlapAnalysis(val);
}

function switchInspectorPair(pairKey) {
  state.selectedInspectorPair = pairKey;

  // Update tab button active states
  ['ab', 'ac', 'bc', '3way'].forEach(k => {
    const btn = document.getElementById(`tab-${k}`);
    if (btn) {
      if (k.toUpperCase() === pairKey.toUpperCase()) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
  });

  renderInspectorCard();
}

function renderInspectorCard() {
  if (!state.overlapData) return;
  const data = state.overlapData;
  const pairKey = state.selectedInspectorPair || 'AB';

  const countEl = document.getElementById('inspector-overlap-count');
  const labelEl = document.getElementById('inspector-overlap-label');
  const badgeEl = document.getElementById('inspector-risk-badge');
  const daysEl = document.getElementById('inspector-coincide-text');
  const a1NameEl = document.getElementById('inspector-algo1-name');
  const a1TradesEl = document.getElementById('inspector-algo1-trades');
  const a2NameEl = document.getElementById('inspector-algo2-name');
  const a2TradesEl = document.getElementById('inspector-algo2-trades');
  const concEl = document.getElementById('inspector-concentration-val');

  if (pairKey === '3WAY') {
    const threeWay = data.threeWayOverlap || { overlappingTrades: 0, sameDayOverlap: 0 };
    const count = threeWay.overlappingTrades;
    if (countEl) countEl.textContent = count;
    if (labelEl) labelEl.textContent = '3-Way Simultaneous Overlap';

    if (badgeEl) {
      if (count >= 10) {
        badgeEl.textContent = '🔴 Heavy 3-Way Duplication';
        badgeEl.className = 'verdict-badge verdict-swap';
      } else if (count >= 3) {
        badgeEl.textContent = '🟡 Moderate 3-Way Overlap';
        badgeEl.className = 'verdict-badge verdict-caution';
      } else {
        badgeEl.textContent = '🟢 Minimal 3-Way Duplication';
        badgeEl.className = 'verdict-badge verdict-retain';
      }
    }

    if (daysEl) {
      daysEl.textContent = `${threeWay.sameDayOverlap || 0} trading days where ALL 3 strategies simultaneously took trades`;
    }

    if (a1NameEl) a1NameEl.textContent = `${data.strategyA.name}:`;
    if (a1TradesEl) a1TradesEl.textContent = `${data.strategyA.totalTrades} trades`;
    if (a2NameEl) a2NameEl.textContent = `${data.strategyB.name} & ${data.strategyC.name}:`;
    if (a2TradesEl) a2TradesEl.textContent = `${data.strategyB.totalTrades} & ${data.strategyC.totalTrades} trades`;
    if (concEl) concEl.textContent = `${count} identical contracts held across all 3`;
    return;
  }

  // Pairwise: AB, AC, or BC
  let st = null;
  let strat1 = null;
  let strat2 = null;

  if (pairKey === 'AC') {
    st = data.pairAC;
    strat1 = data.strategyA;
    strat2 = data.strategyC;
  } else if (pairKey === 'BC') {
    st = data.pairBC;
    strat1 = data.strategyB;
    strat2 = data.strategyC;
  } else {
    // Default AB
    st = data.pairAB;
    strat1 = data.strategyA;
    strat2 = data.strategyB;
  }

  if (!st) {
    st = {
      overlappingTrades: 0,
      sameDayOverlap: 0,
      totalActiveDays: 0,
      totalTradesA: strat1 ? strat1.totalTrades : 0,
      totalTradesB: strat2 ? strat2.totalTrades : 0,
      overlapPctA: 0,
      overlapPctB: 0,
      level: 'LOW',
      riskLabel: '🟢 Low / Zero Overlap'
    };
  }

  if (labelEl) labelEl.textContent = 'Overlapping Trades';
  if (countEl) countEl.textContent = st.overlappingTrades;

  if (badgeEl) {
    badgeEl.textContent = st.riskLabel;
    if (st.level === 'HIGH') {
      badgeEl.className = 'verdict-badge verdict-swap';
    } else if (st.level === 'MODERATE') {
      badgeEl.className = 'verdict-badge verdict-caution';
    } else if (st.level === 'SELF') {
      badgeEl.className = 'verdict-badge';
      badgeEl.style.background = 'rgba(255,255,255,0.06)';
      badgeEl.style.color = 'var(--text-muted)';
    } else {
      badgeEl.className = 'verdict-badge verdict-retain';
    }
  }

  if (daysEl) {
    if (strat1.id === strat2.id) {
      daysEl.textContent = 'Comparing strategy against itself (100% duplicate)';
    } else {
      daysEl.textContent = `${st.sameDayOverlap} trading days coincided out of ${st.totalActiveDays || st.sameDayOverlap} active days in period`;
    }
  }

  if (a1NameEl) a1NameEl.textContent = `${strat1.name}:`;
  if (a1TradesEl) a1TradesEl.textContent = `${strat1.totalTrades} trades`;

  if (a2NameEl) a2NameEl.textContent = `${strat2.name}:`;
  if (a2TradesEl) a2TradesEl.textContent = `${strat2.totalTrades} trades`;

  if (concEl) {
    if (strat1.id === strat2.id) {
      concEl.textContent = '100% (Identical)';
    } else {
      const maxPct = Math.max(st.overlapPctA || 0, st.overlapPctB || 0);
      concEl.textContent = `${maxPct}% of positions duplicated`;
    }
  }
}

function renderOverlapMatrix(data) {
  const headerRow = document.getElementById('matrix-header-row');
  const tbody = document.getElementById('matrix-body');
  if (!headerRow || !tbody) return;

  const strategies = [
    { key: 'A', meta: data.strategyA },
    { key: 'B', meta: data.strategyB },
    { key: 'C', meta: data.strategyC }
  ];

  // 1. Header row
  let hHtml = '<th class="matrix-row-header">Selected Strategy (Row) \\ Compared Strategy (Col)</th>';
  strategies.forEach(s => {
    const isHeld = s.meta.isHeld;
    const shortName = s.meta.name.replace('Credit Spread Overnight', 'CSO')
                                 .replace('Credit Spread Expiry', 'CSE')
                                 .replace('Credit Spread', 'CS')
                                 .replace('Option Buying', 'OB')
                                 .replace('Short Strangle', 'SS')
                                 .replace('Short Straddle', 'SStrd');
    hHtml += `
      <th title="${s.meta.name}">
        <div style="font-size:12px;">Strategy ${s.key}: ${shortName}</div>
        <span class="matrix-th-badge" style="color:${isHeld ? '#818cf8' : '#10b981'}; font-size:10px;">
          ${isHeld ? '[HELD]' : `[${s.meta.category}]`}
        </span>
      </th>
    `;
  });
  headerRow.innerHTML = hHtml;

  // 2. Body rows: Strategy A, Strategy B, Strategy C
  let bHtml = '';
  strategies.forEach((rowStrat, rIdx) => {
    bHtml += `<tr>`;
    bHtml += `
      <td class="matrix-row-title">
        <div style="font-weight:700; color:var(--text-primary); font-size:12px;">
          ${rowStrat.meta.isHeld ? '💼' : '⚡'} Strategy ${rowStrat.key}: ${rowStrat.meta.name}
        </div>
        <div style="font-size:10px; color:var(--text-muted); font-weight:normal; margin-top:2px;">
          ${rowStrat.meta.category} · ${rowStrat.meta.totalTrades} total trades in period
        </div>
      </td>
    `;

    strategies.forEach((colStrat, cIdx) => {
      if (rIdx === cIdx) {
        bHtml += `<td><span class="cell-pill dot-self" title="Same strategy">—</span></td>`;
      } else {
        // Determine pair key
        let pairKey = 'AB';
        if ((rIdx === 0 && cIdx === 2) || (rIdx === 2 && cIdx === 0)) pairKey = 'AC';
        else if ((rIdx === 1 && cIdx === 2) || (rIdx === 2 && cIdx === 1)) pairKey = 'BC';

        const st = (data.matrix && data.matrix[rowStrat.meta.id] && data.matrix[rowStrat.meta.id][colStrat.meta.id])
          ? data.matrix[rowStrat.meta.id][colStrat.meta.id]
          : null;

        const count = st ? st.overlappingTrades : 0;
        let pillClass = 'dot-green';
        if (count >= 10) pillClass = 'dot-red';
        else if (count >= 3) pillClass = 'dot-amber';

        bHtml += `
          <td>
            <button type="button" class="matrix-cell-btn" 
              onclick="selectMatrixPair('${pairKey}')"
              title="${rowStrat.meta.name} vs ${colStrat.meta.name}: ${count} overlapping trades">
              <span class="cell-pill ${pillClass}">${count}</span>
            </button>
          </td>
        `;
      }
    });

    bHtml += `</tr>`;
  });

  tbody.innerHTML = bHtml;
}

function selectMatrixPair(pairKey) {
  switchInspectorPair(pairKey);
  const inspector = document.getElementById('inspector-result-card');
  if (inspector) {
    inspector.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    inspector.style.boxShadow = '0 0 25px rgba(99, 102, 241, 0.6)';
    setTimeout(() => { inspector.style.boxShadow = ''; }, 1200);
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   WATCHLIST
══════════════════════════════════════════════════════════════════════════ */
function toggleWatchlist(algoId, btn) {
  const algo = state.scanResults.find(a => a._id === algoId || a.algoId === algoId);
  if (!algo) return;

  const idx = state.watchlist.findIndex(w => w._id === algoId);
  if (idx >= 0) {
    state.watchlist.splice(idx, 1);
    btn.classList.remove('starred');
    btn.querySelector('svg').setAttribute('fill', 'none');
  } else {
    state.watchlist.push(algo);
    btn.classList.add('starred');
    btn.querySelector('svg').setAttribute('fill', 'currentColor');
  }

  localStorage.setItem('stratzy_watchlist', JSON.stringify(state.watchlist));
  renderWatchlist();

  const badge = document.getElementById('watchlist-badge');
  badge.textContent = state.watchlist.length;
  badge.style.display = state.watchlist.length > 0 ? 'inline-block' : 'none';
}

function renderWatchlist() {
  const empty = document.getElementById('watchlist-empty');
  const grid = document.getElementById('watchlist-grid');

  if (state.watchlist.length === 0) {
    empty.style.display = 'flex';
    grid.innerHTML = '';
    return;
  }

  empty.style.display = 'none';
  grid.innerHTML = state.watchlist.map(algo => {
    const ret1m = get1MReturn(algo);
    const sharpe = getSharpe(algo);
    const wr = getWinRatio(algo);
    const risk = getRisk(algo);
    const cat = algo.displayCategory || algo.category || '';

    return `<div class="pick-card">
      <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px;">
        <div class="pick-rank">⭐ Watchlist</div>
        <button class="icon-btn starred" onclick="removeFromWatchlist('${algo._id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </button>
      </div>
      <div class="pick-name">${algo.name}</div>
      <div class="pick-cat">${cat}${risk ? ` · ${risk} Risk` : ''}</div>
      <div class="pick-stats" style="margin-top:16px;">
        <div class="pick-stat-item">
          <div class="pick-stat-val ${ret1m !== null && ret1m > 0 ? 'val-pos' : 'val-neg'}">${ret1m !== null ? (ret1m > 0 ? '+' : '') + parseFloat(ret1m).toFixed(1) + '%' : '—'}</div>
          <div class="pick-stat-label">1M Return</div>
        </div>
        <div class="pick-stat-item">
          <div class="pick-stat-val val-neu">${wr !== null ? parseFloat(wr).toFixed(0) + '%' : '—'}</div>
          <div class="pick-stat-label">Win Rate</div>
        </div>
        <div class="pick-stat-item">
          <div class="pick-stat-val ${sharpe !== null && sharpe > 1 ? 'val-pos' : 'val-neu'}">${sharpe !== null ? parseFloat(sharpe).toFixed(2) : '—'}</div>
          <div class="pick-stat-label">Sharpe</div>
        </div>
      </div>
      <div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border);">
        <a href="https://stratzy.in/algo-trading-strategies/${(algo.shareLink || '').split('/').pop() || algo._id}" target="_blank" class="btn btn-secondary" style="font-size:12px;padding:6px 12px;width:100%;justify-content:center;">View on Stratzy ↗</a>
      </div>
    </div>`;
  }).join('');
}

function removeFromWatchlist(algoId) {
  const idx = state.watchlist.findIndex(w => w._id === algoId);
  if (idx >= 0) state.watchlist.splice(idx, 1);
  localStorage.setItem('stratzy_watchlist', JSON.stringify(state.watchlist));
  renderWatchlist();
  const badge = document.getElementById('watchlist-badge');
  badge.textContent = state.watchlist.length;
  badge.style.display = state.watchlist.length > 0 ? 'inline-block' : 'none';
  // Update star in results table
  renderResults(state.scanResults);
}

/* ══════════════════════════════════════════════════════════════════════════
   DETAIL MODAL
══════════════════════════════════════════════════════════════════════════ */
function openDetail(algoId) {
  const algo = state.scanResults.find(a => a._id === algoId || a.algoId === algoId);
  if (!algo) return;

  const modal = document.getElementById('detail-modal');
  const content = document.getElementById('modal-content');

  const ps = algo.performanceSummary || {};
  const metrics = algo.metrics || {};
  const qs = algo.quantStats || {};
  const cat = algo.displayCategory || algo.category || '';

  const periods = ['1M', '3M', '6M', '1Y'];

  content.innerHTML = `
    <div class="modal-title">${algo.name}</div>
    <div class="modal-cat">${cat}${algo.risk ? ` · ${algo.risk} Risk` : ''}</div>

    <div class="modal-metrics-grid">
      ${Object.entries(ps).map(([label, val]) => `
        <div class="modal-metric">
          <div class="modal-metric-label">${label}</div>
          <div class="modal-metric-val ${parseFloat(val) > 0 ? 'val-pos' : parseFloat(val) < 0 ? 'val-neg' : 'val-neu'}">${val}</div>
        </div>`).join('')}
    </div>

    <div style="margin-bottom:12px;font-size:13px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.05em;">Period Metrics</div>
    <div class="modal-period-tabs">
      ${periods.map(p => `<div class="period-tab ${p === '1M' ? 'active' : ''}" onclick="switchPeriod(this, '${p}', '${algoId}')">${p}</div>`).join('')}
    </div>
    <div id="period-stats-${algoId}">
      ${renderPeriodStats(metrics['1M'])}
    </div>

    ${Object.keys(qs).length > 0 ? `
    <div style="margin:20px 0 12px;font-size:13px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.05em;">Quant Stats (1Y vs Benchmark)</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
      ${Object.entries(qs).slice(0, 12).map(([k, v]) => `
        <div class="modal-metric">
          <div class="modal-metric-label">${k}</div>
          <div class="modal-metric-val" style="font-size:14px;">${v}</div>
        </div>`).join('')}
    </div>` : ''}

    ${algo.about ? `
    <div class="modal-about">
      <h4>About this Strategy</h4>
      <p>${algo.about?.substring(0, 600)}${algo.about?.length > 600 ? '...' : ''}</p>
    </div>` : ''}

    <div style="margin-top:20px;display:flex;gap:10px;">
      <a href="https://stratzy.in/algo-trading-strategies/${(algo.shareLink || '').split('/').pop() || algo._id}" target="_blank" class="btn btn-primary">View on Stratzy ↗</a>
      <button class="btn btn-secondary" onclick="toggleWatchlist('${algoId}', this)">
        ${state.watchlist.some(w => w._id === algoId) ? '⭐ In Watchlist' : '☆ Add to Watchlist'}
      </button>
    </div>
  `;

  // Store metrics for period switching
  modal._algoMetrics = metrics;
  modal._algoId = algoId;

  modal.classList.remove('hidden');
}

function renderPeriodStats(periodData) {
  if (!periodData) return '<p style="color:var(--text-muted);font-size:13px;">No data for this period</p>';
  const items = [
    { key: 'totalTrades', label: 'Total Trades' },
    { key: 'profitableTrades', label: 'Profitable Trades' },
    { key: 'winRatio', label: 'Win Ratio', suffix: '%' },
    { key: 'avgProfit', label: 'Avg Profit', suffix: '%' },
    { key: 'avgLoss', label: 'Avg Loss', suffix: '%' },
    { key: 'winStreaks', label: 'Win Streak' },
    { key: 'booksizeReturn', label: 'Period Return', suffix: '%' },
  ];
  return `<div class="modal-period-stats">${items.map(item => {
    const val = periodData[item.key];
    if (val === undefined || val === null) return '';
    const n = parseFloat(val);
    const cls = item.suffix === '%' && n > 0 ? 'val-pos' : item.suffix === '%' && n < 0 ? 'val-neg' : 'val-neu';
    return `<div class="period-stat">
      <div class="period-stat-val ${cls}">${item.suffix === '%' && n > 0 ? '+' : ''}${typeof val === 'number' ? val.toFixed(item.key === 'totalTrades' || item.key === 'profitableTrades' || item.key === 'winStreaks' ? 0 : 1) : val}${item.suffix || ''}</div>
      <div class="period-stat-label">${item.label}</div>
    </div>`;
  }).join('')}</div>`;
}

function switchPeriod(tabEl, period, algoId) {
  document.querySelectorAll('.period-tab').forEach(t => t.classList.remove('active'));
  tabEl.classList.add('active');
  const modal = document.getElementById('detail-modal');
  const metrics = modal._algoMetrics || {};
  document.getElementById(`period-stats-${algoId}`).innerHTML = renderPeriodStats(metrics[period]);
}

function closeDetailModal() {
  document.getElementById('detail-modal').classList.add('hidden');
}

function closeModal(event) {
  if (event.target === document.getElementById('detail-modal')) closeDetailModal();
}

/* ══════════════════════════════════════════════════════════════════════════
   EXPORT CSV
══════════════════════════════════════════════════════════════════════════ */
function exportResults() {
  const rows = state.filteredResults;
  if (!rows.length) return;

  const headers = ['Rank', 'Name', 'Category', 'Score', '1M Return%', '3M Return%', '6M Return%', '1Y Return%', 'Win Ratio%', 'Sharpe Ratio', 'Max Drawdown%', 'Risk', 'Min Capital'];
  const csv = [headers.join(','),
    ...rows.map((a, i) => [
      i + 1,
      `"${(a.name || '').replace(/"/g, '""')}"`,
      `"${(a.displayCategory || a.category || '').replace(/"/g, '""')}"`,
      getAlgoScore(a) ?? '',
      get1MReturn(a)?.toFixed(2) ?? '',
      get3MReturn(a)?.toFixed(2) ?? '',
      get6MReturn(a)?.toFixed(2) ?? '',
      get1YReturn(a)?.toFixed(2) ?? '',
      getWinRatio(a)?.toFixed(2) ?? '',
      getSharpe(a)?.toFixed(2) ?? '',
      getDrawdown(a)?.toFixed(2) ?? '',
      getRisk(a) ?? '',
      a.minimumCapital ?? '',
    ].join(','))
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `stratzy_scan_${new Date().toISOString().split('T')[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ══════════════════════════════════════════════════════════════════════════
   DHAN AUDITOR LOGIC
══════════════════════════════════════════════════════════════════════════ */

function switchDhanTab(tab) {
  state.dhan.activeTab = tab;
  document.querySelectorAll('.dhan-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.dhan-tab-content').forEach(c => c.classList.remove('active'));

  document.getElementById(`tab-btn-${tab}`)?.classList.add('active');
  document.getElementById(`dhan-tab-${tab}`)?.classList.add('active');
}

function initDhanDropzone() {
  const dropzone = document.getElementById('dhan-dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, e => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, e => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      processDhanFile(files[0]);
    }
  });
}

function handleDhanFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    processDhanFile(file);
  }
}

async function processDhanFile(file) {
  const titleEl = document.getElementById('dhan-dropzone-title');
  const subEl = document.getElementById('dhan-dropzone-sub');
  const originalTitle = titleEl ? titleEl.innerHTML : '';
  const originalSub = subEl ? subEl.innerHTML : '';

  if (titleEl) {
    titleEl.innerHTML = `<span style="color:var(--indigo);">⏳ Analyzing <strong>${file.name}</strong>...</span>`;
  }
  if (subEl) {
    subEl.textContent = 'Extracting option trade legs and computing FIFO roundtrips...';
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API}/api/dhan/parse-csv`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (data.success && data.analytics) {
      renderDhanAnalytics(data.analytics);
      if (data.analytics.totalTrades > 0) {
        if (titleEl) {
          titleEl.innerHTML = `✅ Successfully loaded <strong>${file.name}</strong> (${data.analytics.totalTrades} closed trades)`;
        }
        if (subEl) {
          subEl.textContent = 'Click or drop another file to replace';
        }
      } else {
        if (titleEl) {
          titleEl.innerHTML = `⚠️ <strong>${file.name}</strong> loaded, but 0 completed trades were detected`;
        }
        if (subEl) {
          subEl.textContent = 'Make sure the file contains executed F&O trades (with Symbol, Buy/Sell side, Qty, and Price) or a Dhan Realized P&L report.';
        }
      }
    } else {
      alert(data.message || 'Failed to parse file. Please verify it is a valid Dhan Tradebook CSV/Excel export.');
      if (titleEl) titleEl.innerHTML = originalTitle;
      if (subEl) subEl.innerHTML = originalSub;
    }
  } catch (err) {
    alert('Failed to send file to server: ' + err.message);
    if (titleEl) titleEl.innerHTML = originalTitle;
    if (subEl) subEl.innerHTML = originalSub;
  }
}

function setDhanDatePreset(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - days);

  const toStr = to.toISOString().split('T')[0];
  const fromStr = from.toISOString().split('T')[0];

  const fromEl = document.getElementById('dhan-from-date');
  const toEl = document.getElementById('dhan-to-date');
  if (fromEl) fromEl.value = fromStr;
  if (toEl) toEl.value = toStr;

  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(`(${days})`));
  });
}

async function connectDhanApi() {
  const clientId = document.getElementById('dhan-client-id').value.trim();
  const accessToken = document.getElementById('dhan-access-token').value.trim();
  const fromDate = document.getElementById('dhan-from-date')?.value || '';
  const toDate = document.getElementById('dhan-to-date')?.value || '';
  const errorEl = document.getElementById('dhan-api-error');
  const btn = document.getElementById('dhan-api-connect-btn');

  if (!clientId && !accessToken && !state.dhan.connected) {
    errorEl.textContent = 'Please enter both Client ID and Access Token';
    errorEl.classList.remove('hidden');
    return;
  }

  errorEl.classList.add('hidden');
  btn.disabled = true;
  btn.textContent = 'Fetching DhanHQ trades...';

  try {
    const res = await fetch(`${API}/api/dhan/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clientId, accessToken, fromDate, toDate }),
    });
    const data = await res.json();

    if (data.success && data.analytics) {
      state.dhan.connected = true;
      renderDhanAnalytics(data.analytics);
      btn.textContent = 'Connected & Updated ✅';
      setTimeout(() => {
        btn.textContent = 'Connect & Fetch Trades';
        btn.disabled = false;
      }, 2500);
    } else {
      errorEl.textContent = data.message || 'Authentication failed. Please check credentials.';
      errorEl.classList.remove('hidden');
      btn.textContent = 'Connect & Fetch Trades';
      btn.disabled = false;
    }
  } catch (err) {
    errorEl.textContent = 'Error connecting to server: ' + err.message;
    errorEl.classList.remove('hidden');
    btn.textContent = 'Connect & Fetch Trades';
    btn.disabled = false;
  }
}

async function loadDhanDemoData() {
  try {
    const res = await fetch(`${API}/api/dhan/demo-trades`);
    const data = await res.json();
    if (data.success && data.analytics) {
      renderDhanAnalytics(data.analytics);
    }
  } catch (err) {
    alert('Could not load demo data: ' + err.message);
  }
}

function formatInr(val) {
  const n = parseFloat(val) || 0;
  const abs = Math.abs(n);
  const formatted = abs.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (n < 0 ? '-' : (n > 0 ? '+' : '')) + '₹' + formatted;
}

function renderDhanAnalytics(analytics) {
  state.dhan.analytics = analytics;
  state.dhan.trades = analytics.trades || [];
  state.dhan.filteredTrades = [...state.dhan.trades];

  // Show dashboard, hide empty state
  document.getElementById('dhan-empty-state')?.classList.add('hidden');
  document.getElementById('dhan-dashboard')?.classList.remove('hidden');
  document.getElementById('dhan-clear-btn')?.classList.remove('hidden');

  // Update Date Range Banner
  const rangeEl = document.getElementById('dhan-banner-range');
  if (rangeEl) {
    if (analytics.fromDate && analytics.toDate) {
      rangeEl.textContent = `${analytics.fromDate} to ${analytics.toDate}`;
    } else if (analytics.trades && analytics.trades.length > 0) {
      const dates = analytics.trades.map(t => (t.exitDate || t.exitTime || t.entryTime || '').slice(0, 10)).filter(Boolean).sort();
      rangeEl.textContent = `${dates[0] || 'Start'} to ${dates[dates.length - 1] || 'Today'}`;
    } else {
      rangeEl.textContent = 'All Available';
    }
  }

  const metaEl = document.getElementById('dhan-banner-meta');
  if (metaEl) {
    metaEl.textContent = `${analytics.totalTrades || 0} closed trades · ${analytics.winTrades || 0} Wins / ${analytics.lossTrades || 0} Losses (${analytics.winRate}% Win Rate)`;
  }

  // Update nav badge
  const badge = document.getElementById('dhan-badge');
  if (badge) {
    badge.textContent = `${analytics.totalTrades} Trds`;
    badge.style.display = 'inline-block';
  }

  // 1. Metric Cards
  const netPnlEl = document.getElementById('dhan-net-pnl');
  if (netPnlEl) {
    netPnlEl.textContent = formatInr(analytics.netPnl);
    netPnlEl.className = 'dhan-metric-val ' + (analytics.netPnl >= 0 ? 'val-pos' : 'val-neg');
  }

  const pnlBreakdown = document.getElementById('dhan-pnl-breakdown');
  if (pnlBreakdown) {
    pnlBreakdown.textContent = 
      `Gross: ${formatInr(analytics.grossProfit - analytics.grossLoss)} · Charges: ₹${analytics.totalCharges.toLocaleString('en-IN')}`;
  }

  const wrEl = document.getElementById('dhan-win-rate');
  if (wrEl) {
    wrEl.textContent = `${analytics.winRate}%`;
    wrEl.className = 'dhan-metric-val ' + (analytics.winRate >= 50 ? 'val-pos' : (analytics.winRate >= 40 ? 'val-neu' : 'val-neg'));
  }

  const trRatio = document.getElementById('dhan-trades-ratio');
  if (trRatio) {
    trRatio.textContent = 
      `${analytics.winTrades} Wins / ${analytics.lossTrades} Losses (${analytics.totalTrades} Total)`;
  }

  const pfEl = document.getElementById('dhan-profit-factor');
  if (pfEl) {
    pfEl.textContent = analytics.profitFactor >= 99 ? '∞' : analytics.profitFactor.toFixed(2);
    pfEl.className = 'dhan-metric-val ' + (analytics.profitFactor >= 1.5 ? 'val-pos' : (analytics.profitFactor >= 1.0 ? 'val-neu' : 'val-neg'));
  }

  const avgWinLoss = document.getElementById('dhan-avg-win-loss');
  if (avgWinLoss) {
    avgWinLoss.textContent = 
      `Avg Win: ₹${analytics.avgWin.toLocaleString('en-IN')} · Avg Loss: ₹${analytics.avgLoss.toLocaleString('en-IN')}`;
  }

  const totCharges = document.getElementById('dhan-total-charges');
  if (totCharges) {
    totCharges.textContent = `₹${analytics.totalCharges.toLocaleString('en-IN')}`;
  }
  
  const chargesSub = document.getElementById('dhan-charges-sub');
  if (chargesSub) {
    const frictionPct = analytics.grossProfit > 0 ? ((analytics.totalCharges / analytics.grossProfit) * 100).toFixed(1) : '0';
    chargesSub.textContent = `Friction: ${frictionPct}% of gross profit`;
  }

  const ddEl = document.getElementById('dhan-max-drawdown');
  if (ddEl) {
    ddEl.textContent = `-₹${analytics.maxDrawdown.toLocaleString('en-IN')}`;
  }

  // 2. Daily Bars Visualizer
  renderDailyBars(analytics.dailyPnl);

  // 3. The 3 Live Algos Audit Cards
  renderAlgoAuditCards(analytics.algoBreakdown);

  // 4. Strategic Recommendation vs Top Picks
  renderStrategicRecommendation(analytics);

  // 5. Populate Algo filter dropdown
  const algoFilter = document.getElementById('dhan-algo-filter');
  if (algoFilter) {
    const algos = toArray(analytics.algoBreakdown);
    algoFilter.innerHTML = '<option value="">All Algos</option>' + 
      algos.map(a => `<option value="${a.name}">${a.name}</option>`).join('');
  }

  // 6. Stratzy Reconciliation Banner
  const recon = analytics.reconciliation || {};
  const matchBadge = document.getElementById('dhan-stratzy-match-badge');
  const summaryText = document.getElementById('dhan-stratzy-summary-text');
  if (matchBadge) {
    const pct = recon.matchPct || 0;
    const matched = recon.matched || 0;
    const total = recon.total || 0;
    if (total === 0) {
      matchBadge.textContent = 'No Trades';
      matchBadge.className = 'verdict-badge verdict-caution';
    } else if (pct >= 80) {
      matchBadge.textContent = `${pct}% Matched`;
      matchBadge.className = 'verdict-badge verdict-retain';
    } else if (pct >= 40) {
      matchBadge.textContent = `${pct}% Matched`;
      matchBadge.className = 'verdict-badge verdict-caution';
    } else {
      matchBadge.textContent = `${pct}% Matched`;
      matchBadge.className = 'verdict-badge verdict-swap';
    }
    if (summaryText) {
      const slipRs = (recon.slippageRs || 0);
      const slipSign = slipRs < 0 ? '' : slipRs > 0 ? '+' : '';
      summaryText.textContent = matched > 0
        ? `${matched} of ${total} Dhan trades attributed to a Stratzy algo · Total execution slippage: ${slipSign}₹${Math.abs(slipRs).toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2})}`
        : 'Click Re-sync Signals to match Dhan executions against Stratzy published signals';
    }
  }

  // 7. Trades Table
  renderDhanTradesTable(state.dhan.filteredTrades);
}

function toArray(val) {
  if (!val) return [];
  if (Array.isArray(val)) return val;
  if (typeof val === 'object') return Object.values(val);
  return [];
}

function renderDailyBars(dailyInput) {
  const container = document.getElementById('dhan-daily-bars');
  if (!container) return;

  const dailyList = toArray(dailyInput);
  if (dailyList.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:20px;">No daily session data found.</div>';
    return;
  }

  const maxVal = Math.max(...dailyList.map(d => Math.abs(d.netPnl || 0)), 1000);

  container.innerHTML = dailyList.map(d => {
    const isPos = (d.netPnl || 0) >= 0;
    const height = Math.max(8, Math.min(100, Math.round((Math.abs(d.netPnl || 0) / maxVal) * 90)));
    const dateLabel = (d.date || '').slice(5); // MM-DD
    const sign = isPos ? '+' : '';

    return `
      <div class="daily-bar-col" title="${d.date}: ${sign}₹${(d.netPnl || 0).toLocaleString('en-IN')} (${d.trades || 0} trades)">
        <span class="daily-bar-val ${isPos ? 'val-pos' : 'val-neg'}">${sign}₹${Math.round((d.netPnl || 0) / 1000)}k</span>
        <div class="daily-bar ${isPos ? 'pos' : 'neg'}" style="height:${height}px;"></div>
        <span class="daily-bar-date">${dateLabel}</span>
      </div>
    `;
  }).join('');
}

function renderAlgoAuditCards(algoInput) {
  const container = document.getElementById('dhan-algo-audit-grid');
  if (!container) return;

  const algoList = toArray(algoInput);
  if (algoList.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted); font-size:13px; padding:12px;">No active algo trade history found. Upload a Dhan Tradebook CSV with past trades to see performance per strategy.</p>';
    return;
  }

  container.innerHTML = algoList.map((algo, i) => {
    const isRetain = algo.verdict === 'RETAIN';
    const isCaution = algo.verdict === 'CAUTION';
    const accentClass = isRetain ? 'retain' : (isCaution ? 'caution' : 'swap');
    const badgeClass = isRetain ? 'verdict-retain' : (isCaution ? 'verdict-caution' : 'verdict-swap');

    // Stratzy official numbers
    const sOverall  = algo.stratzyOverallPnl != null ? algo.stratzyOverallPnl : null;
    const sCurrent  = algo.stratzyCurrentPnl != null ? algo.stratzyCurrentPnl : null;
    const sTrades   = algo.stratzyTrades != null ? algo.stratzyTrades : '—';
    const sOverallFmt = sOverall !== null ? `<span class="${sOverall >= 0 ? 'val-pos' : 'val-neg'}">${formatInr(sOverall)}</span>` : `<span class="val-neu">—</span>`;
    const sCurrentFmt = sCurrent !== null ? `<span class="${sCurrent >= 0 ? 'val-pos' : 'val-neg'}">${formatInr(sCurrent)}</span>` : `<span class="val-neu">—</span>`;

    return `
      <div class="algo-audit-card glass-card">
        <div class="algo-card-accent ${accentClass}"></div>
        <div class="algo-card-header">
          <div>
            <div class="algo-card-title">${algo.name}</div>
            <div class="algo-card-tag">Live Active Algo #${i+1} &middot; ${algo.trades} Broker Legs &middot; ${sTrades} Stratzy Trades</div>
          </div>
          <span class="verdict-badge ${badgeClass}">${algo.verdict}</span>
        </div>

        <div class="source-compare-grid">
          <div class="source-col stratzy-col">
            <div class="source-col-header">
              <span class="source-badge stratzy-badge">&#x1F4CA; Stratzy</span>
              <span class="source-col-sub">Official reported P&amp;L</span>
            </div>
            <div class="source-metrics">
              <div class="source-metric">
                <div class="source-metric-label">Current Cycle P&amp;L</div>
                <div class="source-metric-val">${sCurrentFmt}</div>
              </div>
              <div class="source-metric">
                <div class="source-metric-label">Overall P&amp;L</div>
                <div class="source-metric-val">${sOverallFmt}</div>
              </div>
              <div class="source-metric">
                <div class="source-metric-label">Trades Executed</div>
                <div class="source-metric-val"><span class="val-neu">${sTrades}</span></div>
              </div>
            </div>
          </div>

          <div class="source-divider"></div>

          <div class="source-col dhan-col">
            <div class="source-col-header">
              <span class="source-badge dhan-badge">&#x1F3E6; Dhan</span>
              <span class="source-col-sub">Broker verified P&amp;L</span>
            </div>
            <div class="source-metrics">
              <div class="source-metric">
                <div class="source-metric-label">Net P&amp;L (after charges)</div>
                <div class="source-metric-val"><span class="${algo.netPnl >= 0 ? 'val-pos' : 'val-neg'}">${formatInr(algo.netPnl)}</span></div>
              </div>
              <div class="source-metric">
                <div class="source-metric-label">Win Rate</div>
                <div class="source-metric-val"><span class="${algo.winRate >= 50 ? 'val-pos' : 'val-neu'}">${algo.winRate}%</span></div>
              </div>
              <div class="source-metric">
                <div class="source-metric-label">Profit Factor</div>
                <div class="source-metric-val"><span class="${algo.profitFactor >= 1.5 ? 'val-pos' : 'val-neu'}">${algo.profitFactor >= 99 ? '&infin;' : algo.profitFactor.toFixed(2)}</span></div>
              </div>
            </div>
          </div>
        </div>

        <div class="algo-verdict-box">
          <strong>Audit Diagnosis:</strong> ${algo.reason}
          <div style="margin-top:4px; font-size:11px; color:var(--text-muted);">
            Charges &amp; Taxes paid: &#x20B9;${algo.charges.toLocaleString('en-IN')} &middot; Avg PnL/Trade: &#x20B9;${algo.avgTradePnl.toLocaleString('en-IN')}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderStrategicRecommendation(analytics) {
  const recEl = document.getElementById('dhan-rec-text');
  if (!recEl) return;

  const algos = toArray(analytics.algoBreakdown);
  const swapAlgos = algos.filter(a => a.verdict === 'SWAP CANDIDATE');
  const retainAlgos = algos.filter(a => a.verdict === 'RETAIN');

  // Check top picks from scan results if available
  const topPicks = state.scanResults.slice(0, 5);

  let recHtml = '';

  if (swapAlgos.length > 0) {
    const lagger = swapAlgos[0];
    recHtml += `<strong>Actionable Diagnosis:</strong> Your deployed algo <em>"${lagger.name}"</em> is lagging with a <strong>${lagger.winRate}% Win Rate</strong> and net return of <strong>${formatInr(lagger.netPnl)}</strong> over the last month. Slippage and frequent churn are creating friction.<br/><br/>`;

    if (topPicks.length > 0) {
      const topPick = topPicks[0];
      const pickName = topPick.name || 'Rank #1 Strategy';
      const pickCat = topPick.displayCategory || topPick.category || 'Strategy';
      const pickSharpe = topPick.metrics?.['1M']?.sharpeRatio || topPick.sharpeRatio || '1.8';
      const pickWr = topPick.metrics?.['1M']?.winRatio || topPick.winRatio || '65';

      recHtml += `<strong>Recommended Swap:</strong> Rotate capital from <em>${lagger.name}</em> into the Scanner's Top Pick: <strong>${pickName}</strong> (${pickCat}). It demonstrates a <strong>${pickSharpe} Sharpe Ratio</strong> and <strong>${pickWr}% Win Rate</strong>, providing superior risk-adjusted downside protection.`;
    } else {
      recHtml += `<strong>Recommended Swap:</strong> Run a scan in the <strong>Scanner tab</strong> for <em>Credit Spread</em> or <em>Short Strangle</em> strategies. Replacing this lagging directional buyer with a high-Sharpe non-directional theta strategy will diversify your market regime risk.`;
    }
  } else if (retainAlgos.length === algos.length && algos.length > 0) {
    recHtml = `<strong>Excellent Health:</strong> All 3 of your active algos on Dhan are generating positive net returns with healthy profit factors. Total 30-day Net P&L is <strong>${formatInr(analytics.netPnl)}</strong>. Continue running this basket, but keep an eye on options expiration week when slippage spikes.`;
  } else {
    recHtml = `Your deployed portfolio generated <strong>${formatInr(analytics.netPnl)}</strong> net P&L with a <strong>${analytics.winRate}% win rate</strong>. Check individual cards above to identify strategies with heavy regulatory charge friction.`;
  }

  recEl.innerHTML = recHtml;
}

function renderDhanTradesTable(trades) {
  const tbody = document.getElementById('dhan-trades-tbody');
  if (!tbody) return;

  if (trades.length === 0) {
    tbody.innerHTML = `<tr><td colspan="15" style="text-align:center; padding:30px; color:var(--text-muted);">No matching trades found</td></tr>`;
    return;
  }

  tbody.innerHTML = trades.slice(0, 100).map(t => {
    const isWin = t.isWin;
    const pnlClass = isWin ? 'val-pos' : 'val-neg';
    const statusPill = isWin ? 
      '<span class="verdict-badge verdict-retain">WIN</span>' : 
      '<span class="verdict-badge verdict-swap">LOSS</span>';

    // Algo attribution badge
    const sm = t.stratzyMatch;
    let algoBadge = '';
    if (t.isStratzyMatched && t.algoTag) {
      // Pick icon per algo name
      const name = t.algoTag || '';
      const icon = name.toLowerCase().includes('zen') ? '🧘' :
                   name.toLowerCase().includes('damper') ? '🛡️' :
                   name.toLowerCase().includes('iv') ? '📊' : '🎯';
      algoBadge = `<div style="font-size:11px;color:#10b981;font-weight:700;margin-top:3px;">${icon} ${t.algoTag}</div>`;
    } else if (t.algoTag && t.algoTag !== 'Unknown' && t.algoTag !== '') {
      algoBadge = `<div style="font-size:11px;color:var(--text-secondary);margin-top:3px;">🏷️ ${t.algoTag}</div>`;
    }

    // Slippage column
    let slippageCell = '<span style="color:var(--text-muted);font-size:12px;">—</span>';
    if (sm) {
      const totalSlip = sm.totalSlippageRs || 0;
      const slipClass = totalSlip < 0 ? 'val-neg' : (totalSlip > 0 ? 'val-pos' : 'val-neu');
      const slipSign = totalSlip < 0 ? '' : (totalSlip > 0 ? '+' : '');
      const entSlip = sm.entrySlippage || 0;
      const exSlip = sm.exitSlippage || 0;
      slippageCell = `
        <div title="Stratzy entry ₹${(sm.stratzyEntryPrice||0).toFixed(2)} vs Dhan ₹${(sm.dhanEntryPrice||0).toFixed(2)} · exit ₹${(sm.stratzyExitPrice||0).toFixed(2)} vs ₹${(sm.dhanExitPrice||0).toFixed(2)}">
          <span class="${slipClass}" style="font-family:'JetBrains Mono',monospace;font-weight:700;font-size:12px;">${slipSign}₹${Math.abs(totalSlip).toFixed(2)}</span>
          <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">E:${entSlip>=0?'+':''}${entSlip.toFixed(2)} X:${exSlip>=0?'+':''}${exSlip.toFixed(2)}</div>
        </div>`;
    }
    
    return `
      <tr>
        <td style="font-family:'JetBrains Mono', monospace; font-size:12px; color:var(--text-muted);">${t.id}</td>
        <td><strong>${t.symbol}</strong></td>
        <td><span class="dhan-badge">${t.direction}</span></td>
        <td style="font-size:12px; color:var(--text-secondary);">${algoBadge || (t.algoTag ? `<span style="color:var(--text-muted)">${t.algoTag}</span>` : '—')}</td>
        <td style="font-size:12px; font-family:'JetBrains Mono', monospace;">${t.entryTime || '—'}</td>
        <td style="font-size:12px; font-family:'JetBrains Mono', monospace;">${t.exitTime || '—'}</td>
        <td style="font-family:'JetBrains Mono', monospace;">${t.qty}</td>
        <td style="font-family:'JetBrains Mono', monospace;">₹${t.entryPrice.toFixed(2)}</td>
        <td style="font-family:'JetBrains Mono', monospace;">₹${t.exitPrice.toFixed(2)}</td>
        <td>${slippageCell}</td>
        <td class="${t.grossPnl >= 0 ? 'val-pos' : 'val-neg'}" style="font-family:'JetBrains Mono', monospace;">${formatInr(t.grossPnl)}</td>
        <td class="val-warn" style="font-family:'JetBrains Mono', monospace; font-size:12px;">₹${t.charges.toFixed(2)}</td>
        <td class="${pnlClass}" style="font-weight:700; font-family:'JetBrains Mono', monospace;">${formatInr(t.netPnl)}</td>
        <td style="font-size:12px; color:var(--text-muted);">${t.durationMin}m</td>
        <td>${statusPill}</td>
      </tr>
    `;
  }).join('');
}

function filterDhanTrades() {
  const q = document.getElementById('dhan-search')?.value.trim().toUpperCase() || '';
  const algo = document.getElementById('dhan-algo-filter')?.value || '';
  const pnlFilter = document.getElementById('dhan-pnl-filter')?.value || '';
  const tableFrom = document.getElementById('dhan-table-from-date')?.value || '';
  const tableTo = document.getElementById('dhan-table-to-date')?.value || '';

  state.dhan.filteredTrades = state.dhan.trades.filter(t => {
    if (q && !t.symbol.toUpperCase().includes(q) && !(t.algoTag || '').toUpperCase().includes(q)) return false;
    if (algo && t.algoTag !== algo) return false;
    if (pnlFilter === 'win' && !t.isWin) return false;
    if (pnlFilter === 'loss' && t.isWin) return false;

    // Date range filter
    const tradeDate = (t.exitDate || t.exitTime || t.entryTime || '').slice(0, 10);
    if (tableFrom && tradeDate && tradeDate < tableFrom) return false;
    if (tableTo && tradeDate && tradeDate > tableTo) return false;

    return true;
  });

  renderDhanTradesTable(state.dhan.filteredTrades);
}

function exportDhanTradesCsv() {
  const trades = state.dhan.filteredTrades;
  if (!trades || trades.length === 0) {
    alert('No trades to export');
    return;
  }

  const headers = ['Trade ID', 'Symbol', 'Direction', 'Algo Tag', 'Entry Time', 'Exit Time', 'Quantity', 'Entry Price', 'Exit Price', 'Stratzy Entry', 'Stratzy Exit', 'Entry Slippage', 'Exit Slippage', 'Total Slippage (Rs)', 'Gross PnL', 'Charges', 'Net PnL', 'Duration Mins', 'Status'];
  const rows = trades.map(t => {
    const sm = t.stratzyMatch || {};
    return [
      t.id,
      `"${t.symbol}"`,
      t.direction,
      `"${t.algoTag || ''}"`,
      t.entryTime,
      t.exitTime,
      t.qty,
      t.entryPrice,
      t.exitPrice,
      sm.stratzyEntryPrice || '',
      sm.stratzyExitPrice || '',
      sm.entrySlippage || '',
      sm.exitSlippage || '',
      sm.totalSlippageRs || '',
      t.grossPnl,
      t.charges,
      t.netPnl,
      t.durationMin,
      t.isWin ? 'WIN' : 'LOSS'
    ];
  });

  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `dhan_analyzed_trades_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadSampleCsv() {
  const sample = `Trade Date,Trade Time,Symbol,Type,Quantity,Trade Price,Order Tag
2024-10-01,09:30:00,NIFTY 24500 CE,BUY,75,115.00,Nifty Momentum Buyer (Stratzy)
2024-10-01,10:15:00,NIFTY 24500 CE,SELL,75,168.00,Nifty Momentum Buyer (Stratzy)
2024-10-02,09:20:00,BANKNIFTY 51500 CE,SELL,30,185.00,BankNifty Short Strangle (Stratzy)
2024-10-02,15:20:00,BANKNIFTY 51500 CE,BUY,30,92.00,BankNifty Short Strangle (Stratzy)
2024-10-03,13:15:00,FINNIFTY 23500 CE,BUY,65,45.00,FinNifty Zero-Hero (Stratzy)
2024-10-03,13:45:00,FINNIFTY 23500 CE,SELL,65,28.00,FinNifty Zero-Hero (Stratzy)
`;
  const blob = new Blob([sample], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'dhan_tradebook_sample_template.csv';
  a.click();
  URL.revokeObjectURL(url);
}

async function clearDhanData() {
  await fetch(`${API}/api/dhan/clear`, { method: 'POST' });
  state.dhan.analytics = null;
  state.dhan.trades = [];
  state.dhan.filteredTrades = [];
  document.getElementById('dhan-dashboard')?.classList.add('hidden');
  document.getElementById('dhan-empty-state')?.classList.remove('hidden');
  document.getElementById('dhan-clear-btn')?.classList.add('hidden');
  const badge = document.getElementById('dhan-badge');
  if (badge) badge.style.display = 'none';
}

async function reconcileStratzyAlgos() {
  const btn = document.getElementById('dhan-reconcile-btn');
  const matchBadge = document.getElementById('dhan-stratzy-match-badge');
  const summaryText = document.getElementById('dhan-stratzy-summary-text');

  if (!state.dhan.trades || state.dhan.trades.length === 0) {
    alert('Please connect DhanHQ or upload a tradebook CSV first.');
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = 'Syncing signals...'; }
  if (matchBadge) { matchBadge.textContent = 'Fetching...'; matchBadge.className = 'verdict-badge verdict-caution'; }
  if (summaryText) summaryText.textContent = 'Fetching latest Stratzy signals and matching against Dhan executions...';

  try {
    const res = await fetch(`${API}/api/dhan/reconcile`, { method: 'POST' });
    const data = await res.json();

    if (data.success && data.analytics) {
      renderDhanAnalytics(data.analytics);
      const stats = data.stats || {};
      const toast = document.createElement('div');
      toast.style.cssText = 'position:fixed;bottom:24px;right:24px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.4);color:#10b981;padding:12px 20px;border-radius:10px;font-size:13px;font-weight:600;z-index:9999;backdrop-filter:blur(8px);transition:opacity 0.4s ease;';
      toast.textContent = `✅ Matched ${stats.matched || 0} of ${stats.total || 0} trades (${stats.matchPct || 0}%) with Stratzy Algos`;
      document.body.appendChild(toast);
      setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 400); }, 3500);
    } else {
      alert(data.message || 'Reconciliation failed. Ensure you are logged in to Stratzy.');
      if (matchBadge) { matchBadge.textContent = 'Error'; matchBadge.className = 'verdict-badge verdict-swap'; }
      if (summaryText) summaryText.textContent = data.message || 'Failed to fetch Stratzy signals';
    }
  } catch (err) {
    alert('Error calling reconcile: ' + err.message);
    if (matchBadge) { matchBadge.textContent = 'Error'; matchBadge.className = 'verdict-badge verdict-swap'; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Re-sync Signals'; }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  // Keyboard shortcut: Enter to login
  document.getElementById('cookie-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.ctrlKey) doLogin();
  });

  // Render watchlist badge
  const badge = document.getElementById('watchlist-badge');
  if (state.watchlist.length > 0) {
    badge.textContent = state.watchlist.length;
    badge.style.display = 'inline-block';
  }

  // Init Dhan Drag & Drop
  initDhanDropzone();

  // Init Dhan Date Presets (default to last 30 days)
  setDhanDatePreset(30);

  // Check if already authenticated (server restart case)
  fetch(`${API}/api/auth/status`)
    .then(r => r.json())
    .then(data => {
      if (data.authenticated) showApp();
    })
    .catch(() => {});
});

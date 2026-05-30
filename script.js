// ── Config ────────────────────────────────────────────────
const API = '';   // same origin; change to 'http://localhost:5000' if serving separately

// ── Colour helpers ────────────────────────────────────────
const COLOUR_CSS = {
  Red:'--red', Orange:'--orange', Yellow:'--yellow',
  Green:'--green', Blue:'--blue', Brown:'--brown', Purple:'--purple'
};
function colourOf(n) {
  if (n >=  1 && n <=  7) return 'Red';
  if (n >=  8 && n <= 14) return 'Orange';
  if (n >= 15 && n <= 21) return 'Yellow';
  if (n >= 22 && n <= 28) return 'Green';
  if (n >= 29 && n <= 36) return 'Blue';
  if (n >= 37 && n <= 42) return 'Brown';
  if (n >= 43 && n <= 49) return 'Purple';
  return 'Unknown';
}
function ballColourClass(n) { return 'c-' + colourOf(n); }
function ballColourVar(n)   { return `var(${COLOUR_CSS[colourOf(n)] || '--muted'})`; }

// ── Ball HTML ─────────────────────────────────────────────
function ballHTML(n, extraClass='') {
  const cls = ballColourClass(n);
  return `<div class="ball ${cls} ${extraClass}" role="img" aria-label="Ball ${n}">${n}</div>`;
}
function miniBallHTML(n) {
  const cls = ballColourClass(n);
  return `<div class="mini-ball ${cls}" role="img" aria-label="Ball ${n}">${n}</div>`;
}
function tagBallHTML(n, setLabel) {
  const cls = ballColourClass(n);
  return `<span class="tag-ball"><span class="dot ${cls}" role="img" aria-label="Ball ${n}"></span>${setLabel}</span>`;
}

// ── Tab switching ─────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
  });
});

// ── Draw pill selection ───────────────────────────────────
let activeDraw = 'all';
document.querySelectorAll('.pill').forEach(p => {
  p.addEventListener('click', () => {
    document.querySelectorAll('.pill').forEach(x => x.classList.remove('active'));
    p.classList.add('active');
    activeDraw = p.dataset.draw;
  });
});

// ── Status indicator ──────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch(`${API}/api/health`, {signal: AbortSignal.timeout(3000)});
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (r.ok) {
      dot.className = 'status-dot live';
      txt.textContent = 'API online';
    } else {
      dot.className = 'status-dot';
      txt.textContent = 'API error';
    }
  } catch {
    document.getElementById('statusDot').className = 'status-dot';
    document.getElementById('statusText').textContent = 'API offline';
  }
}
checkHealth();

// ── Fetch Results ─────────────────────────────────────────
const fetchBtn    = document.getElementById('fetchBtn');
const fetchSpinner= document.getElementById('fetchSpinner');
const resultsErr  = document.getElementById('resultsError');

// Cache of last fetched results for auto-fill
let lastResults = {};

fetchBtn.addEventListener('click', fetchResults);

async function fetchResults() {
  const num = document.getElementById('numSelect').value;
  setLoading(fetchBtn, fetchSpinner, document.getElementById('fetchBtnLabel'), true);
  resultsErr.classList.remove('show');
  document.getElementById('resultsContainer').innerHTML = '';

  try {
    const res  = await fetch(`${API}/api/results?draw=${activeDraw}&num=${num}`);
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);
    lastResults = json.data;
    renderResults(json.data);
    updateAutoFill(json.data);
  } catch(e) {
    resultsErr.textContent = e.message;
    resultsErr.classList.add('show');
    document.getElementById('resultsContainer').innerHTML =
      `<div class="empty"><div class="icon">⚠️</div><p>${e.message}</p></div>`;
  } finally {
    setLoading(fetchBtn, fetchSpinner, document.getElementById('fetchBtnLabel'), false);
  }
}

const DRAW_META = {
  brunchtime: { label:'Brunchtime', time:'11:49 AM', weight: 1, icon:'🍳' },
  lunchtime:  { label:'Lunchtime',  time:'12:49 PM', weight: 2, icon:'🥗' },
  drivetime:  { label:'Drivetime',  time:'04:49 PM', weight: 3, icon:'🚗' },
  teatime:    { label:'Teatime',    time:'05:49 PM', weight: 4, icon:'🍵' },
};

function renderResults(data) {
  const container = document.getElementById('resultsContainer');
  let html = '';

  // Flatten all draws into a single list
  let allDraws = [];
  for (const [dtype, draws] of Object.entries(data)) {
    draws.forEach(d => {
      allDraws.push({ ...d, type: dtype });
    });
  }

  // Sort by date (descending)
  allDraws.sort((a, b) => new Date(b.date) - new Date(a.date));

  // Group by date
  const groupedByDate = {};
  allDraws.forEach(d => {
    if (!groupedByDate[d.date]) groupedByDate[d.date] = [];
    groupedByDate[d.date].push(d);
  });

  // For the Generator page "recent results" variable display
  renderRecentVariables(allDraws.slice(0, 20));

  for (const [date, draws] of Object.entries(groupedByDate)) {
    // Sort draws within the same day by weight (chronological)
    draws.sort((a, b) => (DRAW_META[a.type]?.weight || 0) - (DRAW_META[b.type]?.weight || 0));

    html += `
      <div class="draw-section">
        <div class="draw-header">
          <div class="draw-title">${date.toUpperCase()}</div>
          <span class="draw-count">${draws.length} draw${draws.length!==1?'s':''}</span>
        </div>
        <div class="results-grid">`;

    for (const r of draws) {
      const meta = DRAW_META[r.type] || { label: r.type, icon: '🎱' };
      html += `
        <div class="result-card">
          <div class="draw-header" style="border:none; margin-bottom:5px; padding:0;">
            <div class="draw-icon" style="width:20px; height:20px; font-size:12px; background:rgba(0,212,255,.1)">${meta.icon}</div>
            <div class="draw-title" style="font-size:12px;">${meta.label} (${meta.time})</div>
          </div>
          <div class="balls">
            ${r.numbers.map(n => ballHTML(n)).join('')}
            ${r.bonus_ball !== null ? `<span class="ball-divider">|</span>${ballHTML(r.bonus_ball,'bonus')}` : ''}
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }

  container.innerHTML = html || `<div class="empty"><div class="icon">📭</div><p>No data returned</p></div>`;
}

function calculateVZ(numbers, bonus) {
  const v = numbers.reduce((a, b) => a + b, 0);
  const w = v + (bonus || 0);
  const x = v * 3;
  const y = w * 3;
  const z = x + y;
  return { v, w, x, y, z };
}

function renderRecentVariables(draws) {
  const tableContainer = document.getElementById('recentVariablesContainer');
  if (!tableContainer) return;

  let html = `
    <table class="var-table">
      <thead>
        <tr>
          <th>Draw</th>
          <th>Date</th>
          <th>V</th>
          <th>W</th>
          <th>X</th>
          <th>Y</th>
          <th>Z</th>
        </tr>
      </thead>
      <tbody>`;

  draws.forEach(d => {
    const meta = DRAW_META[d.type] || { label: d.type };
    const vars = calculateVZ(d.numbers, d.bonus_ball);
    html += `
      <tr>
        <td style="font-size:11px">${meta.label}</td>
        <td style="font-size:11px">${d.date}</td>
        <td>${vars.v}</td>
        <td>${vars.w}</td>
        <td>${vars.x}</td>
        <td>${vars.y}</td>
        <td style="font-weight:500; color:var(--accent)">${vars.z}</td>
      </tr>`;
  });

  html += '</tbody></table>';
  tableContainer.innerHTML = html;
}

// ── Auto-fill buttons ─────────────────────────────────────
function updateAutoFill(data) {
  const row = document.getElementById('autoFillRow');
  const existing = row.querySelectorAll('.auto-pill');
  existing.forEach(e => e.remove());

  for (const [dtype, draws] of Object.entries(data)) {
    if (!draws.length) continue;
    const latest = draws[0];
    const meta   = DRAW_META[dtype] || { label: dtype };
    const btn    = document.createElement('button');
    btn.className   = 'auto-pill';
    btn.textContent = `Latest ${meta.label}`;
    btn.setAttribute('aria-label', `Auto-fill with latest ${meta.label} draw`);
    btn.addEventListener('click', () => {
      latest.numbers.forEach((n, i) => {
        document.getElementById('r' + (i+1)).value = n;
      });
      if (latest.bonus_ball) document.getElementById('r7').value = latest.bonus_ball;
    });
    row.appendChild(btn);
  }
}

// ── Client-side validation ─────────────────────────────────
function validateBallInput(input) {
  const val = parseInt(input.value);
  if (isNaN(val) || val < 1 || val > 49) {
    input.setCustomValidity('Enter a number between 1 and 49');
    input.classList.add('invalid');
  } else {
    input.setCustomValidity('');
    input.classList.remove('invalid');
  }
}

document.querySelectorAll('.ball-input').forEach(input => {
  input.addEventListener('input', () => validateBallInput(input));
  input.addEventListener('blur', () => validateBallInput(input));
});

// ── Analyser ──────────────────────────────────────────────
const analyseBtn    = document.getElementById('analyseBtn');
const analyseSpinner= document.getElementById('analyseSpinner');
const analyseErr    = document.getElementById('analyseError');

analyseBtn.addEventListener('click', runAnalysis);

async function runAnalysis() {
  analyseErr.classList.remove('show');

  const numbers = ['r1','r2','r3','r4','r5','r6'].map(id => {
    const v = parseInt(document.getElementById(id).value);
    return isNaN(v) ? null : v;
  });
  const bonus = parseInt(document.getElementById('r7').value);
  const tse   = null;

  // Client-side validation
  if (numbers.some(n => n === null) || numbers.some(n => n < 1 || n > 49)) {
    showErr(analyseErr, 'Please enter 6 valid main ball numbers (1–49).');
    return;
  }
  if (isNaN(bonus) || bonus < 1 || bonus > 49) {
    showErr(analyseErr, 'Please enter a valid bonus ball (1–49).');
    return;
  }

  setLoading(analyseBtn, analyseSpinner, document.getElementById('analyseBtnLabel'), true);

  try {
    const res  = await fetch(`${API}/api/analyse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ numbers, bonus, tse }),
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.error);
    renderAnalysis(json.data, numbers, bonus);
  } catch(e) {
    showErr(analyseErr, e.message);
  } finally {
    setLoading(analyseBtn, analyseSpinner, document.getElementById('analyseBtnLabel'), false);
  }
}

function renderAnalysis(data, numbers, bonus) {
  document.getElementById('analyserEmpty').style.display = 'none';
  const out = document.getElementById('analysisOutput');
  out.classList.add('show');

  // ── Variables v, w, x, y, z
  const xGrid = document.getElementById('xGrid');
  xGrid.innerHTML = Object.entries(data.variables).map(([k,v]) =>
    `<div class="x-item"><div class="x-label">${k.toUpperCase()}</div><div class="x-val">${v}</div></div>`
  ).join('');
}

// ── Utility helpers ───────────────────────────────────────
function setLoading(btn, spinner, label, loading) {
  btn.disabled = loading;
  spinner.classList.toggle('show', loading);
  label.textContent = loading ? 'Loading…' : (btn === fetchBtn ? 'Fetch Results' : 'Generate V-Z');
}
function showErr(el, msg) {
  el.textContent = msg;
  el.classList.add('show');
}
// Auto-fetch on load
window.addEventListener('DOMContentLoaded', () => {
  fetchResults();
});

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
  brunchtime: { label:'Brunchtime', time:'11:49 AM UK', icon:'🍳' },
  lunchtime:  { label:'Lunchtime',  time:'12:49 PM UK', icon:'🥗' },
  drivetime:  { label:'Drivetime',  time:'04:49 PM UK', icon:'🚗' },
  teatime:    { label:'Teatime',    time:'05:49 PM UK', icon:'🍵' },
};

function renderResults(data) {
  const container = document.getElementById('resultsContainer');
  let html = '';

  for (const [dtype, draws] of Object.entries(data)) {
    const meta = DRAW_META[dtype] || { label: dtype, time:'', icon:'🎱' };
    html += `
      <div class="draw-section">
        <div class="draw-header">
          <div class="draw-icon" style="background:rgba(0,212,255,.1)" role="img" aria-label="${meta.label} icon">${meta.icon}</div>
          <div class="draw-title">${meta.label.toUpperCase()}</div>
          <span class="draw-count">${draws.length} draw${draws.length!==1?'s':''}</span>
          <span class="draw-time">${meta.time}</span>
        </div>`;

    if (draws.length === 0) {
      html += `<div class="empty"><div class="icon">📭</div><p>No results available</p></div>`;
    } else {
      html += `<div class="results-grid">`;
      for (const r of draws) {
        html += `<div class="result-card">
          <div class="result-date">${r.date}</div>
          <div class="balls">
            ${r.numbers.map(n => ballHTML(n)).join('')}
            ${r.bonus_ball !== null ? `<span class="ball-divider">|</span>${ballHTML(r.bonus_ball,'bonus')}` : ''}
          </div>
        </div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
  }

  container.innerHTML = html || `<div class="empty"><div class="icon">📭</div><p>No data returned</p></div>`;
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
  const tse   = document.getElementById('tseInput').value.trim() || null;

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

  // ── Intermediates
  const xGrid = document.getElementById('xGrid');
  xGrid.innerHTML = Object.entries(data.intermediates).map(([k,v]) =>
    `<div class="x-item"><div class="x-label">${k}</div><div class="x-val">${v}</div></div>`
  ).join('');

  // ── Sets
  const sGrid = document.getElementById('setsGrid');
  const SET_LABELS = {
    S1: 'Concat/Add', S2: 'Neighbour', S3: 'Date ±2', S4: 'TSE Digits', S5: 'x1–x3 Combos'
  };
  sGrid.innerHTML = Object.entries(data.sets).map(([key, nums]) => `
    <div class="set-chip">
      <div class="set-label">${key} — ${SET_LABELS[key]||''}</div>
      <div class="set-nums">
        ${nums.length ? nums.map(miniBallHTML).join('') : '<span style="color:var(--muted);font-size:11px;">none in 1–49</span>'}
      </div>
    </div>`
  ).join('');

  // ── By colour
  const colGroup = document.getElementById('colourGroups');
  if (data.colour_analysis.length === 0) {
    colGroup.innerHTML = `<div class="empty" style="padding:20px"><p>No colour group has 3+ numbers</p></div>`;
  } else {
    colGroup.innerHTML = data.colour_analysis.map(g => `
      <div class="group-card gc-${g.colour}">
        <div class="group-header">
          <span class="mini-ball c-${g.colour}" style="flex-shrink:0">&nbsp;</span>
          <span class="group-name">${g.colour}</span>
          <span style="margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--muted)">${g.numbers.length} numbers</span>
        </div>
        <div class="group-nums">${g.numbers.map(i => tagBallHTML(i.number, i.set)).join('')}</div>
        <div class="section-label" style="margin-top:8px;margin-bottom:6px">3-ball combinations (${g.combos.length})</div>
        <div class="combos">${g.combos.map(c => `<span class="combo-tag">${c.join(' · ')}</span>`).join('')}</div>
      </div>`
    ).join('');
  }

  // ── By ending digit
  const digGroup = document.getElementById('digitGroups');
  if (data.digit_analysis.length === 0) {
    digGroup.innerHTML = `<div class="empty" style="padding:20px"><p>No ending-digit group has 3+ numbers</p></div>`;
  } else {
    digGroup.innerHTML = data.digit_analysis.map(g => `
      <div class="group-card gc-digit">
        <div class="group-header">
          <span class="group-name">Ends in ${g.digit}</span>
          <span style="margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--muted)">${g.numbers.length} numbers</span>
        </div>
        <div class="group-nums">${g.numbers.map(i => tagBallHTML(i.number, i.set)).join('')}</div>
        <div class="section-label" style="margin-top:8px;margin-bottom:6px">3-ball combinations (${g.combos.length})</div>
        <div class="combos">${g.combos.map(c => `<span class="combo-tag">${c.join(' · ')}</span>`).join('')}</div>
      </div>`
    ).join('');
  }
}

// ── Utility helpers ───────────────────────────────────────
function setLoading(btn, spinner, label, loading) {
  btn.disabled = loading;
  spinner.classList.toggle('show', loading);
  label.textContent = loading ? 'Loading…' : (btn === fetchBtn ? 'Fetch Results' : 'Run Analysis');
}
function showErr(el, msg) {
  el.textContent = msg;
  el.classList.add('show');
}
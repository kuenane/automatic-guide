<<<<<<< SEARCH
/* Colour group border colours ─────────────────────────── */
.gc-Red    { border-color: var(--red); }
.gc-Orange { border-color: var(--orange); }
.gc-Yellow { border-color: var(--yellow); }
.gc-Green  { border-color: var(--green); }
.gc-Blue   { border-color: var(--blue); }
.gc-Brown  { border-color: var(--brown); }
.gc-Purple { border-color: var(--purple); }
.gc-digit  { border-color: var(--accent); }
</style>
=======
/* Variables Table ────────────────────────────────────── */
.var-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
  font-family: var(--font-mono);
}
.var-table th, .var-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.var-table th {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 500;
}
.var-table td {
  font-size: 13px;
  color: var(--text);
}
.var-table tr:hover { background: rgba(0,212,255,.03); }

/* Colour group border colours ─────────────────────────── */
.gc-Red    { border-color: var(--red); }
.gc-Orange { border-color: var(--orange); }
.gc-Yellow { border-color: var(--yellow); }
.gc-Green  { border-color: var(--green); }
.gc-Blue   { border-color: var(--blue); }
.gc-Brown  { border-color: var(--brown); }
.gc-Purple { border-color: var(--purple); }
.gc-digit  { border-color: var(--accent); }
</style>
>>>>>>> REPLACE
<<<<<<< SEARCH
          <!-- Intermediates -->
          <div class="analysis-card" id="cardIntermediates">
            <h4>Generated Variables <span class="badge">v – z</span></h4>
            <div class="x-grid" id="xGrid"></div>
          </div>

        </div>
        <div id="analyserEmpty" class="empty">
          <div class="icon">🔬</div>
          <p>Enter a previous draw result and click <strong>Generate V-Z</strong></p>
        </div>
=======
          <!-- Intermediates -->
          <div class="analysis-card" id="cardIntermediates">
            <h4>Calculated Values <span class="badge">v – z</span></h4>
            <div class="x-grid" id="xGrid"></div>
          </div>

        </div>

        <div class="analysis-card" style="margin-top:20px;">
          <h4>Recent Results <span class="badge">v – z values</span></h4>
          <div id="recentVariablesContainer">
            <div class="empty" style="padding: 20px;">
              <p>Fetching results...</p>
            </div>
          </div>
        </div>

        <div id="analyserEmpty" class="empty">
          <div class="icon">🔬</div>
          <p>Enter a previous draw result and click <strong>Generate V-Z</strong></p>
        </div>
>>>>>>> REPLACE

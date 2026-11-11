"""
Amar Tax AI Agent - Local Web Application
Serves an institutional web portal on http://localhost:8080 for executing
the 4-agent CrewAI Tax Readiness Advisor on test cases or custom profiles.
"""

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import logging
from pathlib import Path
import re
import socket
import sys
import threading
import urllib.request
import webbrowser

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
import uvicorn

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.crew import run_tax_advisor  # noqa: E402
from test_cases import TEST_CASES  # noqa: E402

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_CREW_LOCK = threading.Lock()


def parse_profile(payload: dict) -> dict:
    """Validates and normalizes taxpayer profile inputs from the web form."""
    try:
        age = int(payload.get("age", 30))
        total_income = float(payload.get("total_income", 0.0))
        investment = float(payload.get("investment", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value: {exc}") from exc

    gender = str(payload.get("gender", "General")).strip() or "General"
    profession = str(payload.get("profession", "General")).strip() or "General"
    location = str(payload.get("location", "Dhaka")).strip() or "Dhaka"
    raw_sources = payload.get("income_sources", [])
    if isinstance(raw_sources, str):
        income_sources = [s.strip().lower() for s in raw_sources.split(",") if s.strip()]
    elif isinstance(raw_sources, list):
        income_sources = [str(s).strip().lower() for s in raw_sources if str(s).strip()]
    else:
        income_sources = []

    return {
        "age": age,
        "gender": gender,
        "profession": profession,
        "total_income": total_income,
        "investment": investment,
        "location": location,
        "has_tin": bool(payload.get("has_tin", True)),
        "wants_independent_filing": bool(payload.get("wants_independent_filing", True)),
        "claims_required_to_file": bool(payload.get("claims_required_to_file", False)),
        "is_disabled": bool(payload.get("is_disabled", False)),
        "is_freedom_fighter": bool(payload.get("is_freedom_fighter", False)),
        "income_sources": income_sources,
    }


def run_advisory_with_logs(profile: dict) -> tuple[str, str]:
    """Executes the CrewAI advisor sequentially while capturing stdout and logs."""
    buf = io.StringIO()
    stream_handler = logging.StreamHandler(buf)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root_logger = logging.getLogger()

    with _CREW_LOCK:
        root_logger.addHandler(stream_handler)
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                report = run_tax_advisor(profile)
        finally:
            root_logger.removeHandler(stream_handler)

    logs = ANSI_RE.sub("", buf.getvalue())
    return report, logs


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Amar Tax — Individual Income Tax Advisory Portal</title>
  <style>
    :root {
      --bg: #f5f6f8;
      --surface: #ffffff;
      --surface-alt: #f9fafb;
      --border: #e2e5ea;
      --border-strong: #cfd5dd;
      --ink: #111827;
      --ink-secondary: #374151;
      --ink-muted: #6b7280;
      --brand: #0b5d46;
      --brand-hover: #084836;
      --brand-tint: #eef6f3;
      --pass-ink: #065f46;
      --pass-bg: #ecfdf5;
      --pass-border: #a7f3d0;
      --warn-ink: #92400e;
      --warn-bg: #fffbeb;
      --warn-border: #fcd34d;
      --err-ink: #991b1b;
      --err-bg: #fef2f2;
      --err-border: #fecaca;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, "Noto Sans Bengali", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
    }
    .topbar-inner {
      max-width: 1220px;
      margin: 0 auto;
      padding: 14px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-mark {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      background: var(--brand);
      color: #ffffff;
      display: grid;
      place-items: center;
      flex-shrink: 0;
    }
    .brand-title {
      font-size: 1.05rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--ink);
    }
    .brand-sub {
      font-size: 0.8rem;
      color: var(--ink-muted);
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 0.78rem;
      font-weight: 500;
      color: var(--ink-secondary);
      background: var(--surface-alt);
      border: 1px solid var(--border);
      padding: 5px 11px;
      border-radius: 999px;
    }
    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #16a34a;
    }
    .container {
      max-width: 1220px;
      margin: 0 auto;
      padding: 20px 20px 48px;
    }
    .presets-bar {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 18px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }
    .presets-label {
      font-size: 0.76rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--ink-muted);
      margin-right: 4px;
    }
    .tc-btn {
      background: var(--surface-alt);
      color: var(--ink-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 11px;
      font-size: 0.81rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.14s ease;
    }
    .tc-btn:hover {
      border-color: var(--border-strong);
      color: var(--ink);
      background: #f1f3f5;
    }
    .tc-btn.active {
      background: var(--brand-tint);
      border-color: var(--brand);
      color: var(--brand);
      font-weight: 600;
    }
    .workspace {
      display: grid;
      grid-template-columns: 400px 1fr;
      gap: 20px;
      align-items: start;
    }
    @media (max-width: 980px) {
      .workspace { grid-template-columns: 1fr; }
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    .panel-header {
      padding: 14px 18px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .panel-title {
      margin: 0;
      font-size: 0.94rem;
      font-weight: 600;
      color: var(--ink);
    }
    .panel-body {
      padding: 18px;
    }
    .section-group {
      margin-bottom: 16px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .section-group:last-of-type {
      margin-bottom: 14px;
      padding-bottom: 0;
      border-bottom: none;
    }
    .group-label {
      font-size: 0.74rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--ink-muted);
      margin: 0 0 10px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 11px;
    }
    .full { grid-column: 1 / -1; }
    label.field-label {
      display: block;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--ink-secondary);
      margin-bottom: 4px;
    }
    input[type="text"], input[type="number"], select {
      width: 100%;
      padding: 8px 10px;
      border-radius: 6px;
      border: 1px solid var(--border-strong);
      background: #ffffff;
      color: var(--ink);
      font-size: 0.88rem;
      font-family: inherit;
      transition: border-color 0.14s, box-shadow 0.14s;
    }
    input[type="number"] { font-variant-numeric: tabular-nums; }
    input:focus, select:focus {
      outline: none;
      border-color: var(--brand);
      box-shadow: 0 0 0 3px rgba(11, 93, 70, 0.12);
    }
    .checks {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 10px;
    }
    .check-item {
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 0.82rem;
      color: var(--ink-secondary);
      cursor: pointer;
      user-select: none;
    }
    .check-item input {
      accent-color: var(--brand);
      width: 15px;
      height: 15px;
      margin: 0;
      cursor: pointer;
    }
    .primary-btn {
      width: 100%;
      margin-top: 6px;
      padding: 10px 16px;
      border: none;
      border-radius: 7px;
      background: var(--brand);
      color: #ffffff;
      font-weight: 600;
      font-size: 0.9rem;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.14s;
    }
    .primary-btn:hover:not(:disabled) { background: var(--brand-hover); }
    .primary-btn:disabled { opacity: 0.65; cursor: wait; }
    .toolbar-actions {
      display: none;
      gap: 8px;
    }
    .ghost-btn {
      background: #ffffff;
      color: var(--ink-secondary);
      border: 1px solid var(--border-strong);
      border-radius: 6px;
      padding: 5px 10px;
      font-size: 0.78rem;
      font-weight: 500;
      cursor: pointer;
    }
    .ghost-btn:hover { background: var(--surface-alt); color: var(--ink); }
    .progress-box {
      display: none;
      border: 1px solid var(--border);
      background: var(--surface-alt);
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 16px;
    }
    .progress-top {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.87rem;
      font-weight: 500;
      color: var(--ink);
    }
    .spinner {
      width: 15px;
      height: 15px;
      border: 2px solid var(--border-strong);
      border-top-color: var(--brand);
      border-radius: 50%;
      animation: spin 0.75s linear infinite;
      flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .stages {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
      margin-top: 10px;
      font-size: 0.75rem;
      color: var(--ink-muted);
    }
    .stage-chip {
      padding: 4px 8px;
      border-radius: 5px;
      background: #ffffff;
      border: 1px solid var(--border);
      text-align: center;
    }
    .kpi-grid {
      display: none;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-bottom: 18px;
    }
    @media (max-width: 720px) { .kpi-grid { grid-template-columns: 1fr 1fr; } }
    .kpi-card {
      background: var(--surface-alt);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
    }
    .kpi-label {
      font-size: 0.73rem;
      color: var(--ink-muted);
      margin-bottom: 3px;
    }
    .kpi-value {
      font-size: 0.98rem;
      font-weight: 700;
      color: var(--ink);
      font-variant-numeric: tabular-nums;
    }
    .kpi-badge-pass { color: var(--pass-ink); }
    .kpi-badge-flag { color: var(--warn-ink); }
    .empty-state {
      text-align: center;
      padding: 56px 24px;
      color: var(--ink-muted);
      font-size: 0.9rem;
    }
    .empty-state strong { color: var(--ink-secondary); display: block; margin-bottom: 6px; font-size: 0.96rem; }
    .err-box {
      display: none;
      padding: 11px 14px;
      border-radius: 7px;
      margin-bottom: 14px;
      background: var(--err-bg);
      border: 1px solid var(--err-border);
      color: var(--err-ink);
      font-size: 0.87rem;
    }
    .report-area h3 {
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--ink);
      margin: 18px 0 8px;
      padding-bottom: 5px;
      border-bottom: 1px solid var(--border);
    }
    .report-area h3:first-child { margin-top: 0; }
    .report-area table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0 16px;
      font-size: 0.88rem;
    }
    .report-area th, .report-area td {
      padding: 9px 12px;
      border: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }
    .report-area th {
      background: var(--surface-alt);
      color: var(--ink-secondary);
      font-weight: 600;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .report-area td:first-child {
      width: 36%;
      font-weight: 500;
      color: var(--ink-secondary);
    }
    .report-area td:last-child {
      font-variant-numeric: tabular-nums;
      color: var(--ink);
    }
    .report-area p { margin: 8px 0; font-size: 0.92rem; color: var(--ink-secondary); }
    .report-area ul { padding-left: 18px; margin: 8px 0; font-size: 0.9rem; color: var(--ink-secondary); }
    .report-area li { margin-bottom: 4px; }
    .bangla-card {
      margin-top: 14px;
      padding: 13px 15px;
      background: var(--brand-tint);
      border: 1px solid #cce3da;
      border-left: 3px solid var(--brand);
      border-radius: 6px;
      font-size: 0.95rem;
      line-height: 1.75;
      color: var(--ink);
    }
    details {
      margin-top: 18px;
      border-top: 1px solid var(--border);
      padding-top: 12px;
    }
    summary {
      cursor: pointer;
      color: var(--ink-muted);
      font-size: 0.82rem;
      font-weight: 500;
    }
    summary:hover { color: var(--ink); }
    pre {
      background: #f8fafc;
      color: #1e293b;
      border: 1px solid var(--border);
      padding: 12px;
      border-radius: 7px;
      overflow-x: auto;
      max-height: 360px;
      font-size: 0.77rem;
      line-height: 1.45;
      margin-top: 10px;
    }
    @media print {
      body { background: #ffffff; }
      .presets-bar, .workspace > section:first-child, .toolbar-actions, details, .topbar .status-pill { display: none !important; }
      .workspace { grid-template-columns: 1fr; }
      .panel { border: none; box-shadow: none; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
        </div>
        <div>
          <div class="brand-title">Amar Tax Advisory</div>
          <div class="brand-sub">Bangladesh Individual Income Tax Readiness &amp; Compliance System · FY 2026–27</div>
        </div>
      </div>
      <div class="status-pill"><span class="status-dot"></span> Rulebook DB Active</div>
    </div>
  </header>

  <main class="container">
    <div class="presets-bar">
      <span class="presets-label">Scenarios</span>
      <div id="tc-list" style="display:flex;flex-wrap:wrap;gap:7px;"></div>
    </div>

    <div class="workspace">
      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">Taxpayer Profile</h2>
        </div>
        <div class="panel-body">
          <form id="tax-form">
            <div class="section-group">
              <div class="group-label">Personal &amp; Jurisdiction</div>
              <div class="form-grid">
                <div>
                  <label class="field-label" for="age">Age (Years)</label>
                  <input id="age" type="number" value="34" required />
                </div>
                <div>
                  <label class="field-label" for="gender">Gender</label>
                  <select id="gender">
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div class="full">
                  <label class="field-label" for="profession">Profession / Occupation</label>
                  <input id="profession" type="text" value="Software Engineer" required />
                </div>
                <div class="full">
                  <label class="field-label" for="location">City / Tax Jurisdiction</label>
                  <input id="location" type="text" value="Dhaka" required />
                </div>
              </div>
            </div>

            <div class="section-group">
              <div class="group-label">Financial Declaration (BDT)</div>
              <div class="form-grid">
                <div>
                  <label class="field-label" for="total_income">Annual Income (BDT)</label>
                  <input id="total_income" type="number" step="any" value="1500000" required />
                </div>
                <div>
                  <label class="field-label" for="investment">Eligible Investment (BDT)</label>
                  <input id="investment" type="number" step="any" value="200000" required />
                </div>
                <div class="full">
                  <label class="field-label" for="income_sources">Income Sources (comma-separated)</label>
                  <input id="income_sources" type="text" value="salaried, freelancer, investor" />
                </div>
              </div>
            </div>

            <div class="section-group">
              <div class="group-label">Compliance Declarations</div>
              <div class="checks">
                <label class="check-item"><input id="has_tin" type="checkbox" checked /> Active TIN Holder</label>
                <label class="check-item"><input id="wants_independent_filing" type="checkbox" checked /> Independent Filing</label>
                <label class="check-item"><input id="claims_required_to_file" type="checkbox" /> Claims Mandatory</label>
                <label class="check-item"><input id="is_disabled" type="checkbox" /> Disability Category</label>
                <label class="check-item"><input id="is_freedom_fighter" type="checkbox" /> Freedom Fighter</label>
              </div>
            </div>

            <button id="run-btn" class="primary-btn" type="submit">Generate Tax Readiness Report</button>
          </form>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">Assessment &amp; Compliance Statement</h2>
          <div id="toolbar-actions" class="toolbar-actions">
            <button id="copy-btn" class="ghost-btn" type="button">Copy Markdown</button>
            <button id="print-btn" class="ghost-btn" type="button">Print / PDF</button>
          </div>
        </div>
        <div class="panel-body">
          <div id="progress-box" class="progress-box">
            <div class="progress-top">
              <div class="spinner"></div>
              <span>Evaluating eligibility, slab calculation, documentation, and compliance audit...</span>
            </div>
            <div class="stages">
              <div class="stage-chip">1. Classification</div>
              <div class="stage-chip">2. Slab Tax</div>
              <div class="stage-chip">3. Checklist</div>
              <div class="stage-chip">4. Audit Review</div>
            </div>
          </div>

          <div id="err-box" class="err-box"></div>

          <div id="kpi-grid" class="kpi-grid">
            <div class="kpi-card">
              <div class="kpi-label">Net Payable Tax</div>
              <div class="kpi-value" id="kpi-net">—</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Tax-Free Threshold</div>
              <div class="kpi-value" id="kpi-threshold">—</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Investment Rebate</div>
              <div class="kpi-value" id="kpi-rebate">—</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Audit Status</div>
              <div class="kpi-value" id="kpi-status">—</div>
            </div>
          </div>

          <div id="report-area" class="report-area">
            <div class="empty-state">
              <strong>Ready for Assessment</strong>
              Choose a scenario above or enter taxpayer details on the left, then click <em>Generate Tax Readiness Report</em>.
            </div>
          </div>

          <details id="logs-wrap" style="display:none;">
            <summary>Execution &amp; Database Fallback Logs</summary>
            <pre id="logs-box"></pre>
          </details>
        </div>
      </section>
    </div>
  </main>

  <script>
    const tcListEl = document.getElementById('tc-list');
    const formEl = document.getElementById('tax-form');
    const runBtn = document.getElementById('run-btn');
    const progressBox = document.getElementById('progress-box');
    const errBox = document.getElementById('err-box');
    const kpiGrid = document.getElementById('kpi-grid');
    const reportArea = document.getElementById('report-area');
    const logsWrap = document.getElementById('logs-wrap');
    const logsBox = document.getElementById('logs-box');
    const toolbarActions = document.getElementById('toolbar-actions');
    const copyBtn = document.getElementById('copy-btn');
    const printBtn = document.getElementById('print-btn');
    let lastRawMarkdown = '';

    const PRESET_LABELS = [
      'Example: Software Eng. (Dhaka)',
      'Edge 1: Minor (16y)',
      'Edge 4: Below Threshold (Rangpur)',
      'Edge 3: Excess Investment',
      'Edge 5: Missing TIN',
      'Edge 6: Unlisted Profession'
    ];

    function esc(s) {
      return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function inlineFmt(s) {
      return esc(s)
        .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
    }

    function extractKPIs(md) {
      const map = {};
      for (const raw of md.split('\\n')) {
        const line = raw.trim();
        if (!line.startsWith('|') || !line.endsWith('|')) continue;
        const parts = line.slice(1, -1).split('|').map(c => c.trim().replace(/\\*\\*/g, ''));
        if (parts.length >= 2) {
          map[parts[0].toLowerCase()] = parts[1];
        }
      }
      const net = map['net payable tax'];
      const threshold = map['tax-free threshold'];
      const rebate = map['investment rebate (15%)'];
      const status = map['compliance status'];

      if (net || threshold || rebate || status) {
        document.getElementById('kpi-net').textContent = net || '—';
        document.getElementById('kpi-threshold').textContent = threshold || '—';
        document.getElementById('kpi-rebate').textContent = rebate || '—';
        const statusEl = document.getElementById('kpi-status');
        statusEl.textContent = status || '—';
        statusEl.className = 'kpi-value ' + ((status || '').includes('Passed') ? 'kpi-badge-pass' : 'kpi-badge-flag');
        kpiGrid.style.display = 'grid';
      } else {
        kpiGrid.style.display = 'none';
      }
    }

    function isBanglaLine(line) {
      return /[\\u0980-\\u09FF]/.test(line);
    }

    function renderMarkdown(md) {
      const lines = md.replace(/\\r\\n/g, '\\n').split('\\n');
      let html = '', inTable = false, inList = false, banglaBuf = [];

      const closeList = () => { if (inList) { html += '</ul>'; inList = false; } };
      const closeTable = () => { if (inTable) { html += '</tbody></table>'; inTable = false; } };
      const flushBangla = () => {
        if (banglaBuf.length) {
          html += '<div class="bangla-card">' + banglaBuf.map(inlineFmt).join('<br>') + '</div>';
          banglaBuf = [];
        }
      };

      for (const raw of lines) {
        const line = raw.trim();
        if (!line) { closeList(); closeTable(); flushBangla(); continue; }
        if (line === '---') { closeList(); closeTable(); flushBangla(); continue; }

        if (line.startsWith('|') && line.endsWith('|')) {
          closeList(); flushBangla();
          const cells = line.slice(1, -1).split('|').map(c => c.trim());
          if (cells.every(c => /^:?-{2,}:?$/.test(c))) continue;
          if (!inTable) {
            html += '<table><thead><tr>' + cells.map(c => '<th>' + inlineFmt(c) + '</th>').join('') + '</tr></thead><tbody>';
            inTable = true;
          } else {
            html += '<tr>' + cells.map(c => '<td>' + inlineFmt(c) + '</td>').join('') + '</tr>';
          }
          continue;
        }
        closeTable();

        if (/^#{1,4}\\s+/.test(line)) {
          closeList(); flushBangla();
          const txt = line.replace(/^#{1,4}\\s+/, '');
          html += '<h3>' + inlineFmt(txt) + '</h3>';
          continue;
        }
        if (/^[-*]\\s+/.test(line)) {
          flushBangla();
          if (!inList) { html += '<ul>'; inList = true; }
          html += '<li>' + inlineFmt(line.replace(/^[-*]\\s+/, '')) + '</li>';
          continue;
        }
        closeList();

        if (isBanglaLine(line)) {
          banglaBuf.push(line);
        } else {
          flushBangla();
          html += '<p>' + inlineFmt(line) + '</p>';
        }
      }
      closeList();
      closeTable();
      flushBangla();
      return html;
    }

    function fillProfile(p) {
      document.getElementById('age').value = p.age;
      document.getElementById('gender').value = p.gender;
      document.getElementById('profession').value = p.profession;
      document.getElementById('total_income').value = p.total_income;
      document.getElementById('investment').value = p.investment;
      document.getElementById('location').value = p.location;
      document.getElementById('income_sources').value = (p.income_sources || []).join(', ');
      document.getElementById('has_tin').checked = !!p.has_tin;
      document.getElementById('wants_independent_filing').checked = !!p.wants_independent_filing;
      document.getElementById('claims_required_to_file').checked = !!p.claims_required_to_file;
      document.getElementById('is_disabled').checked = !!p.is_disabled;
      document.getElementById('is_freedom_fighter').checked = !!p.is_freedom_fighter;
    }

    fetch('/api/test-cases').then(r => r.json()).then(cases => {
      cases.forEach((tc, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'tc-btn' + (idx === 0 ? ' active' : '');
        btn.textContent = PRESET_LABELS[idx] || tc.name;
        btn.onclick = () => {
          document.querySelectorAll('.tc-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          fillProfile(tc.profile);
        };
        tcListEl.appendChild(btn);
      });
    });

    copyBtn.onclick = async () => {
      if (!lastRawMarkdown) return;
      await navigator.clipboard.writeText(lastRawMarkdown);
      const prev = copyBtn.textContent;
      copyBtn.textContent = 'Copied';
      setTimeout(() => { copyBtn.textContent = prev; }, 1500);
    };
    printBtn.onclick = () => window.print();

    formEl.onsubmit = async (e) => {
      e.preventDefault();
      errBox.style.display = 'none';
      progressBox.style.display = 'block';
      runBtn.disabled = true;

      const payload = {
        age: Number(document.getElementById('age').value),
        gender: document.getElementById('gender').value,
        profession: document.getElementById('profession').value,
        total_income: Number(document.getElementById('total_income').value),
        investment: Number(document.getElementById('investment').value),
        location: document.getElementById('location').value,
        income_sources: document.getElementById('income_sources').value,
        has_tin: document.getElementById('has_tin').checked,
        wants_independent_filing: document.getElementById('wants_independent_filing').checked,
        claims_required_to_file: document.getElementById('claims_required_to_file').checked,
        is_disabled: document.getElementById('is_disabled').checked,
        is_freedom_fighter: document.getElementById('is_freedom_fighter').checked
      };

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Request failed');
        lastRawMarkdown = data.report || '';
        extractKPIs(lastRawMarkdown);
        reportArea.innerHTML = renderMarkdown(lastRawMarkdown);
        logsBox.textContent = data.logs || '';
        logsWrap.style.display = 'block';
        toolbarActions.style.display = 'flex';
      } catch (err) {
        errBox.textContent = 'Assessment failed: ' + err.message;
        errBox.style.display = 'block';
      } finally {
        progressBox.style.display = 'none';
        runBtn.disabled = false;
      }
    };
  </script>
</body>
</html>
"""


async def index(_request: Request) -> HTMLResponse:
    """Serves the Amar Tax web dashboard."""
    return HTMLResponse(HTML_PAGE)


async def get_test_cases(_request: Request) -> JSONResponse:
    """Returns the predefined assignment test cases."""
    return JSONResponse(TEST_CASES)


async def health(_request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "app": "amar-tax"})


async def analyze(request: Request) -> JSONResponse:
    """Runs the 4-agent CrewAI advisory pipeline for the submitted taxpayer profile."""
    try:
        payload = await request.json()
        profile = parse_profile(payload)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    try:
        report, logs = await asyncio.to_thread(run_advisory_with_logs, profile)
        return JSONResponse({"report": report, "logs": logs})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


app = Starlette(
    routes=[
        Route("/", index, methods=["GET"]),
        Route("/api/test-cases", get_test_cases, methods=["GET"]),
        Route("/api/health", health, methods=["GET"]),
        Route("/api/analyze", analyze, methods=["POST"]),
    ]
)


def _port_in_use(host: str, port: int) -> bool:
    """Returns True if a TCP server is already listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _is_amar_tax_running(port: int) -> bool:
    """Checks whether our Amar Tax server is already serving on the given port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as resp:
            return resp.status == 200 and b"amar-tax" in resp.read()
    except Exception:
        return False


def main() -> None:
    """Starts the local Uvicorn web server or opens the browser if already running."""
    host = "127.0.0.1"
    port = 8080
    open_browser = "--no-browser" not in sys.argv

    if _port_in_use(host, port):
        if _is_amar_tax_running(port):
            url = f"http://localhost:{port}"
            print(f"Amar Tax Web UI is already running at {url}.")
            if open_browser:
                webbrowser.open(url)
            return
        # Find next available port if 8080 belongs to another process
        for candidate in range(8081, 8090):
            if not _port_in_use(host, candidate):
                port = candidate
                break

    url = f"http://localhost:{port}"
    print(f"Starting Amar Tax Advisory Portal at {url} ...")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

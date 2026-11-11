"""
Amar Tax AI Agent - Local Web Application (Port 8080)
Provides a browser UI for running the 4-agent CrewAI Tax Readiness Advisor
with all 6 assignment test cases or custom taxpayer profiles.
"""

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import logging
from pathlib import Path
import re
import sys
import threading
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
        raise ValueError(f"Numeric field error: {exc}") from exc

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
    """Executes the CrewAI advisor under a lock while capturing stdout and log output."""
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
  <title>Amar Tax AI Agent — Virtual Tax Advisor</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --card-alt: #162032;
      --border: #334155;
      --text: #f1f5f9;
      --muted: #94a3b8;
      --accent: #10b981;
      --accent-hover: #059669;
      --warn: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Bengali", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }
    .container { max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }
    header {
      display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
      gap: 12px; padding-bottom: 18px; border-bottom: 1px solid var(--border); margin-bottom: 22px;
    }
    h1 { margin: 0; font-size: 1.55rem; display: flex; align-items: center; gap: 10px; }
    .badge {
      font-size: 0.78rem; padding: 4px 10px; border-radius: 999px;
      background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .sub { color: var(--muted); font-size: 0.92rem; margin: 4px 0 0; }
    .grid { display: grid; grid-template-columns: 420px 1fr; gap: 20px; align-items: start; }
    @media (max-width: 960px) { .grid { grid-template-columns: 1fr; } }
    .card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; padding: 18px;
    }
    .card h2 { margin: 0 0 12px; font-size: 1.05rem; color: #e2e8f0; }
    .tc-list { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
    .tc-btn {
      background: var(--card-alt); color: var(--text); border: 1px solid var(--border);
      border-radius: 8px; padding: 8px 10px; text-align: left; cursor: pointer; font-size: 0.82rem;
      transition: border-color 0.15s, background 0.15s;
    }
    .tc-btn:hover, .tc-btn.active { border-color: var(--accent); background: rgba(16, 185, 129, 0.12); }
    .tc-btn strong { display: block; color: #34d399; font-size: 0.78rem; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .full { grid-column: 1 / -1; }
    label { display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 4px; }
    input[type="text"], input[type="number"], select {
      width: 100%; padding: 8px 10px; border-radius: 8px;
      border: 1px solid var(--border); background: var(--bg); color: var(--text); font-size: 0.9rem;
    }
    .checks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; font-size: 0.85rem; }
    .checks label { display: flex; align-items: center; gap: 6px; color: var(--text); margin: 0; cursor: pointer; }
    .run-btn {
      width: 100%; padding: 11px 16px; border: none; border-radius: 8px;
      background: var(--accent); color: #052e16; font-weight: 700; font-size: 0.96rem;
      cursor: pointer; transition: background 0.15s;
    }
    .run-btn:hover:not(:disabled) { background: var(--accent-hover); color: #fff; }
    .run-btn:disabled { opacity: 0.6; cursor: wait; }
    .status-bar {
      display: none; align-items: center; gap: 10px; padding: 12px 14px;
      border-radius: 8px; background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
      margin-bottom: 14px; font-size: 0.9rem;
    }
    .spinner {
      width: 16px; height: 16px; border: 2px solid #93c5fd; border-top-color: transparent;
      border-radius: 50%; animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .report-area h3, .report-area h2, .report-area h1 { color: #34d399; margin: 14px 0 8px; font-size: 1.05rem; }
    .report-area table { width: 100%; border-collapse: collapse; margin: 10px 0 16px; font-size: 0.92rem; }
    .report-area th, .report-area td {
      padding: 9px 11px; border: 1px solid var(--border); text-align: left; vertical-align: top;
    }
    .report-area th { background: var(--card-alt); color: #34d399; }
    .report-area tr:nth-child(even) td { background: rgba(15, 23, 42, 0.35); }
    .report-area ul { padding-left: 20px; margin: 8px 0; }
    .empty { color: var(--muted); text-align: center; padding: 48px 16px; }
    .err-box {
      display: none; padding: 12px; border-radius: 8px; margin-bottom: 12px;
      background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.45); color: #fecaca;
    }
    details { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 12px; }
    summary { cursor: pointer; color: var(--muted); font-size: 0.88rem; }
    pre {
      background: #020617; color: #cbd5e1; padding: 12px; border-radius: 8px;
      overflow-x: auto; max-height: 360px; font-size: 0.78rem; line-height: 1.45;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🇧🇩 "Amar Tax" AI Agent <span class="badge">CrewAI 4-Agent MAS</span></h1>
        <p class="sub">Classifier → Slab Calculator → Document Organizer → Compliance Reviewer (English Table + Bangla Summary)</p>
      </div>
      <span class="badge">Localhost :8080</span>
    </header>

    <div class="grid">
      <section class="card">
        <h2>1. Quick Load Assignment Test Cases</h2>
        <div id="tc-list" class="tc-list"></div>

        <h2>2. Taxpayer Profile</h2>
        <form id="tax-form">
          <div class="form-grid">
            <div>
              <label for="age">Age</label>
              <input id="age" type="number" value="34" required />
            </div>
            <div>
              <label for="gender">Gender</label>
              <select id="gender">
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div class="full">
              <label for="profession">Profession</label>
              <input id="profession" type="text" value="Software Engineer" required />
            </div>
            <div>
              <label for="total_income">Total Annual Income (BDT)</label>
              <input id="total_income" type="number" step="any" value="1500000" required />
            </div>
            <div>
              <label for="investment">Annual Investment (BDT)</label>
              <input id="investment" type="number" step="any" value="200000" required />
            </div>
            <div>
              <label for="location">Location</label>
              <input id="location" type="text" value="Dhaka" required />
            </div>
            <div>
              <label for="income_sources">Income Sources (CSV)</label>
              <input id="income_sources" type="text" value="salaried, freelancer, investor" />
            </div>
          </div>

          <div class="checks">
            <label><input id="has_tin" type="checkbox" checked /> Has TIN</label>
            <label><input id="wants_independent_filing" type="checkbox" checked /> Independent Filing</label>
            <label><input id="claims_required_to_file" type="checkbox" /> Claims Required</label>
            <label><input id="is_disabled" type="checkbox" /> Disabled</label>
            <label><input id="is_freedom_fighter" type="checkbox" /> Freedom Fighter</label>
          </div>

          <button id="run-btn" class="run-btn" type="submit">▶ Run 4-Agent Tax Advisory</button>
        </form>
      </section>

      <section class="card">
        <h2>3. Tax Readiness Report</h2>
        <div id="status-bar" class="status-bar">
          <div class="spinner"></div>
          <span>Running 4 CrewAI agents (Classifier → Calculator → Organizer → Reviewer)... typically takes 15–30s.</span>
        </div>
        <div id="err-box" class="err-box"></div>
        <div id="report-area" class="report-area">
          <div class="empty">Select a Test Case or customize the Taxpayer Profile on the left, then click <strong>Run 4-Agent Tax Advisory</strong>.</div>
        </div>
        <details id="logs-wrap" style="display:none;">
          <summary>Show Verbose Agent Execution & Fallback Logs</summary>
          <pre id="logs-box"></pre>
        </details>
      </section>
    </div>
  </div>

  <script>
    const tcListEl = document.getElementById('tc-list');
    const formEl = document.getElementById('tax-form');
    const runBtn = document.getElementById('run-btn');
    const statusBar = document.getElementById('status-bar');
    const errBox = document.getElementById('err-box');
    const reportArea = document.getElementById('report-area');
    const logsWrap = document.getElementById('logs-wrap');
    const logsBox = document.getElementById('logs-box');

    function esc(s) {
      return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function inlineFmt(s) {
      return esc(s)
        .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
    }

    function renderMarkdown(md) {
      const lines = md.replace(/\\r\\n/g, '\\n').split('\\n');
      let html = '', inTable = false, tableHeadDone = false, inList = false;

      const closeList = () => { if (inList) { html += '</ul>'; inList = false; } };
      const closeTable = () => { if (inTable) { html += '</tbody></table>'; inTable = false; tableHeadDone = false; } };

      for (const raw of lines) {
        const line = raw.trim();
        if (!line) { closeList(); closeTable(); continue; }
        if (line === '---') { closeList(); closeTable(); html += '<hr style="border:0;border-top:1px solid var(--border);margin:14px 0;">'; continue; }

        if (line.startsWith('|') && line.endsWith('|')) {
          closeList();
          const cells = line.slice(1, -1).split('|').map(c => c.trim());
          if (cells.every(c => /^:?-{2,}:?$/.test(c))) continue;
          if (!inTable) {
            html += '<table><thead><tr>' + cells.map(c => '<th>' + inlineFmt(c) + '</th>').join('') + '</tr></thead><tbody>';
            inTable = true; tableHeadDone = true;
          } else {
            html += '<tr>' + cells.map(c => '<td>' + inlineFmt(c) + '</td>').join('') + '</tr>';
          }
          continue;
        }
        closeTable();

        if (/^#{1,4}\\s+/.test(line)) {
          closeList();
          const txt = line.replace(/^#{1,4}\\s+/, '');
          html += '<h3>' + inlineFmt(txt) + '</h3>';
          continue;
        }
        if (/^[-*]\\s+/.test(line)) {
          if (!inList) { html += '<ul>'; inList = true; }
          html += '<li>' + inlineFmt(line.replace(/^[-*]\\s+/, '')) + '</li>';
          continue;
        }
        closeList();
        html += '<p>' + inlineFmt(line) + '</p>';
      }
      closeList();
      closeTable();
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
        btn.innerHTML = '<strong>TC ' + tc.id + '</strong>' + esc(tc.name.replace(/^Test Case \\d+:\\s*/, ''));
        btn.onclick = () => {
          document.querySelectorAll('.tc-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          fillProfile(tc.profile);
        };
        tcListEl.appendChild(btn);
      });
    });

    formEl.onsubmit = async (e) => {
      e.preventDefault();
      errBox.style.display = 'none';
      statusBar.style.display = 'flex';
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
        reportArea.innerHTML = renderMarkdown(data.report || '');
        logsBox.textContent = data.logs || '';
        logsWrap.style.display = 'block';
      } catch (err) {
        errBox.textContent = 'Error: ' + err.message;
        errBox.style.display = 'block';
      } finally {
        statusBar.style.display = 'none';
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
    return JSONResponse({"status": "ok"})


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


def main() -> None:
    """Starts the local Uvicorn web server on port 8080 and opens the browser."""
    url = "http://localhost:8080"
    print(f"Starting Amar Tax Web UI at {url} ...")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()


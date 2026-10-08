/**
 * AgentGuard Suite - Shared Navigation Widget
 * Injected automatically by the Gateway into Project 1 and Project 2 pages.
 */
(function() {
  if (window.__AG_SUITE_WIDGET_LOADED__) return;
  window.__AG_SUITE_WIDGET_LOADED__ = true;

  const currentPath = window.location.pathname;
  const isP1 = currentPath.startsWith('/p1');
  const isP2 = currentPath.startsWith('/p2');
  const isP3 = currentPath.startsWith('/p3');
  const projName = isP1 ? 'Project 1 (6-Agent Core)' : (isP2 ? 'Project 2 (Money Map)' : (isP3 ? 'Project 3 (Model Analytics)' : 'Portal'));

  const css = `
    .ag-suite-bar {
      position: fixed;
      top: 10px;
      right: 16px;
      z-index: 999999;
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 30px;
      padding: 5px 12px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      color: #e2e8f0;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45);
      transition: all 0.2s ease;
    }
    .ag-suite-bar:hover {
      border-color: rgba(56, 189, 248, 0.7);
      box-shadow: 0 6px 24px rgba(56, 189, 248, 0.25);
    }
    .ag-suite-badge {
      font-weight: 700;
      color: #38bdf8;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .ag-suite-badge::before {
      content: '';
      display: inline-block;
      width: 7px;
      height: 7px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
    }
    .ag-suite-btn {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #f1f5f9;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 11.5px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .ag-suite-btn:hover {
      background: rgba(56, 189, 248, 0.2);
      border-color: #38bdf8;
      color: #38bdf8;
      transform: translateY(-1px);
    }
    .ag-suite-logout:hover {
      background: rgba(239, 68, 68, 0.2);
      border-color: #ef4444;
      color: #ef4444;
    }
  `;

  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  const container = document.createElement('div');
  container.className = 'ag-suite-bar';
  container.innerHTML = `
    <span class="ag-suite-badge">${projName}</span>
    <span style="color: rgba(255,255,255,0.2);">|</span>
    <a href="/" class="ag-suite-btn">⇄ Switch Project</a>
    <button class="ag-suite-btn ag-suite-logout" id="agSuiteLogoutBtn">Log Out</button>
  `;

  window.addEventListener('DOMContentLoaded', () => {
    document.body.appendChild(container);
    document.getElementById('agSuiteLogoutBtn').addEventListener('click', async () => {
      try {
        await fetch('/auth/logout', { method: 'POST' });
      } catch(e) {}
      window.location.href = '/';
    });
  });

  if (document.body) {
    document.body.appendChild(container);
    document.getElementById('agSuiteLogoutBtn').addEventListener('click', async () => {
      try {
        await fetch('/auth/logout', { method: 'POST' });
      } catch(e) {}
      window.location.href = '/';
    });
  }
})();

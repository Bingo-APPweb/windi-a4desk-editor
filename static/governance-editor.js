/**
 * WINDI Governance Editor Integration v2.0
 * "O template NUNCA decide o nivel. A API decide. O template apenas manifesta."
 *
 * Self-initializing module that adds governance checking to the BABEL editor.
 * Calls evolution API at /api/evolution/governance/recommend
 * Shows governance level badge + advisor notifications.
 *
 * Phase 2.0 — 02 Feb 2026
 */

(function() {
  'use strict';

  // === CONFIG ===
  const API_BASE = '/api/evolution';
  const CHECK_DEBOUNCE_MS = 800;
  const LEVEL_COLORS = {
    LOW:    { bg: '#f0fdf4', border: '#22c55e', text: '#15803d', dot: '#22c55e', label: 'LOW' },
    MEDIUM: { bg: '#fffbeb', border: '#f59e0b', text: '#b45309', dot: '#f59e0b', label: 'MEDIUM' },
    HIGH:   { bg: '#fef2f2', border: '#ef4444', text: '#dc2626', dot: '#ef4444', label: 'HIGH' },
    NONE:   { bg: '#f8fafc', border: '#94a3b8', text: '#64748b', dot: '#94a3b8', label: '—' }
  };

  // === STATE ===
  let currentLevel = 'NONE';
  let lastDetections = [];
  let badgeEl = null;
  let panelEl = null;
  let isChecking = false;

  // === STYLES ===
  function injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
      /* Governance Badge in Session Bar */
      .windi-gov-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid;
        font-family: 'Segoe UI', system-ui, sans-serif;
      }
      .windi-gov-badge:hover {
        filter: brightness(0.95);
        transform: translateY(-1px);
      }
      .windi-gov-badge .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
      }
      .windi-gov-badge .shield {
        font-size: 14px;
      }

      /* Governance Notification Panel */
      .windi-gov-panel {
        position: fixed;
        top: 60px;
        right: 20px;
        width: 380px;
        max-height: 80vh;
        overflow-y: auto;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.15);
        z-index: 9999;
        display: none;
        font-family: 'Segoe UI', system-ui, sans-serif;
        border: 2px solid #e2e8f0;
      }
      .windi-gov-panel.show { display: block; }

      .windi-gov-panel-header {
        padding: 16px 20px;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .windi-gov-panel-header h3 {
        font-size: 14px;
        font-weight: 700;
        color: #1a365d;
        margin: 0;
      }
      .windi-gov-panel-close {
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        color: #94a3b8;
        padding: 4px;
      }
      .windi-gov-panel-close:hover { color: #1a365d; }

      .windi-gov-panel-body { padding: 16px 20px; }

      /* Level indicator in panel */
      .windi-gov-level-display {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px 16px;
        border-radius: 8px;
        margin-bottom: 14px;
        border: 1px solid;
      }
      .windi-gov-level-display .level-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .windi-gov-level-display .level-text {
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.5px;
      }
      .windi-gov-level-display .level-sub {
        font-size: 12px;
        font-weight: 400;
        opacity: 0.8;
        margin-left: auto;
      }

      /* Detection cards */
      .windi-detection-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
      }
      .windi-detection-card .det-name {
        font-weight: 700;
        font-size: 13px;
        color: #1a365d;
      }
      .windi-detection-card .det-meta {
        font-size: 11px;
        color: #64748b;
        margin-top: 4px;
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }
      .windi-detection-card .det-meta span {
        display: inline-flex;
        align-items: center;
        gap: 3px;
      }

      /* Advisor message */
      .windi-advisor-msg {
        padding: 12px 14px;
        border-radius: 8px;
        font-size: 13px;
        line-height: 1.5;
        margin-top: 12px;
        border-left: 3px solid;
      }

      /* Action buttons */
      .windi-gov-actions {
        display: flex;
        gap: 8px;
        margin-top: 14px;
        padding-top: 14px;
        border-top: 1px solid #e2e8f0;
      }
      .windi-gov-btn {
        flex: 1;
        padding: 8px 14px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        border: 1px solid;
        transition: all 0.2s;
        text-align: center;
      }
      .windi-gov-btn:hover { filter: brightness(0.95); }
      .windi-gov-btn-check {
        background: #3182ce;
        color: #fff;
        border-color: #3182ce;
      }
      .windi-gov-btn-dismiss {
        background: #f8fafc;
        color: #64748b;
        border-color: #e2e8f0;
      }

      /* Editor border glow based on level */
      .editor-gov-low .ProseMirror,
      .editor-gov-low .tiptap,
      .editor-gov-low [contenteditable] {
        border-left: 3px solid #22c55e !important;
      }
      .editor-gov-medium .ProseMirror,
      .editor-gov-medium .tiptap,
      .editor-gov-medium [contenteditable] {
        border-left: 3px solid #f59e0b !important;
      }
      .editor-gov-high .ProseMirror,
      .editor-gov-high .tiptap,
      .editor-gov-high [contenteditable] {
        border-left: 3px solid #ef4444 !important;
      }

      /* Spinning animation for check */
      @keyframes windi-spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
      .windi-spinning { animation: windi-spin 1s linear infinite; }

      /* No detections state */
      .windi-no-detections {
        text-align: center;
        padding: 20px;
        color: #64748b;
        font-size: 13px;
      }
      .windi-no-detections .icon { font-size: 28px; margin-bottom: 8px; }
    `;
    document.head.appendChild(style);
  }

  // === BADGE ===
  function createBadge() {
    badgeEl = document.createElement('div');
    badgeEl.className = 'windi-gov-badge';
    badgeEl.title = 'WINDI Governance Check';
    badgeEl.onclick = togglePanel;
    updateBadgeVisual('NONE');

    // Try to insert in session bar
    const sessionBar = document.querySelector('.session-bar, .toolbar, .header-actions, nav');
    if (sessionBar) {
      sessionBar.appendChild(badgeEl);
    } else {
      // Fallback: fixed position
      badgeEl.style.cssText = 'position:fixed;top:12px;right:20px;z-index:9998;';
      document.body.appendChild(badgeEl);
    }
  }

  function updateBadgeVisual(level) {
    const c = LEVEL_COLORS[level] || LEVEL_COLORS.NONE;
    badgeEl.style.background = c.bg;
    badgeEl.style.borderColor = c.border;
    badgeEl.style.color = c.text;
    badgeEl.innerHTML = `
      <span class="shield">\u{1F6E1}</span>
      <span class="dot" style="background:${c.dot}"></span>
      <span>${c.label}</span>
    `;
  }

  // === PANEL ===
  function createPanel() {
    panelEl = document.createElement('div');
    panelEl.className = 'windi-gov-panel';
    panelEl.innerHTML = `
      <div class="windi-gov-panel-header">
        <h3>\u{1F6E1}\uFE0F WINDI Governance</h3>
        <button class="windi-gov-panel-close" onclick="this.closest('.windi-gov-panel').classList.remove('show')">\u2715</button>
      </div>
      <div class="windi-gov-panel-body" id="windiGovBody">
        <div class="windi-no-detections">
          <div class="icon">\u{1F50D}</div>
          <div>Click <b>Check Document</b> to scan for institutional identities.</div>
        </div>
        <div class="windi-gov-actions">
          <button class="windi-gov-btn windi-gov-btn-check" onclick="window._windiGov.check()">\u{1F6E1}\uFE0F Check Document</button>
        </div>
      </div>
    `;
    document.body.appendChild(panelEl);
  }

  function togglePanel() {
    if (!panelEl) return;
    panelEl.classList.toggle('show');
  }

  // === GET EDITOR TEXT ===
  function getEditorText() {
    // Try multiple selectors for TipTap/ProseMirror editor
    const selectors = [
      '.ProseMirror',
      '.tiptap',
      '[contenteditable="true"]',
      '#editor',
      '.editor-content',
      '.editor-area'
    ];

    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.innerText && el.innerText.trim().length > 0) {
        return el.innerText.trim();
      }
    }

    return '';
  }

  // === FIND EDITOR CONTAINER ===
  function getEditorContainer() {
    const selectors = [
      '.editor-wrapper',
      '.editor-container',
      '.ProseMirror',
      '.tiptap',
      '#editor',
      '.editor-area'
    ];

    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        // Return the parent for border styling
        return el.closest('.editor-wrapper, .editor-container, .card, .editor-panel') || el.parentElement || el;
      }
    }
    return null;
  }

  // === APPLY EDITOR VISUAL ===
  function applyEditorLevel(level) {
    const container = getEditorContainer();
    if (!container) return;

    // Remove old level classes
    container.classList.remove('editor-gov-low', 'editor-gov-medium', 'editor-gov-high');

    // Apply new
    if (level === 'LOW') container.classList.add('editor-gov-low');
    else if (level === 'MEDIUM') container.classList.add('editor-gov-medium');
    else if (level === 'HIGH') container.classList.add('editor-gov-high');
  }

  // === DETECT LANGUAGE ===
  function detectLang() {
    // Check BABEL's current language if available
    if (window.currentLang) return window.currentLang;
    if (document.documentElement.lang) return document.documentElement.lang.substring(0, 2);
    return 'en';
  }

  // === API CALL ===
  async function checkGovernance() {
    if (isChecking) return;

    const text = getEditorText();
    if (!text || text.length < 10) {
      showResult(null, 'empty');
      return;
    }

    isChecking = true;
    showChecking();

    try {
      const resp = await fetch(API_BASE + '/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, current_level: 'LOW' })
      });

      if (!resp.ok) {
        throw new Error('API returned ' + resp.status);
      }

      const data = await resp.json();

      if (data.error) {
        showResult(null, 'error', data.error);
      } else {
        currentLevel = data.recommended_level || 'LOW';
        lastDetections = data.detections || [];
        updateBadgeVisual(currentLevel);
        applyEditorLevel(currentLevel);
        showResult(data, 'ok');
      }
    } catch (err) {
      showResult(null, 'error', { detail: err.message });
    } finally {
      isChecking = false;
    }
  }

  // === SHOW CHECKING STATE ===
  function showChecking() {
    const body = document.getElementById('windiGovBody');
    if (!body) return;
    body.innerHTML = `
      <div style="text-align:center;padding:30px;color:#64748b;">
        <div class="windi-spinning" style="font-size:28px;display:inline-block;">\u{1F6E1}\uFE0F</div>
        <div style="margin-top:10px;font-size:13px;">Scanning document...</div>
      </div>
    `;
  }

  // === SHOW RESULT ===
  function showResult(data, status, error) {
    const body = document.getElementById('windiGovBody');
    if (!body) return;

    let html = '';

    if (status === 'empty') {
      html = `
        <div class="windi-no-detections">
          <div class="icon">\u{270F}\uFE0F</div>
          <div>Write some content in the editor first, then check governance.</div>
        </div>
      `;
    } else if (status === 'error') {
      html = `
        <div class="windi-no-detections">
          <div class="icon">\u26A0\uFE0F</div>
          <div>Governance check failed.<br><small>${error && error.detail ? error.detail : 'API unavailable'}</small></div>
        </div>
      `;
    } else if (status === 'ok' && data) {
      const level = data.recommended_level || 'LOW';
      const c = LEVEL_COLORS[level] || LEVEL_COLORS.LOW;
      const detections = data.detections || [];
      const action = data.action || 'no_change';
      const lang = detectLang();

      // Level display
      html += `
        <div class="windi-gov-level-display" style="background:${c.bg};border-color:${c.border};">
          <span class="level-dot" style="background:${c.dot};"></span>
          <span class="level-text" style="color:${c.text};">${c.label}</span>
          <span class="level-sub" style="color:${c.text};">
            ${action === 'upgrade' ? '\u26A0 Upgrade recommended' : action === 'no_change' ? '\u2713 No change needed' : '\u2713 Confirmed'}
          </span>
        </div>
      `;

      // Detections
      if (detections.length > 0) {
        for (const det of detections) {
          html += `
            <div class="windi-detection-card">
              <div class="det-name">${det.institution_name || 'Unknown'}</div>
              <div class="det-meta">
                <span>\u{1F3F3}\uFE0F ${det.country || '?'}</span>
                <span>\u{1F3E2} ${det.type || '?'}</span>
                <span>\u{1F3AF} ${Math.round((det.confidence || 0) * 100)}%</span>
                <span>\u{1F4CB} ${det.recommended_level || '?'}</span>
              </div>
              <div class="det-meta" style="margin-top:6px;">
                <span>${det.disclaimer_required ? '\u26A0\uFE0F Disclaimer required' : '\u2705 No disclaimer'}</span>
                <span>${det.logo_allowed ? '\u2705 Logo OK' : '\u{1F6AB} No logo'}</span>
                <span>\u{1F4DD} License: ${det.identity_license_status || '?'}</span>
              </div>
            </div>
          `;
        }
      } else {
        html += `
          <div class="windi-no-detections" style="padding:12px;">
            <div>\u2705 No institutional identities detected. Document is governance-free.</div>
          </div>
        `;
      }

      // Advisor message
      if (data.advisor_message) {
        const msg = data.advisor_message[lang] || data.advisor_message.en || data.advisor_message.de || '';
        if (msg) {
          html += `
            <div class="windi-advisor-msg" style="background:${c.bg};border-color:${c.border};color:${c.text};">
              \u{1F4AC} ${msg}
            </div>
          `;
        }
      }

      // Identity governance summary
      if (data.identity_governance) {
        const ig = data.identity_governance;
        html += `
          <div style="margin-top:12px;font-size:11px;color:#64748b;padding:8px;background:#f8fafc;border-radius:6px;">
            Disclaimer: ${ig.disclaimer_required ? 'Required' : 'Not required'} |
            Logo: ${ig.logo_allowed ? 'Allowed' : 'Not allowed'} |
            Licenses: ${(ig.license_statuses || []).join(', ') || 'none'}
          </div>
        `;
      }
    }

    // Always add action buttons
    html += `
      <div class="windi-gov-actions">
        <button class="windi-gov-btn windi-gov-btn-check" onclick="window._windiGov.check()">\u{1F504} Re-check</button>
        <button class="windi-gov-btn windi-gov-btn-dismiss" onclick="document.querySelector('.windi-gov-panel').classList.remove('show')">Close</button>
      </div>
    `;

    body.innerHTML = html;
  }

  // === TOAST (use existing if available) ===
  function showToast(msg, type) {
    if (typeof window.toast === 'function') {
      window.toast(msg, type || 'success');
      return;
    }
    // Fallback
    const t = document.createElement('div');
    t.style.cssText = 'position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:8px;color:#fff;font-weight:600;z-index:10000;font-size:13px;';
    t.style.background = type === 'error' ? '#e53e3e' : '#38a169';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }

  // === PUBLIC API ===
  window._windiGov = {
    check: checkGovernance,
    getLevel: () => currentLevel,
    getDetections: () => lastDetections
  };

  // === INIT ===
  function init() {
    injectStyles();
    createBadge();
    createPanel();
    console.log('[WINDI] Governance Editor Integration v2.0 loaded');
  }

  // Wait for DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

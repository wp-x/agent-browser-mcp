if (!/streamlit/i.test(document.title)) {

// Isolated, hover-to-expand connection capsule. Only the top frame owns it.
if (window.self === window.top) {
  const STATES = Object.freeze({
    connected: { label: '已连接', detail: '本机桥接服务在线', color: '#36a775' },
    connecting: { label: '连接中', detail: '正在连接本机桥接服务', color: '#d69a32' },
    disconnected: { label: '已断开', detail: '本机桥接服务离线', color: '#d65f58' },
    unknown: { label: '状态未知', detail: '无法获取连接状态', color: '#8b8b91' },
  });
  const host = document.createElement('div');
  // Keep the page scanner's exclusion identifier.
  host.id='ljq-ind';
  host.dataset.tmwdCapsule = '';
  host.style.cssText = 'all:initial!important;position:fixed!important;top:16px!important;right:16px!important;z-index:2147483647!important;pointer-events:none!important;';
  const root = host.attachShadow({ mode: 'closed' });
  root.innerHTML = `
    <style>
      :host { color-scheme: light dark; }
      * { box-sizing: border-box; }
      .shell { filter: drop-shadow(0 2px 4px #18202c1c); }
      button {
        --status: #d69a32;
        --idle-opacity: .22;
        --unfold-duration: 1050ms;
        --fold-duration: 900ms;
        --unfold-ease: cubic-bezier(.32, .04, .18, 1);
        --fold-ease: cubic-bezier(.42, 0, .2, 1);
        opacity: var(--idle-opacity);
        appearance: none; position: relative; display: block;
        width: min(164px, calc(100vw - 32px)); height: 30px;
        padding: 0; border: 0; border-radius: 15px;
        background: transparent;
        color: #343536; cursor: pointer; pointer-events: auto;
        font: 12px/1.3 -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        clip-path: inset(0 0 0 calc(100% - 30px) round 15px);
        transform-origin: calc(100% - 15px) center;
        transition: clip-path var(--fold-duration) var(--fold-ease),
          transform 240ms ease, opacity 500ms ease 450ms;
      }
      button[aria-expanded='true'] {
        clip-path: inset(0 0 0 0 round 15px); opacity: 1;
        transition: clip-path var(--unfold-duration) var(--unfold-ease),
          transform 240ms ease, opacity 300ms ease;
      }
      button::before {
        content: ''; position: absolute; inset: 0; border-radius: inherit;
        background: linear-gradient(180deg, #fffefa 0%, #f7f6f2 48%, #eeede8 100%);
        box-shadow: inset 0 1px 1px #ffffff, inset 0 0 0 1px #ffffff80, inset 0 -1px 2px #29282012;
        opacity: 0; transition: opacity 300ms ease 650ms;
      }
      button[aria-expanded='true']::before { opacity: 1; transition: opacity 220ms ease; }
      button:active { transform: scale(.985); }
      button:focus-visible { outline: none; }
      button:focus-visible::before { box-shadow: inset 0 0 0 2px #688eb7; }
      .light {
        position: absolute; right: 11px; top: 11px; width: 8px; height: 8px;
        border-radius: 50%; background: var(--status);
        box-shadow: inset 0 1px 2px #ffffff80, inset 0 -1px 2px #00000028, 0 0 0 4px #36a7750a;
        transition: background-color 220ms ease;
      }
      .copy {
        position: absolute; inset: 0 30px 0 14px; display: flex;
        align-items: center; gap: 7px; white-space: nowrap;
        opacity: 0; transform: translateX(18px);
        transition: opacity 240ms ease, transform 700ms var(--fold-ease);
      }
      [aria-expanded='true'] .copy {
        opacity: 1; transform: translateX(0);
        transition: opacity 450ms ease 300ms, transform 750ms var(--unfold-ease) 180ms;
      }
      .brand { font-weight: 500; letter-spacing: .1px; }
      .separator { color: #92928c; }
      .label { color: #696a68; font-size: 11px; }
      [data-status='connecting'][aria-expanded='true'] .light { animation: breathe 2.2s ease-in-out infinite; }
      @keyframes breathe { 50% { opacity: .45; } }
      .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
      .keyboard, .keyboard::before, .keyboard .copy { transition: none !important; }
      @media (prefers-color-scheme: dark) {
        button { color: #f3f1eb; }
        button::before { background: linear-gradient(180deg, #414344, #2c2e30);
          box-shadow: inset 0 1px 1px #ffffff30, inset 0 -1px 2px #00000060; }
        .label { color: #c1c2bc; }
      }
      @media (prefers-reduced-motion: reduce) {
        button, button::before, .copy, .light { transition: none !important; animation: none !important; }
      }
    </style>
    <div class="shell">
      <button type="button" aria-expanded="false" aria-label="连接中，悬停查看连接状态">
        <span class="copy" aria-hidden="true"><span class="brand">Bridge</span><span class="separator">·</span><span class="label">连接中</span></span>
        <span class="light" aria-hidden="true"></span>
      </button>
    </div>
    <span class="sr-only" role="status" aria-live="polite"></span>
  `;
  const button = root.querySelector('button');
  const label = root.querySelector('.label');
  const announcement = root.querySelector('[role="status"]');
  let current = STATES.connecting;
  let receivedStatus = false;
  const COLLAPSE_DELAY_MS = 260;
  let collapseTimer;
  let touchInput = false;

  function updateAccessibleLabel(expanded) {
    button.setAttribute('aria-label', `${current.label}，${current.detail}，${expanded ? '按 Escape 收起' : '悬停或聚焦查看'}`);
  }

  function setExpanded(expanded) {
    clearTimeout(collapseTimer);
    button.setAttribute('aria-expanded', String(expanded));
    updateAccessibleLabel(expanded);
  }

  function renderStatus(status) {
    const knownStatus = Object.hasOwn(STATES, status) ? status : 'unknown';
    current = STATES[knownStatus];
    button.dataset.status = knownStatus;
    button.style.setProperty('--status', current.color);
    label.textContent = current.label;

    announcement.textContent = `${current.label}：${current.detail}`;
    const expanded = button.getAttribute('aria-expanded') === 'true';
    updateAccessibleLabel(expanded);
  }

  button.addEventListener('pointerenter', event => {
    if (event.pointerType === 'touch') return;
    button.classList.remove('keyboard');
    setExpanded(true);
  });
  button.addEventListener('pointerleave', () => {
    collapseTimer = setTimeout(() => {
      if (!button.matches(':focus-visible')) setExpanded(false);
    }, COLLAPSE_DELAY_MS);
  });
  button.addEventListener('pointerdown', event => {
    touchInput = event.pointerType === 'touch';
    button.classList.remove('keyboard');
  });
  button.addEventListener('focus', () => {
    if (!button.matches(':focus-visible')) return;
    button.classList.add('keyboard');
    setExpanded(true);
  });
  button.addEventListener('blur', () => setExpanded(false));
  button.addEventListener('keydown', event => {
    button.classList.add('keyboard');
    if (event.key === 'Escape') setExpanded(false);
  });
  button.addEventListener('click', event => {
    if (!touchInput && event.detail !== 0) return;
    button.classList.toggle('keyboard', event.detail === 0);
    setExpanded(button.getAttribute('aria-expanded') !== 'true');
  });
  document.addEventListener('pointerdown', event => {
    if (!event.composedPath().includes(host)) setExpanded(false);
  }, { passive: true });
  chrome.runtime.onMessage.addListener(message => {
    if (message?.type !== 'tmwd_status') return;
    receivedStatus = true;
    renderStatus(message.data);
  });
  renderStatus('connecting');
  chrome.runtime.sendMessage({ cmd: 'status' }, response => {
    const error = chrome.runtime.lastError;
    if (error) console.error('TMWD status query failed:', error.message);
    if (!receivedStatus) renderStatus(!error && response?.ok ? response.data : 'unknown');
  });
  (document.body || document.documentElement).appendChild(host);
}

}

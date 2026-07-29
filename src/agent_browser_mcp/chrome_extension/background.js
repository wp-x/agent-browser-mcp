// background.js - Cookie + CDP Bridge
importScripts('commands.js', 'script_builder.js', 'websocket_exec.js');

const DEFAULT_BROWSER = 'Google Chrome';
const SUPPORTED_BROWSERS = ['Google Chrome', 'Google Chrome Dev'];
const BROWSER_STORAGE_KEY = 'tmwdBrowserName';
let browserName = DEFAULT_BROWSER;

async function loadBrowserName() {
  const stored = await chrome.storage.local.get(BROWSER_STORAGE_KEY);
  const candidate = stored[BROWSER_STORAGE_KEY];
  browserName = SUPPORTED_BROWSERS.includes(candidate) ? candidate : DEFAULT_BROWSER;
  return browserName;
}
chrome.runtime.onInstalled.addListener(() => {
  console.log('CDP Bridge installed');
  // Strip CSP headers to allow eval/inline scripts
  chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: [9999],
    addRules: [{
      id: 9999, priority: 1,
      action: { type: 'modifyHeaders', responseHeaders: [
        { header: 'content-security-policy', operation: 'remove' },
        { header: 'content-security-policy-report-only', operation: 'remove' }
      ]},
      condition: { urlFilter: '*', resourceTypes: ['main_frame', 'sub_frame'] }
    }]
  });
});

async function handleExtMessage(msg, sender) {
  if (msg.cmd === 'cookies') return await handleCookies(msg, sender);
  if (msg.cmd === 'cdp') return await handleCDP(msg, sender);
  if (msg.cmd === 'batch') return await handleBatch(msg, sender);
  if (msg.cmd === 'tabs') {
    try {
      if (msg.method === 'switch') {
        const tab = await chrome.tabs.update(msg.tabId, { active: true });
        await chrome.windows.update(tab.windowId, { focused: true });
        return { ok: true };
      } else {
        return { ok: true, data: await queryTabs() };
      }
    } catch (e) { return { ok: false, error: e.message }; }
  }
  if (msg.cmd === 'management') {
    try {
      if (msg.method === 'list') {
        const all = await chrome.management.getAll();
        return { ok: true, data: all.map(e => ({ id: e.id, name: e.name, enabled: e.enabled, type: e.type, version: e.version })) };
      }
      if (msg.method === 'reload') {
        chrome.alarms.create('tmwd-self-reload', { when: Date.now() + 200 });
        return { ok: true };
      }
      if (msg.method === 'disable') {
        await chrome.management.setEnabled(msg.extId, false);
        return { ok: true };
      }
      if (msg.method === 'enable') {
        await chrome.management.setEnabled(msg.extId, true);
        return { ok: true };
      }
      return { ok: false, error: 'Unknown method: ' + msg.method };
    } catch (e) { return { ok: false, error: e.message }; }
  }
  if (msg.cmd === 'ws_state') {
    return { ok: true, connected: !!(ws && ws.readyState === 1), browser: browserName };
  }
  if (msg.cmd === 'browser_info') {
    return { ok: true, browser: await loadBrowserName(), supported: SUPPORTED_BROWSERS };
  }
  if (msg.cmd === 'set_browser') {
    if (!SUPPORTED_BROWSERS.includes(msg.browser)) {
      return { ok: false, error: 'Unsupported browser: ' + msg.browser };
    }
    await chrome.storage.local.set({ [BROWSER_STORAGE_KEY]: msg.browser });
    browserName = msg.browser;
    if (ws) {
      ws.addEventListener('close', () => connectWS(), { once: true });
      ws.close();
    } else {
      connectWS();
    }
    return { ok: true, browser: browserName };
  }
  return { ok: false, error: 'Unknown cmd: ' + msg.cmd };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleExtMessage(msg, sender).then(sendResponse);
  return true;
});

// --- WebSocket Client for TMWebDriver ---
let ws = null;
const WS_URL = 'ws://127.0.0.1:18765';

function scheduleProbe() {
  // Use chrome.alarms to survive MV3 service worker suspension
  chrome.alarms.create('tmwd-ws-probe', { delayInMinutes: 0.083 }); // ~5s
}

function scheduleKeepalive() {
  // Keep SW alive while WS is connected (~25s, under 30s SW timeout)
  chrome.alarms.create('tmwd-ws-keepalive', { delayInMinutes: 0.4 }); // ~24s
}

async function isServerAlive() {
  try {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 2000);
    await fetch('http://127.0.0.1:18765', { signal: ctrl.signal });
    return true; // Got HTTP response → port is listening
  } catch (e) {
    return false; // Network error (connection refused) or timeout → server not alive
  }
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'tmwd-self-reload') {
    chrome.runtime.reload();
    return;
  }
  if (alarm.name === 'tmwd-ws-keepalive') {
    // Keepalive: ping to keep SW alive + detect dead connections
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send('{"type":"ping"}'); } catch (_) {}
      scheduleKeepalive();
    } else {
      // Connection lost, switch to probe mode
      ws = null;
      scheduleProbe();
    }
  }
  if (alarm.name === 'tmwd-ws-probe') {
    if (ws && ws.readyState <= 1) return; // Already connected/connecting
    if (await isServerAlive()) {
      console.log('[TMWD-WS] Server detected, connecting...');
      connectWS();
    } else {
      scheduleProbe(); // Server not up, keep probing
    }
  }
});

async function connectWS() {
  if (ws && ws.readyState <= 1) return; // CONNECTING or OPEN
  await loadBrowserName();
  try {
    ws = new WebSocket(WS_URL);
    bindWebSocket(ws);
  } catch (error) {
    console.error('[TMWD-WS] Constructor error:', error);
    ws = null;
    scheduleProbe();
  }
}

function bindWebSocket(socket) {
  socket.onopen = sendReady;
  socket.onmessage = handleWsMessage;
  socket.onclose = () => {
    console.log('[TMWD-WS] Disconnected');
    ws = null;
    scheduleProbe();
  };
  socket.onerror = error => console.error('[TMWD-WS] Error:', error);
}

async function sendReady() {
  scheduleKeepalive();
  const tabs = await queryTabs();
  ws.send(JSON.stringify({ type: 'ext_ready', browser: browserName, tabs }));
}

async function handleWsMessage(event) {
  try {
    const data = JSON.parse(event.data);
    if (!data.id || !data.code) return;
    const command = parseCommand(data.code);
    if (typeof command === 'string') {
      await handleWsExec(data);
      return;
    }
    if (command.tabId === undefined && data.tabId !== undefined) command.tabId = data.tabId;
    const result = await handleExtMessage(command, {});
    ws.send(JSON.stringify({
      type: result.ok ? 'result' : 'error',
      id: data.id,
      result: result.data ?? result.results ?? result,
      error: result.error
    }));
  } catch (error) {
    console.error('[TMWD-WS] message parse error', error);
  }
}

function parseCommand(code) {
  if (typeof code !== 'string') return code;
  try {
    const parsed = JSON.parse(code);
    return parsed && typeof parsed === 'object' ? parsed : code;
  } catch (_) {
    return code;
  }
}

// Initial connect + wake-up hooks
connectWS();
chrome.runtime.onStartup.addListener(() => connectWS());
chrome.runtime.onInstalled.addListener(() => connectWS());

// Sync tab list on changes
async function sendTabsUpdate() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const tabs = (await chrome.tabs.query({})).filter(t => isScriptable(t.url) && !/streamlit/i.test(t.title));
  ws.send(JSON.stringify({
    type: 'tabs_update',
    browser: browserName,
    tabs: tabs.map(t => ({ id: t.id, url: t.url, title: t.title }))
  }));
}
chrome.tabs.onUpdated.addListener((_, changeInfo) => {
  if (changeInfo.status === 'complete') sendTabsUpdate();
});
chrome.tabs.onRemoved.addListener(() => sendTabsUpdate());
chrome.tabs.onCreated.addListener(() => sendTabsUpdate());

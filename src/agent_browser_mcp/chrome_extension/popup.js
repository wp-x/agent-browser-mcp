document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('refresh');
  btn.addEventListener('click', fetchCookies);
  setupBrowserIdentity();
  fetchCookies();
});

async function setupBrowserIdentity() {
  const select = document.getElementById('browser');
  const status = document.getElementById('status');
  const info = await chrome.runtime.sendMessage({ cmd: 'browser_info' });
  select.value = info.browser;
  renderStatus(status, info.browser);
  select.addEventListener('change', async () => {
    const result = await chrome.runtime.sendMessage({ cmd: 'set_browser', browser: select.value });
    if (!result.ok) {
      status.textContent = '设置失败：' + result.error;
      return;
    }
    status.textContent = `已保存 ${result.browser}，正在重新连接…`;
    setTimeout(async () => renderStatus(status, result.browser), 800);
  });
}

async function renderStatus(element, browser) {
  const state = await chrome.runtime.sendMessage({ cmd: 'ws_state' });
  element.textContent = `${browser} · ${state.connected ? '已连接' : '未连接'}`;
}

async function fetchCookies() {
  const out = document.getElementById('out');
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url) { out.textContent = 'No active tab'; return; }
    const resp = await chrome.runtime.sendMessage({ cmd: 'cookies', url: tab.url });
    if (!resp?.ok) { out.textContent = 'Error: ' + (resp?.error || 'unknown'); return; }
    if (!resp.data.length) { out.textContent = '(no cookies)'; return; }
    // 展示带标记
    out.textContent = resp.data.map(c =>
      `${c.name}=${c.value}` + (c.httpOnly ? ' [H]' : '') + (c.secure ? ' [S]' : '') + (c.partitionKey ? ' [P]' : '')
    ).join('\n');
    // 自动复制 name=value; 格式到剪贴板
    const str = resp.data.map(c => `${c.name}=${c.value}`).join('; ');
    await navigator.clipboard.writeText(str);
  } catch (e) { out.textContent = 'Error: ' + e.message; }
}

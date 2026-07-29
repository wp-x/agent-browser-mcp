async function handleCookies(msg, sender) {
  try {
    let url = msg.url || sender.tab?.url;
    if (!url && msg.tabId) url = (await chrome.tabs.get(msg.tabId)).url;
    const origin = url.match(/^https?:\/\/[^/]+/)[0];
    const all = await chrome.cookies.getAll({ url });
    const partitioned = await chrome.cookies.getAll({
      url,
      partitionKey: { topLevelSite: origin }
    }).catch(() => []);
    const merged = [...all];
    for (const cookie of partitioned) {
      const exists = merged.some(item => item.name === cookie.name && item.domain === cookie.domain);
      if (!exists) merged.push(cookie);
    }
    return { ok: true, data: merged };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

async function handleCDP(msg, sender) {
  const tabId = msg.tabId || sender.tab?.id;
  if (!tabId) return { ok: false, error: 'no tabId' };
  try {
    await chrome.debugger.attach({ tabId }, '1.3');
    const result = await chrome.debugger.sendCommand({ tabId }, msg.method, msg.params || {});
    await chrome.debugger.detach({ tabId });
    return { ok: true, data: result };
  } catch (error) {
    try { await chrome.debugger.detach({ tabId }); } catch (_) {}
    return { ok: false, error: error.message };
  }
}

async function handleBatch(msg, sender) {
  const results = [];
  let attached = null;
  try {
    for (const command of msg.commands) {
      if (command.tabId === undefined && msg.tabId !== undefined) command.tabId = msg.tabId;
      if (command.cmd === 'cookies') {
        results.push(await handleCookies(command, sender));
      } else if (command.cmd === 'tabs') {
        results.push({ ok: true, data: await queryTabs() });
      } else if (command.cmd === 'cdp') {
        const tabId = command.tabId || msg.tabId || sender.tab?.id;
        if (attached !== tabId) {
          if (attached) await chrome.debugger.detach({ tabId: attached });
          await chrome.debugger.attach({ tabId }, '1.3');
          attached = tabId;
        }
        const params = resolveBatchReferences(command.params, results);
        results.push(await chrome.debugger.sendCommand({ tabId }, command.method, params));
      } else {
        results.push({ ok: false, error: 'unknown cmd: ' + command.cmd });
      }
    }
    if (attached) await chrome.debugger.detach({ tabId: attached });
    return { ok: true, results };
  } catch (error) {
    if (attached) try { await chrome.debugger.detach({ tabId: attached }); } catch (_) {}
    return { ok: false, error: error.message, results };
  }
}

function resolveBatchReferences(params, results) {
  return JSON.parse(JSON.stringify(params || {}).replace(
    /"\$(\d+)\.([^"]+)"/g,
    (_, index, path) => {
      let value = results[Number(index)];
      for (const key of path.split('.')) value = value[key];
      return JSON.stringify(value);
    }
  ));
}

async function queryTabs() {
  const tabs = (await chrome.tabs.query({})).filter(tab => isScriptable(tab.url));
  return tabs.map(tab => ({
    id: tab.id,
    url: tab.url,
    title: tab.title,
    active: tab.active,
    windowId: tab.windowId
  }));
}

function isScriptable(url) {
  return Boolean(url && /^https?:/.test(url));
}

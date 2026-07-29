async function handleWsExec(data) {
  const tabId = data.tabId;
  ws.send(JSON.stringify({ type: 'ack', id: data.id }));
  if (!tabId) {
    ws.send(JSON.stringify({ type: 'error', id: data.id, error: 'No tabId provided' }));
    return;
  }
  const newTabIds = new Set();
  const onCreated = tab => newTabIds.add(tab.id);
  chrome.tabs.onCreated.addListener(onCreated);
  try {
    let result = await executeOnPage(tabId, data.code);
    if (result && !result.ok && result.csp) result = await executeWithCdp(tabId, data.code);
    const newTabs = await collectNewTabs(newTabIds);
    const type = result?.ok ? 'result' : 'error';
    const message = { type, id: data.id, newTabs };
    if (result?.ok) message.result = result.data;
    else message.error = result?.error || 'Unknown error';
    ws.send(JSON.stringify(message));
  } catch (error) {
    ws.send(JSON.stringify({
      type: 'error',
      id: data.id,
      error: { name: error.name || 'Error', message: error.message, stack: error.stack || '' }
    }));
  } finally {
    chrome.tabs.onCreated.removeListener(onCreated);
  }
}

async function executeOnPage(tabId, code) {
  try {
    const output = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: async script => await eval(script),
      args: [buildPageScript(code)]
    });
    return output[0]?.result ?? {
      ok: false,
      error: { name: 'Error', message: 'executeScript returned no result', stack: '' },
      csp: true
    };
  } catch (error) {
    return {
      ok: false,
      error: { name: error.name || 'Error', message: error.message, stack: error.stack || '' },
      csp: true
    };
  }
}

async function executeWithCdp(tabId, code) {
  try {
    await chrome.debugger.attach({ tabId }, '1.3');
    const output = await chrome.debugger.sendCommand({ tabId }, 'Runtime.evaluate', {
      expression: buildCdpScript(code),
      awaitPromise: true,
      returnByValue: true
    });
    await chrome.debugger.detach({ tabId });
    if (!output.exceptionDetails) return output.result.value;
    const message = output.exceptionDetails.exception?.description || 'CDP Error';
    return { ok: false, error: { name: 'Error', message, stack: message } };
  } catch (error) {
    try { await chrome.debugger.detach({ tabId }); } catch (_) {}
    return { ok: false, error: { name: 'Error', message: error.message, stack: '' } };
  }
}

async function collectNewTabs(ids) {
  if (ids.size === 0) await new Promise(resolve => setTimeout(resolve, 200));
  const tabs = [];
  for (const id of ids) {
    try {
      const tab = await chrome.tabs.get(id);
      tabs.push({ id: tab.id, url: tab.url, title: tab.title });
    } catch (_) {}
  }
  return tabs;
}

;(function(){ if (/streamlit/i.test(document.title)) return;

// Indicator badge reflects the extension's live WebSocket connection state.
(function(){
  if(window.self!==window.top)return;
  const d=document.createElement('div');
  d.id='ljq-ind';
  d.textContent='ljq_driver: 已连接';
  d.style.cssText='position:fixed;bottom:8px;right:8px;background:#4CAF50;color:white;padding:4px 7px;border-radius:4px;font-size:11px;font-weight:bold;z-index:99999;box-shadow:0 2px 4px rgba(0,0,0,0.2);opacity:0.2;pointer-events:none;';
  const states={connected:['已连接','#4CAF50'],connecting:['重连中','#FF9800'],disconnected:['断开','#F44336']};
  const render=status=>{const [text,color]=states[status]||states.disconnected;d.textContent='ljq_driver: '+text;d.style.background=color;};
  chrome.runtime.onMessage.addListener(msg=>{if(msg?.type==='tmwd_status')render(msg.data);});
  chrome.runtime.sendMessage({cmd:'status'},response=>render(response?.ok?response.data:'connected'));
  (document.body||document.documentElement).appendChild(d);
})();

})();

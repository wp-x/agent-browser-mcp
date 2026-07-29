# Google Chrome / Chrome Dev 路由设计

## 目标

让一个 `agent-browser-mcp` 实例同时管理 Google Chrome 与 Google Chrome Dev。调用方不传 `browser` 时固定使用 Google Chrome；显式传入 `Google Chrome Dev`、`Chrome Dev`、`dev`、`开发版`或`开发浏览器`时使用开发浏览器。

## 架构与数据流

两个浏览器加载同一份 unpacked 扩展。浏览器身份保存在各自浏览器配置中的 `chrome.storage.local`，因此互不影响。扩展首次安装默认使用 `Google Chrome`；用户只需在 Chrome Dev 的扩展弹窗中将身份切换为 `Google Chrome Dev`。身份变更后扩展主动重连，并在 `ext_ready` 与 `tabs_update` 消息中携带 `browser` 字段。

TMWebDriver 使用 `browser::tabId` 作为内部会话 ID。即使两个 Chrome 进程产生相同的 `tabId`，它们也会映射为不同会话。每个浏览器分别维护默认标签页；MCP 工具统一接受可选 `browser` 参数，并在边界处规范化别名。页面扫描、JavaScript、CDP、Cookies、截图、导航和标签切换全部通过浏览器绑定的 driver 路由。

## 错误处理与兼容性

未知浏览器名称直接返回明确错误并列出支持项。指定浏览器没有连接标签页时直接报错，不自动降级到另一个浏览器。旧扩展未上报身份时按 Google Chrome 处理，以保证升级期间 Stable 仍可使用。调试日志写入 stderr，避免污染 stdio MCP 的 JSON-RPC 输出。

## 验证

回归测试覆盖浏览器别名、相同 tabId 隔离、命令发送到正确 WebSocket、扩展权限与身份字段。端到端测试使用两个真实 WebSocket 客户端模拟 Stable 和 Dev，并通过 MCP `list_tabs`、`execute_js` 验证默认路由和显式 Dev 路由。

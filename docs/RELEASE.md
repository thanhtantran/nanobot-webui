# Release Notes

## v0.2.5 — 2026-03-28

**自定义 AI Provider 管理**
- 支持动态添加、配置和删除自定义 AI Provider，无需重启服务
- 自动适配 OpenAI 兼容接口（含 API 密钥、Base URL 及支持的模型列表）
- 增强 Provider 匹配逻辑：通过补丁机制将自定义 Provider 注入 `nanobot` 核心代理循环
- 前端设置界面提供 Provider 创建、编辑与删除弹窗，并同步 7 种语言的 i18n 翻译

**Cron 定时任务增强**
- **任务隔离会话**：每次 Cron 执行现在拥有独立的会话 ID (`cron:{job_id}:{timestamp}`)，避免历史冲突
- **记录查看器改进**：优化时间戳解析逻辑（兼容纳秒/微秒/毫秒精度），新增长消息折叠与分步状态渲染
- **API 修复**：同步 `nanobot` 核心库 API 变更，修复任务切换开关的 422 校验错误，并将 Cron 数据存储迁移至工作区作用域

**消息渲染与交互优化**
- **SubAgent 增强**：`MessageBubble` 现在能更好地渲染 SubAgent 的工具调用状态和总结内容
- **JSON 编辑器更新**：`SystemConfig` 页面将原有的文本框替换为带语法高亮、折叠及 Diff 对比功能的 CodeMirror JSON 编辑器
- **Chat 输入框修复**：优化移动端输入体验及特定场景下的回车提交逻辑

**系统兼容性与补丁**
- 同步适配 `nanobot` nightly/main 分支最新的 API 变更（如 `_announce_result` 替代 `_announce`）
- 更新 [Dockerfile](Dockerfile) 版本号并清理过期依赖

---

## v0.2.4 — 2026-03-24

**Cron Jobs History**
- Add execution history viewer for Cron jobs — trace all past executions and deep-link to session logs
- Support searching and filtering cron job execution records by job ID or message content
- Support persistent session storage for each cron run (`cron:<job_id>:<ts>`) instead of overwriting a single session

**WeChat Channel Enhancement**
- Support outbound media messages — AI can now send images, videos, and files directly to WeChat users
- Implement client-side AES-128-ECB encryption for WeChat CDN uploads (matching official protocol)
- Auto-detect media type from file extension and handle fallback text notification on failure
- Improve login flow: add `nanobot channels login weixin` command for manual authentication

**Web Performance & UX**
- Implement **Lazy Loading** for all main pages using `React.lazy` and `Suspense`
- Introduce `TransitionLink` to prevent Suspense fallback flickering during navigation — UI stays responsive while loading chunks
- Optimize bundle size via Vite manual chunks: separate markdown rendering, UI primitives, and icons into dedicated chunks
- Localize multi-language labels for WeChat login and cron history (en, zh, ja, etc.)

**Infrastructure & Storage**
- Fallback local storage: `upload_to_s3` now supports saving to the local workspace when S3 is not configured
- Update [Dockerfile](Dockerfile) with improved node/npm mirror settings and explicit version pinning
- Refactor CLI: remove redundant gateway parameters and optimize WeChat/storage logic

---

## v0.2.3 — 2026-03-22

**WeChat Channel & QR Login**
- Add WeChat (weixin) channel support based on iLink API
- Add `nanobot weixin login` CLI command for headless QR code login confirmed via scanning
- Add `WeixinQrPanel` in the WebUI Channels page for a seamless in-browser scan-to-login experience
- Support real-time login status polling and automatic token persistence to `~/.nanobot/weixin/account.json`
- Add `qrcode[pil]` as an optional dependency via `pyproject.toml` [weixin] extra (included in default dependencies for convenience)
- Localized WeChat login labels and status messages (en / zh)

**Channel Management**
- Prioritize WeChat (weixin) in the channel list for Chinese users
- Ensure the WeChat channel is Always visible in the UI even before initial configuration is saved
- Support masking sensitive tokens in the WeChat configuration view
- Fix `getattr` missing default value in channel reload route to prevent potential crashes

---

## v0.2.2 — 2026-03-21

**Multi-Session Chat**
- Support concurrent multi-session chat — switch between sessions without losing in-flight messages
- Add message revoke support: retract the last sent message and re-edit before resending
- Fix duplicate messages and off-by-one revoke index issues introduced in #8

**i18n — 7 UI Languages**
- Add 4 new locale files: 繁體中文 (zh-TW), 한국어 (ko), Deutsch (de), Français (fr)
- Auto-detect language from browser locale and timezone (e.g. Asia/Taipei → zh-TW, Asia/Seoul → ko)
- Replace 7-language cycle toggle with a `DropdownMenuSub` picker in Sidebar and MobileTopBar
- Login page dropdown lists all 7 languages directly
- Fix login 401 error: skip page-redirect when the failing request is `/auth/login` itself, so the toast error shows correctly instead of refreshing the page
- Fix login form validation: remove HTML5 `required` attribute; use JS guard with i18n toast to avoid browser-native non-localized bubble

---

## v0.2.1 — 2026-03-18

**Config Editor**
- Add config diff highlight feature — visualize changes between current and saved config
- Add line numbers to config editor (DiffEditor) with scroll-sync gutter, dark mode support

**Agent & Provider**
- Upgrade `nanobot-ai` dependency to `0.1.4.post5`
- Update AgentLoop construction: replace legacy params with `GenerationSettings` + `web_search_config` + `context_window_tokens`
- Fix patch compatibility: add `tool_choice` param to `provider._patched_chat`; update SubagentManager tool registration (`WebSearchConfig`, `extra_allowed_dirs`); add `background_tasks` drain in `close_mcp`
- Fix channels route to handle dict-typed channel configs

**Settings & i18n**
- Replace `memory_window` with `context_window_tokens` in API models, routes and frontend
- Update i18n labels for context window setting (en / zh / ja)

**UI Polish**
- Soften chat bubble and active session colors from vivid primary orange to muted palette; add dark mode variants

---

## v0.2.0 — 2026-03-15

**Settings & Config**
- Migrate to unified `webui_config` for all settings management
- Improve MCP server handling and configuration persistence
- Persist provider default API base URL across restarts

**Debugging**
- Add LLM request debug logging (`--log-level` CLI option)
- Fix message overflow in chat UI

**UI Fixes**
- Fix provider refresh button

**Mobile & PWA**
- Add responsive mobile UI layout
- Register PWA service worker; fix iOS home screen icons
- Polish sidebar collapse/expand on mobile

**UI / UX**
- Redesign dark theme and sidebar visual style
- Add sidebar collapse/expand functionality
- Chat session list: search support + last message preview

**i18n**
- Toast notifications fully internationalized (zh / en / ja)
- Mobile i18n fixes

**Misc**
- Update app logo; change default port to `18780`

---

## v0.1.4 — 2026-03-13

**SubAgent Streaming**
- Live progress streaming from SubAgent to WebUI
- Push SubAgent tool hints and results to external channels
- Save full SubAgent tool-call chain to session (all channels)

**Settings UI**
- Add `send_progress` and `send_tool_hints` toggles in Settings page

---

## v0.1.3 — 2026-03-12

**Core**
- Unified patch management system
- Skills dynamic enable/disable toggle
- WebUI enhancements and OpenAI Responses API compatibility
- Fix CI build: frontend assets not bundled into wheel package

**Onboarding**
- Add first-run setup wizard
- Improved initial configuration flow

**UI**
- UI polish and i18n enhancements

---

## v0.1.0 — 2026-03-11 (Initial Release)

- Project initialization
- WebUI with session management and chat interface
- MCP dynamic tool loading; CLI command support
- S3 storage interface for file uploads
- Internationalization (i18n) foundation
- PyPI packaging configuration

# Release Notes

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

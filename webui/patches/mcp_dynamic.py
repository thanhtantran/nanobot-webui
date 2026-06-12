"""[MCPDynamic] patch — per-server MCP management with WebUI enable/disable toggles.

Replaces AgentLoop._connect_mcp to respect per-server enabled/disabled state
from webui_config.json.  Also adds ``toggle_mcp_server()`` for runtime
load/unload of individual servers.

v0.2.1 note: MCP state (_mcp_servers, _mcp_stacks, _mcp_connected) is still
managed as instance attributes on AgentLoop.  ``connect_missing_servers()``
is the preferred incremental connection API.
"""

from __future__ import annotations


def apply() -> None:
    import asyncio

    from nanobot.agent.loop import AgentLoop
    from nanobot.agent.tools.mcp import connect_missing_servers

    # ------------------------------------------------------------------
    # _connect_mcp: only connect enabled servers (respect WebUI toggles)
    # ------------------------------------------------------------------
    async def _connect_mcp_patched(self) -> None:
        from webui.utils.webui_config import is_mcp_server_enabled

        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return

        # Filter to only MCP servers enabled in the WebUI.  Disabled servers
        # are kept in _mcp_servers (so the config is preserved) but excluded
        # from the connection pass.
        enabled_servers = {
            name: cfg
            for name, cfg in self._mcp_servers.items()
            if is_mcp_server_enabled(name)
        }
        if not enabled_servers:
            return

        # connect_missing_servers reads from state._mcp_servers, so we
        # temporarily swap in only the enabled subset.
        saved = dict(self._mcp_servers)
        self._mcp_servers = enabled_servers
        try:
            await connect_missing_servers(self, self.tools)
        finally:
            # Restore the full server map (disabled servers remain unconnected
            # because they were excluded from the connection pass).
            # Keep any newly created stacks for enabled servers.
            merged = dict(saved)
            # _mcp_servers may have been modified; carry over enabled entries
            merged.update(self._mcp_servers)
            self._mcp_servers = merged

    # ------------------------------------------------------------------
    # close_mcp: close all per-server stacks (unchanged from v0.2.1 built-in)
    # ------------------------------------------------------------------
    async def _close_mcp_patched(self) -> None:
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        for stack in list(self._mcp_stacks.values()):
            try:
                await stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass
        self._mcp_stacks.clear()
        self._mcp_connected = False

    # ------------------------------------------------------------------
    # toggle_mcp_server: load or unload a single server at runtime
    # ------------------------------------------------------------------
    async def _toggle_mcp_server(self, name: str, cfg, enabled: bool) -> None:
        """Load or unload a single MCP server's tools without touching others."""
        prefix = f"mcp_{name}_"

        if not enabled:
            # Unregister all tools for this server from the registry
            to_remove = [k for k in self.tools._tools if k.startswith(prefix)]
            for k in to_remove:
                self.tools.unregister(k)
            # Close and discard the server's stack
            stack = self._mcp_stacks.pop(name, None)
            if stack:
                try:
                    await stack.aclose()
                except (RuntimeError, BaseExceptionGroup):
                    pass
        else:
            # Don't double-connect
            if name in self._mcp_stacks:
                return
            # Use connect_missing_servers for incremental connection
            saved = dict(self._mcp_servers)
            self._mcp_servers = {name: cfg}
            try:
                await connect_missing_servers(self, self.tools)
            finally:
                self._mcp_servers = saved

    AgentLoop._connect_mcp = _connect_mcp_patched  # type: ignore[method-assign]
    AgentLoop.close_mcp = _close_mcp_patched  # type: ignore[method-assign]
    AgentLoop.toggle_mcp_server = _toggle_mcp_server  # type: ignore[attr-defined]

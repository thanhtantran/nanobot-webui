"""[Session] patches — extend session lifecycle for WebUI-initiated deletion."""

from __future__ import annotations


def apply() -> None:
    """Patch 3: SessionManager.delete — evicts the entry from the in-memory cache
    and removes the persisted file from disk.

    Also patches Session.get_history() to remap the custom "sub_tool" role (used to
    store SubAgent tool-call chains for display) back to the LLM-valid roles
    ("assistant" for tool_call declarations, "tool" for tool results) before the
    history is fed to any LLM provider.
    """
    from nanobot.session import manager as _session_manager

    def _session_delete(self, key: str) -> None:
        self._cache.pop(key, None)
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()

    _session_manager.SessionManager.delete = _session_delete  # type: ignore[attr-defined]

    # --- sub_tool filter --------------------------------------------------
    # "sub_tool" is a synthetic role stored in session JSONL purely for UI
    # display (SubAgent tool-call chains).  The LLM only needs the final
    # assistant result — sub_tool entries are dropped from get_history().
    # The "system" bridge message is kept so there is no consecutive-
    # assistant sequence (main agent ends with assistant, SubAgent result
    # is also assistant — the system line separates them).
    _orig_get_history = _session_manager.Session.get_history

    def _get_history_patched(self, max_messages: int = 500):  # type: ignore[override]
        history = _orig_get_history(self, max_messages)
        return [m for m in history if m.get("role") != "sub_tool"]

    _session_manager.Session.get_history = _get_history_patched  # type: ignore[method-assign]

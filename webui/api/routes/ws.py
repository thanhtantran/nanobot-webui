"""WebSocket /ws/chat endpoint."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()

# ---------------------------------------------------------------------------
# Web-channel message capture
#
# When the agent replies via the message() tool instead of returning text
# directly, process_direct() returns "".  The tool calls bus.publish_outbound
# which the channel dispatcher drops (no "web" channel handler exists).
#
# Fix: patch the MessageTool's send_callback once so that messages addressed
# to channel="web" are pushed into per-connection capture queues, letting each
# _run_agent coroutine collect them after process_direct returns.
# ---------------------------------------------------------------------------

# user_id → list[asyncio.Queue[str]]: one queue per active WebSocket connection
_web_captures: dict[str, list[asyncio.Queue]] = {}
_message_tool_patched = False


def _ensure_message_tool_patched(container: Any) -> None:
    """One-time patch of the AgentLoop's MessageTool send_callback."""
    global _message_tool_patched
    if _message_tool_patched:
        return
    try:
        from nanobot.agent.tools.message import MessageTool
        msg_tool = container.agent.tools.get("message")
        if not isinstance(msg_tool, MessageTool):
            return
        original_callback = msg_tool._send_callback

        async def _patched_send(outbound_msg: Any) -> None:
            # Non-progress web messages → route to capture queues, skip the bus
            if (
                outbound_msg.channel == "web"
                and not (outbound_msg.metadata or {}).get("_progress")
            ):
                queues = _web_captures.get(str(outbound_msg.chat_id), [])
                for q in queues:
                    await q.put(outbound_msg.content or "")
                return  # consumed by WebSocket — don't push to shared bus
            if original_callback:
                await original_callback(outbound_msg)

        msg_tool.set_send_callback(_patched_send)
        _message_tool_patched = True
        logger.debug("MessageTool patched for web-channel capture")
    except Exception as exc:
        logger.warning("Could not patch MessageTool: {}", exc)


async def _auth_websocket(websocket: WebSocket) -> dict | None:
    """Validate the JWT token sent as query param ``token=...``."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return None

    from webui.api.auth import decode_access_token
    from webui.api.users import UserStore
    import jwt

    user_store = websocket.app.state.user_store
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return None

    user = user_store.get_by_id(payload["sub"])
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return None

    return user


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """
    WebSocket chat endpoint.

    Query params:
      token=<jwt>              — required for authentication
      session=<session_key>    — optional; if omitted a new ``web:<uid>:<uuid>`` key is created

    Client → Server frames (JSON):
      {"type": "message", "content": "..."}
      {"type": "cancel"}
      {"type": "new_session"}

    Server → Client frames (JSON):
      {"type": "session_info", "session_key": "web:..."}
      {"type": "progress",     "content": "...", "tool_hint": bool}
      {"type": "done",         "content": "..."}
      {"type": "error",        "content": "..."}
    """
    user = await _auth_websocket(websocket)
    if user is None:
        return

    await websocket.accept()
    container = websocket.app.state.services

    if container is None:
        await websocket.send_json({"type": "error", "content": "Services not initialised"})
        await websocket.close()
        return

    # Patch MessageTool once so web-channel replies are captured (not dropped)
    _ensure_message_tool_patched(container)

    is_admin = user.get("role") == "admin"

    def _is_allowed_session(key: str) -> bool:
        """Return True if the user is allowed to use this session key."""
        if key.startswith(f"web:{user['id']}"):
            return True
        # Admins can view/chat in any channel session (feishu/telegram/etc.)
        return is_admin

    # Determine or create session key
    requested_key: str | None = websocket.query_params.get("session")
    session_key = (
        requested_key
        if requested_key and _is_allowed_session(requested_key)
        else f"web:{user['id']}:{uuid.uuid4().hex[:8]}"
    )

    await websocket.send_json({"type": "session_info", "session_key": session_key})

    current_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "cancel":
                if current_task and not current_task.done():
                    current_task.cancel()
                    await websocket.send_json({"type": "error", "content": "cancelled"})

            elif msg_type == "new_session":
                session_key = f"web:{user['id']}:{uuid.uuid4().hex[:8]}"
                await websocket.send_json({"type": "session_info", "session_key": session_key})

            elif msg_type == "message":
                content = raw.get("content", "")
                # Allow per-message session override so the client can switch sessions
                # without reconnecting the WebSocket (used by the "new chat" button).
                msg_session_key = raw.get("session_key")
                if msg_session_key and _is_allowed_session(msg_session_key):
                    if msg_session_key != session_key:
                        session_key = msg_session_key
                        await websocket.send_json({"type": "session_info", "session_key": session_key})
                if not content:
                    continue

                if current_task and not current_task.done():
                    await websocket.send_json({
                        "type": "error",
                        "content": "Previous message still processing",
                    })
                    continue

                async def _on_progress(text: str, *, tool_hint: bool = False) -> None:
                    try:
                        await websocket.send_json({
                            "type": "progress",
                            "content": text,
                            "tool_hint": tool_hint,
                        })
                    except Exception:
                        pass

                async def _run_agent(msg: str, sess: str) -> None:
                    # Register a capture queue for this connection so that
                    # message() tool replies addressed to channel="web" are
                    # delivered here instead of being discarded by the dispatcher.
                    capture_q: asyncio.Queue[str] = asyncio.Queue()
                    uid = str(user["id"])
                    _web_captures.setdefault(uid, []).append(capture_q)
                    # Register on_progress so SubAgent background tasks can push
                    # tool-call hints to this WebSocket connection.
                    # Uses "subagent_progress" type so frontend shows them as
                    # persistent tool bubbles (visible even after main agent done).
                    from webui.patches.subagent import register_progress, register_announce, register_save_turn
                    _subagent_chat_key = f"web:{uid}"

                    async def _on_subagent_progress(text: str, tool_hint: bool = True) -> None:
                        try:
                            await websocket.send_json({
                                "type": "subagent_progress",
                                "content": text,
                                "tool_hint": True,
                            })
                        except Exception:
                            pass

                    async def _on_subagent_save_turn(all_messages: list) -> None:
                        """Persist SubAgent's full tool-call chain to the main session.

                        all_messages structure (from SubAgent):
                          [0] system prompt  (skip)
                          [1] user: task     (skip)
                          [2+] assistant(tool_calls) / tool / assistant(final)

                        Tool-call messages are saved with role="sub_tool" so the UI
                        can render them differently.  session.py patches get_history()
                        to remap sub_tool → assistant/tool before sending to any LLM.

                        A system bridge message is prepended to separate the main
                        agent's last assistant turn from SubAgent content.
                        """
                        try:
                            from datetime import datetime
                            _TRUNCATE = 500  # matches AgentLoop._TOOL_RESULT_MAX_CHARS
                            session = container.agent.sessions.get_or_create(sess)
                            # Separator: not shown as a user bubble in the UI
                            session.add_message("system", "[Background task progress]")
                            now = datetime.now().isoformat()
                            for m in all_messages[2:]:  # skip SubAgent system+user
                                role = m.get("role", "")
                                content = m.get("content") or ""
                                if role == "assistant" and m.get("tool_calls"):
                                    # Tool-call declaration → sub_tool
                                    session.messages.append({
                                        "role": "sub_tool",
                                        "content": content,
                                        "tool_calls": m["tool_calls"],
                                        "timestamp": now,
                                    })
                                elif role == "tool":
                                    # Tool result → sub_tool (truncate if large)
                                    if isinstance(content, str) and len(content) > _TRUNCATE:
                                        content = content[:_TRUNCATE] + "\n... (truncated)"
                                    session.messages.append({
                                        "role": "sub_tool",
                                        "content": content,
                                        "tool_call_id": m.get("tool_call_id", ""),
                                        "name": m.get("name", ""),
                                        "timestamp": now,
                                    })
                                elif role == "assistant":
                                    # Final result (no tool_calls) — keep as assistant
                                    if not content:
                                        continue
                                    session.messages.append({
                                        "role": "assistant",
                                        "content": content,
                                        "timestamp": now,
                                    })
                            session.updated_at = datetime.now()
                            container.agent.sessions.save(session)
                        except Exception:
                            pass

                    async def _on_subagent_done(text: str) -> None:
                        # Session already saved by _on_subagent_save_turn before this fires.
                        try:
                            await websocket.send_json({"type": "done", "content": text})
                        except Exception:
                            pass

                    register_progress(_subagent_chat_key, _on_subagent_progress)
                    register_save_turn(_subagent_chat_key, _on_subagent_save_turn)
                    register_announce(_subagent_chat_key, _on_subagent_done)
                    try:
                        response = await container.agent.process_direct(
                            msg,
                            session_key=sess,
                            channel="web",
                            chat_id=user["id"],
                            on_progress=_on_progress,
                        )
                        # If the agent replied via message() tool, process_direct
                        # returns "".  Drain whatever the patched callback captured.
                        if not response:
                            collected: list[str] = []
                            while not capture_q.empty():
                                try:
                                    collected.append(capture_q.get_nowait())
                                except asyncio.QueueEmpty:
                                    break
                            response = "\n\n".join(c for c in collected if c)
                        await websocket.send_json({"type": "done", "content": response})
                    except asyncio.CancelledError:
                        pass
                    except Exception as exc:
                        logger.error("WebSocket agent error: {}", exc)
                        try:
                            await websocket.send_json({"type": "error", "content": str(exc)})
                        except Exception:
                            pass
                    finally:
                        lst = _web_captures.get(uid, [])
                        if capture_q in lst:
                            lst.remove(capture_q)
                        if not lst:
                            _web_captures.pop(uid, None)
                        # Unregister only when WebSocket closes or errors, not here,
                        # because SubAgent may still be running in the background.
                        # The registry entry is overwritten on the next message and
                        # errors inside _emit_progress are silently swallowed.

                current_task = asyncio.create_task(_run_agent(content, session_key))

    except WebSocketDisconnect:
        if current_task and not current_task.done():
            current_task.cancel()
    except Exception as exc:
        logger.error("WebSocket error: {}", exc)
        try:
            await websocket.send_json({"type": "error", "content": str(exc)})
        except Exception:
            pass

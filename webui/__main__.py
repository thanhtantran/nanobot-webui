"""Entry point: ``python -m webui``

Starts nanobot gateway + FastAPI WebUI in a single asyncio process.
Zero modifications to any nanobot source files.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from webui.patches import apply_all as _apply_all_patches

_patches_applied = False


def _apply_patches() -> None:
    """Apply all patches (idempotent — safe to call multiple times)."""
    global _patches_applied
    if _patches_applied:
        return
    _patches_applied = True
    _apply_all_patches()


def _is_default_workspace(workspace: Path | None) -> bool:
    """Return whether a workspace resolves to nanobot's default workspace path."""
    current = workspace if workspace is not None else Path.home() / ".nanobot" / "workspace"
    default = Path.home() / ".nanobot" / "workspace"
    return current.resolve(strict=False) == default.resolve(strict=False)


async def main(
    web_port: int = 18780,
    web_host: str = "0.0.0.0",
    workspace: str | None = None,
    log_level: str = "DEBUG",
    webui_only: bool = False,
) -> None:
    _apply_patches()

    import sys as _sys
    from loguru import logger

    logger.remove()
    logger.add(_sys.stderr, level=log_level.upper())

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.bus.events import OutboundMessage
    from nanobot.config.loader import load_config, get_config_path, save_config
    from nanobot.config.paths import get_cron_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.session.manager import SessionManager
    from nanobot.utils.helpers import sync_workspace_templates

    from webui.api.channel_ext import ExtendedChannelManager
    from webui.api.gateway import ServiceContainer, start_api_server
    from webui.patches.provider import make_provider_patched

    config = load_config()

    # Auto-initialize config on first run (equivalent to `nanobot onboard`).
    if not get_config_path().exists():
        save_config(config)
        logger.info("First run: created default config at {}", get_config_path())

    if workspace:
        config.agents.defaults.workspace = workspace
    sync_workspace_templates(config.workspace_path)

    bus = MessageBus()
    provider = make_provider_patched(config)
    from nanobot.providers.base import GenerationSettings
    provider.generation = GenerationSettings(
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        reasoning_effort=config.agents.defaults.reasoning_effort,
    )
    session_manager = SessionManager(config.workspace_path)

    # Migrate legacy global cron store to workspace-scoped path (one-time).
    if _is_default_workspace(config.workspace_path):
        legacy_path = get_cron_dir() / "jobs.json"
        new_path = config.workspace_path / "cron" / "jobs.json"
        if legacy_path.is_file() and not new_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.move(str(legacy_path), str(new_path))

    cron_store_path = config.workspace_path / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Build AgentLoop kwargs — compatible with nanobot >= 0.2.1
    # v0.2.0+ consolidated web_config/exec_config into tools_config.
    _agent_kwargs: dict = dict(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        max_concurrent_subagents=config.agents.defaults.max_concurrent_subagents,
        context_window_tokens=config.agents.defaults.context_window_tokens,
        max_tool_result_chars=config.agents.defaults.max_tool_result_chars,
        tool_hint_max_length=config.agents.defaults.tool_hint_max_length,
        tools_config=config.tools,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
        timezone=config.agents.defaults.timezone,
        session_ttl_minutes=config.agents.defaults.session_ttl_minutes,
        consolidation_ratio=config.agents.defaults.consolidation_ratio,
        max_messages=config.agents.defaults.max_messages,
        disabled_skills=config.agents.defaults.disabled_skills,
        model_presets=config.model_presets,
        model_preset=config.agents.defaults.model_preset or None,
    )
    agent = AgentLoop(**_agent_kwargs)

    # ------------------------------------------------------------------ cron
    async def on_cron_job(job: CronJob) -> str | None:
        from nanobot.agent.tools.cron import CronTool
        from nanobot.agent.tools.message import MessageTool

        reminder_note = (
            "[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' has been triggered.\n"
            f"Scheduled instruction: {job.payload.message}"
        )
        cron_tool = agent.tools.get("cron")
        cron_token = None
        if isinstance(cron_tool, CronTool):
            cron_token = cron_tool.set_cron_context(True)

        # Web-channel jobs store the originating session key in payload.to
        to = job.payload.to or ""
        is_web_session = job.payload.channel == "web" and to.startswith("web:")
        is_web = job.payload.channel == "web" and bool(to)

        exec_session_key = f"cron:{job.id}:{int(time.time() * 1000)}"

        try:
            response = await agent.process_direct(
                reminder_note,
                session_key=exec_session_key,
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )
        finally:
            if isinstance(cron_tool, CronTool) and cron_token is not None:
                cron_tool.reset_cron_context(cron_token)

        message_tool = agent.tools.get("message")
        if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
            return response

        if job.payload.deliver and job.payload.to and response:
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response,
            ))

        # For web-session jobs: append only the final AI response to the
        # originating session — no trigger message pollution.
        if is_web_session and response:
            from datetime import datetime
            orig_sess = agent.sessions.get_or_create(to)
            orig_sess.messages.append({
                "role": "assistant",
                "content": response,
            })
            orig_sess.updated_at = datetime.now()
            agent.sessions.save(orig_sess)

        # Push result to any active WebSocket connections.
        if is_web and response:
            from webui.api.routes.ws import push_cron_result
            parts = to.split(":")
            push_uid = parts[1] if len(parts) >= 3 else to
            notify_session = to if is_web_session else exec_session_key
            await push_cron_result(push_uid, {
                "type": "cron_result",
                "job_id": job.id,
                "job_name": job.name,
                "content": response,
                "session_key": notify_session,
            })

        return response

    cron.on_job = on_cron_job

    # --------------------------------------------------------------- channels
    channels = ExtendedChannelManager(config, bus)
    channels.webui_only = webui_only

    _svc_kwargs = dict(
        config=config,
        bus=bus,
        agent=agent,
        channels=channels,
        session_manager=session_manager,
        cron=cron,
        make_provider=make_provider_patched,
        webui_only=webui_only,
    )
    container = ServiceContainer(**_svc_kwargs)

    if channels.enabled_channels:
        logger.info("Channels enabled: {}", ", ".join(channels.enabled_channels))
    else:
        logger.warning("No IM channels enabled")

    if webui_only:
        logger.info(
            "WebUI-only mode: IM channels will NOT be started. "
            "An external nanobot process is expected to handle IM traffic."
        )

    logger.info("Starting nanobot webui on http://{}:{}", web_host, web_port)

    async def run() -> None:
        try:
            await cron.start()
            if webui_only:
                await asyncio.gather(
                    agent.run(),
                    start_api_server(container, host=web_host, port=web_port),
                )
            else:
                await asyncio.gather(
                    agent.run(),
                    channels.start_all(),
                    start_api_server(container, host=web_host, port=web_port),
                )
        except KeyboardInterrupt:
            logger.info("Shutting down…")
        finally:
            await agent.close_mcp()
            cron.stop()
            agent.stop()
            if not webui_only:
                await channels.stop_all()

    await run()


def main_cli() -> None:
    """Entry point for ``nanobot-webui`` and ``webui`` scripts."""
    from webui.cli import run_webui
    run_webui()


if __name__ == "__main__":
    main_cli()

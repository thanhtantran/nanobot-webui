"""[ExecWindows] patches — backport cross-platform exec behavior from upstream.

Temporary patch notice:
    This file is a short-term compatibility backport for nanobot-ai==0.1.5.
    REMOVE in the next release after dependency is upgraded to an upstream
    version that includes native Windows ExecTool fixes.

Context:
    nanobot-ai==0.1.5 executes commands via bash unconditionally, which breaks
    on Windows environments without a POSIX shell and can surface RPC failures.

Patch:
    Monkey-patch ``nanobot.agent.tools.shell.ExecTool`` to:
    - spawn via ``cmd.exe /c`` on Windows (``COMSPEC`` aware)
    - build a minimal but usable Windows env (without leaking secrets)
    - apply ``path_append`` in a platform-aware way
    - skip Linux-only sandbox wrappers on Windows
"""

from __future__ import annotations


def apply() -> None:
    # TODO(next release): remove this entire patch module once nanobot-ai is
    # upgraded to a version that includes upstream cross-platform ExecTool.
    import asyncio
    import os
    import shutil
    import sys
    from pathlib import Path
    from typing import Any

    from loguru import logger
    from nanobot.agent.tools.sandbox import wrap_command
    from nanobot.agent.tools.shell import ExecTool

    _IS_WINDOWS = sys.platform == "win32"

    async def _spawn_patched(
        command: str,
        cwd: str,
        env: dict[str, str],
    ) -> asyncio.subprocess.Process:
        """Launch command in a platform-appropriate shell."""
        if _IS_WINDOWS:
            comspec = env.get("COMSPEC", os.environ.get("COMSPEC", "cmd.exe"))
            return await asyncio.create_subprocess_exec(
                comspec,
                "/c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

        bash = shutil.which("bash") or "/bin/bash"
        return await asyncio.create_subprocess_exec(
            bash,
            "-l",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

    def _build_env_patched(self: ExecTool) -> dict[str, str]:
        """Build a minimal environment for subprocess execution.

        On Windows, cmd.exe has no login-profile behavior, so forward a curated
        set of baseline variables (including PATH) while still avoiding full env
        inheritance.
        """
        allowed = getattr(self, "allowed_env_keys", []) or []
        if _IS_WINDOWS:
            sr = os.environ.get("SYSTEMROOT", r"C:\Windows")
            env = {
                "SYSTEMROOT": sr,
                "COMSPEC": os.environ.get("COMSPEC", f"{sr}\\system32\\cmd.exe"),
                "USERPROFILE": os.environ.get("USERPROFILE", ""),
                "HOMEDRIVE": os.environ.get("HOMEDRIVE", "C:"),
                "HOMEPATH": os.environ.get("HOMEPATH", "\\"),
                "TEMP": os.environ.get("TEMP", f"{sr}\\Temp"),
                "TMP": os.environ.get("TMP", f"{sr}\\Temp"),
                "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
                "PATH": os.environ.get("PATH", f"{sr}\\system32;{sr}"),
                "APPDATA": os.environ.get("APPDATA", ""),
                "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
                "ProgramData": os.environ.get("ProgramData", ""),
                "ProgramFiles": os.environ.get("ProgramFiles", ""),
                "ProgramFiles(x86)": os.environ.get("ProgramFiles(x86)", ""),
                "ProgramW6432": os.environ.get("ProgramW6432", ""),
            }
            for key in allowed:
                val = os.environ.get(key)
                if val is not None:
                    env[key] = val
            return env

        home = os.environ.get("HOME", "/tmp")
        env = {
            "HOME": home,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "TERM": os.environ.get("TERM", "dumb"),
        }
        for key in allowed:
            val = os.environ.get(key)
            if val is not None:
                env[key] = val
        return env

    async def _execute_patched(
        self: ExecTool,
        command: str,
        working_dir: str | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        if self.sandbox:
            if _IS_WINDOWS:
                logger.warning(
                    "Sandbox '{}' is not supported on Windows; running unsandboxed",
                    self.sandbox,
                )
            else:
                workspace = self.working_dir or cwd
                command = wrap_command(self.sandbox, command, workspace, cwd)
                cwd = str(Path(workspace).resolve())

        effective_timeout = min(timeout or self.timeout, self._MAX_TIMEOUT)
        env = self._build_env()

        if self.path_append:
            if _IS_WINDOWS:
                env["PATH"] = env.get("PATH", "") + ";" + self.path_append
            else:
                command = f'export PATH="$PATH:{self.path_append}"; {command}'

        try:
            process = await self._spawn(command, cwd, env)

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                await self._kill_process(process)
                return f"Error: Command timed out after {effective_timeout} seconds"
            except asyncio.CancelledError:
                await self._kill_process(process)
                raise

            output_parts: list[str] = []

            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))

            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"
            max_len = self._MAX_OUTPUT
            if len(result) > max_len:
                half = max_len // 2
                result = (
                    result[:half]
                    + f"\n\n... ({len(result) - max_len:,} chars truncated) ...\n\n"
                    + result[-half:]
                )

            return result

        except Exception as e:
            return f"Error executing command: {str(e)}"

    ExecTool._spawn = staticmethod(_spawn_patched)  # type: ignore[attr-defined]
    ExecTool._build_env = _build_env_patched  # type: ignore[method-assign]
    ExecTool.execute = _execute_patched  # type: ignore[method-assign]

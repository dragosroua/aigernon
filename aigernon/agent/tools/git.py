"""Git tool — explicit operations via subprocess, shell=False, no arbitrary passthrough."""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from aigernon.agent.tools.base import Tool


class GitTool(Tool):
    """
    Git operations with hard path enforcement.

    Uses subprocess with shell=False and an explicit arg list — no shell
    metacharacter injection is possible. Path restriction is enforced in Python
    before the subprocess is created, matching the same guarantee as filesystem tools.

    Supported actions: clone, pull, push, status, log, diff,
                       checkout, add, commit, branch
    """

    ALLOWED_ACTIONS = frozenset({
        "clone", "pull", "push", "status", "log", "diff",
        "checkout", "add", "commit", "branch",
    })

    def __init__(self, workspace: Path, allowed_dir: Path | None = None, timeout: int = 60):
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return (
            "Execute git operations on a repository. "
            "Actions: clone, pull, push, status, log, diff, checkout, add, commit, branch."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": sorted(self.ALLOWED_ACTIONS),
                    "description": "Git operation to perform",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the local git repository (required for all actions except clone)",
                },
                "repo_url": {
                    "type": "string",
                    "description": "Repository URL (required for clone)",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name — for checkout (switch) or branch (create with -b)",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (required for commit)",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to stage (for add). Omit to stage all changes ('git add .')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of log entries to show (default 20)",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to scope (for diff)",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        repo_path: str | None = None,
        repo_url: str | None = None,
        branch: str | None = None,
        message: str | None = None,
        files: list[str] | None = None,
        limit: int = 20,
        path: str | None = None,
        _allowed_dir: Path | None = None,
        **kwargs: Any,
    ) -> str:
        if action not in self.ALLOWED_ACTIONS:
            return f"Error: '{action}' is not allowed. Use: {', '.join(sorted(self.ALLOWED_ACTIONS))}"

        effective_dir = _allowed_dir or self._allowed_dir

        # ── clone ──────────────────────────────────────────────────────────────
        if action == "clone":
            if not repo_url:
                return "Error: repo_url is required for clone"
            dest = repo_path or self._derive_dest(repo_url, effective_dir)
            return await self._clone(repo_url, dest, effective_dir)

        # ── all other actions need repo_path ───────────────────────────────────
        if not repo_path:
            return "Error: repo_path is required for this action"

        cwd = self._validate_path(repo_path, effective_dir)
        if isinstance(cwd, str) and cwd.startswith("Error:"):
            return cwd  # validation error

        if action == "status":
            return await self._run(["git", "status"], cwd)

        if action == "pull":
            return await self._run(["git", "pull"], cwd)

        if action == "push":
            return await self._run(["git", "push"], cwd)

        if action == "log":
            return await self._run(
                ["git", "log", f"--max-count={max(1, limit)}", "--oneline", "--decorate"], cwd
            )

        if action == "diff":
            cmd = ["git", "diff"]
            if path:
                cmd.append(path)
            return await self._run(cmd, cwd)

        if action == "checkout":
            if not branch:
                return "Error: branch is required for checkout"
            return await self._run(["git", "checkout", branch], cwd)

        if action == "add":
            if files:
                # Validate each file path stays inside repo
                for f in files:
                    fp = Path(cwd) / f
                    if not str(fp.resolve()).startswith(cwd):
                        return f"Error: file path '{f}' is outside the repository"
                return await self._run(["git", "add", "--"] + files, cwd)
            return await self._run(["git", "add", "."], cwd)

        if action == "commit":
            if not message:
                return "Error: message is required for commit"
            return await self._run(["git", "commit", "-m", message], cwd)

        if action == "branch":
            if branch:
                return await self._run(["git", "checkout", "-b", branch], cwd)
            return await self._run(["git", "branch", "--list"], cwd)

        return f"Error: unhandled action '{action}'"

    # ── helpers ────────────────────────────────────────────────────────────────

    def _validate_path(self, path_str: str, allowed_dir: Path | None) -> str:
        """Resolve and enforce allowed_dir. Returns resolved str or 'Error: ...' string."""
        try:
            resolved = Path(path_str).expanduser().resolve()
        except Exception as e:
            return f"Error: cannot resolve path '{path_str}': {e}"
        if allowed_dir:
            if not str(resolved).startswith(str(allowed_dir.resolve())):
                return f"Error: path is outside the allowed directory"
        return str(resolved)

    def _derive_dest(self, repo_url: str, allowed_dir: Path | None) -> str:
        """Derive clone destination from URL."""
        name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
        base = allowed_dir or self._workspace
        return str(base / name)

    async def _clone(self, repo_url: str, dest: str, allowed_dir: Path | None) -> str:
        """Validate destination then run git clone."""
        dest_check = self._validate_path(dest, allowed_dir)
        if dest_check.startswith("Error:"):
            return dest_check
        dest_path = Path(dest_check)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        return await self._run(["git", "clone", repo_url, str(dest_path)], str(dest_path.parent))

    async def _run(self, args: list[str], cwd: str) -> str:
        """Run a git command with shell=False and return combined output."""
        logger.debug(f"GitTool: {' '.join(args)} (cwd={cwd})")
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self._timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: git command timed out after {self._timeout}s"

            parts = []
            if stdout:
                parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                text = stderr.decode("utf-8", errors="replace").strip()
                if text:
                    parts.append(f"stderr:\n{text}")
            if process.returncode != 0:
                parts.append(f"Exit code: {process.returncode}")

            result = "\n".join(parts) if parts else "(no output)"

            max_len = 8000
            if len(result) > max_len:
                result = result[:max_len] + "\n... (output truncated)"

            return result

        except FileNotFoundError:
            return "Error: git is not installed or not in PATH"
        except Exception as e:
            return f"Error running git: {e}"

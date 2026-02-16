"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from loguru import logger

from aigernon.agent.tools.base import Tool


class ExecTool(Tool):
    """Tool to execute shell commands with security controls."""

    # Default allowlist of safe command prefixes
    DEFAULT_ALLOW_PREFIXES = [
        # Version control
        "git ",
        # Package managers (read operations)
        "npm list", "npm ls", "npm view", "npm search", "npm info",
        "pip list", "pip show", "pip search",
        "brew list", "brew info", "brew search",
        # File inspection (read-only)
        "ls ", "ls\n", "cat ", "head ", "tail ", "less ", "more ",
        "wc ", "file ", "stat ", "du ", "df ",
        "find ", "locate ", "which ", "whereis ", "type ",
        # Text processing
        "grep ", "awk ", "sed ", "sort ", "uniq ", "cut ", "tr ",
        "jq ", "yq ",
        # Development tools
        "python ", "python3 ", "node ", "npm run", "npm test", "npm start",
        "cargo ", "go ", "rustc ", "gcc ", "clang ",
        "make ", "cmake ", "pytest ", "jest ", "mocha ",
        # System info (read-only)
        "echo ", "printf ", "date ", "whoami ", "id ", "pwd ",
        "env ", "printenv ", "uname ", "hostname ",
        "ps ", "top ", "htop ", "free ", "uptime ",
        # Network diagnostics
        "ping ", "curl ", "wget ", "nc ", "nslookup ", "dig ", "host ",
        # Misc utilities
        "tar ", "zip ", "unzip ", "gzip ", "gunzip ",
        "diff ", "patch ", "md5 ", "sha256sum ", "base64 ",
    ]

    # Patterns that are always blocked (cannot be overridden)
    CRITICAL_DENY_PATTERNS = [
        r":\(\)\s*\{.*\};\s*:",              # fork bomb
        r"\bdd\s+if=.*of=/dev/",             # dd to disk device
        r">\s*/dev/sd",                      # write to disk device
        r"\b(mkfs|fdisk|parted)\b",          # disk formatting
        r"\b(shutdown|reboot|poweroff|halt|init\s+0)\b",  # system power
        r"\brm\s+-[rf]{2,}\s+/\s*$",         # rm -rf /
        r"\brm\s+-[rf]{2,}\s+/\*",           # rm -rf /*
        r"\bchmod\s+-R\s+777\s+/",           # chmod 777 on root
        r"\bchown\s+-R\s+.*\s+/\s*$",        # chown on root
    ]

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        allow_prefixes: list[str] | None = None,
        restrict_to_workspace: bool = False,
        use_allowlist: bool = True,
    ):
        """
        Initialize ExecTool.

        Args:
            timeout: Command timeout in seconds.
            working_dir: Default working directory.
            deny_patterns: Additional regex patterns to block.
            allow_patterns: Regex patterns to explicitly allow.
            allow_prefixes: Command prefixes to allow (default: DEFAULT_ALLOW_PREFIXES).
            restrict_to_workspace: If True, block paths outside working_dir.
            use_allowlist: If True, only allow commands matching allow_prefixes/patterns.
        """
        self.timeout = timeout
        self.working_dir = working_dir
        self.use_allowlist = use_allowlist

        # Additional deny patterns (merged with critical)
        self.deny_patterns = self.CRITICAL_DENY_PATTERNS.copy()
        if deny_patterns:
            self.deny_patterns.extend(deny_patterns)

        # Allow patterns (regex)
        self.allow_patterns = allow_patterns or []

        # Allow prefixes (simple string matching, more intuitive)
        self.allow_prefixes = allow_prefixes if allow_prefixes is not None else self.DEFAULT_ALLOW_PREFIXES

        self.restrict_to_workspace = restrict_to_workspace
    
    @property
    def name(self) -> str:
        return "exec"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout} seconds"
            
            output_parts = []
            
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"
            
            return result
            
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """
        Security guard for command execution.

        Uses a combination of:
        1. Critical deny patterns (always blocked)
        2. Allowlist (prefix or regex based)
        3. Workspace restriction (optional)
        """
        cmd = command.strip()
        lower = cmd.lower()

        # Step 1: Check critical deny patterns (always blocked)
        for pattern in self.CRITICAL_DENY_PATTERNS:
            if re.search(pattern, lower):
                logger.warning(f"Command blocked (critical pattern): {cmd[:100]}")
                return "Error: Command blocked by security guard (dangerous operation detected)"

        # Step 2: Check additional deny patterns
        for pattern in self.deny_patterns:
            if pattern not in self.CRITICAL_DENY_PATTERNS and re.search(pattern, lower):
                logger.warning(f"Command blocked (deny pattern): {cmd[:100]}")
                return "Error: Command blocked by security guard (pattern denied)"

        # Step 3: Allowlist check (if enabled)
        if self.use_allowlist:
            allowed = False

            # Check prefix allowlist
            for prefix in self.allow_prefixes:
                if lower.startswith(prefix.lower()) or cmd.startswith(prefix):
                    allowed = True
                    break

            # Check regex allow patterns
            if not allowed and self.allow_patterns:
                for pattern in self.allow_patterns:
                    if re.search(pattern, lower):
                        allowed = True
                        break

            if not allowed:
                logger.warning(f"Command blocked (not in allowlist): {cmd[:100]}")
                return (
                    "Error: Command not in allowlist. For security, only approved commands are allowed. "
                    "Common operations like git, npm, python, grep, find, ls are permitted."
                )

        # Step 4: Workspace restriction
        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by security guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()

            # Extract paths from command
            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"']+", cmd)
            posix_paths = re.findall(r"/[^\s\"']+", cmd)

            for raw in win_paths + posix_paths:
                # Skip common system paths that are read-only
                if raw.startswith(("/usr/", "/bin/", "/opt/", "/etc/", "/tmp/")):
                    continue

                try:
                    p = Path(raw).resolve()
                except Exception:
                    continue

                if cwd_path not in p.parents and p != cwd_path and not str(p).startswith(str(cwd_path)):
                    return "Error: Command blocked by security guard (path outside workspace)"

        return None

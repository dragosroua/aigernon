"""Health check functionality for the doctor command."""

import json
from pathlib import Path
from typing import Literal

from aigernon.daemon.status import DaemonStatus


class HealthCheck:
    """
    Performs health checks on the AIGernon installation.

    Checks configuration, daemon status, channels, and workspace.
    """

    def __init__(self):
        self.results: list[tuple[str, str, str]] = []  # (status, message, details)
        self.errors = 0
        self.warnings = 0

    def _add(self, status: Literal["ok", "warn", "error"], message: str, details: str = "") -> None:
        """Add a check result."""
        self.results.append((status, message, details))
        if status == "error":
            self.errors += 1
        elif status == "warn":
            self.warnings += 1

    def check_config_exists(self, config_path: Path) -> bool:
        """Check if config file exists."""
        if config_path.exists():
            self._add("ok", f"Config file exists ({config_path})")
            return True
        else:
            self._add("error", f"Config file missing ({config_path})")
            return False

    def check_config_valid(self, config_path: Path) -> bool:
        """Check if config file is valid JSON."""
        if not config_path.exists():
            return False

        try:
            with open(config_path) as f:
                json.load(f)
            self._add("ok", "Config is valid JSON")
            return True
        except json.JSONDecodeError as e:
            self._add("error", "Config has invalid JSON", str(e))
            return False

    def check_llm_provider(self, config) -> bool:
        """Check if an LLM provider is configured."""
        provider = config.get_provider()
        provider_name = config.get_provider_name()

        if provider and provider.api_key:
            self._add("ok", f"LLM provider configured ({provider_name})")
            return True
        elif config.agents.defaults.model.startswith("bedrock/"):
            self._add("ok", f"LLM provider configured (AWS Bedrock)")
            return True
        else:
            self._add("error", "No LLM provider API key configured")
            return False

    def check_web_search(self, config) -> None:
        """Check if web search API key is configured."""
        if config.tools.web.search.api_key:
            self._add("ok", "Web search API key configured")
        else:
            self._add("warn", "No web search API key configured")

    def check_daemon_status(self, daemon_status: DaemonStatus) -> None:
        """Check daemon running status."""
        pid = daemon_status.read_pid()

        if pid and daemon_status.is_process_running(pid):
            uptime = daemon_status.get_uptime() or "unknown"
            self._add("ok", f"Daemon is running (PID {pid}, uptime {uptime})")

            # Check heartbeat
            age = daemon_status.get_heartbeat_age()
            if age is not None:
                if age < 120:  # 2 minutes
                    self._add("ok", f"Last heartbeat: {age} seconds ago")
                else:
                    self._add("warn", f"Last heartbeat: {age} seconds ago (stale)")
        else:
            self._add("warn", "Daemon is not running")

    def check_channels(self, config) -> None:
        """Check channel configuration."""
        channels_checked = False

        if config.channels.telegram.enabled:
            if config.channels.telegram.token:
                self._add("ok", "Telegram channel configured")
            else:
                self._add("error", "Telegram enabled but token missing")
            channels_checked = True

        if config.channels.whatsapp.enabled:
            self._add("ok", "WhatsApp channel configured")
            channels_checked = True

        if config.channels.discord.enabled:
            if config.channels.discord.token:
                self._add("ok", "Discord channel configured")
            else:
                self._add("error", "Discord enabled but token missing")
            channels_checked = True

        if not channels_checked:
            self._add("warn", "No channels configured")

    def check_workspace(self, workspace_path: Path) -> None:
        """Check workspace directory and files."""
        if workspace_path.exists():
            self._add("ok", f"Workspace exists ({workspace_path})")
        else:
            self._add("error", f"Workspace missing ({workspace_path})")
            return

        # Check memory directory
        memory_dir = workspace_path / "memory"
        if memory_dir.exists():
            self._add("ok", "Memory directory exists")
        else:
            self._add("warn", "Memory directory missing")

        # Count skills
        skills_dir = workspace_path / "skills"
        if skills_dir.exists():
            skills = list(skills_dir.glob("*.md"))
            if skills:
                self._add("ok", f"{len(skills)} skills loaded")
            else:
                self._add("warn", "No skills found")
        else:
            self._add("warn", "Skills directory missing")

    def check_cron(self, data_dir: Path) -> None:
        """Check cron job status."""
        cron_path = data_dir / "cron" / "jobs.json"

        if cron_path.exists():
            try:
                with open(cron_path) as f:
                    data = json.load(f)
                jobs = data.get("jobs", [])
                enabled_jobs = [j for j in jobs if j.get("enabled", True)]
                if enabled_jobs:
                    self._add("ok", f"Cron: {len(enabled_jobs)} jobs scheduled")
                else:
                    self._add("ok", "Cron: no jobs scheduled")
            except (json.JSONDecodeError, KeyError):
                self._add("warn", "Cron jobs file is invalid")
        else:
            self._add("ok", "Cron: no jobs scheduled")

    def format_output(self, use_color: bool = True) -> str:
        """
        Format the health check results.

        Args:
            use_color: Whether to use ANSI color codes.

        Returns:
            Formatted output string.
        """
        lines = ["AIGernon Health Check", "=" * 21, ""]

        for status, message, details in self.results:
            if use_color:
                if status == "ok":
                    icon = "\033[32m✓\033[0m"  # Green
                elif status == "warn":
                    icon = "\033[33m⚠\033[0m"  # Yellow
                else:
                    icon = "\033[31m✗\033[0m"  # Red
            else:
                if status == "ok":
                    icon = "✓"
                elif status == "warn":
                    icon = "⚠"
                else:
                    icon = "✗"

            line = f"{icon} {message}"
            if details:
                line += f"\n    {details}"
            lines.append(line)

        # Summary
        lines.append("")
        if self.errors > 0:
            summary = f"Overall: Issues found ({self.errors} errors"
            if self.warnings > 0:
                summary += f", {self.warnings} warnings"
            summary += ")"
        elif self.warnings > 0:
            summary = f"Overall: Healthy ({self.warnings} warnings)"
        else:
            summary = "Overall: Healthy"
        lines.append(summary)

        return "\n".join(lines)

    @property
    def exit_code(self) -> int:
        """Get exit code based on check results."""
        return 1 if self.errors > 0 else 0


def run_health_check() -> tuple[str, int]:
    """
    Run all health checks.

    Returns:
        Tuple of (formatted output, exit code).
    """
    from aigernon.config.loader import load_config, get_config_path, get_data_dir
    from aigernon.daemon.status import DaemonStatus

    checker = HealthCheck()
    config_path = get_config_path()
    data_dir = get_data_dir()

    # Config checks
    if checker.check_config_exists(config_path):
        if checker.check_config_valid(config_path):
            config = load_config()
            checker.check_llm_provider(config)
            checker.check_web_search(config)
            checker.check_channels(config)
            checker.check_workspace(config.workspace_path)

    # Daemon checks
    daemon_status = DaemonStatus(data_dir)
    checker.check_daemon_status(daemon_status)

    # Cron checks
    checker.check_cron(data_dir)

    return checker.format_output(), checker.exit_code

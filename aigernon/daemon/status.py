"""PID file management and status tracking for the daemon."""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class DaemonStatus:
    """
    Manages daemon PID file and status tracking.

    Writes and reads status information to track the running daemon process.
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path.home() / ".aigernon"
        self.pid_file = self.data_dir / "daemon.pid"
        self.status_file = self.data_dir / "daemon.status.json"
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    def write_pid(self) -> None:
        """Write current process PID to file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        logger.debug(f"Wrote PID {os.getpid()} to {self.pid_file}")

    def read_pid(self) -> int | None:
        """
        Read PID from file.

        Returns:
            PID if file exists and is readable, None otherwise.
        """
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def remove_pid(self) -> None:
        """Remove PID file."""
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
                logger.debug(f"Removed PID file {self.pid_file}")
            except OSError as e:
                logger.warning(f"Failed to remove PID file: {e}")

    def is_process_running(self, pid: int | None = None) -> bool:
        """
        Check if the daemon process is actually running.

        Args:
            pid: PID to check. Reads from file if not provided.

        Returns:
            True if process is running, False otherwise.
        """
        pid = pid or self.read_pid()
        if pid is None:
            return False

        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we can't signal it
            return True

    def write_status(
        self,
        channels_active: list[str] | None = None,
        sessions_active: int = 0,
    ) -> None:
        """
        Write daemon status to file.

        Args:
            channels_active: List of active channel names.
            sessions_active: Number of active sessions.
        """
        from aigernon import __version__

        now = datetime.now(timezone.utc).isoformat()

        status = {
            "pid": os.getpid(),
            "started_at": now,
            "last_heartbeat": now,
            "version": __version__,
            "channels_active": channels_active or [],
            "sessions_active": sessions_active,
        }

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(json.dumps(status, indent=2))
        logger.debug(f"Wrote status to {self.status_file}")

    def read_status(self) -> dict[str, Any] | None:
        """
        Read daemon status from file.

        Returns:
            Status dict if file exists and is readable, None otherwise.
        """
        if not self.status_file.exists():
            return None

        try:
            return json.loads(self.status_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def update_heartbeat(
        self,
        channels_active: list[str] | None = None,
        sessions_active: int = 0,
    ) -> None:
        """
        Update the last_heartbeat timestamp in status file.

        Args:
            channels_active: List of active channel names.
            sessions_active: Number of active sessions.
        """
        status = self.read_status()
        if status is None:
            self.write_status(channels_active, sessions_active)
            return

        status["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        status["channels_active"] = channels_active or status.get("channels_active", [])
        status["sessions_active"] = sessions_active

        try:
            self.status_file.write_text(json.dumps(status, indent=2))
        except OSError as e:
            logger.warning(f"Failed to update heartbeat: {e}")

    def remove_status(self) -> None:
        """Remove status file."""
        if self.status_file.exists():
            try:
                self.status_file.unlink()
                logger.debug(f"Removed status file {self.status_file}")
            except OSError as e:
                logger.warning(f"Failed to remove status file: {e}")

    def cleanup(self) -> None:
        """Remove PID and status files."""
        self.remove_pid()
        self.remove_status()

    async def start_heartbeat_loop(
        self,
        get_channels: callable = None,
        get_sessions: callable = None,
        interval_s: int = 60,
    ) -> None:
        """
        Start periodic heartbeat updates.

        Args:
            get_channels: Callable that returns list of active channel names.
            get_sessions: Callable that returns number of active sessions.
            interval_s: Heartbeat interval in seconds.
        """
        self._running = True
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(get_channels, get_sessions, interval_s)
        )
        logger.debug(f"Started daemon heartbeat (every {interval_s}s)")

    async def _heartbeat_loop(
        self,
        get_channels: callable = None,
        get_sessions: callable = None,
        interval_s: int = 60,
    ) -> None:
        """Internal heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(interval_s)
                if not self._running:
                    break

                channels = get_channels() if get_channels else []
                sessions = get_sessions() if get_sessions else 0
                self.update_heartbeat(channels, sessions)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Daemon heartbeat error: {e}")

    def stop_heartbeat_loop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    def get_uptime(self) -> str | None:
        """
        Get human-readable uptime.

        Returns:
            Uptime string (e.g., "2h 15m") or None if not running.
        """
        status = self.read_status()
        if status is None or not status.get("started_at"):
            return None

        try:
            started = datetime.fromisoformat(status["started_at"].replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - started

            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        except (ValueError, KeyError):
            return None

    def get_heartbeat_age(self) -> int | None:
        """
        Get seconds since last heartbeat.

        Returns:
            Seconds since last heartbeat, or None if unknown.
        """
        status = self.read_status()
        if status is None or not status.get("last_heartbeat"):
            return None

        try:
            last = datetime.fromisoformat(status["last_heartbeat"].replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - last
            return int(delta.total_seconds())
        except (ValueError, KeyError):
            return None

"""Daemon manager for platform-specific service management."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

from aigernon.daemon.templates import LAUNCHD_PLIST, SYSTEMD_UNIT
from aigernon.daemon.status import DaemonStatus


Platform = Literal["macos", "linux", "unsupported"]


class DaemonManager:
    """
    Manages daemon installation and control.

    Detects the platform and uses the appropriate service manager
    (launchd on macOS, systemd on Linux).
    """

    # API key environment variables to pass through
    API_KEY_VARS = [
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "BRAVE_API_KEY",
    ]

    def __init__(self):
        self.home = Path.home()
        self.data_dir = self.home / ".aigernon"
        self.logs_dir = self.data_dir / "logs"
        self.log_file = self.logs_dir / "daemon.log"
        self.status = DaemonStatus(self.data_dir)

        # Platform-specific paths
        self.platform = self._detect_platform()
        if self.platform == "macos":
            self.service_file = self.home / "Library" / "LaunchAgents" / "com.aigernon.gateway.plist"
            self.service_name = "com.aigernon.gateway"
        elif self.platform == "linux":
            self.service_file = self.home / ".config" / "systemd" / "user" / "aigernon.service"
            self.service_name = "aigernon"
        else:
            self.service_file = None
            self.service_name = None

    def _detect_platform(self) -> Platform:
        """Detect the current platform."""
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "linux":
            # Check if systemd is available
            if shutil.which("systemctl"):
                return "linux"
        return "unsupported"

    def _get_python_path(self) -> str:
        """Get the path to the Python interpreter."""
        return sys.executable

    def _get_env_vars(self) -> dict[str, str]:
        """Get environment variables to pass to the service."""
        env = {}
        for var in self.API_KEY_VARS:
            value = os.environ.get(var)
            if value:
                env[var] = value
        return env

    def _generate_plist(self) -> str:
        """Generate launchd plist content."""
        env_vars = self._get_env_vars()
        extra_entries = ""
        for key, value in env_vars.items():
            extra_entries += f"        <key>{key}</key>\n"
            extra_entries += f"        <string>{value}</string>\n"

        return LAUNCHD_PLIST.format(
            python_path=self._get_python_path(),
            working_dir=str(self.data_dir),
            log_file=str(self.log_file),
            path_env=os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            home=str(self.home),
            extra_env_entries=extra_entries.rstrip("\n"),
        )

    def _generate_systemd_unit(self) -> str:
        """Generate systemd unit file content."""
        env_vars = self._get_env_vars()
        extra_lines = ""
        for key, value in env_vars.items():
            extra_lines += f'Environment="{key}={value}"\n'

        return SYSTEMD_UNIT.format(
            python_path=self._get_python_path(),
            working_dir=str(self.data_dir),
            log_file=str(self.log_file),
            path_env=os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            home=str(self.home),
            extra_env_lines=extra_lines.rstrip("\n"),
        )

    def is_supported(self) -> bool:
        """Check if daemon management is supported on this platform."""
        return self.platform != "unsupported"

    def install(self) -> tuple[bool, str]:
        """
        Install the daemon service.

        Returns:
            Tuple of (success, message).
        """
        if not self.is_supported():
            return False, (
                "Daemon management is not supported on this platform. "
                "Run `aigernon gateway` manually or use Docker."
            )

        # Create logs directory
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.platform == "macos":
            return self._install_macos()
        elif self.platform == "linux":
            return self._install_linux()

        return False, "Unknown platform"

    def _install_macos(self) -> tuple[bool, str]:
        """Install launchd service on macOS."""
        # Create LaunchAgents directory if needed
        self.service_file.parent.mkdir(parents=True, exist_ok=True)

        # Generate and write plist
        content = self._generate_plist()
        self.service_file.write_text(content)

        # Load the service
        result = subprocess.run(
            ["launchctl", "load", str(self.service_file)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False, f"Failed to load service: {result.stderr}"

        return True, f"Installed service at {self.service_file}"

    def _install_linux(self) -> tuple[bool, str]:
        """Install systemd user service on Linux."""
        # Create systemd user directory if needed
        self.service_file.parent.mkdir(parents=True, exist_ok=True)

        # Generate and write unit file
        content = self._generate_systemd_unit()
        self.service_file.write_text(content)

        # Reload systemd
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)

        # Enable the service
        result = subprocess.run(
            ["systemctl", "--user", "enable", self.service_name],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False, f"Failed to enable service: {result.stderr}"

        # Enable linger so service survives logout
        user = os.environ.get("USER", "")
        if user:
            subprocess.run(["loginctl", "enable-linger", user], capture_output=True)

        return True, f"Installed service at {self.service_file}"

    def uninstall(self) -> tuple[bool, str]:
        """
        Uninstall the daemon service.

        Returns:
            Tuple of (success, message).
        """
        if not self.is_supported():
            return False, "Daemon management is not supported on this platform."

        if not self.service_file or not self.service_file.exists():
            return False, "Service is not installed."

        if self.platform == "macos":
            return self._uninstall_macos()
        elif self.platform == "linux":
            return self._uninstall_linux()

        return False, "Unknown platform"

    def _uninstall_macos(self) -> tuple[bool, str]:
        """Uninstall launchd service on macOS."""
        # Unload the service
        subprocess.run(
            ["launchctl", "unload", str(self.service_file)],
            capture_output=True,
        )

        # Remove the plist
        try:
            self.service_file.unlink()
        except OSError as e:
            return False, f"Failed to remove service file: {e}"

        return True, "Service uninstalled"

    def _uninstall_linux(self) -> tuple[bool, str]:
        """Uninstall systemd user service on Linux."""
        # Stop the service
        subprocess.run(
            ["systemctl", "--user", "stop", self.service_name],
            capture_output=True,
        )

        # Disable the service
        subprocess.run(
            ["systemctl", "--user", "disable", self.service_name],
            capture_output=True,
        )

        # Remove the unit file
        try:
            self.service_file.unlink()
        except OSError as e:
            return False, f"Failed to remove service file: {e}"

        # Reload systemd
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)

        return True, "Service uninstalled"

    def start(self) -> tuple[bool, str]:
        """
        Start the daemon.

        Returns:
            Tuple of (success, message).
        """
        if not self.is_supported():
            return False, "Daemon management is not supported on this platform."

        if not self.service_file or not self.service_file.exists():
            return False, "Service is not installed. Run `aigernon daemon install` first."

        if self.platform == "macos":
            result = subprocess.run(
                ["launchctl", "start", self.service_name],
                capture_output=True,
                text=True,
            )
        elif self.platform == "linux":
            result = subprocess.run(
                ["systemctl", "--user", "start", self.service_name],
                capture_output=True,
                text=True,
            )
        else:
            return False, "Unknown platform"

        if result.returncode != 0:
            return False, f"Failed to start service: {result.stderr}"

        # Give the service a moment to start
        import time
        time.sleep(1)

        pid = self.status.read_pid()
        if pid and self.status.is_process_running(pid):
            return True, f"Daemon started (PID {pid})"

        return True, "Daemon start command sent"

    def stop(self) -> tuple[bool, str]:
        """
        Stop the daemon gracefully.

        Returns:
            Tuple of (success, message).
        """
        if not self.is_supported():
            return False, "Daemon management is not supported on this platform."

        if self.platform == "macos":
            result = subprocess.run(
                ["launchctl", "stop", self.service_name],
                capture_output=True,
                text=True,
            )
        elif self.platform == "linux":
            result = subprocess.run(
                ["systemctl", "--user", "stop", self.service_name],
                capture_output=True,
                text=True,
            )
        else:
            return False, "Unknown platform"

        if result.returncode != 0:
            return False, f"Failed to stop service: {result.stderr}"

        return True, "Daemon stopped"

    def restart(self) -> tuple[bool, str]:
        """
        Restart the daemon.

        Returns:
            Tuple of (success, message).
        """
        if not self.is_supported():
            return False, "Daemon management is not supported on this platform."

        if not self.service_file or not self.service_file.exists():
            return False, "Service is not installed. Run `aigernon daemon install` first."

        # Stop first (ignore failure if not running)
        self.stop()

        # Start
        return self.start()

    def get_status(self) -> dict:
        """
        Get daemon status.

        Returns:
            Dict with status information.
        """
        result = {
            "platform": self.platform,
            "installed": self.service_file and self.service_file.exists() if self.service_file else False,
            "running": False,
            "pid": None,
            "uptime": None,
            "last_heartbeat": None,
            "channels_active": [],
            "sessions_active": 0,
        }

        pid = self.status.read_pid()
        if pid and self.status.is_process_running(pid):
            result["running"] = True
            result["pid"] = pid
            result["uptime"] = self.status.get_uptime()
            result["last_heartbeat"] = self.status.get_heartbeat_age()

            status_data = self.status.read_status()
            if status_data:
                result["channels_active"] = status_data.get("channels_active", [])
                result["sessions_active"] = status_data.get("sessions_active", 0)

        return result

    def get_log_path(self) -> Path:
        """Get the daemon log file path."""
        return self.log_file

    def rotate_logs(self, max_size_mb: int = 10, max_files: int = 3) -> None:
        """
        Rotate log files if they exceed the size limit.

        Args:
            max_size_mb: Maximum log file size in MB before rotation.
            max_files: Maximum number of rotated files to keep.
        """
        if not self.log_file.exists():
            return

        # Check file size
        size_mb = self.log_file.stat().st_size / (1024 * 1024)
        if size_mb < max_size_mb:
            return

        logger.info(f"Rotating daemon log ({size_mb:.1f}MB > {max_size_mb}MB)")

        # Rotate existing files
        for i in range(max_files - 1, 0, -1):
            old_file = self.logs_dir / f"daemon.log.{i}"
            new_file = self.logs_dir / f"daemon.log.{i + 1}"
            if old_file.exists():
                if i + 1 > max_files:
                    old_file.unlink()
                else:
                    old_file.rename(new_file)

        # Move current log to .1
        rotated = self.logs_dir / "daemon.log.1"
        self.log_file.rename(rotated)

        # Create empty new log file
        self.log_file.touch()

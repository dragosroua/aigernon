"""File integrity monitoring for critical configuration files."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from aigernon.utils.helpers import ensure_dir


@dataclass
class FileHash:
    """Hash record for a monitored file."""

    path: str
    hash: str
    size: int
    modified: str
    checked_at: str


@dataclass
class IntegrityConfig:
    """Configuration for integrity monitoring."""

    enabled: bool = True
    hash_algorithm: str = "sha256"
    check_on_startup: bool = True
    auto_alert: bool = True


class IntegrityMonitor:
    """
    File integrity monitor for critical configuration files.

    Monitors SOUL.md, AGENTS.md, config.json and other critical files
    for unauthorized modifications.
    """

    DEFAULT_MONITORED_FILES = [
        "SOUL.md",
        "AGENTS.md",
        "IDENTITY.md",
        "USER.md",
    ]

    def __init__(
        self,
        workspace: Path,
        config_path: Path | None = None,
        config: IntegrityConfig | None = None,
        on_violation: Callable[[str, str, str], None] | None = None,
    ):
        """
        Initialize integrity monitor.

        Args:
            workspace: Workspace directory containing monitored files.
            config_path: Path to config.json (also monitored).
            config: Integrity monitoring configuration.
            on_violation: Callback for integrity violations (file, expected, actual).
        """
        self.workspace = workspace
        self.config_path = config_path or (Path.home() / ".aigernon" / "config.json")
        self.config = config or IntegrityConfig()
        self.on_violation = on_violation

        self._state_dir = ensure_dir(Path.home() / ".aigernon" / "security")
        self._hashes_file = self._state_dir / "integrity_hashes.json"
        self._hashes: dict[str, FileHash] = {}

        self._load_hashes()

    def _load_hashes(self) -> None:
        """Load stored hashes from disk."""
        if not self._hashes_file.exists():
            return

        try:
            with open(self._hashes_file) as f:
                data = json.load(f)

            for path, info in data.items():
                self._hashes[path] = FileHash(**info)
        except Exception as e:
            logger.warning(f"Failed to load integrity hashes: {e}")

    def _save_hashes(self) -> None:
        """Save hashes to disk."""
        try:
            data = {
                path: {
                    "path": h.path,
                    "hash": h.hash,
                    "size": h.size,
                    "modified": h.modified,
                    "checked_at": h.checked_at,
                }
                for path, h in self._hashes.items()
            }

            with open(self._hashes_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save integrity hashes: {e}")

    def _compute_hash(self, file_path: Path) -> str | None:
        """Compute hash of a file."""
        if not file_path.exists():
            return None

        try:
            hasher = hashlib.new(self.config.hash_algorithm)
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return None

    def get_monitored_files(self) -> list[Path]:
        """Get list of all monitored file paths."""
        files = []

        # Workspace files
        for filename in self.DEFAULT_MONITORED_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                files.append(file_path)

        # Config file
        if self.config_path.exists():
            files.append(self.config_path)

        return files

    def initialize(self) -> dict[str, str]:
        """
        Initialize hashes for all monitored files.

        This should be called on first setup to establish baseline hashes.

        Returns:
            Dict mapping file paths to their hashes.
        """
        results = {}

        for file_path in self.get_monitored_files():
            file_hash = self._compute_hash(file_path)
            if file_hash:
                stat = file_path.stat()
                self._hashes[str(file_path)] = FileHash(
                    path=str(file_path),
                    hash=file_hash,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    checked_at=datetime.now().isoformat(),
                )
                results[str(file_path)] = file_hash
                logger.info(f"Initialized integrity hash for {file_path.name}: {file_hash[:16]}...")

        self._save_hashes()
        return results

    def verify(self) -> list[dict[str, Any]]:
        """
        Verify integrity of all monitored files.

        Returns:
            List of violations, each containing file path and hash mismatch details.
        """
        if not self.config.enabled:
            return []

        violations = []

        for file_path in self.get_monitored_files():
            path_str = str(file_path)
            current_hash = self._compute_hash(file_path)

            if path_str not in self._hashes:
                # New file, not yet tracked
                logger.debug(f"File not tracked: {file_path.name}")
                continue

            stored = self._hashes[path_str]

            if current_hash is None:
                # File was deleted
                violations.append({
                    "file": path_str,
                    "type": "deleted",
                    "expected_hash": stored.hash,
                    "actual_hash": None,
                })
                logger.error(f"INTEGRITY: Monitored file deleted: {file_path.name}")

                if self.on_violation:
                    self.on_violation(path_str, stored.hash, "DELETED")

            elif current_hash != stored.hash:
                # File was modified
                violations.append({
                    "file": path_str,
                    "type": "modified",
                    "expected_hash": stored.hash,
                    "actual_hash": current_hash,
                })
                logger.error(f"INTEGRITY: File modified: {file_path.name} (expected {stored.hash[:16]}..., got {current_hash[:16]}...)")

                if self.on_violation:
                    self.on_violation(path_str, stored.hash, current_hash)

        return violations

    def update_hash(self, file_path: Path) -> str | None:
        """
        Update the stored hash for a file.

        Call this after an authorized modification to update the baseline.

        Args:
            file_path: Path to the file.

        Returns:
            The new hash, or None if file doesn't exist.
        """
        file_hash = self._compute_hash(file_path)
        if file_hash:
            stat = file_path.stat()
            self._hashes[str(file_path)] = FileHash(
                path=str(file_path),
                hash=file_hash,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                checked_at=datetime.now().isoformat(),
            )
            self._save_hashes()
            logger.info(f"Updated integrity hash for {file_path.name}: {file_hash[:16]}...")

        return file_hash

    def get_status(self) -> dict[str, Any]:
        """Get current integrity monitoring status."""
        return {
            "enabled": self.config.enabled,
            "monitored_files": len(self.get_monitored_files()),
            "tracked_files": len(self._hashes),
            "files": [
                {
                    "path": h.path,
                    "hash": h.hash[:16] + "...",
                    "size": h.size,
                    "last_checked": h.checked_at,
                }
                for h in self._hashes.values()
            ],
        }

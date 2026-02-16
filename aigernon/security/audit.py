"""Audit logging for tool invocations and security events."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from aigernon.utils.helpers import ensure_dir


class AuditLogger:
    """
    Audit logger for security-relevant events.

    Logs all tool invocations, access denials, and security events
    to a dedicated audit log file.
    """

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or ensure_dir(Path.home() / ".aigernon" / "audit")
        self._current_date: str | None = None
        self._log_file: Path | None = None

    def _get_log_file(self) -> Path:
        """Get the current log file (rotates daily)."""
        today = datetime.now().strftime("%Y-%m-%d")

        if self._current_date != today:
            self._current_date = today
            self._log_file = self.log_dir / f"audit-{today}.jsonl"

        return self._log_file  # type: ignore

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write an entry to the audit log."""
        log_file = self._get_log_file()

        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def log_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
        user_id: str | None = None,
        channel: str | None = None,
        session_key: str | None = None,
        result_preview: str | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """
        Log a tool invocation.

        Args:
            tool_name: Name of the tool called.
            params: Tool parameters (will be sanitized).
            user_id: User who triggered the call.
            channel: Channel the request came from.
            session_key: Session identifier.
            result_preview: First 200 chars of result (optional).
            success: Whether the call succeeded.
            error: Error message if failed.
        """
        # Sanitize params - redact potential secrets
        safe_params = self._sanitize_params(params)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "tool_call",
            "tool": tool_name,
            "params": safe_params,
            "user_id": user_id,
            "channel": channel,
            "session_key": session_key,
            "success": success,
            "error": error,
        }

        if result_preview:
            entry["result_preview"] = result_preview[:200]

        self._write_entry(entry)

    def log_access_denied(
        self,
        user_id: str,
        channel: str,
        reason: str,
    ) -> None:
        """Log an access denial event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "access_denied",
            "user_id": user_id,
            "channel": channel,
            "reason": reason,
        }
        self._write_entry(entry)
        logger.warning(f"AUDIT: Access denied for {user_id} on {channel}: {reason}")

    def log_rate_limited(
        self,
        user_id: str,
        channel: str,
        limit_type: str,
    ) -> None:
        """Log a rate limit event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "rate_limited",
            "user_id": user_id,
            "channel": channel,
            "limit_type": limit_type,
        }
        self._write_entry(entry)

    def log_security_event(
        self,
        event_type: str,
        details: dict[str, Any],
        severity: str = "warning",
    ) -> None:
        """
        Log a generic security event.

        Args:
            event_type: Type of security event (e.g., "integrity_violation", "suspicious_input").
            details: Event details.
            severity: Event severity (info, warning, error, critical).
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "security_event",
            "event_type": event_type,
            "severity": severity,
            "details": details,
        }
        self._write_entry(entry)

        log_method = getattr(logger, severity, logger.warning)
        log_method(f"AUDIT: Security event [{event_type}]: {details}")

    def log_integrity_alert(
        self,
        file_path: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        """Log a file integrity violation."""
        self.log_security_event(
            "integrity_violation",
            {
                "file": file_path,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            },
            severity="error",
        )

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Sanitize parameters to avoid logging secrets."""
        sensitive_keys = {
            "password", "secret", "token", "api_key", "apikey",
            "key", "credential", "auth", "authorization",
        }

        result = {}
        for key, value in params.items():
            key_lower = key.lower()

            # Check if key looks sensitive
            if any(s in key_lower for s in sensitive_keys):
                result[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 500:
                # Truncate long strings
                result[key] = value[:500] + "...[truncated]"
            elif isinstance(value, dict):
                result[key] = self._sanitize_params(value)
            else:
                result[key] = value

        return result

    def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent audit events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of recent audit events.
        """
        log_file = self._get_log_file()

        if not log_file.exists():
            return []

        events = []
        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []

        return events[-limit:]

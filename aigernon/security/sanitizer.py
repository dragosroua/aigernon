"""Input sanitization for tool arguments."""

import re
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class SanitizationResult:
    """Result of input sanitization."""

    safe: bool
    sanitized_value: Any
    warnings: list[str]
    blocked_reason: str | None = None


class InputSanitizer:
    """
    Input sanitizer for tool arguments.

    Validates and sanitizes inputs to prevent injection attacks
    and other malicious inputs.
    """

    # Patterns that indicate potential injection attempts
    DANGEROUS_PATTERNS = [
        # Shell injection
        (r"[;&|`$]", "shell_metachar"),
        (r"\$\([^)]+\)", "command_substitution"),
        (r"`[^`]+`", "backtick_execution"),

        # Path traversal
        (r"\.\./", "path_traversal"),
        (r"\.\.\\", "path_traversal_windows"),

        # Null bytes
        (r"\x00", "null_byte"),

        # ANSI escape sequences (potential terminal injection)
        (r"\x1b\[", "ansi_escape"),
    ]

    # Patterns specifically dangerous for exec/shell commands
    EXEC_DANGEROUS_PATTERNS = [
        (r"\brm\s+-[rf]{1,2}\s+/", "recursive_delete_root"),
        (r"\bsudo\b", "sudo_usage"),
        (r"\bchmod\s+777\b", "insecure_permissions"),
        (r"\bcurl\b.*\|\s*(ba)?sh", "curl_pipe_shell"),
        (r"\bwget\b.*\|\s*(ba)?sh", "wget_pipe_shell"),
        (r">\s*/dev/sd", "direct_disk_write"),
        (r"\bdd\s+if=.*of=/dev/", "dd_disk_write"),
        (r"\bmkfs\b", "filesystem_format"),
        (r":\(\)\s*\{.*\};\s*:", "fork_bomb"),
        (r"\b(shutdown|reboot|poweroff|halt)\b", "system_power"),
    ]

    # Maximum lengths for different input types
    MAX_LENGTHS = {
        "command": 10000,
        "path": 4096,
        "content": 1000000,  # 1MB
        "default": 50000,
    }

    def __init__(self, strict_mode: bool = False):
        """
        Initialize sanitizer.

        Args:
            strict_mode: If True, block on any warning. If False, only block on critical issues.
        """
        self.strict_mode = strict_mode

    def sanitize_string(
        self,
        value: str,
        input_type: str = "default",
        allow_shell_chars: bool = False,
    ) -> SanitizationResult:
        """
        Sanitize a string input.

        Args:
            value: The input string.
            input_type: Type of input (command, path, content, default).
            allow_shell_chars: Whether to allow shell metacharacters.

        Returns:
            SanitizationResult with safety assessment.
        """
        warnings = []
        blocked_reason = None

        # Check length
        max_len = self.MAX_LENGTHS.get(input_type, self.MAX_LENGTHS["default"])
        if len(value) > max_len:
            blocked_reason = f"Input exceeds maximum length ({len(value)} > {max_len})"
            return SanitizationResult(
                safe=False,
                sanitized_value=value[:max_len],
                warnings=[blocked_reason],
                blocked_reason=blocked_reason,
            )

        # Check for null bytes (always dangerous)
        if "\x00" in value:
            blocked_reason = "Input contains null bytes"
            return SanitizationResult(
                safe=False,
                sanitized_value=value.replace("\x00", ""),
                warnings=[blocked_reason],
                blocked_reason=blocked_reason,
            )

        # Check dangerous patterns
        patterns_to_check = self.DANGEROUS_PATTERNS.copy()
        if input_type == "command":
            patterns_to_check.extend(self.EXEC_DANGEROUS_PATTERNS)

        for pattern, name in patterns_to_check:
            # Skip shell metachar check if allowed
            if name == "shell_metachar" and allow_shell_chars:
                continue

            if re.search(pattern, value, re.IGNORECASE):
                warning = f"Detected potentially dangerous pattern: {name}"
                warnings.append(warning)

                # Some patterns are always blocking
                if name in ("fork_bomb", "null_byte", "recursive_delete_root", "dd_disk_write", "filesystem_format"):
                    blocked_reason = warning

        # In strict mode, any warning blocks
        if self.strict_mode and warnings:
            blocked_reason = warnings[0]

        return SanitizationResult(
            safe=blocked_reason is None,
            sanitized_value=value,
            warnings=warnings,
            blocked_reason=blocked_reason,
        )

    def sanitize_path(self, path: str) -> SanitizationResult:
        """Sanitize a file path input."""
        warnings = []
        blocked_reason = None

        # Check for path traversal
        if ".." in path:
            blocked_reason = "Path contains traversal sequence (..)"
            return SanitizationResult(
                safe=False,
                sanitized_value=path,
                warnings=[blocked_reason],
                blocked_reason=blocked_reason,
            )

        # Check for null bytes
        if "\x00" in path:
            blocked_reason = "Path contains null bytes"
            return SanitizationResult(
                safe=False,
                sanitized_value=path.replace("\x00", ""),
                warnings=[blocked_reason],
                blocked_reason=blocked_reason,
            )

        # Check for suspicious patterns
        suspicious_paths = ["/etc/passwd", "/etc/shadow", "/dev/", "~root"]
        for susp in suspicious_paths:
            if susp in path.lower():
                warnings.append(f"Path references sensitive location: {susp}")

        # Check length
        if len(path) > self.MAX_LENGTHS["path"]:
            blocked_reason = f"Path exceeds maximum length ({len(path)} > {self.MAX_LENGTHS['path']})"

        if self.strict_mode and warnings:
            blocked_reason = warnings[0]

        return SanitizationResult(
            safe=blocked_reason is None,
            sanitized_value=path,
            warnings=warnings,
            blocked_reason=blocked_reason,
        )

    def sanitize_tool_params(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> SanitizationResult:
        """
        Sanitize all parameters for a tool call.

        Args:
            tool_name: Name of the tool being called.
            params: Tool parameters.

        Returns:
            SanitizationResult for the overall parameter set.
        """
        all_warnings = []
        blocked_reason = None
        sanitized_params = {}

        for key, value in params.items():
            if isinstance(value, str):
                # Determine input type based on parameter name and tool
                if tool_name == "exec" and key == "command":
                    result = self.sanitize_string(value, "command", allow_shell_chars=True)
                elif key in ("path", "file_path", "working_dir", "directory"):
                    result = self.sanitize_path(value)
                elif key == "content":
                    result = self.sanitize_string(value, "content")
                else:
                    result = self.sanitize_string(value)

                sanitized_params[key] = result.sanitized_value
                all_warnings.extend(result.warnings)

                if result.blocked_reason and not blocked_reason:
                    blocked_reason = f"Parameter '{key}': {result.blocked_reason}"
            else:
                sanitized_params[key] = value

        # Log warnings
        if all_warnings:
            logger.warning(f"Sanitization warnings for {tool_name}: {all_warnings}")

        return SanitizationResult(
            safe=blocked_reason is None,
            sanitized_value=sanitized_params,
            warnings=all_warnings,
            blocked_reason=blocked_reason,
        )

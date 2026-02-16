"""Tool registry for dynamic tool management."""

from typing import Any

from loguru import logger

from aigernon.agent.tools.base import Tool
from aigernon.security.audit import AuditLogger
from aigernon.security.sanitizer import InputSanitizer


class ToolRegistry:
    """
    Registry for agent tools.

    Allows dynamic registration and execution of tools.
    Includes audit logging and input sanitization.
    """

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        sanitizer: InputSanitizer | None = None,
        enable_audit: bool = True,
        enable_sanitization: bool = True,
    ):
        self._tools: dict[str, Tool] = {}
        self._audit = audit_logger or (AuditLogger() if enable_audit else None)
        self._sanitizer = sanitizer or (InputSanitizer() if enable_sanitization else None)
        self._context: dict[str, str] = {}  # user_id, channel, session_key

    def set_context(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        session_key: str | None = None,
    ) -> None:
        """Set context for audit logging."""
        if user_id:
            self._context["user_id"] = user_id
        if channel:
            self._context["channel"] = channel
        if session_key:
            self._context["session_key"] = session_key
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.

        Includes input sanitization and audit logging.

        Args:
            name: Tool name.
            params: Tool parameters.

        Returns:
            Tool execution result as string.

        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(name)
        if not tool:
            self._log_tool_call(name, params, success=False, error="Tool not found")
            return f"Error: Tool '{name}' not found"

        # Input sanitization
        if self._sanitizer:
            sanitization_result = self._sanitizer.sanitize_tool_params(name, params)
            if not sanitization_result.safe:
                self._log_tool_call(
                    name, params,
                    success=False,
                    error=f"Input blocked: {sanitization_result.blocked_reason}"
                )
                return f"Error: Input blocked by security filter: {sanitization_result.blocked_reason}"
            # Use sanitized params
            params = sanitization_result.sanitized_value

        try:
            errors = tool.validate_params(params)
            if errors:
                error_msg = "; ".join(errors)
                self._log_tool_call(name, params, success=False, error=f"Validation: {error_msg}")
                return f"Error: Invalid parameters for tool '{name}': {error_msg}"

            result = await tool.execute(**params)

            # Log successful execution
            self._log_tool_call(name, params, success=True, result_preview=result)

            return result
        except Exception as e:
            error_msg = str(e)
            self._log_tool_call(name, params, success=False, error=error_msg)
            return f"Error executing {name}: {error_msg}"

    def _log_tool_call(
        self,
        name: str,
        params: dict[str, Any],
        success: bool,
        error: str | None = None,
        result_preview: str | None = None,
    ) -> None:
        """Log a tool call to the audit log."""
        if not self._audit:
            return

        self._audit.log_tool_call(
            tool_name=name,
            params=params,
            user_id=self._context.get("user_id"),
            channel=self._context.get("channel"),
            session_key=self._context.get("session_key"),
            result_preview=result_preview[:200] if result_preview else None,
            success=success,
            error=error,
        )
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools

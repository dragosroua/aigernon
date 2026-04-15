"""Spawn tool for creating background subagents."""

from typing import Any, TYPE_CHECKING

from aigernon.agent.tools.base import Tool

if TYPE_CHECKING:
    from aigernon.agent.subagent import SubagentManager


class SpawnTool(Tool):
    """
    Tool to spawn a subagent for background task execution.
    
    The subagent runs asynchronously and announces its result back
    to the main agent when complete.
    """
    
    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "spawn"
    
    @property
    def description(self) -> str:
        return (
            "Spawn a background subagent for tasks that require extensive file exploration, "
            "multi-step web research, or many iterations of work. "
            "Do NOT use this for conversational questions or simple lookups — answer those directly. "
            "After calling spawn, you MUST write a brief acknowledgment to the user in your response text "
            "(e.g. 'I'm on it — I'll report back shortly.'). Never spawn silently."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
            },
            "required": ["task"],
        }
    
    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        """Spawn a subagent to execute the given task."""
        status = await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
        )
        return (
            f"{status} "
            f"IMPORTANT: Write a brief acknowledgment to the user now in your response text — "
            f"one sentence saying you've started working on this and will report back. "
            f"Do not call any tool to deliver this, just write it directly."
        )

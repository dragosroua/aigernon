"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from pathlib import Path
from typing import Any

from aigernon.agent.memory import MemoryStore
from aigernon.agent.skills import SkillsLoader


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """
    
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md", "PROJECTS.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def build_system_prompt(self, skill_names: list[str] | None = None, instance_id: str | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.
            instance_id: Instance ID for scoping memory and bootstrap files.

        Returns:
            Complete system prompt.
        """
        parts = []

        # Core identity
        parts.append(self._get_identity(instance_id=instance_id))

        # Bootstrap files — instance-scoped with global fallback (Fix C)
        bootstrap = self._load_bootstrap_files(instance_id=instance_id)
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context — instance-scoped (Fix B)
        if instance_id:
            memory_store = MemoryStore(self.workspace / "instances" / instance_id)
        else:
            memory_store = self.memory
        memory = memory_store.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        # Projects summary
        projects_summary = self._get_projects_summary(instance_id=instance_id)
        if projects_summary:
            parts.append(f"# Active Projects\n\n{projects_summary}")

        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self, instance_id: str | None = None) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        if instance_id:
            instance_base = f"{workspace_path}/instances/{instance_id}"
            workspace_section = f"""## Workspace
Your workspace is at: {workspace_path}
- Memory files: {instance_base}/memory/MEMORY.md
- Daily notes: {instance_base}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md
- Projects: {instance_base}/projects/{{project-id}}/

Each project directory contains:
  - project.yaml   — name, realm (assess/decide/do), repo URL, current version
  - tasks/         — one YAML file per task (001.yaml, 002.yaml, …)
  - versions/      — one YAML file per version (1_0_0.yaml, …)

If the user asks about their projects and the Active Projects section is empty or missing,
use list_dir to check {instance_base}/projects/ directly.
NEVER browse {workspace_path}/instances/ or {workspace_path}/projects/ — your projects live only at the path shown above.

When remembering something, write to {instance_base}/memory/MEMORY.md"""
        else:
            workspace_section = f"""## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md
- Projects: {workspace_path}/projects/{{project-id}}/

When remembering something, write to {workspace_path}/memory/MEMORY.md"""

        return f"""# AIGernon

You are AIGernon, a cognitive companion operating on the Assess-Decide-Do (ADD) framework.
You don't automate thinking — you augment it.

## The ADD Framework

Human cognition flows through three realms:

**ASSESS** — Explore, evaluate, dream without commitment. Support with expansive thinking.
**DECIDE** — Prioritize, allocate resources, commit. Brief, values-based, honor the weight of choosing.
**DO** — Execute, complete, create livelines (not deadlines). Clear, actionable, celebrate completions.

### Your Approach

1. **Detect implicitly** — Recognize which realm the user occupies without announcing it
2. **Match your response** — Adapt to support their current cognitive mode
3. **Watch for imbalances** — Analysis paralysis (stuck Assess), decision avoidance (stuck Decide), perpetual doing (stuck Do)
4. **Honor the cascade** — Poor Assess leads to poor Decide leads to poor Do
5. **Track patterns** — Log realm flow in daily memory notes

### Response Styles

**In Assess:** Be expansive. Offer possibilities. Ask "what else?" not "what next?"
**In Decide:** Honor the weight. Support commitment. Keep it brief.
**In Do:** Be clear and actionable. Celebrate completions as new starting points.

## Current Time
{now}

## Runtime
{runtime}

{workspace_section}

## Tools

You have access to:
- Read, write, and edit files
- Execute shell commands
- Search the web and fetch web pages
- Send messages to users on chat channels
- Spawn subagents for complex background tasks

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp).
For normal conversation, just respond with text - do not call the message tool.

Be warm, helpful, and present. You're a companion, not a task bot."""
    
    def _load_bootstrap_files(self, instance_id: str | None = None) -> str:
        """Load bootstrap files — instance path first, global fallback. Skills stay global."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            content = None
            # Check instance-scoped path first (Fix C)
            if instance_id:
                instance_path = self.workspace / "instances" / instance_id / filename
                if instance_path.exists():
                    content = instance_path.read_text(encoding="utf-8")
            # Fall back to global workspace
            if content is None:
                global_path = self.workspace / filename
                if global_path.exists():
                    content = global_path.read_text(encoding="utf-8")
            if content:
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    def _get_projects_summary(self, instance_id: str | None = None) -> str:
        """Get summary of active projects for context injection.

        When instance_id is present (web/API mode): only the instance-scoped
        workspace is checked — never the global one, to prevent cross-user leakage.
        When instance_id is absent (CLI mode): falls back to the global workspace.
        """
        try:
            from aigernon.projects.store import ProjectStore
            if instance_id:
                ws = self.workspace / "instances" / instance_id
                return ProjectStore(ws).get_projects_summary()
            else:
                return ProjectStore(self.workspace).get_projects_summary()
        except Exception:
            return ""

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        instance_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names, instance_id=instance_id)
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text
        
        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        
        if not images:
            return text
        return images + [{"type": "text", "text": text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
            reasoning_content: Thinking output (Kimi, DeepSeek-R1, etc.).
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        # Thinking models reject history without this
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        
        messages.append(msg)
        return messages

"""Agent loop: the core processing engine."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

_MINIMAX_XML_RE = re.compile(
    r"<minimax:tool_call>.*?</minimax:tool_call>|<invoke\s+name=\"[^\"]+\">.*?</invoke>",
    re.DOTALL,
)


def _strip_minimax_xml(text: str) -> str:
    """Strip any leaked MiniMax XML tool call blocks from a string."""
    return _MINIMAX_XML_RE.sub("", text).strip()


def _tool_description(tool_name: str, args: dict) -> str:
    """Return a short human-readable description of a tool call."""
    if tool_name == "read_file":
        p = str(args.get("path", ""))
        return f"Reading {Path(p).name or p}\u2026"
    if tool_name == "write_file":
        p = str(args.get("path", ""))
        return f"Writing {Path(p).name or p}\u2026"
    if tool_name == "edit_file":
        p = str(args.get("path", ""))
        return f"Editing {Path(p).name or p}\u2026"
    if tool_name == "list_dir":
        p = str(args.get("path", ""))
        return f"Listing {Path(p).name or 'directory'}\u2026"
    if tool_name in ("bash", "exec"):
        cmd = str(args.get("command", ""))[:50]
        return f"Running: {cmd}\u2026"
    if tool_name == "git":
        action = str(args.get("action", ""))
        return f"Git: {action}\u2026"
    if tool_name == "web_search":
        q = str(args.get("query", ""))[:50]
        return f"Searching: {q}\u2026"
    if tool_name == "web_fetch":
        return "Fetching page\u2026"
    if tool_name == "spawn":
        label = str(args.get("label", args.get("task", "")))[:40]
        return f"Spawning: {label}\u2026"
    if tool_name == "cron":
        return "Setting reminder\u2026"
    return f"Using {tool_name}\u2026"

from loguru import logger

from aigernon.bus.events import InboundMessage, OutboundMessage
from aigernon.bus.queue import MessageBus
from aigernon.providers.base import LLMProvider
from aigernon.agent.context import ContextBuilder
from aigernon.agent.tools.registry import ToolRegistry
from aigernon.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from aigernon.agent.tools.shell import ExecTool
from aigernon.agent.tools.git import GitTool
from aigernon.agent.tools.web import WebSearchTool, WebFetchTool
from aigernon.agent.tools.message import MessageTool
from aigernon.agent.tools.spawn import SpawnTool
from aigernon.agent.tools.cron import CronTool
from aigernon.agent.subagent import SubagentManager
from aigernon.session.manager import SessionManager


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        web_mode: bool = False,
        token_resolver=None,
        result_callback=None,
        start_callback=None,
        progress_callback=None,
    ):
        from aigernon.config.schema import ExecToolConfig
        from aigernon.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.web_mode = web_mode
        self.token_resolver = token_resolver  # async (owner: str) -> token | None
        self.progress_callback = progress_callback  # async (chat_id, tool_name, description) -> None

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            web_mode=web_mode,
            result_callback=result_callback,
            start_callback=start_callback,
            token_resolver=token_resolver,
            progress_callback=progress_callback,
        )
        
        self._running = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools: web mode always restricts to workspace minimum for security;
        # CLI/daemon mode respects the restrict_to_workspace flag
        allowed_dir = self.workspace if (self.web_mode or self.restrict_to_workspace) else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))
        
        if self.web_mode:
            # Web/API mode: GitTool only — no arbitrary shell execution
            self.tools.register(GitTool(workspace=self.workspace, token_resolver=self.token_resolver))
        else:
            # CLI/daemon mode: full ExecTool + GitTool for convenience
            workspaces_dir = str(self.workspace.parent / "workspaces")
            self.tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                extra_allowed_dirs=[workspaces_dir] if self.restrict_to_workspace else [],
            ))
            self.tools.register(GitTool(workspace=self.workspace))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())

        # Message tool — only in CLI/daemon mode where outbound bus is consumed.
        # In web mode the bus is never read; registering it causes the model to
        # call message() for confirmations and then return content=None.
        if not self.web_mode:
            message_tool = MessageTool(send_callback=self.bus.publish_outbound)
            self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage, session_key: str | None = None, model: str | None = None) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.
            session_key: Explicit session key override (uses msg.session_key if not provided).

        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")

        # Compute instance-scoped allowed_dir for filesystem tools (Fix D)
        instance_id = getattr(msg, "instance_id", None)
        instance_allowed_dir = (
            self.workspace / "instances" / instance_id if instance_id else None
        )

        # Use explicit session_key if provided, otherwise derive from message
        effective_session_key = session_key or msg.session_key

        # Get or create session
        session = self.sessions.get_or_create(effective_session_key)

        # Set audit context for tool registry
        self.tools.set_context(
            user_id=msg.sender_id,
            channel=msg.channel,
            session_key=effective_session_key,
        )

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id, session_key=effective_session_key)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)

        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            instance_id=getattr(msg, "instance_id", None),
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        last_intermediate_content = None  # text seen alongside tool calls (fallback)

        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=model or self.model
            )

            # Handle tool calls
            if response.has_tool_calls:
                # Save any accompanying text as a potential fallback
                if response.content:
                    last_intermediate_content = response.content

                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                # Execute tools — inject instance-scoped allowed_dir (Fix D)
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")
                    if self.progress_callback and msg.channel == "web":
                        try:
                            desc = _tool_description(tool_call.name, tool_call.arguments)
                            await self.progress_callback(msg.chat_id, tool_call.name, desc)
                        except Exception:
                            pass
                    result = await self.tools.execute(
                        tool_call.name, tool_call.arguments, allowed_dir=instance_allowed_dir
                    )
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break

        if not final_content:
            # Use any text the model produced alongside tool calls as a fallback
            if last_intermediate_content:
                final_content = last_intermediate_content
                logger.warning(
                    f"Agent loop ended with empty final response after {iteration} iteration(s); "
                    f"using last intermediate content as fallback."
                )
            else:
                # The model gathered context via tools but produced no text.
                # Retry once with no tools so it is forced to write a response.
                logger.warning(
                    f"Agent loop ended with no content after {iteration} iteration(s); "
                    f"retrying without tools to force a text response."
                )
                try:
                    messages.append({
                        "role": "user",
                        "content": "[Please provide your response now.]",
                    })
                    retry = await self.provider.chat(
                        messages=messages,
                        tools=[],  # no tools — must produce text
                        model=model or self.model,
                    )
                    final_content = retry.content or ""
                except Exception as _retry_exc:
                    logger.error(f"Retry after empty response failed: {_retry_exc}")
                    final_content = ""

                if not final_content:
                    logger.error("Retry also produced empty content — giving up.")
                    final_content = "Sorry, I ran into an issue generating a response. Please try again."

        # Strip any MiniMax XML that leaked into the final response
        final_content = _strip_minimax_xml(final_content)

        # Log response preview
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info(f"Response to {msg.channel}:{msg.sender_id}: {preview}")

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        # Set audit context for tool registry
        self.tools.set_context(
            user_id=msg.sender_id,
            channel=origin_channel,
            session_key=session_key,
        )

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id, session_key=session_key)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")
                    result = await self.tools.execute(
                        tool_call.name, tool_call.arguments, allowed_dir=None
                    )
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break

        if not final_content:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        instance_id: str | None = None,
        model: str | None = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            instance_id=instance_id,
        )
        
        response = await self._process_message(msg, session_key=session_key, model=model)
        return response.content if response else ""

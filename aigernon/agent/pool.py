"""Per-user agent loop pool with per-user message queuing."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from aigernon.agent.loop import AgentLoop
from aigernon.session.manager import SessionManager


class AgentPool:
    """
    Manages one AgentLoop per user_id, each with a serializing message queue.

    Guarantees:
    - No cross-user tool context mutation (each user has isolated tools).
    - Messages from the same user are processed one at a time, regardless of channel
      (web chat and Telegram from the same user are serialized, not interleaved).
    """

    def __init__(
        self,
        provider,
        workspace: Path,
        bus,
        model: str | None = None,
        brave_api_key: str | None = None,
        exec_config=None,
        cron_service=None,
        restrict_to_workspace: bool = False,
        db=None,
        ws_manager=None,
    ):
        self._provider = provider
        self._workspace = workspace
        self._bus = bus
        self._model = model
        self._brave_api_key = brave_api_key
        self._exec_config = exec_config
        self._cron_service = cron_service
        self._restrict_to_workspace = restrict_to_workspace
        self._db = db  # Database instance for per-user token resolution
        self._ws_manager = ws_manager  # WebSocketManager for async subagent delivery

        self._loops: dict[str, AgentLoop] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._workers: dict[str, asyncio.Task] = {}

    def _make_token_resolver(self, user_id: str):
        """Build a per-user async callable: owner -> plaintext token | None."""
        db = self._db

        async def resolver(owner: str):
            if db is None:
                return None
            return await db.get_github_token_for_owner(user_id, owner)

        return resolver

    def _make_start_callback(self, user_id: str):
        """Build a callback that shows the typing indicator while a subagent is running."""
        async def on_subagent_start(
            origin_channel: str,
            origin_chat_id: str,
            label: str,
        ) -> None:
            ws = self._ws_manager
            if ws:
                try:
                    await ws.connections.send_to_user(origin_chat_id, {
                        "type": "typing",
                        "is_typing": True,
                    })
                except Exception as e:
                    logger.warning(f"Failed to send subagent typing indicator for {origin_chat_id}: {e}")

        return on_subagent_start

    def _make_result_callback(self, user_id: str):
        """Build a callback that delivers subagent results to the user's WebSocket."""
        async def on_subagent_result(
            origin_channel: str,
            origin_chat_id: str,
            label: str,
            result: str,
            status: str,
        ) -> None:
            status_text = "completed" if status == "ok" else "encountered an error"
            content = f"**{label}** {status_text}:\n\n{result}"
            ws = self._ws_manager
            if ws:
                try:
                    await ws.connections.send_to_user(origin_chat_id, {
                        "type": "typing",
                        "is_typing": False,
                    })
                    await ws.connections.send_to_user(origin_chat_id, {
                        "type": "chat_message",
                        "content": content,
                        "is_complete": True,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    logger.info(f"Delivered subagent result for '{label}' to user {origin_chat_id}")
                except Exception as e:
                    logger.error(f"Failed to push subagent result to WebSocket for {origin_chat_id}: {e}")
            else:
                logger.warning(f"No WebSocket manager — subagent result for '{label}' not delivered to {origin_chat_id}")

        return on_subagent_result

    def _get_or_create_loop(self, user_id: str) -> AgentLoop:
        if user_id not in self._loops:
            logger.info(f"Creating agent loop for user {user_id}")
            self._loops[user_id] = AgentLoop(
                bus=self._bus,
                provider=self._provider,
                workspace=self._workspace,
                model=self._model,
                brave_api_key=self._brave_api_key,
                exec_config=self._exec_config,
                cron_service=self._cron_service,
                restrict_to_workspace=self._restrict_to_workspace,
                web_mode=True,  # web/API users: GitTool only, no ExecTool
                token_resolver=self._make_token_resolver(user_id),
                result_callback=self._make_result_callback(user_id),
                start_callback=self._make_start_callback(user_id),
            )
        return self._loops[user_id]

    def _ensure_worker(self, user_id: str) -> None:
        if user_id not in self._queues:
            self._queues[user_id] = asyncio.Queue()
            self._workers[user_id] = asyncio.create_task(
                self._worker(user_id), name=f"agent-worker-{user_id}"
            )

    async def _worker(self, user_id: str) -> None:
        """Drain the queue for one user, one message at a time."""
        queue = self._queues[user_id]
        loop = self._get_or_create_loop(user_id)
        while True:
            try:
                content, kwargs, future = await queue.get()
                try:
                    result = await loop.process_direct(content, **kwargs)
                    if not future.done():
                        future.set_result(result)
                except Exception as exc:
                    if not future.done():
                        future.set_exception(exc)
                finally:
                    queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Agent worker error for user {user_id}: {exc}")

    async def process_direct(
        self,
        user_id: str,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        instance_id: str | None = None,
        model: str | None = None,
    ) -> str:
        """
        Enqueue a message for the given user and await the result.

        Messages from the same user are always processed serially.
        """
        self._ensure_worker(user_id)
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        kwargs: dict[str, Any] = {
            "session_key": session_key,
            "channel": channel,
            "chat_id": chat_id,
            "instance_id": instance_id,
            "model": model,
        }
        await self._queues[user_id].put((content, kwargs, future))
        return await future

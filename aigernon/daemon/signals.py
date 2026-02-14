"""Signal handling for graceful daemon shutdown."""

import asyncio
import signal
from typing import Callable, Coroutine, Any

from loguru import logger


class GracefulShutdown:
    """
    Manages graceful shutdown of the daemon.

    Registers signal handlers and coordinates shutdown sequence with timeout.
    """

    def __init__(self, timeout_s: int = 30):
        """
        Initialize shutdown handler.

        Args:
            timeout_s: Maximum seconds to wait for graceful shutdown.
        """
        self.timeout_s = timeout_s
        self._shutdown_event = asyncio.Event()
        self._shutdown_callbacks: list[Callable[[], Coroutine[Any, Any, None]]] = []
        self._sync_callbacks: list[Callable[[], None]] = []
        self._force_exit = False

    def register_callback(self, callback: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """
        Register an async callback to run during shutdown.

        Args:
            callback: Async function to call during shutdown.
        """
        self._shutdown_callbacks.append(callback)

    def register_sync_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a sync callback to run during shutdown.

        Args:
            callback: Sync function to call during shutdown.
        """
        self._sync_callbacks.append(callback)

    @property
    def should_shutdown(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()

    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown is requested."""
        await self._shutdown_event.wait()

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self._shutdown_event.set()

    def setup_handlers(self) -> None:
        """
        Register signal handlers for SIGTERM and SIGINT.

        This should be called before the event loop starts.
        """
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        logger.debug("Signal handlers registered (SIGTERM, SIGINT)")

    async def execute_shutdown(self) -> bool:
        """
        Execute the shutdown sequence.

        Returns:
            True if shutdown completed gracefully, False if timeout exceeded.
        """
        logger.info("Starting graceful shutdown sequence...")

        try:
            # Run all callbacks with timeout
            async def run_callbacks():
                for callback in self._shutdown_callbacks:
                    try:
                        await callback()
                    except Exception as e:
                        logger.error(f"Shutdown callback error: {e}")

            await asyncio.wait_for(run_callbacks(), timeout=self.timeout_s)

            # Run sync callbacks
            for callback in self._sync_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Sync shutdown callback error: {e}")

            logger.info("Graceful shutdown completed")
            return True

        except asyncio.TimeoutError:
            logger.warning(f"Shutdown timeout ({self.timeout_s}s) exceeded, forcing exit")
            self._force_exit = True
            return False

    @property
    def exit_code(self) -> int:
        """Get the appropriate exit code."""
        return 1 if self._force_exit else 0


def create_shutdown_handler(
    daemon_status,
    agent=None,
    channels=None,
    heartbeat=None,
    cron=None,
    timeout_s: int = 30,
) -> GracefulShutdown:
    """
    Create a configured shutdown handler for the gateway.

    Args:
        daemon_status: DaemonStatus instance for cleanup.
        agent: AgentLoop instance (optional).
        channels: ChannelManager instance (optional).
        heartbeat: HeartbeatService instance (optional).
        cron: CronService instance (optional).
        timeout_s: Shutdown timeout in seconds.

    Returns:
        Configured GracefulShutdown instance.
    """
    handler = GracefulShutdown(timeout_s=timeout_s)

    # Stop accepting new messages
    async def stop_services():
        logger.info("Stopping channels...")
        if channels:
            await channels.stop_all()

        logger.info("Stopping heartbeat...")
        if heartbeat:
            heartbeat.stop()

        logger.info("Stopping cron...")
        if cron:
            cron.stop()

        logger.info("Stopping agent...")
        if agent:
            agent.stop()

    handler.register_callback(stop_services)

    # Cleanup daemon files (sync)
    def cleanup_daemon():
        logger.info("Cleaning up daemon files...")
        daemon_status.stop_heartbeat_loop()
        daemon_status.cleanup()

    handler.register_sync_callback(cleanup_daemon)

    return handler

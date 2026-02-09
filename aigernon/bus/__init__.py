"""Message bus module for decoupled channel-agent communication."""

from aigernon.bus.events import InboundMessage, OutboundMessage
from aigernon.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]

"""Channel adapter interface — web (default), WhatsApp, Telegram."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Channel(ABC):
    name: str

    @abstractmethod
    async def send(self, session_id: str, content: str, attachments: list | None = None) -> None: ...

    @abstractmethod
    async def receive_loop(self) -> None: ...

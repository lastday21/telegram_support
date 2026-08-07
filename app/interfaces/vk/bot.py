from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Sequence
from typing import Any

import requests

from app.infra.remote_client import RemoteServiceClient
from app.infra.dns_fallback import install_dns_fallback
from app.prompts import PROMPTS
from app.settings import get_settings
from app.interfaces.telegram.bot import ANSWER_ERROR, BULB, HELP, THINKING
from app.interfaces.vk.sender import VkApiError, VkSender

logger = logging.getLogger(__name__)


class VkBotService:
    def __init__(
        self,
        sender: VkSender,
        solve_text_fn: Callable[[str], str],
        allowed_user_id: str,
        prompts: Sequence[str] = PROMPTS,
    ) -> None:
        self.sender = sender
        self.solve_text = solve_text_fn
        self.allowed_user_id = str(allowed_user_id)
        self.prompts = list(prompts)

    def handle_event(self, event: dict[str, Any]) -> None:
        if event.get("type") != "message_new":
            return
        body = event.get("object")
        if not isinstance(body, dict):
            return
        message = body.get("message")
        if not isinstance(message, dict):
            return
        if str(message.get("from_id", "")) != self.allowed_user_id:
            return
        if message.get("out"):
            return
        text = str(message.get("text", "")).strip()
        if not text:
            return
        self.handle_text(text)

    def handle_text(self, text: str) -> None:
        command, _, argument = text.partition(" ")
        command = command.lower().split("@", 1)[0]
        if command in {"/start", "/help"}:
            self.sender.send_message(HELP)
            return
        if command == "/prompts":
            prompt_list = "\n".join(
                f"{index}. {prompt.splitlines()[0][:60]}..."
                for index, prompt in enumerate(self.prompts, 1)
            )
            self.sender.send_message(prompt_list)
            return
        if command == "/p":
            normalized_argument = argument.strip()
            if not normalized_argument.isdigit():
                self.sender.send_message("Использование: /p <1-9>")
                return
            prompt_index = int(normalized_argument)
            if not 1 <= prompt_index <= len(self.prompts):
                self.sender.send_message("Использование: /p <1-9>")
                return
            self._answer(self.prompts[prompt_index - 1])
            return
        self._answer(text)

    def _answer(self, text: str) -> None:
        self.sender.send_message(THINKING)
        try:
            answer = self.solve_text(text)
        except Exception:
            logger.exception("Не удалось ответить на сообщение ВКонтакте")
            self.sender.send_message(ANSWER_ERROR)
            return
        self.sender.send_message(f"{BULB}{answer}")


class VkLongPoll:
    def __init__(
        self,
        sender: VkSender,
        group_id: str,
        service: VkBotService,
        http_get: Callable[..., Any] = requests.get,
        wait_seconds: int = 25,
    ) -> None:
        self.sender = sender
        self.group_id = group_id
        self.service = service
        self.http_get = http_get
        self.wait_seconds = wait_seconds
        self.server = ""
        self.key = ""
        self.ts = ""

    def refresh(self) -> None:
        payload = self.sender._call(
            "groups.getLongPollServer",
            group_id=self.group_id,
        )
        if not isinstance(payload, dict):
            raise VkApiError("ВКонтакте не вернул настройки получения сообщений")
        self.server = str(payload.get("server", ""))
        self.key = str(payload.get("key", ""))
        self.ts = str(payload.get("ts", ""))
        if not self.server or not self.key or not self.ts:
            raise VkApiError("Настройки получения сообщений ВКонтакте неполные")

    def poll_once(self) -> None:
        if not self.server:
            self.refresh()
        response = self.http_get(
            self.server,
            params={
                "act": "a_check",
                "key": self.key,
                "ts": self.ts,
                "wait": self.wait_seconds,
            },
            timeout=self.wait_seconds + 10,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise VkApiError("ВКонтакте вернул неожиданный ответ")
        failed = payload.get("failed")
        if failed == 1:
            self.ts = str(payload.get("ts", self.ts))
            return
        if failed:
            self.refresh()
            return
        self.ts = str(payload.get("ts", self.ts))
        updates = payload.get("updates", [])
        if not isinstance(updates, list):
            raise VkApiError("ВКонтакте вернул неверный список событий")
        for event in updates:
            if isinstance(event, dict):
                self.service.handle_event(event)

    def run_forever(self) -> None:
        retry_delay = 1
        while True:
            try:
                self.poll_once()
                retry_delay = 1
            except KeyboardInterrupt:
                return
            except Exception as exc:
                logger.warning(
                    "Связь с ВКонтакте временно недоступна: %s",
                    type(exc).__name__,
                )
                self.server = ""
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)


def main() -> None:
    install_dns_fallback()
    settings = get_settings()
    if not (settings.vk_group_token and settings.vk_group_id and settings.vk_user_id):
        raise RuntimeError("ВКонтакте не настроен")
    server_url = os.getenv("SMARTHELPER_SERVER_URL", "http://server:8000")
    remote_server = RemoteServiceClient(
        server_url=server_url,
        access_token=settings.app_access_token,
        model=settings.yc_model,
    )
    sender = VkSender(
        group_token=settings.vk_group_token,
        user_id=settings.vk_user_id,
        api_version=settings.vk_api_version,
    )
    service = VkBotService(
        sender=sender,
        solve_text_fn=remote_server.solve_text,
        allowed_user_id=settings.vk_user_id,
    )
    VkLongPoll(
        sender=sender,
        group_id=settings.vk_group_id,
        service=service,
    ).run_forever()


if __name__ == "__main__":
    main()

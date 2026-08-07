from __future__ import annotations

from typing import Any

from app.interfaces.vk.bot import VkBotService, VkLongPoll


class Sender:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, text: str) -> None:
        self.messages.append(text)


class LongPollSender(Sender):
    def _call(self, method: str, **_params: Any) -> dict[str, str]:
        assert method == "groups.getLongPollServer"
        return {"server": "https://lp.vk/test", "key": "KEY", "ts": "1"}


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


def test_vk_bot_responds_only_to_allowed_user():
    sender = Sender()
    service = VkBotService(
        sender=sender,  # type: ignore[arg-type]
        solve_text_fn=lambda text: f"готово: {text}",
        allowed_user_id="114676356",
    )

    service.handle_event(
        {
            "type": "message_new",
            "object": {
                "message": {"from_id": 999, "text": "чужое сообщение", "out": 0}
            },
        }
    )
    service.handle_event(
        {
            "type": "message_new",
            "object": {"message": {"from_id": 114676356, "text": "вопрос", "out": 0}},
        }
    )

    assert len(sender.messages) == 2
    assert sender.messages[-1].endswith("готово: вопрос")


def test_vk_long_poll_passes_message_event_to_service():
    sender = LongPollSender()
    service = VkBotService(
        sender=sender,  # type: ignore[arg-type]
        solve_text_fn=lambda text: text,
        allowed_user_id="114676356",
    )

    poll = VkLongPoll(
        sender=sender,  # type: ignore[arg-type]
        group_id="240722997",
        service=service,
        http_get=lambda *_args, **_kwargs: FakeResponse(
            {
                "ts": "2",
                "updates": [
                    {
                        "type": "message_new",
                        "object": {
                            "message": {
                                "from_id": 114676356,
                                "text": "/help",
                                "out": 0,
                            }
                        },
                    }
                ],
            }
        ),
    )

    poll.poll_once()

    assert poll.ts == "2"
    assert sender.messages

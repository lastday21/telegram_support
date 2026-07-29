import json
from pathlib import Path

from app.domain.request_journal import RequestJournal, request_journal_path


def test_request_journal_saves_complete_entry_outside_project(tmp_path):
    screenshot = tmp_path / "SmartHelper" / "screenshots" / "screen.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"PNG")
    journal = RequestJournal(base_dir=tmp_path)

    journal.record(
        command="f1",
        prompt="Реши задачу",
        model="qwen3.6-35b-a3b",
        duration_ms=1234,
        screenshot_path=screenshot,
        answer="Ответ: 4",
    )

    path = request_journal_path(tmp_path)
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry == {
        "id": entry["id"],
        "created_at": entry["created_at"],
        "status": "success",
        "command": "f1",
        "prompt": "Реши задачу",
        "model": "qwen3.6-35b-a3b",
        "duration_ms": 1234,
        "screenshot": str(Path("screenshots") / "screen.png"),
        "context_chars": 0,
        "answer": "Ответ: 4",
        "error_type": None,
        "error_message": None,
    }


def test_request_journal_saves_error_details(tmp_path):
    journal = RequestJournal(base_dir=tmp_path)

    journal.record(
        command="alt+1",
        prompt="Ответь",
        model="qwen3-235b-a22b-fp8/latest",
        duration_ms=250,
        error=RuntimeError("Сервер недоступен"),
        context_chars=1200,
    )

    entry = json.loads(journal.path.read_text(encoding="utf-8"))
    assert entry["status"] == "error"
    assert entry["error_type"] == "RuntimeError"
    assert entry["error_message"] == "Сервер недоступен"
    assert entry["context_chars"] == 1200
    assert entry["answer"] is None


def test_request_journal_keeps_only_latest_hundred_entries(tmp_path):
    journal = RequestJournal(base_dir=tmp_path)

    for index in range(101):
        journal.record(
            command=f"command-{index}",
            prompt="Подсказка",
            model="model",
            duration_ms=index,
            answer=str(index),
        )

    entries = [
        json.loads(line)
        for line in journal.path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(entries) == 100
    assert entries[0]["command"] == "command-1"
    assert entries[-1]["command"] == "command-100"

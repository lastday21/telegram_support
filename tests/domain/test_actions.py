import threading

from app.domain.actions import SerialActionQueue


def test_actions_are_processed_in_order():
    queue = SerialActionQueue()
    release = threading.Event()
    finished = threading.Event()
    calls = []

    def first():
        calls.append("first-start")
        release.wait(timeout=2)
        calls.append("first-end")

    def second():
        calls.append("second")
        finished.set()

    assert queue.submit(first) is True
    assert queue.submit(second) is True
    release.set()
    assert finished.wait(timeout=2) is True
    queue.close()

    assert calls == ["first-start", "first-end", "second"]


def test_full_queue_rejects_extra_action():
    queue = SerialActionQueue(max_pending=1)
    started = threading.Event()
    release = threading.Event()

    def blocking_action():
        started.set()
        release.wait(timeout=2)

    assert queue.submit(blocking_action) is True
    assert started.wait(timeout=2) is True
    assert queue.submit(lambda: None) is True
    assert queue.submit(lambda: None) is False
    release.set()
    queue.close()


def test_default_queue_accepts_seven_pending_screens():
    queue = SerialActionQueue()
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    processed = []

    def blocking_action():
        started.set()
        release.wait(timeout=2)

    def process(index):
        processed.append(index)
        if index == 7:
            finished.set()

    assert queue.submit(blocking_action) is True
    assert started.wait(timeout=2) is True
    assert all(queue.submit(process, (index,)) for index in range(1, 8))
    release.set()
    assert finished.wait(timeout=2) is True
    queue.close()

    assert processed == list(range(1, 8))

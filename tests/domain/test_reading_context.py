from app.domain.reading_context import ReadingContext


def test_context_collects_fragments_in_order():
    context = ReadingContext()

    first = context.add("Первая строка\nВторая строка")
    second = context.add("Третья строка")

    assert first.fragments == 1
    assert second.fragments == 2
    assert context.text == "Первая строка\nВторая строка\n\nТретья строка"


def test_context_removes_repeated_long_lines():
    context = ReadingContext()
    repeated = "Это достаточно длинная строка из соседнего снимка"

    context.add(f"{repeated}\nПервая новая строка")
    update = context.add(f"{repeated}\nВторая новая строка")

    assert context.text.count(repeated) == 1
    assert update.duplicate is False
    assert "Вторая новая строка" in context.text


def test_context_ignores_empty_and_exact_duplicate_fragments():
    context = ReadingContext()
    text = "Длинная строка, которая уже была добавлена в контекст"

    context.add(text)
    duplicate = context.add(text)
    empty = context.add(" \n ")

    assert duplicate.duplicate is True
    assert duplicate.fragments == 1
    assert empty.duplicate is True
    assert context.text == text


def test_context_keeps_only_the_newest_text_within_limit():
    context = ReadingContext(max_chars=30)

    context.add("Первая очень длинная строка")
    update = context.add("Вторая очень длинная строка")

    assert update.truncated is True
    assert len(context.text) <= 30
    assert "Вторая" in context.text


def test_context_truncates_one_oversized_line_instead_of_dropping_it():
    context = ReadingContext(max_chars=10)

    update = context.add("0123456789ABC")

    assert update.truncated is True
    assert context.text == "3456789ABC"


def test_context_keeps_seven_large_screen_fragments():
    context = ReadingContext()
    repeated_header = "Повторяющийся заголовок большого задания"

    for index in range(1, 8):
        fragment = f"Часть {index}: " + (f"содержимое{index} " * 900)
        context.add(f"{repeated_header}\n{fragment}")

    assert context.stats().fragments == 7
    assert context.text.count(repeated_header) == 1
    assert 70_000 < len(context.text) < 120_000
    for index in range(1, 8):
        assert f"Часть {index}:" in context.text


def test_context_can_be_cleared():
    context = ReadingContext()
    context.add("Содержимое большого текста")

    update = context.clear()

    assert context.text == ""
    assert update.total_chars == 0
    assert update.fragments == 0

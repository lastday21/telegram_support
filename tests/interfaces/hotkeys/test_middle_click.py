from app.interfaces.hotkeys.middle_click import MiddleClickHook


def test_middle_click_routes_modifier_actions():
    calls = []
    hook = MiddleClickHook(
        lambda: calls.append("answer"),
        lambda: calls.append("context"),
        lambda: calls.append("clear"),
    )

    hook._dispatch_click(control_pressed=False, alt_pressed=False)
    hook._dispatch_click(control_pressed=False, alt_pressed=True)
    hook._dispatch_click(control_pressed=True, alt_pressed=False)
    hook._dispatch_click(control_pressed=True, alt_pressed=True)

    assert calls == ["answer", "context", "clear", "clear"]

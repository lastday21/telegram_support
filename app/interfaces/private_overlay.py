from __future__ import annotations

import ctypes
import logging
import queue
import threading
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

from app.infra.windows_api import get_last_error, load_library

logger = logging.getLogger(__name__)

WDA_EXCLUDEFROMCAPTURE = 0x00000011
GA_ROOT = 2
WINDOW_WIDTH = 560
WINDOW_HEIGHT = 300
WINDOW_MARGIN = 24
DEFAULT_HIDE_SECONDS = 20


@dataclass
class _OverlayCommand:
    action: str
    text: str = ""
    done: threading.Event | None = None
    errors: list[Exception] = field(default_factory=list)


def _native_window_handle(window: tk.Tk) -> int:
    user32 = load_library("user32")
    user32.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    user32.GetAncestor.restype = ctypes.c_void_p
    handle = int(user32.GetAncestor(window.winfo_id(), GA_ROOT) or 0)
    return handle or int(window.winfo_id())


def protect_window_from_capture(window: tk.Tk) -> None:
    user32 = load_library("user32")
    user32.SetWindowDisplayAffinity.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    user32.SetWindowDisplayAffinity.restype = ctypes.c_int
    handle = _native_window_handle(window)
    if not user32.SetWindowDisplayAffinity(handle, WDA_EXCLUDEFROMCAPTURE):
        raise OSError(
            get_last_error(),
            "Windows не разрешила исключить окно ответа из захвата",
        )


class PrivateAnswerOverlay:
    def __init__(self, hide_seconds: int = DEFAULT_HIDE_SECONDS) -> None:
        self.hide_seconds = hide_seconds
        self._commands: queue.Queue[_OverlayCommand] = queue.Queue()
        self._ready = threading.Event()
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._start_error: Exception | None = None
        self._hide_after_id: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()
            self._start_error = None
            self._thread = threading.Thread(
                target=self._run,
                name="smarthelper-private-overlay",
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("Окно ответа не запустилось вовремя")
        if self._start_error is not None:
            raise RuntimeError("Не удалось запустить закрытое окно ответа") from (
                self._start_error
            )

    def show(self, text: str) -> None:
        self.start()
        self._commands.put(_OverlayCommand(action="show", text=text))

    def hide(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        command = _OverlayCommand(action="hide", done=threading.Event())
        self._commands.put(command)
        if command.done is None or not command.done.wait(timeout=2):
            raise RuntimeError("Окно ответа не успело скрыться перед снимком")
        if command.errors:
            raise RuntimeError("Не удалось скрыть окно ответа перед снимком") from (
                command.errors[0]
            )

    def close(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        command = _OverlayCommand(action="close", done=threading.Event())
        self._commands.put(command)
        if command.done is not None:
            command.done.wait(timeout=2)
        thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        root: tk.Tk | None = None
        try:
            root, answer_text = self._build_window()
            root.update_idletasks()
            protect_window_from_capture(root)
            logger.info("Окно ответа исключено из захвата экрана")
            root.after(25, self._process_commands, root, answer_text)
            self._ready.set()
            root.mainloop()
        except Exception as exc:
            self._start_error = exc
            logger.exception("Закрытое окно ответа аварийно завершено")
            self._ready.set()
        finally:
            if root is not None:
                try:
                    root.destroy()
                except tk.TclError:
                    pass

    def _build_window(self) -> tuple[tk.Tk, tk.Text]:
        root = tk.Tk()
        root.withdraw()
        root.title("Ответ SmartHelper")
        root.configure(background="#0f172a")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.96)

        screen_width = root.winfo_screenwidth()
        x = max(screen_width - WINDOW_WIDTH - WINDOW_MARGIN, 0)
        root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{WINDOW_MARGIN}")

        container = tk.Frame(
            root,
            background="#0f172a",
            highlightbackground="#60a5fa",
            highlightthickness=1,
        )
        container.pack(fill="both", expand=True)

        header = tk.Frame(container, background="#172554", height=42)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="ОТВЕТ SMARTHELPER",
            background="#172554",
            foreground="#bfdbfe",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=14)
        tk.Button(
            header,
            text="×",
            command=root.withdraw,
            background="#172554",
            activebackground="#1e3a8a",
            foreground="#ffffff",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 14),
            cursor="hand2",
            padx=12,
        ).pack(side="right", fill="y")

        body = tk.Frame(container, background="#0f172a", padx=14, pady=12)
        body.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        answer_text = tk.Text(
            body,
            wrap="word",
            state="disabled",
            background="#0f172a",
            foreground="#f8fafc",
            selectbackground="#1d4ed8",
            selectforeground="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI", 11),
            padx=2,
            pady=2,
            yscrollcommand=scrollbar.set,
        )
        answer_text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=answer_text.yview)
        root.bind("<Escape>", lambda _event: root.withdraw())
        return root, answer_text

    def _process_commands(self, root: tk.Tk, answer_text: tk.Text) -> None:
        should_continue = True
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                break
            try:
                if command.action == "show":
                    if self._hide_after_id is not None:
                        root.after_cancel(self._hide_after_id)
                    answer_text.configure(state="normal")
                    answer_text.delete("1.0", "end")
                    answer_text.insert("1.0", command.text)
                    answer_text.configure(state="disabled")
                    root.deiconify()
                    root.lift()
                    self._hide_after_id = root.after(
                        self.hide_seconds * 1000,
                        root.withdraw,
                    )
                    logger.info("Окно ответа показано")
                elif command.action == "hide":
                    if self._hide_after_id is not None:
                        root.after_cancel(self._hide_after_id)
                        self._hide_after_id = None
                    root.withdraw()
                    root.update_idletasks()
                    logger.info("Окно ответа скрыто перед снимком")
                elif command.action == "close":
                    should_continue = False
                    root.destroy()
            except Exception as exc:
                command.errors.append(exc)
                logger.exception("Не удалось выполнить действие окна ответа")
            finally:
                if command.done is not None:
                    command.done.set()
                self._commands.task_done()
            if not should_continue:
                return
        root.after(25, self._process_commands, root, answer_text)

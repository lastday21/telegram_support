from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import keyboard

from app.infra.process_control import (
    is_main_running,
    restart_main,
    start_main,
    stop_main,
)
from app.settings import (
    MODEL_OPTIONS,
    load_client_settings,
    save_client_connection_settings,
    save_client_preferences,
    validate_client_connection,
)

BACKGROUND = "#eef2f7"
CARD = "#ffffff"
NAVY = "#111827"
TEXT = "#172033"
MUTED = "#667085"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
BORDER = "#d9e1ec"
FIELD = "#f8fafc"


class SettingsWindow:
    def run(self) -> None:
        settings = load_client_settings(require_connection=False)
        root = tk.Tk()
        root.title("Настройки SmartHelper")
        root.configure(background=BACKGROUND)
        root.minsize(880, 720)
        self._center(root, width=980, height=850)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(
            "Modern.TEntry",
            fieldbackground=FIELD,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=7,
        )
        style.configure(
            "Modern.TCombobox",
            fieldbackground=FIELD,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=ACCENT,
            padding=7,
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", FIELD)],
            selectbackground=[("readonly", FIELD)],
            selectforeground=[("readonly", TEXT)],
        )
        style.configure(
            "Modern.TCheckbutton",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 9),
        )
        style.map(
            "Modern.TCheckbutton",
            background=[("active", CARD)],
            foreground=[("active", TEXT)],
        )

        header = tk.Frame(root, background=NAVY, height=92)
        header.pack(fill="x")
        header.pack_propagate(False)
        header_text = tk.Frame(header, background=NAVY)
        header_text.pack(fill="both", expand=True, padx=24, pady=15)
        tk.Label(
            header_text,
            text="SMARTHELPER  /  НАСТРОЙКИ",
            background=NAVY,
            foreground="#93c5fd",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header_text,
            text="Управление моделями и быстрыми командами",
            background=NAVY,
            foreground="#ffffff",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(3, 0))

        scroll_host = tk.Frame(root, background=BACKGROUND)
        scroll_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(
            scroll_host,
            background=BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        outer = tk.Frame(canvas, background=BACKGROUND, padx=20, pady=16)
        outer_window = canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(outer_window, width=event.width),
        )
        root.bind_all(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"),
        )

        labels = [label for label, _model in MODEL_OPTIONS]
        models_by_label = dict(MODEL_OPTIONS)
        labels_by_model = {model: label for label, model in MODEL_OPTIONS}
        model_value = tk.StringVar(
            value=labels_by_model.get(settings.yc_model, labels[0])
        )
        server_url_value = tk.StringVar(value=settings.server_url)
        access_token_value = tk.StringVar(value=settings.app_access_token)
        tg_chat_id_value = tk.StringVar(value=settings.tg_chat_id or "")
        record_value = tk.StringVar(value=settings.record_hotkey)
        show_answer_overlay_value = tk.BooleanVar(value=settings.show_answer_overlay)

        main_card = self._card(outer)
        main_card.pack(fill="x")
        main_card.columnconfigure(1, weight=1)
        self._card_title(main_card, "01", "Основные настройки").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        self._field_label(main_card, "Адрес сервера").grid(
            row=1, column=0, sticky="w", padx=(0, 14), pady=5
        )
        ttk.Entry(
            main_card,
            textvariable=server_url_value,
            style="Modern.TEntry",
        ).grid(row=1, column=1, sticky="ew", pady=5)
        self._field_label(main_card, "Ключ доступа").grid(
            row=2, column=0, sticky="w", padx=(0, 14), pady=5
        )
        ttk.Entry(
            main_card,
            textvariable=access_token_value,
            show="•",
            style="Modern.TEntry",
        ).grid(row=2, column=1, sticky="ew", pady=5)
        self._field_label(main_card, "Идентификатор чата Telegram").grid(
            row=3, column=0, sticky="w", padx=(0, 14), pady=5
        )
        ttk.Entry(
            main_card,
            textvariable=tg_chat_id_value,
            style="Modern.TEntry",
        ).grid(row=3, column=1, sticky="ew", pady=5)
        self._field_label(main_card, "Модель ответа").grid(
            row=4, column=0, sticky="w", padx=(0, 14), pady=5
        )
        ttk.Combobox(
            main_card,
            textvariable=model_value,
            values=labels,
            state="readonly",
            style="Modern.TCombobox",
        ).grid(row=4, column=1, sticky="ew", pady=5)
        self._field_label(main_card, "Запуск микрофона").grid(
            row=5, column=0, sticky="w", padx=(0, 14), pady=5
        )
        microphone_row = tk.Frame(main_card, background=CARD)
        microphone_row.grid(row=5, column=1, sticky="ew", pady=5)
        microphone_row.columnconfigure(0, weight=1)
        ttk.Entry(
            microphone_row,
            textvariable=record_value,
            style="Modern.TEntry",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            microphone_row,
            text=f"СЕЙЧАС: {settings.record_hotkey.upper()}",
            background="#dbeafe",
            foreground="#1d4ed8",
            font=("Segoe UI", 8, "bold"),
            padx=9,
            pady=5,
        ).grid(row=0, column=1, padx=(10, 0))
        self._field_label(main_card, "Окно ответа").grid(
            row=6, column=0, sticky="w", padx=(0, 14), pady=5
        )
        ttk.Checkbutton(
            main_card,
            text="Показывать ответ поверх рабочего стола",
            variable=show_answer_overlay_value,
            style="Modern.TCheckbutton",
        ).grid(row=6, column=1, sticky="w", pady=5)

        mouse_card = self._card(outer)
        mouse_card.pack(fill="x", pady=(12, 0))
        mouse_title = self._card_title(mouse_card, "02", "Нажатие колёсика мыши")
        mouse_title.pack(fill="x", pady=(0, 7))
        tk.Label(
            mouse_title,
            text="ФИКСИРОВАНО",
            background="#dcfce7",
            foreground="#15803d",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=3,
        ).pack(side="right")
        tk.Label(
            mouse_card,
            text="Кнопка не меняется — редактируется только подсказка.",
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 7))
        mouse_prompt = self._prompt_field(mouse_card, height=3)
        mouse_prompt.pack(fill="x")
        mouse_prompt.insert("1.0", settings.mouse_prompt)

        actions_card = self._card(outer)
        actions_card.pack(fill="both", expand=True, pady=(12, 0))
        self._card_title(actions_card, "03", "Пять дополнительных команд").grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8)
        )
        actions_card.columnconfigure(2, weight=1)
        self._column_label(actions_card, "№").grid(row=1, column=0, padx=(0, 8))
        self._column_label(actions_card, "СОЧЕТАНИЕ").grid(
            row=1, column=1, sticky="w", padx=(0, 10)
        )
        self._column_label(actions_card, "ПОДСКАЗКА").grid(row=1, column=2, sticky="w")

        hotkey_values: list[tk.StringVar] = []
        prompt_fields: list[tk.Text] = []
        for index, (hotkey, prompt) in enumerate(
            zip(settings.action_hotkeys, settings.action_prompts, strict=True),
            start=1,
        ):
            tk.Label(
                actions_card,
                text=str(index),
                background=ACCENT,
                foreground="#ffffff",
                font=("Segoe UI", 9, "bold"),
                width=2,
                pady=4,
            ).grid(row=index + 1, column=0, padx=(0, 8), pady=4)
            hotkey_value = tk.StringVar(value=hotkey)
            hotkey_values.append(hotkey_value)
            ttk.Entry(
                actions_card,
                textvariable=hotkey_value,
                width=17,
                style="Modern.TEntry",
            ).grid(
                row=index + 1,
                column=1,
                sticky="new",
                padx=(0, 10),
                pady=4,
            )
            prompt_field = self._prompt_field(actions_card, height=2)
            prompt_field.grid(
                row=index + 1,
                column=2,
                sticky="nsew",
                pady=4,
            )
            prompt_field.insert("1.0", prompt)
            prompt_fields.append(prompt_field)
            actions_card.rowconfigure(index + 1, weight=1)

        control_card = self._card(outer)
        control_card.pack(fill="x", pady=(12, 0))
        self._card_title(control_card, "04", "Управление SmartHelper").pack(
            fill="x", pady=(0, 10)
        )
        control_row = tk.Frame(control_card, background=CARD)
        control_row.pack(fill="x")
        process_status = tk.StringVar()

        def refresh_process_status() -> None:
            process_status.set(
                "СОСТОЯНИЕ: ЗАПУЩЕН" if is_main_running() else "СОСТОЯНИЕ: ОСТАНОВЛЕН"
            )

        def start_program() -> None:
            try:
                started = start_main()
            except Exception as exc:
                messagebox.showerror("Не удалось запустить", str(exc), parent=root)
            else:
                message = (
                    "SmartHelper запущен" if started else "SmartHelper уже запущен"
                )
                messagebox.showinfo("SmartHelper", message, parent=root)
            refresh_process_status()

        def stop_program() -> None:
            try:
                stopped = stop_main()
            except Exception as exc:
                messagebox.showerror("Не удалось остановить", str(exc), parent=root)
            else:
                message = (
                    "SmartHelper остановлен"
                    if stopped
                    else "SmartHelper уже остановлен"
                )
                messagebox.showinfo("SmartHelper", message, parent=root)
            refresh_process_status()

        def restart_program() -> None:
            try:
                restart_main()
            except Exception as exc:
                messagebox.showerror("Не удалось перезапустить", str(exc), parent=root)
            else:
                messagebox.showinfo(
                    "SmartHelper", "SmartHelper перезапущен", parent=root
                )
            refresh_process_status()

        tk.Label(
            control_row,
            textvariable=process_status,
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        for title, command in (
            ("Запустить", start_program),
            ("Остановить", stop_program),
            ("Перезапустить", restart_program),
        ):
            tk.Button(
                control_row,
                text=title,
                command=command,
                background=FIELD,
                activebackground="#e2e8f0",
                foreground=TEXT,
                relief="flat",
                borderwidth=1,
                cursor="hand2",
                padx=12,
                pady=6,
            ).pack(side="right", padx=(8, 0))
        refresh_process_status()

        footer = tk.Frame(outer, background=BACKGROUND)
        footer.pack(fill="x", pady=(14, 0))
        tk.Label(
            footer,
            text="Формат клавиш: ctrl+1  •  alt+q  •  ctrl+shift+a",
            background=BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left")

        def save() -> None:
            record_hotkey = record_value.get().strip().lower()
            action_hotkeys = [value.get().strip().lower() for value in hotkey_values]
            try:
                validate_client_connection(
                    server_url_value.get(), access_token_value.get()
                )
                for hotkey in (record_hotkey, *action_hotkeys):
                    keyboard.parse_hotkey(hotkey)
                actions = [
                    (hotkey, field.get("1.0", "end-1c"))
                    for hotkey, field in zip(action_hotkeys, prompt_fields, strict=True)
                ]
                save_client_preferences(
                    yc_model=models_by_label[model_value.get()],
                    record_hotkey=record_hotkey,
                    mouse_prompt=mouse_prompt.get("1.0", "end-1c"),
                    actions=actions,
                    show_answer_overlay=show_answer_overlay_value.get(),
                )
                save_client_connection_settings(
                    server_url=server_url_value.get(),
                    access_token=access_token_value.get(),
                    tg_chat_id=tg_chat_id_value.get(),
                    mic_device=settings.mic_device,
                    mix_device=settings.mix_device,
                )
            except Exception as exc:
                messagebox.showerror("Не удалось сохранить", str(exc), parent=root)
                return
            messagebox.showinfo(
                "Настройки сохранены",
                "Настройки сохранены. Для их применения перезапустите SmartHelper.",
                parent=root,
            )

        save_button = tk.Button(
            footer,
            text="Сохранить настройки",
            command=save,
            background=ACCENT,
            activebackground=ACCENT_HOVER,
            foreground="#ffffff",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=18,
            pady=8,
        )
        save_button.pack(side="right")
        root.mainloop()

    @staticmethod
    def _center(root: tk.Tk, width: int, height: int) -> None:
        x = max((root.winfo_screenwidth() - width) // 2, 0)
        y = max((root.winfo_screenheight() - height) // 2, 0)
        root.geometry(f"{width}x{height}+{x}+{y}")

    @staticmethod
    def _card(parent: tk.Misc) -> tk.Frame:
        return tk.Frame(
            parent,
            background=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=14,
            pady=11,
        )

    @staticmethod
    def _card_title(parent: tk.Misc, number: str, title: str) -> tk.Frame:
        frame = tk.Frame(parent, background=CARD)
        tk.Label(
            frame,
            text=number,
            background="#eff6ff",
            foreground=ACCENT,
            font=("Segoe UI", 8, "bold"),
            padx=7,
            pady=3,
        ).pack(side="left")
        tk.Label(
            frame,
            text=title,
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=(8, 0))
        return frame

    @staticmethod
    def _field_label(parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 9),
        )

    @staticmethod
    def _column_label(parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 8, "bold"),
        )

    @staticmethod
    def _prompt_field(parent: tk.Misc, height: int) -> tk.Text:
        return tk.Text(
            parent,
            height=height,
            wrap="word",
            undo=True,
            font=("Segoe UI", 9),
            background=FIELD,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=8,
            pady=5,
        )

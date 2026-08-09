"""Engineering console — a presentation-only command surface over the app.

A compact terminal that turns typed commands into the *same public actions the
toolbar and menus already expose*. ``help / open / run / stop / reload / mock /
clear`` map to MainWindow methods via signals; the console itself holds no
business logic and can never touch the engine, the workbook, or the
filesystem. There is deliberately no ``eval``/``exec``/subprocess — an unknown
command just prints a clean message.

v2.2 Workspace Revolution: styled as an engineering terminal using the
``CONSOLE_*`` theme tokens — monospace output on a deep surface, an accent
prompt, up/down history, command completion, auto-scroll, and a compact
toolbar.

Public API: ``append(text, level)``, ``clear()``, ``.text`` (the output
QPlainTextEdit), ``.input`` (the QLineEdit), ``.commands`` (the name→handler
map), plus the action signals MainWindow wires to existing methods.
"""

from __future__ import annotations

import html
import logging

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (QCompleter, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout,
                               QWidget)

from gui import theme

_PROMPT = "slipstream ›"

# Semantic output colours — the console's own compact terminal palette.
_COLORS = {logging.DEBUG: "#7f8695", logging.INFO: "#4fb3d9",   # blue info
           logging.WARNING: "#e8a33d", logging.ERROR: "#e5534b",
           logging.CRITICAL: "#ff6b63"}
_OK = "#3fbf7f"   # success green


class ConsolePanel(QWidget):
    # Action signals — MainWindow connects these to its existing public
    # methods (_open_dialog, start_run, _stop, _reload, _on_mock_toggled).
    openRequested = Signal()
    runRequested = Signal()
    stopRequested = Signal()
    reloadRequested = Signal()
    mockSet = Signal(bool)              # mock on / mock off
    mockToggleRequested = Signal()      # bare "mock" flips the current state

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_index = 0

        # -- output ------------------------------------------------------- #
        self.text = QPlainTextEdit(readOnly=True)
        self.text.setMaximumBlockCount(4000)      # bounded scrollback
        self.text.setProperty("console", True)

        # -- compact toolbar --------------------------------------------- #
        brand = QLabel("CONSOLE")
        brand.setProperty("caption", True)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
        bar = QHBoxLayout()
        bar.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM,
                               theme.SPACE_SM, 0)
        bar.setSpacing(theme.SPACE_SM)
        bar.addWidget(brand)
        bar.addStretch(1)
        bar.addWidget(clear_btn)

        # -- prompt + input ---------------------------------------------- #
        prompt = QLabel(_PROMPT)
        prompt.setStyleSheet(
            f"color: {theme.CONSOLE_PROMPT}; font-family: {theme.FONT_MONO}; "
            f"font-weight: 700; padding: 0 {theme.SPACE_SM}px;")
        self.input = QLineEdit()
        self.input.setProperty("consoleInput", True)
        self.input.setPlaceholderText("type a command — help for the list")
        self.input.returnPressed.connect(self._run_command)
        self.input.installEventFilter(self)
        cmpl = QCompleter(sorted(self.commands), self.input)
        cmpl.setCaseSensitivity(Qt.CaseInsensitive)
        self.input.setCompleter(cmpl)

        in_row = QHBoxLayout()
        in_row.setContentsMargins(0, 0, 0, 0)
        in_row.setSpacing(0)
        in_row.addWidget(prompt)
        in_row.addWidget(self.input, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addLayout(bar)
        lay.addWidget(self.text, 1)
        lay.addLayout(in_row)

    # -- command map (public) -------------------------------------------- #
    @property
    def commands(self) -> dict:
        return {
            "help": self._cmd_help,
            "open": self._cmd_open,
            "run": self._cmd_run,
            "stop": self._cmd_stop,
            "reload": self._cmd_reload,
            "mock": self._cmd_mock,
            "clear": self._cmd_clear,
        }

    # ------------------------------------------------------------------ #
    def append(self, text: str, level: int = logging.INFO) -> None:
        """Append one line of output to the console (public, used by the
        shell to surface run started / idle lines)."""
        color = _COLORS.get(level, _COLORS[logging.INFO])
        self._line(text, color)

    def clear(self) -> None:
        self.text.clear()

    # ------------------------------------------------------------------ #
    def _line(self, text: str, color: str) -> None:
        self.text.appendHtml(f'<span style="color:{color}">{html.escape(text)}</span>')
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _echo(self, raw: str) -> None:
        self._line(
            f'{_PROMPT} <span style="color:{theme.CONSOLE_TEXT}">'
            f'{html.escape(raw)}</span>', theme.CONSOLE_PROMPT)

    def _run_command(self) -> None:
        raw = self.input.text().strip()
        if not raw:                       # empty input → do nothing
            return
        self._echo(raw)
        parts = raw.split(maxsplit=1)
        name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        handler = self.commands.get(name)
        if handler is None:
            self._line(f"Unknown command: {name}", _COLORS[logging.WARNING])
            self._line('Type "help" for available commands.',
                       _COLORS[logging.INFO])
        else:
            try:
                handler(args)
            except Exception as exc:      # pragma: no cover — defensive
                self._line(f"error: {exc}", _COLORS[logging.ERROR])
        self._history.append(raw)
        self._hist_index = len(self._history)
        self.input.clear()

    # -- history (Up/Down) ----------------------------------------------- #
    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Up, Qt.Key_Down):
                self._history_move(event.key())
                return True
        return super().eventFilter(obj, event)

    def _history_move(self, key: Qt.Key) -> None:
        if not self._history:
            return
        if key == Qt.Key_Up:
            if self._hist_index > 0:
                self._hist_index -= 1
                self.input.setText(self._history[self._hist_index])
        else:                                             # Down
            if self._hist_index < len(self._history) - 1:
                self._hist_index += 1
                self.input.setText(self._history[self._hist_index])
            else:
                self._hist_index = len(self._history)
                self.input.clear()
        self.input.setCursorPosition(len(self.input.text()))

    # -- command handlers (GUI layer only) -------------------------------- #
    def _cmd_help(self, _args: str) -> None:
        self._line("Available commands:", _OK)
        for name, desc in (
                ("help", "show this help"),
                ("open", "open a project (Open Project…)"),
                ("run", "run all pending cases (Run All)"),
                ("stop", "stop after the current case"),
                ("reload", "reload the current project"),
                ("mock", "mock on | mock off | mock  (toggle no-ANSYS mode)"),
                ("clear", "clear the console output")):
            self._line(f"  {name:<10} {desc}", _COLORS[logging.INFO])

    def _cmd_open(self, _args: str) -> None:
        self.openRequested.emit()
        self._line("Opening project…", _OK)

    def _cmd_run(self, _args: str) -> None:
        self.runRequested.emit()
        self._line("Run All requested.", _OK)

    def _cmd_stop(self, _args: str) -> None:
        self.stopRequested.emit()
        self._line("Stop requested.", _OK)

    def _cmd_reload(self, _args: str) -> None:
        self.reloadRequested.emit()
        self._line("Reloading project…", _OK)

    def _cmd_mock(self, args: str) -> None:
        arg = args.strip().lower()
        if arg == "on":
            self.mockSet.emit(True)
            self._line("Mock mode on.", _OK)
        elif arg == "off":
            self.mockSet.emit(False)
            self._line("Mock mode off.", _OK)
        elif arg == "":
            self.mockToggleRequested.emit()
            self._line("Mock mode toggled.", _OK)
        else:
            self._line("Usage: mock [on|off]  (bare 'mock' toggles).",
                       _COLORS[logging.WARNING])

    def _cmd_clear(self, _args: str) -> None:
        self.clear()

from __future__ import annotations

import getpass
import os
import re
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from typing import Iterable, Iterator

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

RESET = "\033[0m" if _USE_COLOR else ""
BOLD = "\033[1m" if _USE_COLOR else ""
DIM = "\033[2m" if _USE_COLOR else ""
PRIMARY = "\033[38;5;39m" if _USE_COLOR else ""
PRIMARY_SOFT = "\033[38;5;45m" if _USE_COLOR else ""
WHITE = "\033[97m" if _USE_COLOR else ""
GREEN = "\033[38;5;82m" if _USE_COLOR else ""
YELLOW = "\033[38;5;220m" if _USE_COLOR else ""
RED = "\033[38;5;203m" if _USE_COLOR else ""

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}" if code else text


def bold(text: str) -> str:
    return color(text, BOLD)


def dim(text: str) -> str:
    return color(text, DIM)


def primary(text: str) -> str:
    return color(text, PRIMARY)


def cyan(text: str) -> str:  # Backward-compatible alias.
    return primary(text)


def green(text: str) -> str:
    return color(text, GREEN)


def yellow(text: str) -> str:
    return color(text, YELLOW)


def red(text: str) -> str:
    return color(text, RED)


def white(text: str) -> str:
    return color(text, WHITE)


def _plain(value: str) -> str:
    return _ANSI_RE.sub("", value)


def clear() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="", flush=True)


def terminal_width() -> int:
    return max(56, min(96, shutil.get_terminal_size((80, 24)).columns))


def ok(text: str) -> None:
    print(f"{green('●')} {text}")


def warn(text: str) -> None:
    print(f"{yellow('●')} {text}")


def error(text: str) -> None:
    print(f"{red('●')} {text}")


def info(text: str) -> None:
    print(f"{primary('›')} {text}")


def heading(text: str) -> None:
    width = min(terminal_width() - 2, max(24, len(_plain(text)) + 4))
    print(f"\n{primary('─' * width)}")
    print(f"{primary('◆')} {bold(text)}")


def header(title: str, subtitle: str = "", badge: str | None = None) -> None:
    width = terminal_width() - 2
    inner = width - 2
    print(primary("╭" + "─" * inner + "╮"))
    title_text = f"  {title}"
    if badge:
        badge_text = f"  {badge}  "
        spaces = max(1, inner - len(_plain(title_text)) - len(_plain(badge_text)))
        line = title_text + " " * spaces + badge_text
    else:
        line = title_text
    print(primary("│") + f"{bold(line)}" + " " * max(0, inner - len(_plain(line))) + primary("│"))
    if subtitle:
        sub = f"  {subtitle}"
        print(primary("│") + dim(sub) + " " * max(0, inner - len(_plain(sub))) + primary("│"))
    print(primary("╰" + "─" * inner + "╯"))


def notice(text: str, level: str = "info") -> None:
    marker = {"warning": yellow("!"), "error": red("×"), "success": green("✓")}.get(level, primary("i"))
    width = terminal_width() - 6
    print()
    print(f"  {marker} {text[:width]}")
    print()


def card(title: str, lines: list[str], width: int | None = None) -> None:
    width = width or terminal_width() - 2
    inner = width - 2
    print(primary("╭" + "─" * inner + "╮"))
    title_line = f"  {title}"
    print(primary("│") + bold(title_line) + " " * max(0, inner - len(_plain(title_line))) + primary("│"))
    print(primary("├" + "─" * inner + "┤"))
    for line in lines:
        rendered = f"  {line}"
        print(primary("│") + rendered + " " * max(0, inner - len(_plain(rendered))) + primary("│"))
    print(primary("╰" + "─" * inner + "╯"))


def prompt(text: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        try:
            label = f"{primary('›')} {text}{suffix}: "
            if secret:
                value = getpass.getpass(label)
            else:
                value = input(label)
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(130)
        value = value.strip()
        if value:
            return value
        if default is not None:
            return default


def confirm(text: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    yes = {"y", "yes", "д", "да"}
    no = {"n", "no", "н", "нет"}
    while True:
        try:
            value = input(f"{primary('›')} {text}{suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(130)
        if not value:
            return default
        if value in yes:
            return True
        if value in no:
            return False
        print(dim("  Y / N"))


def choose(text: str, choices: Iterable[str], default: str | None = None) -> str:
    allowed = set(choices)
    while True:
        value = prompt(text, default=default)
        if value in allowed:
            return value
        print(dim(f"  {', '.join(sorted(allowed))}"))


def prompt_int(text: str, default: int) -> int:
    while True:
        raw = prompt(text, str(default))
        try:
            value = int(raw)
            if 1 <= value <= 65535:
                return value
        except ValueError:
            pass
        print(dim("  1-65535"))


def menu(items: list[str]) -> None:
    width = terminal_width() - 2
    inner = width - 2
    print(primary("╭" + "─" * inner + "╮"))
    for index, item in enumerate(items, 1):
        number = primary(f"{index:>2}")
        line = f"  {number}  {item}"
        print(primary("│") + line + " " * max(0, inner - len(_plain(line))) + primary("│"))
    print(primary("╰" + "─" * inner + "╯"))


def pause(text: str) -> None:
    try:
        input(f"\n{dim(text)}")
    except (EOFError, KeyboardInterrupt):
        print()


def table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        return
    widths = [len(_plain(h)) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(_plain(str(value))))
    widths = [min(w, 42) for w in widths]

    def border(left: str, middle: str, right: str) -> str:
        return primary(left + middle.join("─" * (w + 2) for w in widths) + right)

    def fmt(row: list[str]) -> str:
        cells = []
        for i, value in enumerate(row):
            raw = str(value)
            visible = _plain(raw)
            if len(visible) > widths[i]:
                visible = visible[: max(0, widths[i] - 1)] + "…"
                raw = visible
            pad = max(0, widths[i] - len(_plain(raw)))
            cells.append(" " + raw + " " * pad + " ")
        return primary("│") + primary("│").join(cells) + primary("│")

    print(border("╭", "┬", "╮"))
    print(fmt([bold(h) for h in headers]))
    print(border("├", "┼", "┤"))
    for row in rows:
        print(fmt(row))
    print(border("╰", "┴", "╯"))


class Spinner:
    frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, text: str):
        self.text = text
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False

    def _run(self) -> None:
        index = 0
        while not self._stop.is_set():
            frame = self.frames[index % len(self.frames)]
            print(f"\r\033[2K{primary(frame)} {self.text}", end="", flush=True)
            index += 1
            self._stop.wait(0.08)

    def start(self) -> "Spinner":
        if self._active:
            return self
        self._active = True
        if sys.stdout.isatty():
            print("\033[?25l", end="", flush=True)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            print(f"{primary('›')} {self.text}")
        return self

    def update(self, text: str) -> None:
        self.text = text

    def stop(self, ok_state: bool | None = True, final_text: str | None = None) -> None:
        if not self._active:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        if sys.stdout.isatty():
            print("\r\033[2K\033[?25h", end="", flush=True)
        text = final_text or self.text
        if ok_state is True:
            print(f"{green('✓')} {text}")
        elif ok_state is False:
            print(f"{red('×')} {text}")
        else:
            print(f"{primary('›')} {text}")
        self._active = False


@contextmanager
def spinner(text: str) -> Iterator[Spinner]:
    item = Spinner(text).start()
    try:
        yield item
    except Exception:
        item.stop(False)
        raise
    else:
        item.stop(True)


class StepSpinner:
    def __init__(self, labels: dict[str, str]):
        self.labels = labels
        self.current: Spinner | None = None

    def __call__(self, step: str) -> None:
        if self.current:
            self.current.stop(True)
        self.current = Spinner(self.labels.get(step, step)).start()

    def finish(self, ok_state: bool = True) -> None:
        if self.current:
            self.current.stop(ok_state)
            self.current = None

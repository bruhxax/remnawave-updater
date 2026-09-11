from __future__ import annotations

import getpass
import os
import re
import sys
from typing import Iterable

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

RESET = "\033[0m" if _USE_COLOR else ""
BOLD = "\033[1m" if _USE_COLOR else ""
DIM = "\033[2m" if _USE_COLOR else ""
CYAN = "\033[36m" if _USE_COLOR else ""
GREEN = "\033[32m" if _USE_COLOR else ""
YELLOW = "\033[33m" if _USE_COLOR else ""
RED = "\033[31m" if _USE_COLOR else ""

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}" if code else text


def bold(text: str) -> str:
    return color(text, BOLD)


def dim(text: str) -> str:
    return color(text, DIM)


def cyan(text: str) -> str:
    return color(text, CYAN)


def green(text: str) -> str:
    return color(text, GREEN)


def yellow(text: str) -> str:
    return color(text, YELLOW)


def red(text: str) -> str:
    return color(text, RED)


def ok(text: str) -> None:
    print(f"{green('✓')} {text}")


def warn(text: str) -> None:
    print(f"{yellow('!')} {text}")


def error(text: str) -> None:
    print(f"{red('✗')} {text}")


def info(text: str) -> None:
    print(f"{cyan('›')} {text}")


def heading(text: str) -> None:
    print(f"\n{bold(text)}")


def header(title: str, subtitle: str = "") -> None:
    width = max(44, min(72, max(len(title), len(subtitle)) + 8))
    print(cyan("╭" + "─" * width + "╮"))
    print(cyan("│") + f"  {bold(title)}" + " " * max(0, width - len(title) - 2) + cyan("│"))
    if subtitle:
        print(cyan("│") + f"  {subtitle}" + " " * max(0, width - len(subtitle) - 2) + cyan("│"))
    print(cyan("╰" + "─" * width + "╯"))


def notice(text: str, level: str = "info") -> None:
    marker = {"warning": yellow("!"), "error": red("✗"), "success": green("✓")}.get(level, cyan("i"))
    print(f"\n{marker} {text}\n")


def prompt(text: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        try:
            if secret:
                value = getpass.getpass(f"{text}{suffix}: ")
            else:
                value = input(f"{text}{suffix}: ")
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
            value = input(f"{text}{suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(130)
        if not value:
            return default
        if value in yes:
            return True
        if value in no:
            return False
        print("Y/N")


def choose(text: str, choices: Iterable[str], default: str | None = None) -> str:
    allowed = set(choices)
    while True:
        value = prompt(text, default=default)
        if value in allowed:
            return value
        print(f"Allowed: {', '.join(sorted(allowed))}")


def prompt_int(text: str, default: int) -> int:
    while True:
        raw = prompt(text, str(default))
        try:
            value = int(raw)
            if 1 <= value <= 65535:
                return value
        except ValueError:
            pass
        print("1-65535")


def menu(items: list[str]) -> None:
    for index, item in enumerate(items, 1):
        print(f"  {cyan(str(index))}. {item}")


def pause(text: str) -> None:
    try:
        input(f"\n{text}")
    except (EOFError, KeyboardInterrupt):
        print()


def _plain(value: str) -> str:
    return _ANSI_RE.sub("", value)


def table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        return
    widths = [len(_plain(h)) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(_plain(str(value))))
    widths = [min(w, 70) for w in widths]

    def fmt(row: list[str]) -> str:
        cells = []
        for i, value in enumerate(row):
            raw = str(value)
            pad = max(0, widths[i] - len(_plain(raw)))
            cells.append(raw + " " * pad)
        return "  ".join(cells)

    print(fmt(headers))
    print("  ".join("─" * w for w in widths))
    for row in rows:
        print(fmt(row))

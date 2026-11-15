"""ckernel utilities"""
from __future__ import annotations

import html as _html
import os
import platform
import re
import traceback
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from tempfile import mkdtemp
from typing import NamedTuple, Optional


is_macOS: bool = platform.system() == "Darwin"


def temporary_directory(prefix: Optional[str] = None):
    "Return a temporary directory"
    return Path(mkdtemp(prefix=prefix))


class EnvironmentVariables(NamedTuple):
    CKERNEL_DEBUG: Optional[str]
    CKERNEL_CC: Optional[str]
    CKERNEL_CXX: Optional[str]
    CKERNEL_EXE_CFLAGS: Optional[str]
    CKERNEL_EXE_CXXFLAGS: Optional[str]
    CKERNEL_EXE_LDFLAGS: Optional[str]
    CKERNEL_EAT_NEWLINE: Optional[str]


def get_environment_variables(default: Optional[str] = None) -> EnvironmentVariables:
    return EnvironmentVariables(
        **{name: os.getenv(name, default) for name in EnvironmentVariables._fields}
    )


@contextmanager
def switch_directory(new: str):
    old = os.getcwd()
    os.chdir(new)
    yield
    os.chdir(old)


class Stream(str, Enum):
    """Constants representing standard output channels"""

    STDERR = "stderr"
    STDOUT = "stdout"


STDERR = Stream.STDERR
STDOUT = Stream.STDOUT


class Lang(str, Enum):
    """Represents the recognised languages"""

    C = "C"
    CPP = "C++"


language = {
    "c": Lang.C,
    "cpp": Lang.CPP,
    "cxx": Lang.CPP,
    "cc": Lang.CPP,
}


def success(execution_count: int) -> dict[str, str | int]:
    """Construct a dict representing a success message"""
    return {"status": "ok", "execution_count": execution_count}


def error(
    ename: str, evalue: str, trace: Optional[list[str]] = None
) -> dict[str, str | list[str]]:
    """Construct a dict representing an error message"""
    return {
        "status": "error",
        "ename": ename,
        "evalue": evalue,
        "traceback": trace or [],
    }


def error_from_exception(exc_type, exc, tb):
    """Get the last traceback and return the message and an error dict"""
    tb_str = "\n".join(traceback.format_tb(tb))
    message = f"{tb_str}\n{exc_type.__name__}: {exc}"
    return message, error(exc_type.__name__, str(exc), traceback.format_tb(tb))

# ANSI SGR (color) -> HTML conversion, used to render tool output (e.g. the
# AddressSanitizer report) in the notebook the way it appears in a terminal
# instead of on Jupyter's default pink stderr background.

_ANSI_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# Palette based on the default VS Code integrated terminal colours.
_ANSI_BASE = {
    0: "#000000",
    1: "#cd3131",
    2: "#0dbc79",
    3: "#e5e510",
    4: "#2472c8",
    5: "#bc3fbc",
    6: "#11a8cd",
    7: "#e5e5e5",
}
_ANSI_BRIGHT = {
    0: "#666666",
    1: "#f14c4c",
    2: "#23d18b",
    3: "#f5f543",
    4: "#3b8eea",
    5: "#d670d6",
    6: "#29b8db",
    7: "#f5f5f5",
}


def _ansi_resolve_fg(code: Optional[int], bold: bool) -> Optional[str]:
    if code is None:
        return None
    if 30 <= code <= 37:
        return (_ANSI_BRIGHT if bold else _ANSI_BASE)[code - 30]
    if 90 <= code <= 97:
        return _ANSI_BRIGHT[code - 90]
    return None


def _ansi_resolve_bg(code: Optional[int]) -> Optional[str]:
    if code is None:
        return None
    if 40 <= code <= 47:
        return _ANSI_BASE[code - 40]
    if 100 <= code <= 107:
        return _ANSI_BRIGHT[code - 100]
    return None


def _ansi_apply(state: dict, codes: str) -> None:
    parts = codes.split(";") if codes else ["0"]
    for part in parts:
        code = int(part) if part else 0
        if code == 0:
            state["bold"] = False
            state["fg"] = None
            state["bg"] = None
        elif code == 1:
            state["bold"] = True
        elif code == 22:
            state["bold"] = False
        elif code == 39:
            state["fg"] = None
        elif code == 49:
            state["bg"] = None
        elif (30 <= code <= 37) or (90 <= code <= 97):
            state["fg"] = code
        elif (40 <= code <= 47) or (100 <= code <= 107):
            state["bg"] = code


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR escape codes, returning plain text."""
    return _ANSI_SGR_RE.sub("", text.replace("\r\n", "\n").replace("\r", ""))


def ansi_to_html(text: str) -> str:
    """Convert text containing ANSI SGR escape codes into terminal-styled HTML.

    Any text without escape codes is simply HTML-escaped, so plain output is
    rendered faithfully (monochrome) on the same dark background.
    """
    text = text.replace("\r\n", "\n").replace("\r", "")
    state = {"bold": False, "fg": None, "bg": None}
    out: list[str] = []

    def emit(segment: str) -> None:
        if not segment:
            return
        escaped = _html.escape(segment)
        styles = []
        fg = _ansi_resolve_fg(state["fg"], state["bold"])
        bg = _ansi_resolve_bg(state["bg"])
        if fg:
            styles.append(f"color:{fg}")
        if bg:
            styles.append(f"background-color:{bg}")
        if state["bold"]:
            styles.append("font-weight:bold")
        if styles:
            out.append(f'<span style="{";".join(styles)}">{escaped}</span>')
        else:
            out.append(escaped)

    pos = 0
    for match in _ANSI_SGR_RE.finditer(text):
        emit(text[pos : match.start()])
        _ansi_apply(state, match.group(1))
        pos = match.end()
    emit(text[pos:])

    body = "".join(out)
    return (
        '<pre style="background:#1e1e1e;color:#cccccc;'
        "padding:10px;border-radius:4px;overflow-x:auto;line-height:1.2;"
        'margin:0;font-family:monospace,monospace;white-space:pre">'
        f"{body}</pre>"
    )

import re
import sys
import os

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[38;2;110;230;220m"


SGR_TO_COLOR : dict[str, str] = {
    "31": "red",
    "32": "green",
    "33": "yellow",
    "34": "blue",
    "35": "magenta",
    "91": "red",
    "92": "green",
    "93": "yellow",
    "94": "blue",
    "95": "magenta",
}


ACTORS : dict[str, str] = {
    "blue": "Attacker",
    "green": "Enclave",
    "yellow": "No actor",
    "magenta": "Attacker",
    "red": "No actor",
}


RUN_SEPARATOR_RE = re.compile(r"\x1b\[1;33m.")
COLOR_SEPARATOR_RE = re.compile(r"\x1b\[([0-9;]*)m|([^\x1b]+)", re.DOTALL)


DEBUG_PARSED_OUTPUT_ERROR = (
    "Cannot use --debug together with --parsed-output."
)
DEBUG_REQUIRES_RAW_OUTPUT_ERROR = (
    "Alvie's --debug output cannot be parsed reliably. Use --raw-output (-r)."
)


LOGO_LINES = [
    " █████╗  ██╗     ██╗   ██╗ ██╗ ███████╗       ██████╗ ██╗     ██╗",
    "██╔══██╗ ██║     ██║   ██║ ██║ ██╔════╝      ██╔════╝ ██║     ██║",
    "███████║ ██║     ██║   ██║ ██║ █████╗        ██║      ██║     ██║",
    "██╔══██║ ██║     ╚██╗ ██╔╝ ██║ ██╔══╝        ██║      ██║     ██║",
    "██║  ██║ ███████╗ ╚████╔╝  ██║ ███████╗      ╚██████╗ ███████╗██║",
    "╚═╝  ╚═╝ ╚══════╝  ╚═══╝   ╚═╝ ╚══════╝       ╚═════╝ ╚══════╝╚═╝",
]


# Gradient endpoints (blue -> cyan).
GRADIENT_START = (80, 150, 255)
GRADIENT_END = (110, 230, 220)


TAGLINE = "Interface for the Alvie analysis tool"
TIP = "Pick an action below  ·  Ctrl+C to exit"


def supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def color_from_sgr(sgr_code: str) -> str | None:
    """Return the semantic color from a plain or styled ANSI SGR code."""
    for code in reversed(sgr_code.split(";")):
        color = SGR_TO_COLOR.get(code)
        if color:
            return color

    return None


def truecolor(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


def gradient_line(text: str, ratio: float) -> str:
    sr, sg, sb = GRADIENT_START
    er, eg, eb = GRADIENT_END
    r = round(sr + (er - sr) * ratio)
    g = round(sg + (eg - sg) * ratio)
    b = round(sb + (eb - sb) * ratio)
    return f"{BOLD}{truecolor(r, g, b)}{text}{RESET}"


def style(text: str, *codes: str) -> str:
    if not supports_color():
        return text
    return f"{''.join(codes)}{text}{RESET}"


def info(message: str) -> None:
    print(style(message, CYAN))


def success(message: str) -> None:
    print(style(message, GREEN, BOLD))


def warn(message: str) -> None:
    print(style(message, YELLOW, BOLD))


def error(message: str) -> None:
    print(style(message, RED, BOLD))


def hint(message: str) -> None:
    print(style(message, DIM))


def banner() -> None:
    """Print the Alvie CLI welcome banner."""
    color = supports_color()
    width = max(len(line) for line in LOGO_LINES)
    pad = "  "

    print()
    for i, line in enumerate(LOGO_LINES):
        ratio = i / (len(LOGO_LINES) - 1)
        rendered = gradient_line(line, ratio) if color else line
        print(f"{pad}{rendered}")
    print()

    # Rounded info box, sized to the widest content line (logo or text).
    box_texts = ["✻ Welcome to Alvie CLI", "", TAGLINE, TIP]
    inner = max(width, *(len(t) for t in box_texts))
    top = f"╭{'─' * (inner + 2)}╮"
    bottom = f"╰{'─' * (inner + 2)}╯"

    def box_line(text: str, *, accent: bool = False) -> str:
        body = f"│ {text.ljust(inner)} │"
        if not color:
            return f"{pad}{body}"
        style = BOLD if accent else DIM
        return f"{pad}{DIM}│{RESET} {style}{text.ljust(inner)}{RESET} {DIM}│{RESET}"

    edge = f"{pad}{DIM}{top}{RESET}" if color else f"{pad}{top}"
    edge_b = f"{pad}{DIM}{bottom}{RESET}" if color else f"{pad}{bottom}"

    print(edge)
    print(box_line("✻ Welcome to Alvie CLI", accent=True))
    print(box_line(""))
    print(box_line(TAGLINE))
    print(box_line(TIP))
    print(edge_b)
    print()
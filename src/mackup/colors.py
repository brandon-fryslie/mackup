"""
Colorized logging for Mackup.

Color alone carries the log level -- there are no textual level labels. The
`colorize` helper is reset-safe: it re-applies the color after any embedded
reset so a nested reset inside the message does not strip color from the rest
of the line.
"""

import sys

RESET = "\x1b[0m"


def color_code(code: int) -> str:
    return f"\x1b[{code}m"


def colorize(code: int, s: str) -> str:
    # Re-apply the color after any embedded reset so nested resets don't bleed.
    c = color_code(code)
    return f"{c}{str(s).replace(RESET, c)}{RESET}"


def green(s: str) -> str:
    return colorize(32, s)


def yellow(s: str) -> str:
    return colorize(33, s)


def blue(s: str) -> str:
    return colorize(34, s)


def red(s: str) -> str:
    return colorize(31, s)


def bright_red(s: str) -> str:
    return colorize(91, s)


def cyan(s: str) -> str:
    return colorize(36, s)


def magenta(s: str) -> str:
    return colorize(35, s)


def bold(s: str) -> str:
    return colorize(1, s)


def info_log(*strs: str) -> None:
    """Normal, user-visible progress (yellow)."""
    for s in strs:
        print(yellow(s))


def warning_log(*strs: str) -> None:
    """Non-fatal anomaly, recoverable (bold yellow)."""
    for s in strs:
        print(bold(yellow(s)))


def success_log(*strs: str) -> None:
    """Completion / good outcome (green)."""
    for s in strs:
        print(green(s))


def error_log(*strs: str) -> None:
    """Error that does not exit (red).

    Errors go to stderr so a script or pipeline can detect a failure and a
    partial run is never mistaken for a clean one on stdout.
    """
    # [LAW:effects-at-boundaries] stdout is for parseable output; errors are
    # diagnostics and belong on stderr (CLI binding: streams have defined semantics).
    for s in strs:
        print(red(s), file=sys.stderr)


def vlog(message: str, verbose: bool) -> None:
    """Verbose-only trace (magenta). Gated on the caller's verbose flag."""
    if verbose:
        print(magenta(message))

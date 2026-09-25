"""Extract log-statement templates from HDT source (read-only, via `git show <rev>:<path>`)."""
from __future__ import annotations

import re
import subprocess

HDT_REPO = r"C:\projects\github\Hearthstone-Deck-Tracker"
INVOKER_PATH = "Hearthstone Deck Tracker/BobsBuddy/BobsBuddyInvoker.cs"

# HDT version reported in log (Core.Initialize) -> upstream git revision
VERSION_REV = {
    "1.49.2.0": "v1.49.2",
    "1.49.7.0": "v1.49.7",
    "1.49.10.0": "v1.49.10",
    "1.49.15.0": "v1.49.15",
    "1.50.6.0": "v1.50.6",
    "1.57.12.0": "bb3493f2",  # commit "v1.57.12" (no tag)
    "1.58.1.0": "ef8ab6e8",  # commit "v1.58.1" (no tag)
}
BASELINE_REV = "509bb0b9"

CALL_RE = re.compile(r"\b(DebugLog|Log\.(?:Info|Debug|Warn|Error))\(")


def git_show(rev: str, path: str = INVOKER_PATH) -> str:
    return subprocess.run(["git", "-C", HDT_REPO, "show", f"{rev}:{path}"], capture_output=True,
                          check=True).stdout.decode("utf-8-sig", errors="replace")


def _balanced_args(text: str, start: int) -> str:
    depth, i, in_str = 1, start, None
    while i < len(text) and depth:
        c = text[i]
        if in_str:
            if c == "\\" and in_str == '"':
                i += 2
                continue
            if c == '"':
                in_str = None
        elif c == '"':
            in_str = '"'
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return text[start:i - 1]


WILD = "\x00"


def _template_parts(args: str) -> list[str]:
    """Turn the first argument expression into literal parts separated by WILD."""
    # only the first argument matters (memberName etc. are optional)
    parts, i, buf = [], 0, []
    depth = 0
    while i < len(args):
        c = args[i]
        if c == "," and depth == 0:
            break
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == '"' or (c == "$" and i + 1 < len(args) and args[i + 1] == '"'):
            interp = c == "$"
            i += 2 if interp else 1
            while i < len(args) and args[i] != '"':
                ch = args[i]
                if ch == "\\":
                    nxt = args[i + 1]
                    buf.append({"n": "\n", "t": "\t"}.get(nxt, nxt))
                    i += 2
                    continue
                if interp and ch == "{":
                    if args[i + 1] == "{":
                        buf.append("{")
                        i += 2
                        continue
                    d = 1
                    i += 1
                    while d:
                        if args[i] == "{":
                            d += 1
                        elif args[i] == "}":
                            d -= 1
                        i += 1
                    buf.append(WILD)
                    continue
                if interp and ch == "}" and args[i + 1] == "}":
                    buf.append("}")
                    i += 2
                    continue
                buf.append(ch)
                i += 1
            i += 1
            continue
        if not c.isspace() and c != "+":
            if not buf or buf[-1] != WILD:
                buf.append(WILD)
            # skip identifier/expression chars until next literal or '+'
        i += 1
    s = "".join(buf)
    s = re.sub(WILD + "+", WILD, s)
    return s.split(WILD)


def extract(source: str) -> list[dict]:
    out = []
    for m in CALL_RE.finditer(source):
        line = source.count("\n", 0, m.start()) + 1
        args = _balanced_args(source, m.end())
        parts = _template_parts(args)
        literal = "".join(parts).strip()
        regex = "^" + ".*?".join(re.escape(p) for p in parts) + "$"
        out.append({"line": line, "call": m.group(1), "text": WILD.join(parts).replace(WILD, "{…}"),
                    "regex": re.compile(regex, re.S), "has_literal": bool(literal)})
    return out

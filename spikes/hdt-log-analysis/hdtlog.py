"""Parse HDT log files (hdt_log_*.txt) into sessions, games and Bob's Buddy simulation blocks.

Only reads the logs. Personal data (BattleTags, player names, IPs) stays in memory or in out/.
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
from dataclasses import dataclass, field

DEFAULT_LOG_DIR = os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\Logs")

LINE_RE = re.compile(r"^(\d{1,2}):(\d\d):(\d\d)(?: ([AP]M))?\|(\w+)\|(.+?) >> (.*)$")
MOD_MARK = "【团子专属】"

# Bob's Buddy Minion.ToString(): "[Name A/H, flag, flag, Key=Value, Enchantments=[...]]"
MINION_RE = re.compile(r"^\[(?P<name>[^\[\]]+?) (?P<atk>-?\d+)/(?P<hp>-?\d+)(?P<rest>.*)\]$")
QUEST_RE = re.compile(r"^\[(?P<quest>\S*) \((?P<prog>-?\d+)/(?P<total>-?\d+)\): (?P<reward>\S*), (?P<n1>-?\d+), (?P<n2>-?\d+)\]$")
HP_RE = re.compile(r"^(?P<who>Player|Opponent|PlayerTeammate|OpponentTeammate): (?P<kind>heroPower|extraHeroPower)=(?P<card>\S*), used=(?P<used>\w+), data=(?P<data>-?\d+)$")
DUR_RE = re.compile(r"^Duration=(?P<ms>[\d.]+)ms, ExitCondition=(?P<exit>\w+), Iterations=(?P<it>\d+)$")
RATE_RE = re.compile(
    r"^WinRate=(?P<win>[\d.E-]+)% \(Lethal=(?P<wl>[\d.E-]+)%\), TieRate=(?P<tie>[\d.E-]+)%, "
    r"LossRate=(?P<loss>[\d.E-]+)% \(Lethal=(?P<ll>[\d.E-]+)%\)$")
RUNWITH_RE = re.compile(r"^Running simulations with MaxIterations=(\d+) and ThreadCount=(\d+)")
KEY_RE = re.compile(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})_(\d+)\b")
MOD_MINION_RE = re.compile(r"模拟对战，(?P<side>我方|对方)随从(?P<idx>\d+)：(?P<cn>.*)（(?P<card>[^（）]+)）$")


def split_top(s: str, sep: str = ", ") -> list[str]:
    """Split on sep only at bracket depth 0."""
    out, depth, cur, i = [], 0, [], 0
    while i < len(s):
        c = s[i]
        if c in "[(":
            depth += 1
        elif c in "])":
            depth -= 1
        if depth == 0 and s.startswith(sep, i):
            out.append("".join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(c)
        i += 1
    if cur or out:
        out.append("".join(cur))
    return out


def parse_minion(s: str) -> dict | None:
    m = MINION_RE.match(s)
    if not m or QUEST_RE.match(s):
        return None
    d = {"name": m["name"], "atk": int(m["atk"]), "hp": int(m["hp"]), "flags": [], "kv": {}}
    for tok in split_top(m["rest"].lstrip(", ")) if m["rest"] else []:
        if "=" in tok:
            k, v = tok.split("=", 1)
            d["kv"][k] = v
        elif tok:
            d["flags"].append(tok)
    return d


@dataclass
class Side:
    hero_powers: list = field(default_factory=list)
    hand_raw: str | None = None
    hand: list = field(default_factory=list)
    minions: list = field(default_factory=list)
    quests: list = field(default_factory=list)
    mod_minions: list = field(default_factory=list)
    other: list = field(default_factory=list)


@dataclass
class Sim:
    file: str
    line: int
    key: str | None
    rerun_index: int  # number of TryRerun lines seen for this combat instance before this block
    trigger: str | None  # last event before the block: StartCombat | TryRerun | mod:DoSimulation
    sides: list = field(default_factory=list)  # Player, Opponent, [PlayerTeammate, OpponentTeammate]
    secrets: dict = field(default_factory=dict)  # "player"/"opponent"/... -> [str]
    mod_lines: list = field(default_factory=list)
    unparsed: list = field(default_factory=list)
    max_iter: int | None = None
    threads: int | None = None
    output: dict | None = None
    end_line: int | None = None


@dataclass
class Session:
    file: str
    hdt_version: str | None = None
    os: str | None = None
    carddefs_builds: list = field(default_factory=list)
    start_guess: dt.datetime | None = None
    mtime: dt.datetime | None = None
    lines: list = field(default_factory=list)  # (lineno, abs_seconds, level, source, msg)


def list_logs(log_dir: str = DEFAULT_LOG_DIR) -> list[str]:
    files = glob.glob(os.path.join(log_dir, "hdt_log_*.txt"))
    return sorted(files, key=lambda f: int(re.search(r"hdt_log_(\d+)", f).group(1)))


def load_sessions(log_dir: str = DEFAULT_LOG_DIR) -> list[Session]:
    """HDT renames the previous hdt_log.txt to hdt_log_<unix now>.txt when it starts.
    So the file name timestamp is the start of the *next* session; this session's start is
    approximately the previous file's name timestamp."""
    files = list_logs(log_dir)
    sessions = []
    prev_ts = None
    for f in files:
        ts = int(re.search(r"hdt_log_(\d+)", f).group(1))
        s = Session(file=os.path.basename(f))
        s.mtime = dt.datetime.fromtimestamp(os.path.getmtime(f))
        s.start_guess = dt.datetime.fromtimestamp(prev_ts) if prev_ts else None
        prev_ts = ts
        day_offset = 0
        last_sec = None
        with open(f, encoding="utf-8", errors="replace") as fh:
            for no, raw in enumerate(fh, 1):
                raw = raw.rstrip("\r\n")
                m = LINE_RE.match(raw)
                if not m:
                    continue
                hour = int(m[1])
                if m[4]:  # the first lines of a session may use a 12-hour clock
                    hour = hour % 12 + (12 if m[4] == "PM" else 0)
                sec = hour * 3600 + int(m[2]) * 60 + int(m[3])
                if last_sec is not None and sec + 3600 < last_sec:
                    day_offset += 86400
                last_sec = sec
                level, src, msg = m[5], m[6], m[7]
                s.lines.append((no, sec + day_offset, level, src, msg))
                if src == "Core.Initialize" and "HDT: " in msg:
                    s.hdt_version = re.search(r"HDT: ([\d.]+)", msg).group(1)
                    s.os = re.search(r"Operating System: ([^,]+)", msg).group(1) if "Operating System" in msg else None
                if src == "CardDefsManager.EnsureLatestCardDefs":
                    b = re.search(r"Build=(\d+)", msg)
                    if b:
                        s.carddefs_builds.append(int(b.group(1)))
        sessions.append(s)
    return sessions


def parse_sims(session: Session) -> list[Sim]:
    sims: list[Sim] = []
    cur_key = None
    reruns_since_key = 0
    cur: Sim | None = None
    section = 0
    in_secrets = None
    phase = None  # "input" | "output"
    trigger = None
    for no, sec, level, src, msg in session.lines:
        if src == "BobsBuddyInvoker.StartCombat":
            k = KEY_RE.match(msg)
            if k and msg.strip() == k.group(0):
                if k.group(0) != cur_key:
                    reruns_since_key = 0
                cur_key = k.group(0)
                trigger = "StartCombat"
            elif msg.endswith(" continuing..."):
                # a TryRerun can fire during StartCombat's state-change delay, before the initial run
                trigger = "StartCombat"
            continue
        if src == "BobsBuddyInvoker.TryRerun" and msg.startswith("Input changed, re-running"):
            reruns_since_key += 1
            trigger = "TryRerun"
            continue
        if src == "BobsBuddyInvoker.DoSimulation" and MOD_MARK in msg:
            trigger = "mod:DoSimulation"
            continue
        if src != "BobsBuddyInvoker.RunSimulation":
            continue
        if msg == "----- Simulation Input -----":
            cur = Sim(file=session.file, line=no, key=cur_key, rerun_index=reruns_since_key, trigger=trigger)
            trigger = None
            cur.sides = [Side(), Side()]
            section, in_secrets, phase = 0, None, "input"
            sims.append(cur)
            continue
        if cur is None:
            continue
        if phase == "input":
            if msg == "----- End of Input -----":
                phase = "between"
                continue
            if MOD_MARK in msg:
                cur.mod_lines.append((no, msg))
                mm = MOD_MINION_RE.search(msg)
                if mm and section < len(cur.sides):
                    cur.sides[section].mod_minions.append(mm.groupdict())
                continue
            if msg == "---":
                section += 1
                if section >= len(cur.sides) and section < 4:
                    cur.sides.append(Side())
                continue
            if msg.startswith("Detected the following"):
                in_secrets = msg[len("Detected the following "):].rstrip(" S.").strip()
                cur.secrets.setdefault(in_secrets, [])
                continue
            if in_secrets is not None:
                cur.secrets[in_secrets].append(msg)
                continue
            side = cur.sides[min(section, len(cur.sides) - 1)]
            hp = HP_RE.match(msg)
            if hp:
                side.hero_powers.append(hp.groupdict())
                continue
            if msg.startswith("Hand:"):
                side.hand_raw = msg[5:].strip()
                side.hand = split_top(side.hand_raw) if side.hand_raw else []
                continue
            q = QUEST_RE.match(msg)
            if q:
                side.quests.append(q.groupdict())
                continue
            mn = parse_minion(msg)
            if mn:
                side.minions.append(mn)
                continue
            if msg.endswith("Teammate: null"):
                continue
            cur.unparsed.append((no, msg))
        else:
            r = RUNWITH_RE.match(msg)
            if r:
                cur.max_iter, cur.threads = int(r.group(1)), int(r.group(2))
                continue
            if msg == "----- Simulation Output -----":
                phase = "output"
                cur.output = {}
                continue
            d = DUR_RE.match(msg)
            if d and cur.output is not None:
                cur.output.update(duration_ms=float(d["ms"]), exit=d["exit"], iterations=int(d["it"]))
                continue
            rr = RATE_RE.match(msg)
            if rr and cur.output is not None:
                cur.output.update({k: float(v) for k, v in rr.groupdict().items()})
                continue
            if msg == "----- End of Output -----":
                cur.end_line = no
                cur = None
                continue
    return sims

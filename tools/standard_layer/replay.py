# -*- coding: utf-8 -*-
"""Optional same-version BB replay delta via spikes/replay-harness."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Optional

from ._paths import REPLAY_HARNESS, ensure_spike_paths

ensure_spike_paths()


def binomial_se(p: float, n: int) -> float:
    if n <= 0:
        return 1.0
    p = min(max(p, 0.0), 1.0)
    return math.sqrt(p * (1.0 - p) / n)


def rates_within_3sigma(rec: dict, sim: dict) -> tuple[bool, dict]:
    n1 = int(rec.get("simulationCount") or 0)
    n2 = int(sim.get("simulationCount") or 0)
    detail = {}
    ok = True
    for key in ("winRate", "tieRate", "lossRate"):
        p1 = float(rec.get(key) or 0.0)
        p2 = float(sim.get(key) or 0.0)
        se = math.sqrt(binomial_se(p1, n1) ** 2 + binomial_se(p2, n2) ** 2)
        delta = abs(p1 - p2)
        floor = 3.0 * math.sqrt(0.5 * (1.0 / max(n1, 1) + 1.0 / max(n2, 1)))
        limit = max(3.0 * se, floor) if se > 0 else max(1e-6, floor)
        passed = delta <= limit + 1e-12
        detail[key] = {"rec": p1, "sim": p2, "delta": delta, "limit": limit, "ok": passed}
        ok = ok and passed
    return ok, detail


def load_bb_map(path: Optional[Path] = None) -> dict[str, str]:
    path = path or (REPLAY_HARNESS / "bb-dirs.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for k, v in raw.items():
        ver = k.split(":", 1)[0]
        expanded = os.path.expandvars(os.path.expanduser(v))
        if ver not in out:
            out[ver] = expanded
    return out


def default_exe() -> Path:
    return REPLAY_HARNESS / "ReplaySim" / "bin" / "run" / "ReplaySim.exe"


def replay_one(
    inp: dict,
    out: dict,
    bb_version: str,
    *,
    exe: Optional[Path] = None,
    bb_map: Optional[dict[str, str]] = None,
    max_duration: int = 15000,
) -> dict:
    from roundtrip import run_replay  # type: ignore

    exe = exe or default_exe()
    bb_map = bb_map or load_bb_map()
    if not exe.is_file():
        return {"ok": False, "error": "no_replay_exe", "path": str(exe)}
    bb_dir = bb_map.get(bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        return {"ok": False, "error": "skipped_no_dll", "bbVersion": bb_version, "bbDir": bb_dir}
    iters = out.get("simulationCount")
    sim = run_replay(exe, bb_dir, inp, int(iters) if iters else None, max_duration)
    if not sim.get("ok", True) and sim.get("error"):
        return {"ok": False, "error": sim.get("error"), "sim": sim}
    # ReplaySim returns rates at top level when successful
    if "winRate" not in sim and isinstance(sim.get("output"), dict):
        sim = {**sim, **sim["output"]}
    if sim.get("winRate") is None:
        return {"ok": False, "error": sim.get("error") or "no_rates", "sim": sim}
    ok, detail = rates_within_3sigma(out, sim)
    return {
        "ok": ok,
        "within3sigma": ok,
        "detail": detail,
        "simCount": sim.get("simulationCount"),
        "wallMs": sim.get("wallMs"),
        "bbVersion": bb_version,
    }

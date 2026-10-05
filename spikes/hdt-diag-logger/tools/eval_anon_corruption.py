"""Detect anonymizer substring collisions that rename Input.Player / $type."""
import json
import sys
from pathlib import Path

from diag_io import iter_record_lines, records_path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\projects\github\hdt-bg-helper\data\BgHelperDiag")

for gd in sorted(ROOT.iterdir()):
    if not gd.is_dir() or not records_path(str(gd)):
        continue
    meta = json.loads((gd / "meta.json").read_text(encoding="utf-8"))
    status = "no_input"
    odd = []
    for line in iter_record_lines(str(gd)):
        r = json.loads(line)
        if r.get("type") != "hdt_bb" or not r.get("hasInput"):
            continue
        inp = (r.get("invoker") or {}).get("_input") or {}
        keys = [k for k in inp if k in ("Player", "Opponent") or k.startswith("player_")]
        odd = [k for k in keys if k.startswith("player_")]
        if "Player" in inp and not odd:
            status = "ok"
        elif odd:
            status = "corrupted"
        else:
            status = "missing_player"
        break
    print(
        f"{gd.name} BB={meta.get('bobsBuddy', {}).get('fileVersion')} "
        f"HS={meta.get('hearthstoneBuild')} {status} odd={odd}"
    )

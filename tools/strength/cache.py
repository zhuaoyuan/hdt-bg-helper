# -*- coding: utf-8 -*-
"""SQLite cache for boards + pair simulation counts (mergeable)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from . import ASSEMBLER_VERSION
from .assembler import rates_to_counts, score_of


SCHEMA = """
CREATE TABLE IF NOT EXISTS boards (
  boardId TEXT PRIMARY KEY,
  gameId TEXT NOT NULL,
  turn INTEGER NOT NULL,
  side TEXT NOT NULL,
  bbVersion TEXT NOT NULL,
  boardHash TEXT NOT NULL,
  shellHash TEXT NOT NULL,
  status TEXT NOT NULL,
  isGhost INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pairs (
  pairKey TEXT PRIMARY KEY,
  bbVersion TEXT NOT NULL,
  rowBoardHash TEXT NOT NULL,
  colBoardHash TEXT NOT NULL,
  shellHash TEXT NOT NULL,
  assemblerVersion TEXT NOT NULL,
  sims INTEGER NOT NULL DEFAULT 0,
  wins REAL NOT NULL DEFAULT 0,
  ties REAL NOT NULL DEFAULT 0,
  losses REAL NOT NULL DEFAULT 0,
  myDeathRate REAL,
  theirDeathRate REAL,
  avDamage REAL,
  elapsedMs REAL,
  createdAt REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pairs_bb ON pairs(bbVersion);
CREATE INDEX IF NOT EXISTS idx_boards_bucket ON boards(bbVersion, turn);
"""


class StrengthCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> StrengthCache:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def upsert_board(self, row: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO boards(boardId, gameId, turn, side, bbVersion, boardHash, shellHash, status, isGhost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(boardId) DO UPDATE SET
              gameId=excluded.gameId,
              turn=excluded.turn,
              side=excluded.side,
              bbVersion=excluded.bbVersion,
              boardHash=excluded.boardHash,
              shellHash=excluded.shellHash,
              status=excluded.status,
              isGhost=excluded.isGhost
            """,
            (
                row["boardId"],
                row["gameId"],
                int(row["turn"]),
                row["side"],
                row["bbVersion"],
                row["boardHash"],
                row["shellHash"],
                row["status"],
                int(row.get("isGhost") or 0),
            ),
        )

    def upsert_boards(self, rows: Iterable[dict[str, Any]]) -> int:
        n = 0
        for r in rows:
            self.upsert_board(r)
            n += 1
        self._conn.commit()
        return n

    def get_pair(self, pair_key: str) -> dict[str, Any] | None:
        cur = self._conn.execute("SELECT * FROM pairs WHERE pairKey = ?", (pair_key,))
        row = cur.fetchone()
        return dict(row) if row else None

    def pair_sims(self, pair_key: str) -> int:
        p = self.get_pair(pair_key)
        return int(p["sims"]) if p else 0

    def merge_pair(
        self,
        *,
        pair_key: str,
        bb_version: str,
        row_board_hash: str,
        col_board_hash: str,
        shell_hash: str,
        assembler_version: str,
        sims: int,
        wins: float,
        ties: float,
        losses: float,
        my_death_rate: float | None,
        their_death_rate: float | None,
        av_damage: float | None,
        elapsed_ms: float | None,
    ) -> dict[str, Any]:
        """Add counts into an existing row (or insert). Rates re-averaged by sims."""
        old = self.get_pair(pair_key)
        if old is None:
            self._conn.execute(
                """
                INSERT INTO pairs(
                  pairKey, bbVersion, rowBoardHash, colBoardHash, shellHash, assemblerVersion,
                  sims, wins, ties, losses, myDeathRate, theirDeathRate, avDamage, elapsedMs, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pair_key,
                    bb_version,
                    row_board_hash,
                    col_board_hash,
                    shell_hash,
                    assembler_version,
                    int(sims),
                    float(wins),
                    float(ties),
                    float(losses),
                    my_death_rate,
                    their_death_rate,
                    av_damage,
                    elapsed_ms,
                    time.time(),
                ),
            )
            self._conn.commit()
            return self.get_pair(pair_key)  # type: ignore[return-value]

        old_sims = int(old["sims"])
        new_sims = old_sims + int(sims)
        def blend(old_v, new_v):
            if new_sims <= 0:
                return None
            if old_v is None and new_v is None:
                return None
            o = 0.0 if old_v is None else float(old_v)
            n = 0.0 if new_v is None else float(new_v)
            return (o * old_sims + n * int(sims)) / new_sims

        self._conn.execute(
            """
            UPDATE pairs SET
              sims = ?,
              wins = ?,
              ties = ?,
              losses = ?,
              myDeathRate = ?,
              theirDeathRate = ?,
              avDamage = ?,
              elapsedMs = ?,
              bbVersion = ?,
              rowBoardHash = ?,
              colBoardHash = ?,
              shellHash = ?,
              assemblerVersion = ?
            WHERE pairKey = ?
            """,
            (
                new_sims,
                float(old["wins"]) + float(wins),
                float(old["ties"]) + float(ties),
                float(old["losses"]) + float(losses),
                blend(old["myDeathRate"], my_death_rate),
                blend(old["theirDeathRate"], their_death_rate),
                blend(old["avDamage"], av_damage),
                blend(old["elapsedMs"], elapsed_ms),
                bb_version,
                row_board_hash,
                col_board_hash,
                shell_hash,
                assembler_version,
                pair_key,
            ),
        )
        self._conn.commit()
        return self.get_pair(pair_key)  # type: ignore[return-value]

    def merge_from_sim_result(
        self,
        *,
        pair_key: str,
        bb_version: str,
        row_board_hash: str,
        col_board_hash: str,
        shell_hash: str,
        result: dict[str, Any],
        assembler_version: str = ASSEMBLER_VERSION,
    ) -> dict[str, Any]:
        counts = rates_to_counts(
            int(result.get("simulationCount") or 0),
            result.get("winRate"),
            result.get("tieRate"),
            result.get("lossRate"),
            result.get("myDeathRate"),
            result.get("theirDeathRate"),
            result.get("avDamage"),
        )
        n = int(counts["sims"])
        return self.merge_pair(
            pair_key=pair_key,
            bb_version=bb_version,
            row_board_hash=row_board_hash,
            col_board_hash=col_board_hash,
            shell_hash=shell_hash,
            assembler_version=assembler_version,
            sims=n,
            wins=float(counts["wins"]),
            ties=float(counts["ties"]),
            losses=float(counts["losses"]),
            my_death_rate=(float(counts["myDeathRateSum"]) / n) if n else None,
            their_death_rate=(float(counts["theirDeathRateSum"]) / n) if n else None,
            av_damage=(float(counts["avDamageSum"]) / n) if n else None,
            elapsed_ms=float(result["elapsedMs"]) if result.get("elapsedMs") is not None else None,
        )

    def get_pair_by_hashes(
        self,
        *,
        bb_version: str,
        row_board_hash: str,
        col_board_hash: str,
        shell_hash: str,
        assembler_version: str = ASSEMBLER_VERSION,
    ) -> dict[str, Any] | None:
        cur = self._conn.execute(
            """
            SELECT * FROM pairs
            WHERE bbVersion = ? AND rowBoardHash = ? AND colBoardHash = ?
              AND shellHash = ? AND assemblerVersion = ?
            LIMIT 1
            """,
            (bb_version, row_board_hash, col_board_hash, shell_hash, assembler_version),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def load_pair_index(self, bb_version: str) -> dict[tuple[str, str, str], dict[str, Any]]:
        """Index pairs by (rowBoardHash, colBoardHash, shellHash) for one BB version."""
        cur = self._conn.execute(
            """
            SELECT * FROM pairs
            WHERE bbVersion = ? AND assemblerVersion = ? AND sims > 0
            """,
            (bb_version, ASSEMBLER_VERSION),
        )
        out: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in cur.fetchall():
            d = dict(row)
            key = (d["rowBoardHash"], d["colBoardHash"], d["shellHash"])
            out[key] = d
        return out

    def pair_rates(self, pair_key: str) -> dict[str, float] | None:
        p = self.get_pair(pair_key)
        if not p or int(p["sims"]) <= 0:
            return None
        n = float(p["sims"])
        win = float(p["wins"]) / n
        tie = float(p["ties"]) / n
        loss = float(p["losses"]) / n
        return {
            "sims": n,
            "winRate": win,
            "tieRate": tie,
            "lossRate": loss,
            "s": score_of(win, tie),
            "myDeathRate": p["myDeathRate"],
            "theirDeathRate": p["theirDeathRate"],
            "avDamage": p["avDamage"],
        }

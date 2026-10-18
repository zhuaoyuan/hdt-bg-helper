# -*- coding: utf-8 -*-
"""SQLite cache for boards + pair simulation counts (mergeable)."""
from __future__ import annotations

import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from . import ASSEMBLER_VERSION
from .assembler import rates_to_counts, score_of
from .sim_pools import sim_pool_of

# Bump when pair/matchup grouping moves from file version to simPool.
_SCHEMA_VERSION = 2

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
  simPool TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS matchups (
  simPool TEXT NOT NULL,
  bbVersion TEXT NOT NULL,
  rowBoardId TEXT NOT NULL,
  colBoardId TEXT NOT NULL,
  pairKey TEXT NOT NULL,
  rowBoardHash TEXT NOT NULL,
  colBoardHash TEXT NOT NULL,
  shellHash TEXT NOT NULL,
  turnRow INTEGER NOT NULL,
  turnCol INTEGER NOT NULL,
  PRIMARY KEY (simPool, rowBoardId, colBoardId)
);
"""


class StrengthCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate_sim_pool()
        self._ensure_loss_summary_columns()
        self._conn.commit()

    def _user_version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def _migrate_sim_pool(self) -> None:
        if self._user_version() >= _SCHEMA_VERSION:
            return
        self._ensure_pairs_sim_pool()
        self._rebuild_matchups_if_needed()
        self.consolidate_sim_pools()
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pairs_pool ON pairs(simPool)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_matchups_pool ON matchups(simPool)")
        self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    def _ensure_loss_summary_columns(self) -> None:
        """ADR-0019 loss-damage columns. Wins, ties, and losses are not touched."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(pairs)")}
        adds = {
            "lossCount": "INTEGER",
            "cappedLossCount": "INTEGER",
            "uncappedLossMedian": "REAL",
            "lossSampleCount": "INTEGER",
            "takenSum": "REAL",
        }
        for name, decl in adds.items():
            if name not in cols:
                self._conn.execute(f"ALTER TABLE pairs ADD COLUMN {name} {decl}")

    def write_loss_summary(
        self,
        pair_key: str,
        *,
        loss_count: int,
        capped_loss_count: int,
        uncapped_median: float | None,
        sample_count: int,
        taken_sum: float,
    ) -> None:
        """Write the loss-damage summary only. Does not change win/tie/loss counts."""
        cur = self._conn.execute(
            """
            UPDATE pairs
            SET lossCount = ?, cappedLossCount = ?, uncappedLossMedian = ?, lossSampleCount = ?, takenSum = ?
            WHERE pairKey = ?
            """,
            (
                int(loss_count),
                int(capped_loss_count),
                None if uncapped_median is None else float(uncapped_median),
                int(sample_count),
                float(taken_sum),
                pair_key,
            ),
        )
        if cur.rowcount != 1:
            raise KeyError(f"pairKey not in cache: {pair_key}")
        self._conn.commit()

    def write_loss_summaries(self, rows: Iterable[tuple]) -> int:
        """Batch form of write_loss_summary. Each row is
        (loss_count, capped_loss_count, uncapped_median, sample_count, taken_sum, pair_key).
        """
        payload = list(rows)
        if not payload:
            return 0
        self._conn.executemany(
            """
            UPDATE pairs
            SET lossCount = ?, cappedLossCount = ?, uncappedLossMedian = ?, lossSampleCount = ?, takenSum = ?
            WHERE pairKey = ?
            """,
            payload,
        )
        self._conn.commit()
        return len(payload)

    def _ensure_pairs_sim_pool(self) -> None:
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(pairs)")}
        if "simPool" in cols:
            return
        backup = self.path.with_name(self.path.stem + ".pre-sim-pool" + self.path.suffix)
        if self.path.is_file() and not backup.is_file() and self.path.stat().st_size > 0:
            dest = sqlite3.connect(str(backup))
            try:
                self._conn.backup(dest)
            finally:
                dest.close()
        self._conn.execute("ALTER TABLE pairs ADD COLUMN simPool TEXT")

    def _rebuild_matchups_if_needed(self) -> None:
        row = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='matchups'"
        ).fetchone()
        sql = (row[0] if row else "") or ""
        compact = "".join(sql.split())
        if "PRIMARY KEY (simPool,rowBoardId,colBoardId)" in compact:
            return
        self._conn.execute(
            """
            CREATE TABLE matchups_v2 (
              simPool TEXT NOT NULL,
              bbVersion TEXT NOT NULL,
              rowBoardId TEXT NOT NULL,
              colBoardId TEXT NOT NULL,
              pairKey TEXT NOT NULL,
              rowBoardHash TEXT NOT NULL,
              colBoardHash TEXT NOT NULL,
              shellHash TEXT NOT NULL,
              turnRow INTEGER NOT NULL,
              turnCol INTEGER NOT NULL,
              PRIMARY KEY (simPool, rowBoardId, colBoardId)
            )
            """
        )
        if row is not None:
            old_cols = {r[1] for r in self._conn.execute("PRAGMA table_info(matchups)")}
            for src in self._conn.execute("SELECT * FROM matchups"):
                d = dict(src)
                bb = str(d.get("bbVersion") or "")
                pool = str(d["simPool"]) if "simPool" in old_cols and d.get("simPool") else sim_pool_of(bb)
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO matchups_v2(
                      simPool, bbVersion, rowBoardId, colBoardId, pairKey,
                      rowBoardHash, colBoardHash, shellHash, turnRow, turnCol
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pool,
                        bb or pool,
                        d["rowBoardId"],
                        d["colBoardId"],
                        d["pairKey"],
                        d["rowBoardHash"],
                        d["colBoardHash"],
                        d["shellHash"],
                        int(d["turnRow"]),
                        int(d["turnCol"]),
                    ),
                )
        self._conn.execute("DROP TABLE matchups")
        self._conn.execute("ALTER TABLE matchups_v2 RENAME TO matchups")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_matchups_pool ON matchups(simPool)")

    def consolidate_sim_pools(self) -> dict[str, int]:
        """Tag pairs with simPool and sum counts that share one assembled input.

        Groups by (simPool, row/col/shell hash, assemblerVersion). The surviving
        pairKey prefers the row whose file version already equals the pool id
        (that hash is sha256(simPool | …)). Other file versions in the same pool
        add their counts. Versions in different pools are never merged.
        Placeholder hashes (``verify``) are retagged but not merged.
        """
        groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        placeholders = 0
        tag: list[tuple[str, str]] = []
        for src in self._conn.execute("SELECT * FROM pairs"):
            d = dict(src)
            bb = str(d.get("bbVersion") or "")
            pool = str(d.get("simPool") or "") or sim_pool_of(bb)
            d["simPool"] = pool
            hashes = (d.get("rowBoardHash"), d.get("colBoardHash"), d.get("shellHash"))
            if any(h in (None, "", "verify") for h in hashes):
                tag.append((pool, d["pairKey"]))
                placeholders += 1
                continue
            key = (pool, d["rowBoardHash"], d["colBoardHash"], d["shellHash"], d["assemblerVersion"])
            groups[key].append(d)

        merged = 0
        deleted = 0
        for key, items in groups.items():
            pool = key[0]
            if len(items) == 1:
                tag.append((pool, items[0]["pairKey"]))
                continue
            items.sort(key=lambda it: (0 if str(it.get("bbVersion")) == pool else 1, -int(it["sims"])))
            keep = items[0]
            sims = sum(int(it["sims"]) for it in items)
            wins = sum(float(it["wins"]) for it in items)
            ties = sum(float(it["ties"]) for it in items)
            losses = sum(float(it["losses"]) for it in items)

            def blend(name: str) -> float | None:
                if sims <= 0:
                    return None
                acc = 0.0
                seen = False
                for it in items:
                    if it.get(name) is None:
                        continue
                    seen = True
                    acc += float(it[name]) * int(it["sims"])
                return (acc / sims) if seen else None

            self._conn.execute(
                """
                UPDATE pairs SET
                  sims = ?, wins = ?, ties = ?, losses = ?,
                  myDeathRate = ?, theirDeathRate = ?, avDamage = ?, elapsedMs = ?,
                  simPool = ?
                WHERE pairKey = ?
                """,
                (
                    sims,
                    wins,
                    ties,
                    losses,
                    blend("myDeathRate"),
                    blend("theirDeathRate"),
                    blend("avDamage"),
                    blend("elapsedMs"),
                    pool,
                    keep["pairKey"],
                ),
            )
            for extra in items[1:]:
                self._conn.execute("DELETE FROM pairs WHERE pairKey = ?", (extra["pairKey"],))
                deleted += 1
            merged += 1
        if tag:
            self._conn.executemany(
                "UPDATE pairs SET simPool = ? WHERE pairKey = ?",
                tag,
            )
        self._conn.commit()
        return {"groupsMerged": merged, "rowsDeleted": deleted, "placeholders": placeholders}

    def median_elapsed_ms(self) -> float | None:
        cur = self._conn.execute(
            """
            SELECT elapsedMs FROM pairs
            WHERE elapsedMs IS NOT NULL AND elapsedMs > 0
            ORDER BY elapsedMs
            LIMIT 1
            OFFSET (
              SELECT COUNT(*) / 2 FROM pairs
              WHERE elapsedMs IS NOT NULL AND elapsedMs > 0
            )
            """
        )
        row = cur.fetchone()
        return float(row[0]) if row else None

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
        sim_pool: str | None = None,
    ) -> dict[str, Any]:
        """Add counts into an existing row (or insert). Rates re-averaged by sims."""
        pool = sim_pool or sim_pool_of(bb_version)
        old = self.get_pair(pair_key)
        if old is None:
            self._conn.execute(
                """
                INSERT INTO pairs(
                  pairKey, simPool, bbVersion, rowBoardHash, colBoardHash, shellHash, assemblerVersion,
                  sims, wins, ties, losses, myDeathRate, theirDeathRate, avDamage, elapsedMs, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pair_key,
                    pool,
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
              simPool = ?,
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
                pool,
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
        sim_pool: str | None = None,
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
            sim_pool=sim_pool or sim_pool_of(bb_version),
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
        sim_pool: str | None = None,
    ) -> dict[str, Any] | None:
        pool = sim_pool or sim_pool_of(bb_version)
        cur = self._conn.execute(
            """
            SELECT * FROM pairs
            WHERE simPool = ? AND rowBoardHash = ? AND colBoardHash = ?
              AND shellHash = ? AND assemblerVersion = ?
            LIMIT 1
            """,
            (pool, row_board_hash, col_board_hash, shell_hash, assembler_version),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def load_pair_index(self, bb_version: str) -> dict[tuple[str, str, str], dict[str, Any]]:
        """Index pairs by (rowBoardHash, colBoardHash, shellHash) for one sim pool.

        ``bb_version`` may be a file version; it is mapped to ``simPool`` first.
        """
        pool = sim_pool_of(bb_version)
        cur = self._conn.execute(
            """
            SELECT * FROM pairs
            WHERE simPool = ? AND assemblerVersion = ? AND sims > 0
            """,
            (pool, ASSEMBLER_VERSION),
        )
        out: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in cur.fetchall():
            d = dict(row)
            key = (d["rowBoardHash"], d["colBoardHash"], d["shellHash"])
            out[key] = d
        return out

    def upsert_matchups(self, rows: Iterable[dict[str, Any]]) -> int:
        """Record which lineup fought which. Rates stay on ``pairs`` (keyed by pairKey)."""
        payload = []
        for r in rows:
            bb = str(r.get("bbVersion") or "")
            pool = str(r.get("simPool") or sim_pool_of(bb))
            payload.append(
                (
                    pool,
                    bb or pool,
                    r["rowBoardId"],
                    r["colBoardId"],
                    r["pairKey"],
                    r["rowBoardHash"],
                    r["colBoardHash"],
                    r["shellHash"],
                    int(r["turnRow"]),
                    int(r["turnCol"]),
                )
            )
        if not payload:
            return 0
        self._conn.executemany(
            """
            INSERT INTO matchups(
              simPool, bbVersion, rowBoardId, colBoardId, pairKey,
              rowBoardHash, colBoardHash, shellHash, turnRow, turnCol
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(simPool, rowBoardId, colBoardId) DO UPDATE SET
              pairKey=excluded.pairKey,
              bbVersion=excluded.bbVersion,
              rowBoardHash=excluded.rowBoardHash,
              colBoardHash=excluded.colBoardHash,
              shellHash=excluded.shellHash,
              turnRow=excluded.turnRow,
              turnCol=excluded.turnCol
            """,
            payload,
        )
        self._conn.commit()
        return len(payload)

    def matchup_count(self, bb_version: str | None = None) -> int:
        if bb_version is None:
            cur = self._conn.execute("SELECT COUNT(*) FROM matchups")
        else:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM matchups WHERE simPool = ?",
                (sim_pool_of(bb_version),),
            )
        return int(cur.fetchone()[0])

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

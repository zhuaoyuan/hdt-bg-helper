# -*- coding: utf-8 -*-
"""Review view data model and strength-state labeling."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class TurnReview:
    turn: int
    status: str
    opp_hero: Optional[str] = None
    result: Optional[str] = None
    damage: Optional[int] = None
    result_source: Optional[str] = None
    hdt_win: Optional[float] = None
    hdt_tie: Optional[float] = None
    hdt_loss: Optional[float] = None
    # Player strength
    S: Optional[float] = None
    percentile: Optional[float] = None
    ci95: Optional[tuple[float, float]] = None
    width_pts: Optional[float] = None
    level: Optional[str] = None
    flags: list[str] = field(default_factory=list)
    strength_state: str = "missing"
    # Opponent strength (same metric; non-primary product path)
    opp_S: Optional[float] = None
    opp_percentile: Optional[float] = None
    opp_ci95: Optional[tuple[float, float]] = None
    opp_width_pts: Optional[float] = None
    opp_level: Optional[str] = None
    opp_flags: list[str] = field(default_factory=list)
    opp_strength_state: str = "missing"
    my_tavern_tier: Optional[int] = None
    opp_tavern_tier: Optional[int] = None
    my_tavern_up: bool = False
    opp_tavern_up: bool = False
    my_health: Optional[int] = None  # combat Output.friendlyHealth (开战/记录血量)
    board_player: Optional[str] = None
    board_opponent: Optional[str] = None
    combat: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.ci95 is not None:
            d["ci95"] = [self.ci95[0], self.ci95[1]]
        if self.opp_ci95 is not None:
            d["opp_ci95"] = [self.opp_ci95[0], self.opp_ci95[1]]
        return d


@dataclass
class GameReview:
    game_id: str
    my_hero: Optional[str] = None
    placement: Optional[int] = None
    bb_version: Optional[str] = None
    engine_version: Optional[str] = None
    turns: list[TurnReview] = field(default_factory=list)
    notes: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gameId": self.game_id,
            "myHero": self.my_hero,
            "placement": self.placement,
            "bbVersion": self.bb_version,
            "engineVersion": self.engine_version,
            "turns": [t.to_dict() for t in self.turns],
            "notes": self.notes,
        }


def strength_state_for(
    *,
    status: str,
    strength_row: Optional[dict],
    allow_missing: bool = False,
) -> str:
    """Map standard-layer status + strength.jsonl row to UI strength_state."""
    del allow_missing
    if status and status != "ready":
        return "non_ready"
    if strength_row is None:
        return "missing"
    level = strength_row.get("level")
    flags = list(strength_row.get("flags") or [])
    pct = strength_row.get("percentile")
    if level == "insufficient" or pct is None:
        return "insufficient"
    if isinstance(level, str) and level.startswith("L1"):
        return "relaxed"
    if "wide" in flags:
        return "wide"
    width = strength_row.get("widthPts")
    if width is not None and float(width) > 20:
        return "wide"
    return "ok"


def _format_strength_blurb(
    *,
    strength_state: str,
    status: str,
    percentile: Optional[float],
    ci95: Optional[tuple[float, float]],
    S: Optional[float],
    level: Optional[str],
) -> str:
    st = strength_state
    if st == "non_ready":
        return f"标准层非 ready：{status}"
    if st == "missing":
        return "尚无 strength 行（未入池）"
    if st == "insufficient":
        if S is not None:
            return f"参照不足，仅有 S={S:.3f}"
        return "参照不足，无数"
    parts: list[str] = []
    if percentile is not None:
        if ci95 is not None:
            lo, hi = ci95[0] * 100, ci95[1] * 100
            parts.append(f"分位 {percentile * 100:.1f}%（95% CI {lo:.1f}–{hi:.1f}）")
        else:
            parts.append(f"分位 {percentile * 100:.1f}%")
    if st == "wide":
        parts.append("区间偏宽，参考用")
    if st == "relaxed":
        parts.append(f"已放宽：{level or 'L1'}")
    if S is not None:
        parts.append(f"S={S:.3f}")
    return "；".join(parts) if parts else "—"


def turn_detail_text(t: TurnReview) -> str:
    """Human-readable strength blurb for the player (己方) detail panel."""
    return _format_strength_blurb(
        strength_state=t.strength_state,
        status=t.status,
        percentile=t.percentile,
        ci95=t.ci95,
        S=t.S,
        level=t.level,
    )


def opp_detail_text(t: TurnReview) -> str:
    """Human-readable strength blurb for the opponent board."""
    return _format_strength_blurb(
        strength_state=t.opp_strength_state,
        status=t.status,
        percentile=t.opp_percentile,
        ci95=t.opp_ci95,
        S=t.opp_S,
        level=t.opp_level,
    )

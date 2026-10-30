"""Possession-state example on synthetic tracking data.

EDUCATIONAL SIMPLIFICATION. This reproduces the *shape* of the possession logic
used in MatchLens on a tiny synthetic CSV so the idea can be inspected and run
in a few seconds. The production state machine additionally uses ball and
player velocity, a contested/duel state, dead-ball detection from set-piece
geometry, and confidence/visibility gating. Numbers here are not the product's.

Usage:
    python possession_state.py [sample_tracking.csv] [--plot timeline.png]

Input CSV columns (one row per player per frame):
    frame, ball_x, ball_y, player_id, team, x, y
Positions are pitch metres with the origin at the pitch centre (x along the
length, y along the width), matching the convention MatchLens uses internally.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass

FPS = 25
CONTROL_RADIUS_M = 1.5     # a player within this distance of the ball may control it
HOLD_FRAMES = 5            # the candidate must be nearest for this many frames in a row
RELEASE_RADIUS_M = 3.0     # possession is only lost once nobody is within this radius


@dataclass
class PossessionChange:
    frame: int
    seconds: float
    team: str | None
    player_id: int | None
    kind: str            # "gain" | "loss" | "turnover"


def load_rows(path: str):
    frames: dict[int, dict] = defaultdict(lambda: {"ball": None, "players": []})
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fr = int(r["frame"])
            frames[fr]["ball"] = (float(r["ball_x"]), float(r["ball_y"]))
            frames[fr]["players"].append((int(r["player_id"]), r["team"], float(r["x"]), float(r["y"])))
    return dict(sorted(frames.items()))


def nearest_player(ball, players):
    best, best_d = None, math.inf
    for pid, team, x, y in players:
        d = math.hypot(x - ball[0], y - ball[1])
        if d < best_d:
            best, best_d = (pid, team), d
    return best, best_d


def infer_possession(frames):
    """Return (per-frame owner list, change events).

    Rules, in order:
      1. The nearest player within CONTROL_RADIUS_M is the *candidate*.
      2. A candidate becomes the owner after HOLD_FRAMES consecutive frames —
         this is the hysteresis that stops possession flickering during a pass.
      3. The current owner keeps the ball while *someone of the same team* is within
         RELEASE_RADIUS_M; once nobody is, possession is released (loose ball).
    """
    owner = None                 # (player_id, team) or None
    candidate, streak = None, 0
    per_frame, changes = [], []

    for fr, data in frames.items():
        ball, players = data["ball"], data["players"]
        if ball is None or not players:
            per_frame.append((fr, owner))
            continue
        near, dist = nearest_player(ball, players)

        # 1–2: candidate + hysteresis
        if dist <= CONTROL_RADIUS_M:
            if near == candidate:
                streak += 1
            else:
                candidate, streak = near, 1
        else:
            candidate, streak = None, 0

        if candidate is not None and streak >= HOLD_FRAMES and candidate != owner:
            kind = "gain" if owner is None else ("turnover" if owner[1] != candidate[1] else "gain")
            owner = candidate
            changes.append(PossessionChange(fr, fr / FPS, owner[1], owner[0], kind))

        # 3: release when the owning team has nobody near the ball
        elif owner is not None:
            same_team_near = any(
                t == owner[1] and math.hypot(x - ball[0], y - ball[1]) <= RELEASE_RADIUS_M
                for _, t, x, y in players
            )
            if not same_team_near:
                changes.append(PossessionChange(fr, fr / FPS, owner[1], owner[0], "loss"))
                owner = None

        per_frame.append((fr, owner))
    return per_frame, changes


def summarise(per_frame):
    counts = defaultdict(int)
    for _, owner in per_frame:
        counts[owner[1] if owner else "none"] += 1
    total = sum(counts.values()) or 1
    return {k: v / total for k, v in counts.items()}


def plot_timeline(per_frame, changes, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {"home": "#3b82f6", "away": "#f97316", None: "#444444"}
    fig, ax = plt.subplots(figsize=(11, 2.6))
    start_fr, cur = per_frame[0][0], per_frame[0][1]
    for fr, owner in per_frame[1:] + [(per_frame[-1][0] + 1, "END")]:
        team = cur[1] if cur else None
        if owner == "END" or (owner[1] if owner else None) != team:
            ax.axvspan(start_fr / FPS, fr / FPS, color=colours[team], alpha=0.85 if team else 0.35, lw=0)
            start_fr, cur = fr, owner
    for c in changes:
        ax.axvline(c.seconds, color="white", lw=0.8, ls="--" if c.kind == "loss" else "-")
    ax.set_xlim(0, per_frame[-1][0] / FPS)
    ax.set_yticks([])
    ax.set_xlabel("match time (s)")
    ax.set_title("Possession timeline — blue: home, orange: away, grey: loose ball; lines mark changes")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    print(f"timeline written to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="sample_tracking.csv")
    ap.add_argument("--plot", default=None, help="write a PNG timeline here")
    args = ap.parse_args()

    frames = load_rows(args.csv)
    per_frame, changes = infer_possession(frames)
    print(f"{len(frames)} frames, {len(changes)} possession changes")
    for c in changes:
        who = f"{c.team} #{c.player_id}" if c.player_id is not None else "nobody"
        print(f"  {c.seconds:6.2f}s  frame {c.frame:4d}  {c.kind:8s}  {who}")
    share = summarise(per_frame)
    print("possession share:", ", ".join(f"{k}: {v:.0%}" for k, v in sorted(share.items())))
    if args.plot:
        plot_timeline(per_frame, changes, args.plot)


if __name__ == "__main__":
    main()

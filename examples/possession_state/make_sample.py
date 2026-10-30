"""Generate sample_tracking.csv: 20 s of synthetic play at 25 fps.

Scripted sequence (pitch metres, origin at centre):
  0–4 s   home #8 carries the ball forward
  4–6 s   pass home #8 -> home #10 (ball in flight, nobody in control)
  6–10 s  home #10 holds, then is closed down
  10–11 s away #5 intercepts (turnover)
  11–16 s away #5 carries, passes to away #9
  16–20 s away #9 holds
Two defenders and two midfielders per team jog around to make "nearest player"
non-trivial. Deterministic (fixed seed).
"""
import csv
import math
import random

FPS = 25
random.seed(7)


def lerp(a, b, t):
    return a + (b - a) * t


def ball_at(s):
    if s < 4:          return (lerp(-20, -5, s / 4), 0.0)
    if s < 6:          return (lerp(-5, 18, (s - 4) / 2), lerp(0, 8, (s - 4) / 2))      # pass in flight
    if s < 10:         return (18 + 0.3 * (s - 6), 8.0)
    if s < 11:         return (lerp(19.2, 17.5, s - 10), lerp(8, 6, s - 10))              # knocked away
    if s < 14:         return (lerp(17.5, 5, (s - 11) / 3), lerp(6, -4, (s - 11) / 3))   # away #5 carries
    if s < 16:         return (lerp(5, -15, (s - 14) / 2), lerp(-4, -12, (s - 14) / 2))  # pass to away #9
    return (-15 - 0.2 * (s - 16), -12.0)


def players_at(s):
    out = []
    # home #8: carries 0–4 s, then drifts
    out.append((8, "home", lerp(-20, -5, min(s, 4) / 4) + (0 if s < 4 else 0.4 * (s - 4)), 0.3 * math.sin(s)))
    # home #10: receives at 6 s, holds until 10 s, then stands off
    hx = 18 + 0.3 * max(0, min(s, 10) - 6) if s >= 5.5 else lerp(12, 18, s / 5.5)
    out.append((10, "home", hx + (0.8 * (s - 10) if s > 10 else 0), 8.0 + (0.5 if s > 10 else 0)))
    # away #5: closes down from 7 s, takes the ball at ~10.3 s, carries to 14 s
    if s < 7:          ax, ay = 26 + random.uniform(-0.2, 0.2), 4 + 0.2 * s
    elif s < 10.3:     ax, ay = lerp(26, 18.2, (s - 7) / 3.3), lerp(5.4, 6.4, (s - 7) / 3.3)
    elif s < 14:       bx, by = ball_at(s); ax, ay = bx + 0.3, by - 0.2
    else:              ax, ay = 5 + 0.3 * (s - 14), -4 - 0.3 * (s - 14)
    out.append((5, "away", ax, ay))
    # away #9: waits, receives at 16 s
    if s < 16:         ox, oy = lerp(-10, -15, min(s, 16) / 16), lerp(-8, -12, min(s, 16) / 16)
    else:              bx, by = ball_at(s); ox, oy = bx - 0.3, by + 0.1
    out.append((9, "away", ox, oy))
    # background runners
    for pid, team, cx, cy, r, ph in [(4, "home", -30, -10, 6, 0.0), (6, "home", -10, 15, 5, 1.2),
                                     (3, "away", 30, -12, 6, 2.1), (7, "away", 10, 18, 5, 0.6)]:
        out.append((pid, team, cx + r * math.cos(0.4 * s + ph), cy + r * math.sin(0.4 * s + ph)))
    return out


with open("sample_tracking.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["frame", "ball_x", "ball_y", "player_id", "team", "x", "y"])
    for fr in range(20 * FPS):
        s = fr / FPS
        bx, by = ball_at(s)
        for pid, team, x, y in players_at(s):
            w.writerow([fr, f"{bx:.2f}", f"{by:.2f}", pid, team, f"{x:.2f}", f"{y:.2f}"])
print("sample_tracking.csv written")

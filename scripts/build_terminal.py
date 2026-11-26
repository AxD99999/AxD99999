#!/usr/bin/env python3
"""Generate tmux terminal SVGs and pure-CSS Fourier epicycle AXD SVGs.

Zero third-party dependencies (Python 3.10+ stdlib only).
Set GITHUB_TOKEN to pull live GitHub GraphQL telemetry; otherwise falls
back to deterministic local preview data.

Usage:
    python3 scripts/build_terminal.py
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

USERNAME = os.environ.get("GITHUB_USERNAME", "AxD99999")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TZ_OFFSET = dt.timezone(dt.timedelta(hours=5, minutes=45))
TZ_LABEL = "UTC+05:45"

# Edit these lines to customize your profile readout
PROMPT = "axd@github:~$ "
COMMAND = "fastfetch --live"
PROFILE = [
    ("Focus", "full-stack, mobile & systems"),
    ("Stack", "Python · TypeScript · Flutter · Kotlin"),
    ("Infra", "Linux · Docker · GCP · Actions"),
    ("Tools", "Neovim · VS Code · tmux · zsh"),
    ("Zone", "Kathmandu (UTC+05:45)"),
    ("Status", "● active — building & shipping"),
]

LOGO = [
    " █████╗ ██╗  ██╗██████╗ ",
    "██╔══██╗╚██╗██╔╝██╔══██╗",
    "███████║ ╚███╔╝ ██║  ██║",
    "██╔══██║ ██╔██╗ ██║  ██║",
    "██║  ██║██╔╝ ██╗██████╔╝",
    "╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ",
]

FONT = (
    "'JetBrains Mono','Fira Code',ui-monospace,SFMono-Regular,"
    "Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"
)

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "surface": "#161b22",
        "border": "#30363d",
        "rule": "#21262d",
        "fg": "#e6edf3",
        "muted": "#8b949e",
        "subtle": "#484f58",
        "accent": "#3fb950",
        "accent_hi": "#7ee787",
        "accent_soft": "#12261e",
        "accent_text": "#0d1117",
        "logo_top": "#e6edf3",
        "logo_bot": "#3fb950",
        "track": "#21262d",
        "bar_colors": ["#3fb950", "#58a6ff", "#d2a8ff", "#8b949e"],
        "ep_circle": "#58a6ff",
        "ep_circle_op": "0.22",
        "ep_arm": "#8b949e",
        "ep_arm_op": "0.62",
        "ghost_op": "0.14",
        "grid": "#21262d",
        "glow": "2.4",
    },
    "light": {
        "bg": "#ffffff",
        "surface": "#f6f8fa",
        "border": "#d0d7de",
        "rule": "#e5e9ee",
        "fg": "#1f2328",
        "muted": "#656d76",
        "subtle": "#8c959f",
        "accent": "#1a7f37",
        "accent_hi": "#2da44e",
        "accent_soft": "#dafbe1",
        "accent_text": "#ffffff",
        "logo_top": "#1f2328",
        "logo_bot": "#1a7f37",
        "track": "#eaeef2",
        "bar_colors": ["#1a7f37", "#0969da", "#8250df", "#656d76"],
        "ep_circle": "#0969da",
        "ep_circle_op": "0.20",
        "ep_arm": "#656d76",
        "ep_arm_op": "0.58",
        "ghost_op": "0.13",
        "grid": "#eaeef2",
        "glow": "0",
    },
}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
          }
        }
      }
    }
    repositories(first: 40, ownerAffiliations: OWNER, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        pushedAt
        isPrivate
        languages(first: 6, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name }
          }
        }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 3) {
                nodes {
                  oid
                  messageHeadline
                  committedDate
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def relative_time(iso_ts: str, now: dt.datetime) -> str:
    try:
        parsed = dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        delta = max(0, int((now - parsed).total_seconds()))
    except Exception:
        return "recent"
    if delta < 3600:
        return f"{max(1, delta // 60)}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    days = delta // 86400
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


def compute_stats(weeks: list[list[dict]]) -> dict:
    flat = [d for w in weeks for d in w]
    total = sum(d["count"] for d in flat)
    peak_week = max((sum(d["count"] for d in w) for w in weeks), default=0)
    peak_day = max((d["count"] for d in flat), default=0)
    active_days = sum(1 for d in flat if d["count"] > 0)

    streak = 0
    idx = len(flat) - 1
    if idx >= 0 and flat[idx]["count"] == 0:
        idx -= 1
    while idx >= 0 and flat[idx]["count"] > 0:
        streak += 1
        idx -= 1

    best, cur = 0, 0
    for d in flat:
        if d["count"] > 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0

    return {
        "total": total,
        "peakWeek": peak_week,
        "peakDay": peak_day,
        "streak": streak,
        "longestStreak": best,
        "activeDays": active_days,
    }


def fallback_data(now: dt.datetime) -> dict:
    """Deterministic fallback dataset when running locally without GITHUB_TOKEN."""
    today = now.astimezone(TZ_OFFSET).date()
    days_since_sun = (today.weekday() + 1) % 7
    end_sat = today + dt.timedelta(days=(6 - days_since_sun))
    start_sun = end_sat - dt.timedelta(days=52 * 7 - 1)

    weeks: list[list[dict]] = []
    for w in range(52):
        col = []
        for d in range(7):
            cur = start_sun + dt.timedelta(days=w * 7 + d)
            if cur > today:
                count = 0
            else:
                wave = (
                    math.sin(w * 0.27 + d * 0.55) * 0.5
                    + math.cos(w * 0.13 - d * 0.9) * 0.35
                    + math.sin((w * 7 + d) * 0.41) * 0.3
                )
                burst = 1.6 if (w in (9, 18, 29, 38, 46, 50) and d in (1, 2, 3, 4)) else 0.0
                val = wave + burst + (0.25 if d in (1, 2, 3, 4) else -0.25)
                if w >= 49 and d <= days_since_sun:
                    val = max(val, 0.55)
                if val < 0.05:
                    count = 0
                else:
                    count = max(1, int(round((val + 0.2) ** 2 * 3.1)))
            if count == 0:
                lvl = 0
            elif count <= 2:
                lvl = 1
            elif count <= 5:
                lvl = 2
            elif count <= 9:
                lvl = 3
            else:
                lvl = 4
            col.append({"date": cur.isoformat(), "count": count, "level": lvl})
        weeks.append(col)

    return {
        "username": USERNAME,
        "updatedAt": now.astimezone(TZ_OFFSET).strftime("%Y-%m-%d %H:%M"),
        "timezone": TZ_LABEL,
        "stats": compute_stats(weeks),
        "weeks": weeks,
        "languages": [
            {"name": "Python", "pct": 42},
            {"name": "TypeScript", "pct": 29},
            {"name": "Dart", "pct": 18},
            {"name": "Kotlin", "pct": 11},
        ],
        "recentCommits": [
            {"sha": "a9f4c12", "repo": "AxD99999", "msg": "feat: pure-css fourier epicycle axd", "age": "2h ago"},
            {"sha": "97bc17b", "repo": "heos-web", "msg": "ui: update deployment card assets", "age": "1d ago"},
            {"sha": "4e81d0a", "repo": "hueshift", "msg": "perf: smooth tile transitions", "age": "3d ago"},
            {"sha": "1c09b3e", "repo": "bosstimer", "msg": "chore: tighten gcp swap watchdog", "age": "6d ago"},
        ],
    }


def fetch_github_data(now: dt.datetime) -> dict:
    if not TOKEN:
        return fallback_data(now)

    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": USERNAME}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USERNAME}-profile-builder",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        user = body["data"]["user"]
        if not user:
            raise ValueError("User not found in GraphQL response")
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"warning: GitHub API fetch failed ({exc}); using fallback data")
        return fallback_data(now)

    cal = user["contributionsCollection"]["contributionCalendar"]
    raw_weeks = cal["weeks"][-52:]
    weeks: list[list[dict]] = []
    for w in raw_weeks:
        col = [
            {
                "date": d["date"],
                "count": int(d["contributionCount"]),
                "level": LEVEL_MAP.get(d["contributionLevel"], 0),
            }
            for d in w["contributionDays"]
        ]
        while len(col) < 7:
            col.append({"date": "", "count": 0, "level": 0})
        weeks.append(col[:7])

    lang_bytes: dict[str, int] = {}
    commits_pool: list[tuple[str, dict]] = []
    for repo in user["repositories"]["nodes"]:
        for edge in repo.get("languages", {}).get("edges", []):
            lname = edge["node"]["name"]
            lang_bytes[lname] = lang_bytes.get(lname, 0) + int(edge["size"])

        if repo.get("isPrivate"):
            continue
        ref = repo.get("defaultBranchRef") or {}
        target = ref.get("target") or {}
        history = (target.get("history") or {}).get("nodes") or []
        for c in history:
            ts = c.get("committedDate", "")
            commits_pool.append((
                ts,
                {
                    "sha": c["oid"][:7],
                    "repo": repo["name"],
                    "msg": c["messageHeadline"].strip(),
                    "age": relative_time(ts, now),
                },
            ))

    total_bytes = sum(lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:4]
    languages = [
        {"name": name, "pct": max(1, round(size * 100 / total_bytes))}
        for name, size in top_langs
    ]
    if not languages:
        languages = fallback_data(now)["languages"]

    commits_pool.sort(key=lambda item: item[0], reverse=True)
    recent_commits = [c for _, c in commits_pool[:4]]
    if not recent_commits:
        recent_commits = fallback_data(now)["recentCommits"]

    stats = compute_stats(weeks)
    stats["total"] = int(cal.get("totalContributions", stats["total"]))

    return {
        "username": USERNAME,
        "updatedAt": now.astimezone(TZ_OFFSET).strftime("%Y-%m-%d %H:%M"),
        "timezone": TZ_LABEL,
        "stats": stats,
        "weeks": weeks,
        "languages": languages,
        "recentCommits": recent_commits,
    }


def trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def mono(x: float, y: float, text: str, cw: float = 8.2, cls: str = "", style: str = "") -> str:
    length = len(text) * cw
    attrs = f' class="{cls}"' if cls else ""
    attrs += f' style="{style}"' if style else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" textLength="{length:.1f}" '
        f'lengthAdjust="spacingAndGlyphs"{attrs}>{escape(text)}</text>'
    )


def build_terminal_svg(theme_name: str, data: dict) -> str:
    t = THEMES[theme_name]
    W, H = 860, 440
    CW = 8.2
    LOGO_LH = 16.5

    type_start, type_dur = 0.25, 0.85
    reveal = type_start + type_dur + 0.18
    step = 0.08

    stats = data["stats"]
    langs = data["languages"][:4]
    commits = data["recentCommits"][:4]
    updated_short = data["updatedAt"].split(" ")[0]

    parts: list[str] = []
    parts.append(f'<rect class="win" x="1" y="1" width="{W-2}" height="{H-2}" rx="10"/>')

    # Typed command at top of pane 0
    x0, y_cmd = 26.0, 36.0
    cmd_x = x0 + len(PROMPT) * CW
    parts.append(f'<g>{mono(x0, y_cmd, PROMPT, CW, "accent b")}{mono(cmd_x, y_cmd, COMMAND, CW, "fg")}</g>')
    n = len(COMMAND)
    parts.append(
        f'<g class="typer" style="--w:{n * CW:.1f}px;animation:type {type_dur:.2f}s steps({n}) {type_start:.2f}s both">'
        f'<rect class="cur typecur" x="{cmd_x:.1f}" y="{y_cmd - 12:.1f}" width="{CW:.1f}" height="15"/>'
        f'<rect class="bgfill" x="{cmd_x + CW:.1f}" y="{y_cmd - 14:.1f}" width="{n * CW + 6:.1f}" height="19"/></g>'
    )

    # Left column: AXD monochrome-to-accent block logo + compact telemetry strip
    logo_x, logo_y = 30.0, 74.0
    logo_svg = "".join(mono(logo_x, logo_y + i * LOGO_LH, line, CW) for i, line in enumerate(LOGO))
    parts.append(f'<g class="fade" style="animation-delay:{reveal:.2f}s"><g class="logo">{logo_svg}</g></g>')

    stat_y = 196.0
    parts.append(
        f'<g class="in" style="animation-delay:{reveal + 0.20:.2f}s">'
        f'<text x="{logo_x:.1f}" y="{stat_y:.1f}" class="small">'
        f'<tspan class="accent b">{stats["total"]:,}</tspan>'
        f'<tspan class="muted"> commits / yr</tspan></text>'
        f'<text x="{logo_x:.1f}" y="{stat_y + 20:.1f}" class="small">'
        f'<tspan class="fg b">{stats["streak"]}d</tspan>'
        f'<tspan class="muted"> streak  ·  </tspan>'
        f'<tspan class="fg b">{stats["peakWeek"]}/wk</tspan>'
        f'<tspan class="muted"> peak</tspan></text></g>'
    )

    # Right column: fastfetch specs
    info_x, y = 296.0, 74.0
    parts.append(
        f'<g class="in" style="animation-delay:{reveal:.2f}s">'
        f'<text x="{info_x:.1f}" y="{y:.1f}"><tspan class="accent b">axd</tspan>'
        f'<tspan class="muted">@</tspan><tspan class="fg b">github</tspan></text></g>'
    )
    y += 17.0
    parts.append(
        f'<g class="in" style="animation-delay:{reveal + step:.2f}s">'
        f'{mono(info_x, y, "──────────", CW, "subtle")}</g>'
    )
    for i, (k, v) in enumerate(PROFILE):
        y += 21.5
        delay = reveal + (i + 2) * step
        if k == "Status" and v.startswith("●"):
            rest = v[1:]
            val_svg = (
                f'<text x="{info_x + 78:.1f}" y="{y:.1f}">'
                f'<tspan class="accent pulse">●</tspan>'
                f'<tspan class="fg">{escape(rest)}</tspan></text>'
            )
        else:
            val_svg = f'<text x="{info_x + 78:.1f}" y="{y:.1f}" class="fg">{escape(v)}</text>'
        parts.append(
            f'<g class="in" style="animation-delay:{delay:.2f}s">'
            f'<text x="{info_x:.1f}" y="{y:.1f}" class="muted b">{escape(k)}</text>{val_svg}</g>'
        )

    # Tmux split dividers
    split_y, split_x, bar_y = 244, 364, 412
    parts.append(f'<line x1="1" y1="{split_y}" x2="{W-1}" y2="{split_y}" class="rule"/>')
    parts.append(f'<line x1="{split_x}" y1="{split_y}" x2="{split_x}" y2="{bar_y}" class="rule"/>')

    # Bottom-left pane: Top Languages
    pane_delay = reveal + (len(PROFILE) + 2) * step
    parts.append(
        f'<g class="in" style="animation-delay:{pane_delay:.2f}s">'
        f'<text x="26" y="268" class="label muted">LANGUAGES</text>'
        f'<text x="342" y="268" text-anchor="end" class="label subtle">top {len(langs)}</text></g>'
    )
    bar_x, bar_w = 122, 168
    for i, lang in enumerate(langs):
        ly = 296 + i * 28
        pct = max(1, min(100, int(lang["pct"])))
        fill_w = max(4.0, bar_w * pct / 100.0)
        color = t["bar_colors"][i % len(t["bar_colors"])]
        d = pane_delay + (i + 1) * 0.07
        parts.append(
            f'<g class="in" style="animation-delay:{d:.2f}s">'
            f'<text x="26" y="{ly}" class="fg small">{escape(trunc(lang["name"], 11))}</text>'
            f'<rect x="{bar_x}" y="{ly - 9}" width="{bar_w}" height="7" rx="3.5" fill="{t["track"]}"/>'
            f'<rect x="{bar_x}" y="{ly - 9}" width="{fill_w:.1f}" height="7" rx="3.5" fill="{color}"/>'
            f'<text x="342" y="{ly}" text-anchor="end" class="muted small">{pct}%</text></g>'
        )

    # Bottom-right pane: git log --oneline -n 4
    parts.append(
        f'<g class="in" style="animation-delay:{pane_delay:.2f}s">'
        f'<text x="384" y="268" class="label muted">GIT LOG --ONELINE -N 4</text>'
        f'<rect class="cur blink" x="556" y="257" width="7" height="12"/></g>'
    )
    for i, c in enumerate(commits):
        cy = 296 + i * 28
        d = pane_delay + (i + 1) * 0.07
        label = trunc(f'{c["repo"]}: {c["msg"]}', 35)
        parts.append(
            f'<g class="in" style="animation-delay:{d:.2f}s">'
            f'<text x="384" y="{cy}" class="accent small b">{escape(c["sha"])}</text>'
            f'<text x="452" y="{cy}" class="fg small">{escape(label)}</text>'
            f'<text x="834" y="{cy}" text-anchor="end" class="muted small">{escape(c["age"])}</text></g>'
        )

    # Bottom tmux status bar
    parts.append(f'<rect x="1" y="{bar_y}" width="{W-2}" height="{H - bar_y - 1}" fill="{t["surface"]}"/>')
    parts.append(f'<line x1="1" y1="{bar_y}" x2="{W-1}" y2="{bar_y}" class="rule"/>')
    parts.append(f'<rect x="1" y="{bar_y}" width="84" height="{H - bar_y - 1}" fill="{t["accent"]}"/>')
    parts.append(f'<text x="43" y="430" text-anchor="middle" class="bar-badge b">[0] axd</text>')
    parts.append(f'<text x="102" y="430" class="fg small b">1:profile*</text>')
    parts.append(f'<text x="196" y="430" class="muted small">2:fourier-axd</text>')
    parts.append(
        f'<text x="834" y="430" text-anchor="end" class="muted small">'
        f'<tspan class="accent">●</tspan> {escape(TZ_LABEL)}  │  {escape(updated_short)}</text>'
    )

    css = f"""
    text {{ font-family: {FONT}; font-size: 13.5px; white-space: pre; }}
    .win {{ fill: {t['bg']}; stroke: {t['border']}; stroke-width: 1; }}
    .bgfill {{ fill: {t['bg']}; }}
    .rule {{ stroke: {t['rule']}; stroke-width: 1; }}
    .fg {{ fill: {t['fg']}; }}
    .muted {{ fill: {t['muted']}; }}
    .subtle {{ fill: {t['subtle']}; }}
    .accent {{ fill: {t['accent']}; }}
    .bar-badge {{ fill: {t['accent_text']}; font-size: 12px; }}
    .b {{ font-weight: 700; }}
    .small {{ font-size: 12.2px; }}
    .label {{ font-size: 11px; letter-spacing: 0.08em; font-weight: 600; }}
    .logo {{ fill: url(#logoGrad); }}
    .cur {{ fill: {t['accent']}; }}
    .typer {{ animation-fill-mode: both; }}
    .typecur {{ animation: hide 0.01s linear {reveal - 0.12:.2f}s both; }}
    .in {{ opacity: 0; animation: slidein .38s cubic-bezier(.2,.8,.2,1) both; }}
    .fade {{ opacity: 0; animation: fadein .45s ease-out both; }}
    .blink {{ animation: blink 1.1s steps(1) infinite; }}
    .pulse {{ animation: pulse 2.6s ease-in-out infinite; }}
    @keyframes type {{ from {{ transform: translateX(0); }} to {{ transform: translateX(var(--w)); }} }}
    @keyframes hide {{ to {{ opacity: 0; }} }}
    @keyframes slidein {{ from {{ opacity: 0; transform: translateX(-6px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes fadein {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes blink {{ 0%, 50% {{ opacity: 1; }} 51%, 100% {{ opacity: 0; }} }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
    @media (prefers-reduced-motion: reduce) {{
      *, .in, .fade {{ animation: none !important; opacity: 1; }}
      .typer {{ display: none; }}
    }}"""

    defs = f"""<defs>
    <linearGradient id="logoGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{t['logo_top']}"/>
      <stop offset="100%" stop-color="{t['logo_bot']}"/>
    </linearGradient>
    <clipPath id="frame"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="10"/></clipPath>
  </defs>"""

    body = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t">
  <title id="t">{escape(data['username'])} — tmux terminal profile</title>
  <style>{css}
  </style>
  {defs}
  <g clip-path="url(#frame)">
  {body}
  </g>
</svg>
"""


def _axd_letter_contours() -> list[tuple[str, float, list[tuple[float, float]], float]]:
    """Three independent closed contours (A, X, D) of uniform height [-66, +66]."""
    x_bar = 60.0 * (16.0 + 66.0) / 132.0
    contour_a = [
        (-60.0, 66.0),
        (-x_bar, 16.0),
        (x_bar, 16.0),
        (-x_bar, 16.0),
        (0.0, -66.0),
        (60.0, 66.0),
        (0.0, -66.0),
        (-60.0, 66.0),
    ]
    contour_x = [
        (-54.0, -66.0),
        (54.0, 66.0),
        (0.0, 0.0),
        (54.0, -66.0),
        (-54.0, 66.0),
        (0.0, 0.0),
        (-54.0, -66.0),
    ]
    contour_d: list[tuple[float, float]] = [(-56.0, 66.0), (-56.0, -66.0), (-10.0, -66.0)]
    for k in range(1, 24):
        ang = -math.pi / 2.0 + math.pi * (k / 24.0)
        contour_d.append((-10.0 + 66.0 * math.cos(ang), 66.0 * math.sin(ang)))
    contour_d.append((-10.0, 66.0))
    contour_d.append((-56.0, 66.0))

    return [
        ("A", 232.0, contour_a, 0.0),
        ("X", 430.0, contour_x, -1.0 / 3.0),
        ("D", 624.0, contour_d, -2.0 / 3.0),
    ]


def _resample_closed(pts: list[tuple[float, float]], n_samples: int = 256) -> list[complex]:
    if pts[0] != pts[-1]:
        pts = list(pts) + [pts[0]]
    dists = [0.0]
    for i in range(1, len(pts)):
        dists.append(dists[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = dists[-1]
    out: list[complex] = []
    seg = 0
    for k in range(n_samples):
        target = (k / n_samples) * total
        while seg < len(dists) - 2 and dists[seg + 1] < target:
            seg += 1
        d0, d1 = dists[seg], dists[seg + 1]
        u = 0.0 if d1 == d0 else (target - d0) / (d1 - d0)
        x = pts[seg][0] + u * (pts[seg + 1][0] - pts[seg][0])
        y = pts[seg][1] + u * (pts[seg + 1][1] - pts[seg][1])
        out.append(complex(x, y))
    return out


def _compute_dft(samples: list[complex]) -> tuple[complex, list[tuple[int, float, float]]]:
    """Compute signed-frequency DFT; return (dc, sorted_ac_terms) as (freq, amp, phase)."""
    n = len(samples)
    dc = sum(samples) / n
    ac: list[tuple[int, float, float]] = []
    for freq in range(-(n // 2), n // 2):
        if freq == 0:
            continue
        c = 0j
        for idx, z in enumerate(samples):
            ang = -2.0 * math.pi * freq * idx / n
            c += z * complex(math.cos(ang), math.sin(ang))
        c /= n
        ac.append((freq, abs(c), math.atan2(c.imag, c.real)))
    ac.sort(key=lambda item: item[1], reverse=True)
    return dc, ac


def build_fourier_svg(theme_name: str, data: dict) -> str:
    """Build a pure-CSS 3-channel Fourier epicycle SVG tracing A, X, D."""
    t = THEMES[theme_name]
    W, H = 860, 326
    CY = 168.0
    HARMONICS = 24
    PERIOD = 10.0
    n_curve = 160
    n_stops = 48

    trail_specs = [
        ("tr1", 820.0),
        ("tr2", 460.0),
        ("tr3", 110.0),
    ]
    glow_attr = ' filter="url(#fglow)"' if t["glow"] != "0" else ""

    trail_css_rules: list[str] = []
    ep_css_rules: list[str] = []
    scope_parts: list[str] = [
        f'<line x1="24" y1="{CY:.1f}" x2="{W - 24}" y2="{CY:.1f}" class="grid-line"/>'
    ]
    trail_layers: list[str] = []
    epicycle_chains: list[str] = []
    all_amps: list[float] = []

    for li, (_, cx, pts, phase_frac) in enumerate(_axd_letter_contours()):
        samples = _resample_closed(pts, 256)
        dc, ac_all = _compute_dft(samples)
        terms = ac_all[:HARMONICS]
        all_amps.extend(amp for _, amp, _ in terms)

        # Evaluate exact reconstructed curve and cumulative arc length for trail sync
        curve_pts: list[tuple[float, float]] = []
        for i in range(n_curve):
            frac = i / n_curve
            z = dc
            for freq, amp, phase in terms:
                ang = 2.0 * math.pi * freq * frac + phase
                z += complex(amp * math.cos(ang), amp * math.sin(ang))
            curve_pts.append((cx + z.real, CY + z.imag))

        arc = [0.0]
        for i in range(1, n_curve + 1):
            x0, y0 = curve_pts[i - 1]
            x1, y1 = curve_pts[i % n_curve]
            arc.append(arc[-1] + math.hypot(x1 - x0, y1 - y0))
        total_arc = arc[-1]

        path_d = (
            f"M {curve_pts[0][0]:.1f},{curve_pts[0][1]:.1f} "
            + " ".join(f"L {x:.1f},{y:.1f}" for x, y in curve_pts[1:])
            + " Z"
        )

        delay = phase_frac * PERIOD
        for ti, (cls_prefix, dash_w) in enumerate(trail_specs):
            kf_name = f"t{li}_{ti}"
            stops = []
            for s_idx in range(n_stops + 1):
                pct = (s_idx / n_stops) * 100.0
                c_idx = round((s_idx / n_stops) * n_curve)
                s_val = (arc[c_idx] / total_arc) * 1000.0
                offset = dash_w - s_val
                stops.append(f"{pct:.2f}%{{stroke-dashoffset:{offset:.1f}}}")
            trail_css_rules.append(f"@keyframes {kf_name}{{{' '.join(stops)}}}")
            trail_css_rules.append(
                f".{cls_prefix}_{li}{{animation:{kf_name} {PERIOD:.1f}s linear {delay:.2f}s infinite}}"
            )

        dc_x, dc_y = cx + dc.real, CY + dc.imag
        scope_parts.append(
            f'<line x1="{dc_x:.1f}" y1="54" x2="{dc_x:.1f}" y2="{H - 42}" class="grid-line"/>'
            f'<circle cx="{dc_x:.1f}" cy="{dc_y:.1f}" r="45" class="grid-ring"/>'
            f'<circle cx="{dc_x:.1f}" cy="{dc_y:.1f}" r="82" class="grid-ring"/>'
        )

        trail_layers.append(f'<path class="ghost" d="{path_d}"/>')
        trail_layers.append(f'<path class="tr tr1 tr1_{li}" pathLength="1000" d="{path_d}"/>')
        trail_layers.append(f'<path class="tr tr2 tr2_{li}" pathLength="1000" d="{path_d}"{glow_attr}/>')
        trail_layers.append(f'<path class="tr tr3 tr3_{li}" pathLength="1000" d="{path_d}"{glow_attr}/>')

        # Nested relative-rotation epicycle chain with static transform fallback
        ep_open: list[str] = [f'<g transform="translate({dc_x:.2f},{dc_y:.2f})">']
        ep_close: list[str] = ["</g>"]
        prev_freq = 0
        prev_phi = 0.0
        for idx, (freq, amp, phase) in enumerate(terms):
            rel_freq = freq - prev_freq
            rel_phi_deg = math.degrees(phase - prev_phi)
            end_deg = rel_phi_deg + 360.0 * rel_freq
            cls_name = f"e{li}_{idx}"
            kf_name = f"r{li}_{idx}"

            ep_css_rules.append(
                f".{cls_name}{{transform:rotate({rel_phi_deg:.2f}deg);"
                f"animation:{kf_name} {PERIOD:.1f}s linear {delay:.2f}s infinite}}"
                f"@keyframes {kf_name}{{from{{transform:rotate({rel_phi_deg:.2f}deg)}}"
                f"to{{transform:rotate({end_deg:.2f}deg)}}}}"
            )

            circle_el = f'<circle class="ec" r="{amp:.2f}"/>' if amp >= 2.0 else ""
            arm_el = f'<line class="ea" x2="{amp:.2f}"/>' if amp >= 1.2 else ""
            joint_el = '<circle class="ej" r="1.3"/>' if amp >= 3.5 else ""

            ep_open.append(
                f'{circle_el}<g class="ep {cls_name}">{arm_el}{joint_el}<g transform="translate({amp:.2f},0)">'
            )
            ep_close.append("</g></g>")

            prev_freq = freq
            prev_phi = phase

        stylus_el = '<circle class="tip-halo" r="6.5"/><circle class="tip-core" r="2.8"/>'
        epicycle_chains.append("".join(ep_open) + stylus_el + "".join(reversed(ep_close)))

    # Mini harmonic spectrum bars (top 16 combined amplitudes across A, X, D)
    all_amps.sort(reverse=True)
    max_amp = all_amps[0] if all_amps else 1.0
    spec_bars = []
    for i, amp in enumerate(all_amps[:16]):
        bh = max(2.5, (amp / max_amp) * 14.0)
        bx = 26 + i * 6
        by = H - 14 - bh
        op = 0.95 if i < 4 else 0.45
        spec_bars.append(
            f'<rect x="{bx}" y="{by:.1f}" width="3.5" height="{bh:.1f}" rx="1" '
            f'fill="{t["accent"]}" opacity="{op:.2f}"/>'
        )

    parts: list[str] = []
    parts.append(f'<rect class="win" x="1" y="1" width="{W-2}" height="{H-2}" rx="10"/>')
    parts.append(f'<g class="scope">{"".join(scope_parts)}</g>')

    # Header bar
    parts.append(
        f'<text x="26" y="30" class="fg b small">'
        f'<tspan class="accent">●</tspan> fourier-axd'
        f'<tspan class="muted" font-weight="400">  ·  DFT epicycles  ·  3 × {HARMONICS} harmonics</tspan></text>'
    )
    parts.append(
        f'<text x="{W - 26}" y="30" text-anchor="end" class="muted tiny">'
        f'z(t) = Σ cₖ · e^(iωₖt)</text>'
    )

    # Ghost guides + 3-layer phosphor comet trails + nested epicycles
    parts.extend(trail_layers)
    parts.extend(epicycle_chains)

    # Footer HUD + mini harmonic spectrum
    parts.append("<g>" + "".join(spec_bars) + "</g>")
    parts.append(
        f'<text x="132" y="{H - 16}" class="muted tiny">'
        f'spectrum |cₖ|  ·  T={int(PERIOD)}s  ·  pure CSS</text>'
    )
    parts.append(
        f'<text x="{W - 26}" y="{H - 16}" text-anchor="end" class="muted tiny">'
        f'{escape(data["username"])} · closed-contour DFT</text>'
    )

    css = f"""
    text {{ font-family: {FONT}; white-space: pre; }}
    .win {{ fill: {t['bg']}; stroke: {t['border']}; stroke-width: 1; }}
    .fg {{ fill: {t['fg']}; }}
    .muted {{ fill: {t['muted']}; }}
    .accent {{ fill: {t['accent']}; }}
    .b {{ font-weight: 700; }}
    .small {{ font-size: 12.2px; }}
    .tiny {{ font-size: 11px; }}
    .grid-line {{ stroke: {t['grid']}; stroke-width: 1; stroke-dasharray: 3 4; }}
    .grid-ring {{ fill: none; stroke: {t['grid']}; stroke-width: 0.9; stroke-dasharray: 2 5; }}
    .ghost {{ fill: none; stroke: {t['accent']}; stroke-width: 1.6; opacity: {t['ghost_op']}; stroke-linejoin: round; stroke-linecap: round; }}
    .tr {{ fill: none; stroke-linejoin: round; stroke-linecap: round; }}
    .tr1 {{ stroke: {t['accent']}; stroke-width: 2.6; opacity: 0.35; stroke-dasharray: 820 180; }}
    .tr2 {{ stroke: {t['accent']}; stroke-width: 2.8; opacity: 0.92; stroke-dasharray: 460 540; }}
    .tr3 {{ stroke: {t['accent_hi']}; stroke-width: 3.0; opacity: 1; stroke-dasharray: 110 890; }}
    .ep {{ transform-origin: 0px 0px; transform-box: view-box; }}
    .ec {{ fill: none; stroke: {t['ep_circle']}; stroke-width: 0.85; opacity: {t['ep_circle_op']}; }}
    .ea {{ stroke: {t['ep_arm']}; stroke-width: 1.05; opacity: {t['ep_arm_op']}; stroke-linecap: round; }}
    .ej {{ fill: {t['ep_arm']}; opacity: 0.55; }}
    .tip-halo {{ fill: {t['accent']}; opacity: 0.30; }}
    .tip-core {{ fill: {t['accent_hi']}; }}
    {"".join(trail_css_rules)}
    {"".join(ep_css_rules)}"""

    glow_def = (
        f'<filter id="fglow" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feGaussianBlur stdDeviation="{t["glow"]}" result="b"/>'
        f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        f"</filter>"
        if t["glow"] != "0"
        else ""
    )
    defs = f"""<defs>
    {glow_def}
    <clipPath id="fframe"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="10"/></clipPath>
  </defs>"""

    body = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="ft">
  <title id="ft">{escape(data['username'])} — Fourier epicycle series tracing AXD</title>
  <style>{css}
  </style>
  {defs}
  <g clip-path="url(#fframe)">
  {body}
  </g>
</svg>
"""


def main() -> None:
    fourier_only = "--fourier-only" in sys.argv[1:]
    ASSETS.mkdir(parents=True, exist_ok=True)

    if fourier_only:
        data = {"username": USERNAME}
    else:
        now = dt.datetime.now(dt.timezone.utc)
        data = fetch_github_data(now)

    for theme_name in THEMES:
        if not fourier_only:
            term_path = ASSETS / f"terminal-{theme_name}.svg"
            term_path.write_text(build_terminal_svg(theme_name, data), encoding="utf-8")
            print(f"wrote {term_path.relative_to(ROOT)}")

        fourier_path = ASSETS / f"fourier-{theme_name}.svg"
        fourier_path.write_text(build_fourier_svg(theme_name, data), encoding="utf-8")
        print(f"wrote {fourier_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

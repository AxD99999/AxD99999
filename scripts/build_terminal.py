#!/usr/bin/env python3
"""Generate tmux terminal SVGs, isometric 3D contribution skylines, and docs/data.json.

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
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"

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
        "iso": [
            ("#161b22", "#12161c", "#0f1318"),
            ("#0e4429", "#0a3320", "#072517"),
            ("#006d32", "#005226", "#003d1c"),
            ("#26a641", "#1d8233", "#156126"),
            ("#39d353", "#29a840", "#1e7d2f"),
        ],
        "iso_stroke": "#0d1117",
        "iso_empty_stroke": "#21262d",
        "pill_bg": "#12261e",
        "pill_border": "#238636",
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
        "iso": [
            ("#ebedf0", "#dfe3e8", "#d5dae0"),
            ("#9be9a8", "#7fd88f", "#66c277"),
            ("#40c463", "#30a650", "#24873f"),
            ("#30a14e", "#24803d", "#1b632e"),
            ("#216e39", "#175229", "#103b1d"),
        ],
        "iso_stroke": "#ffffff",
        "iso_empty_stroke": "#d8dee4",
        "pill_bg": "#dafbe1",
        "pill_border": "#4ac26b",
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
            {"sha": "a9f4c12", "repo": "AxD99999", "msg": "feat: interactive 3d skyline viewer", "age": "2h ago"},
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
    parts.append(f'<text x="196" y="430" class="muted small">2:skyline-3d</text>')
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


def build_skyline_svg(theme_name: str, data: dict) -> str:
    t = THEMES[theme_name]
    W, H = 860, 326
    weeks = data["weeks"]
    stats = data["stats"]
    max_count = max(stats["peakDay"], 1)

    dx_w, dy_w = 12.2, 2.35
    dx_d, dy_d = -13.6, 5.2
    tile_scale = 0.84
    max_tower_h = 64.0
    base_h = 3.5

    min_x = 7 * dx_d
    max_x = 52 * dx_w
    ox = (W - (max_x - min_x)) / 2.0 - min_x
    max_y_base = 52 * dy_w + 7 * dy_d
    oy = 114.0 + (176.0 - max_y_base) / 2.0

    def project(w: float, d: float, z: float = 0.0) -> tuple[float, float]:
        return (ox + w * dx_w + d * dx_d, oy + w * dy_w + d * dy_d - z)

    def pts(coords: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    parts: list[str] = []
    parts.append(f'<rect class="win" x="1" y="1" width="{W-2}" height="{H-2}" rx="10"/>')

    parts.append(
        f'<text x="26" y="30" class="fg b small">'
        f'<tspan class="accent">●</tspan> skyline-3d'
        f'<tspan class="muted" font-weight="400">  ·  {stats["total"]:,} contributions  ·  '
        f'{stats["peakWeek"]}/wk peak  ·  {stats["streak"]}d streak</tspan></text>'
    )

    pill_x, pill_y, pill_w, pill_h = 708, 13, 128, 24
    parts.append(
        f'<g class="cta">'
        f'<rect x="{pill_x}" y="{pill_y}" width="{pill_w}" height="{pill_h}" rx="12" '
        f'fill="{t["pill_bg"]}" stroke="{t["pill_border"]}" stroke-width="1"/>'
        f'<text x="{pill_x + pill_w / 2:.1f}" y="{pill_y + 16}" text-anchor="middle" '
        f'class="accent b pill-txt">Explore in 3D ↗</text></g>'
    )

    pad = 0.7
    plinth_top = [
        project(-pad, -pad, 0),
        project(52 + pad, -pad, 0),
        project(52 + pad, 7 + pad, 0),
        project(-pad, 7 + pad, 0),
    ]
    plinth_left = [
        project(-pad, 7 + pad, 0),
        project(52 + pad, 7 + pad, 0),
        project(52 + pad, 7 + pad, -6),
        project(-pad, 7 + pad, -6),
    ]
    plinth_right = [
        project(52 + pad, 7 + pad, 0),
        project(52 + pad, -pad, 0),
        project(52 + pad, -pad, -6),
        project(52 + pad, 7 + pad, -6),
    ]
    parts.append(f'<polygon points="{pts(plinth_left)}" fill="{t["rule"]}"/>')
    parts.append(f'<polygon points="{pts(plinth_right)}" fill="{t["border"]}" opacity="0.65"/>')
    parts.append(
        f'<polygon points="{pts(plinth_top)}" fill="{t["surface"]}" '
        f'stroke="{t["border"]}" stroke-width="0.9"/>'
    )

    pillars: list[str] = []
    inset = (1.0 - tile_scale) / 2.0
    for w_idx, col in enumerate(weeks):
        for d_idx, day in enumerate(col):
            cnt = int(day["count"])
            lvl = max(0, min(4, int(day["level"])))

            w0, w1 = w_idx + inset, w_idx + 1.0 - inset
            d0, d1 = d_idx + inset, d_idx + 1.0 - inset

            if cnt <= 0:
                p_top = [project(w0, d0, 0), project(w1, d0, 0), project(w1, d1, 0), project(w0, d1, 0)]
                pillars.append(f'<polygon class="e" points="{pts(p_top)}"/>')
                continue

            ratio = math.sqrt(cnt / max_count)
            h = base_h + ratio * (max_tower_h - base_h)

            top_face = [project(w0, d0, h), project(w1, d0, h), project(w1, d1, h), project(w0, d1, h)]
            left_face = [project(w0, d1, h), project(w1, d1, h), project(w1, d1, 0), project(w0, d1, 0)]
            right_face = [project(w1, d1, h), project(w1, d0, h), project(w1, d0, 0), project(w1, d1, 0)]

            cls_attr = ' class="peak"' if lvl == 4 else ""
            delay_attr = f' style="animation-delay:{(w_idx % 8) * 0.35:.2f}s"' if lvl == 4 else ""
            pillars.append(
                f'<g{cls_attr}{delay_attr}>'
                f'<polygon class="p l{lvl}" points="{pts(left_face)}"/>'
                f'<polygon class="p r{lvl}" points="{pts(right_face)}"/>'
                f'<polygon class="p t{lvl}" points="{pts(top_face)}"/>'
                f'</g>'
            )

    parts.append("<g>\n    " + "\n    ".join(pillars) + "\n  </g>")

    leg_y = H - 18
    parts.append(f'<text x="26" y="{leg_y}" class="muted tiny">Less</text>')
    for i in range(5):
        lx = 62 + i * 15
        parts.append(
            f'<rect x="{lx}" y="{leg_y - 9}" width="10" height="10" rx="2" '
            f'fill="{t["iso"][i][0]}" stroke="{t["border"]}" stroke-width="0.5"/>'
        )
    parts.append(f'<text x="142" y="{leg_y}" class="muted tiny">More</text>')
    parts.append(
        f'<text x="{W - 26}" y="{leg_y}" text-anchor="end" class="muted tiny">'
        f'click to orbit, zoom &amp; inspect in WebGL</text>'
    )

    css = f"""
    text {{ font-family: {FONT}; white-space: pre; }}
    .win {{ fill: {t['bg']}; stroke: {t['border']}; stroke-width: 1; }}
    .fg {{ fill: {t['fg']}; }}
    .muted {{ fill: {t['muted']}; }}
    .accent {{ fill: {t['accent']}; }}
    .b {{ font-weight: 700; }}
    .small {{ font-size: 12.2px; }}
    .pill-txt {{ font-size: 11px; }}
    .tiny {{ font-size: 11px; }}
    .e {{ fill: {t['iso'][0][0]}; stroke: {t['iso_empty_stroke']}; stroke-width: 0.45; }}
    .p {{ stroke: {t['iso_stroke']}; stroke-width: 0.35; stroke-linejoin: round; }}
    .t1 {{ fill: {t['iso'][1][0]}; }} .l1 {{ fill: {t['iso'][1][1]}; }} .r1 {{ fill: {t['iso'][1][2]}; }}
    .t2 {{ fill: {t['iso'][2][0]}; }} .l2 {{ fill: {t['iso'][2][1]}; }} .r2 {{ fill: {t['iso'][2][2]}; }}
    .t3 {{ fill: {t['iso'][3][0]}; }} .l3 {{ fill: {t['iso'][3][1]}; }} .r3 {{ fill: {t['iso'][3][2]}; }}
    .t4 {{ fill: {t['iso'][4][0]}; }} .l4 {{ fill: {t['iso'][4][1]}; }} .r4 {{ fill: {t['iso'][4][2]}; }}
    .peak {{ animation: shimmer 3.6s ease-in-out infinite; }}
    @keyframes shimmer {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.78; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .peak {{ animation: none !important; opacity: 1; }}
    }}"""

    defs = f"""<defs>
    <clipPath id="sframe"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="10"/></clipPath>
  </defs>"""

    body = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="st">
  <title id="st">{escape(data['username'])} — 3D contribution skyline</title>
  <style>{css}
  </style>
  {defs}
  <g clip-path="url(#sframe)">
  {body}
  </g>
</svg>
"""


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    data = fetch_github_data(now)

    ASSETS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    for theme_name in THEMES:
        term_path = ASSETS / f"terminal-{theme_name}.svg"
        term_path.write_text(build_terminal_svg(theme_name, data), encoding="utf-8")
        print(f"wrote {term_path.relative_to(ROOT)}")

        sky_path = ASSETS / f"skyline-{theme_name}.svg"
        sky_path.write_text(build_skyline_svg(theme_name, data), encoding="utf-8")
        print(f"wrote {sky_path.relative_to(ROOT)}")

    data_path = DOCS / "data.json"
    data_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {data_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

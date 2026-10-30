#!/usr/bin/env python3
"""Generate assets/terminal-{dark,light}.svg — a neofetch-style card.

CSS-only animation (GitHub strips scripts from SVGs): a typed command,
info lines appearing in sequence, a glitching logo and a blinking cursor.
Edit INFO / LOGO below, then run: python3 scripts/build_terminal.py
"""

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets"
W, H = 860, 470
FS, CW, LH = 14, 8.4, 20  # font size, forced char width, line height
LOGO_LH = 16               # block glyphs need tight rows to read as solid letters
FONT = ("'JetBrains Mono','Fira Code',ui-monospace,SFMono-Regular,Menlo,"
        "Consolas,'DejaVu Sans Mono','Liberation Mono',monospace")

PROMPT = "axd@github:~$ "
COMMAND = "neofetch --flex"

LOGO = [
    " █████╗ ██╗  ██╗██████╗ ",
    "██╔══██╗╚██╗██╔╝██╔══██╗",
    "███████║ ╚███╔╝ ██║  ██║",
    "██╔══██║ ██╔██╗ ██║  ██║",
    "██║  ██║██╔╝ ██╗██████╔╝",
    "╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ",
]
MASCOT = [
    "    /\\_/\\            ",
    "   ( o.o )  < ship it ",
    "    > ^ <      v99999 ",
]

INFO = [
    ("OS", "Caffeine Linux x86_64 (unstable)"),
    ("Host", "a chair that squeaks"),
    ("Kernel", "6.9.0-sleep-deprived"),
    ("Uptime", "way too long, ∞ side quests"),
    ("Packages", "1337 (npm), 3 actually used"),
    ("Shell", "zsh + pure vibes"),
    ("Editor", "whichever one opens first"),
    ("CPU", "Brain™ i9 @ 3 coffees/hr"),
    ("GPU", "Imagination RTX 9090"),
    ("Memory", "420MiB / 69420MiB"),
    ("Bugs", "0 known (∞ unknown)"),
    ("Status", "● online, probably shipping"),
]

THEMES = {
    "dark": dict(bg="#0d1117", bar="#161b22", border="#30363d", fg="#e6edf3",
                 dim="#8b949e", key="#58a6ff", user="#7ee787", accent="#d2a8ff",
                 g1="#79c0ff", g2="#d2a8ff", g3="#ff7b72", gl1="#ff2e88", gl2="#00e5ff",
                 scan="#58a6ff", scan_op="0.07", glow="2.2"),
    "light": dict(bg="#ffffff", bar="#f6f8fa", border="#d0d7de", fg="#1f2328",
                  dim="#656d76", key="#0969da", user="#1a7f37", accent="#8250df",
                  g1="#0969da", g2="#8250df", g3="#cf222e", gl1="#ff2e88", gl2="#00b8d4",
                  scan="#0969da", scan_op="0.04", glow="0"),
}
PALETTE = ["#ff7b72", "#ffa657", "#e3b341", "#7ee787", "#79c0ff", "#58a6ff", "#d2a8ff", "#f778ba"]


def mono(x, y, text, cls="", style="", extra=""):
    """Monospace text forced to an exact width so columns always line up."""
    length = len(text) * CW
    attrs = f' class="{cls}"' if cls else ""
    attrs += f' style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" textLength="{length:.1f}" '
            f'lengthAdjust="spacingAndGlyphs"{attrs}{extra}>{escape(text)}</text>')


def build(theme: str) -> str:
    t = THEMES[theme]
    x0, y_cmd = 28, 72
    type_start, type_dur = 0.4, 1.1
    reveal = type_start + type_dur + 0.25          # when output starts appearing
    logo_x, logo_y = 32, 118
    info_x = 312
    step = 0.11

    parts = []
    # Window chrome
    parts.append(f'<rect class="win" x="1" y="1" width="{W-2}" height="{H-2}" rx="12"/>')
    parts.append(f'<path class="bar" d="M1 13a12 12 0 0 1 12-12h{W-26}a12 12 0 0 1 12 12v23H1z"/>')
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        parts.append(f'<circle cx="{22 + i * 20}" cy="19" r="6" fill="{c}"/>')
    parts.append(f'<text class="dim title" x="{W/2}" y="23" text-anchor="middle">'
                 f'axd@github — zsh — {W // 10}×{H // 20}</text>')

    # Typed command: a background-coloured cover slides right one char at a time.
    cmd_x = x0 + len(PROMPT) * CW
    parts.append(f'<g>{mono(x0, y_cmd, PROMPT, "user")}{mono(cmd_x, y_cmd, COMMAND, "fg")}</g>')
    n = len(COMMAND)
    parts.append(
        f'<g class="typer" style="--w:{n * CW:.1f}px;animation: type {type_dur}s steps({n}) {type_start}s both">'
        f'<rect class="cur typecur" x="{cmd_x}" y="{y_cmd - 13}" width="{CW}" height="17"/>'
        f'<rect class="bgfill" x="{cmd_x + CW}" y="{y_cmd - 15}" width="{n * CW + 4}" height="21"/></g>')

    # Logo: base copy plus two coloured copies that only flash during the glitch.
    logo_lines = "".join(mono(logo_x, logo_y - 2 + i * LOGO_LH, line) for i, line in enumerate(LOGO))
    parts.append(f'<g class="pop" style="animation-delay:{reveal}s">'
                 f'<g class="gl gl1">{logo_lines}</g><g class="gl gl2">{logo_lines}</g>'
                 f'<g class="logo">{logo_lines}</g></g>')
    my = logo_y + len(LOGO) * LOGO_LH + 34
    for i, line in enumerate(MASCOT):
        parts.append(f'<g class="in" style="animation-delay:{reveal + 0.3 + i * step:.2f}s">'
                     f'{mono(logo_x, my + i * LH, line, "accent")}</g>')

    # Info column
    y = logo_y
    header = "axd@github"
    parts.append(f'<g class="in" style="animation-delay:{reveal:.2f}s">'
                 f'<text x="{info_x}" y="{y}"><tspan class="user b">axd</tspan>'
                 f'<tspan class="fg">@</tspan><tspan class="user b">github</tspan></text></g>')
    y += LH
    parts.append(f'<g class="in" style="animation-delay:{reveal + step:.2f}s">'
                 f'{mono(info_x, y, "─" * len(header), "dim")}</g>')
    for i, (k, v) in enumerate(INFO):
        y += LH
        d = reveal + (i + 2) * step
        parts.append(f'<g class="in" style="animation-delay:{d:.2f}s">'
                     f'{mono(info_x, y, k, "key b")}'
                     f'<text x="{info_x + 10 * CW}" y="{y}" class="fg">{escape(v)}</text></g>')

    # Colour blocks
    y += 18
    d = reveal + (len(INFO) + 2) * step
    blocks = "".join(f'<rect x="{info_x + i * 30}" y="{y}" width="26" height="14" rx="3" fill="{c}"/>'
                     for i, c in enumerate(PALETTE))
    parts.append(f'<g class="in" style="animation-delay:{d:.2f}s">{blocks}</g>')

    # Final prompt with a blinking cursor
    y_end = H - 30
    d += 0.35
    end_prompt = PROMPT + "echo $MOOD → unstoppable"
    parts.append(f'<g class="in" style="animation-delay:{d:.2f}s">'
                 f'{mono(x0, y_end, PROMPT, "user")}'
                 f'{mono(x0 + len(PROMPT) * CW, y_end, end_prompt[len(PROMPT):], "dim")}'
                 f'<rect class="cur blink" x="{x0 + len(end_prompt) * CW + 4}" y="{y_end - 13}" '
                 f'width="{CW}" height="17"/></g>')

    # CRT scanline sweep over everything
    parts.append(f'<rect class="scan" x="1" y="0" width="{W-2}" height="80" fill="url(#scan)"/>')

    css = f"""
    text {{ font-family: {FONT}; font-size: {FS}px; white-space: pre; }}
    .win {{ fill: {t['bg']}; stroke: {t['border']}; }}
    .bar {{ fill: {t['bar']}; }}
    .bgfill {{ fill: {t['bg']}; }}
    .title {{ font-size: 12px; }}
    .fg {{ fill: {t['fg']}; }} .dim {{ fill: {t['dim']}; }} .key {{ fill: {t['key']}; }}
    .user {{ fill: {t['user']}; }} .accent {{ fill: {t['accent']}; }} .b {{ font-weight: 700; }}
    .cur {{ fill: {t['fg']}; }}
    .logo {{ fill: url(#grad); filter: url(#glow); animation: jitter 5s steps(1) 3s infinite; }}
    .gl {{ opacity: 0; }}
    .gl1 {{ fill: {t['gl1']}; animation: glitch1 5s steps(1) 3s infinite; }}
    .gl2 {{ fill: {t['gl2']}; animation: glitch2 5s steps(1) 3s infinite; }}
    .typer {{ animation-fill-mode: both; }}
    .typecur {{ animation: hide 0.01s linear {reveal - 0.2:.2f}s both; }}
    .in {{ opacity: 0; animation: slidein .45s cubic-bezier(.2,.8,.2,1) both; }}
    .pop {{ opacity: 0; animation: popin .6s steps(6) both; }}
    .blink {{ animation: blink 1.1s steps(1) infinite; }}
    .scan {{ opacity: {t['scan_op']}; animation: scan 6s linear infinite; pointer-events: none; }}
    @keyframes type {{ from {{ transform: translateX(0); }} to {{ transform: translateX(var(--w)); }} }}
    @keyframes hide {{ to {{ opacity: 0; }} }}
    @keyframes slidein {{ from {{ opacity: 0; transform: translateX(-10px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes popin {{ 0% {{ opacity: 0; }} 30% {{ opacity: 1; }} 45% {{ opacity: .2; }} 60%, 100% {{ opacity: 1; }} }}
    @keyframes blink {{ 0%, 50% {{ opacity: 1; }} 51%, 100% {{ opacity: 0; }} }}
    @keyframes scan {{ from {{ transform: translateY(-80px); }} to {{ transform: translateY({H}px); }} }}
    @keyframes jitter {{
      0%, 88%, 100% {{ transform: none; }}
      89% {{ transform: translate(2px, -1px) skewX(-6deg); }}
      91% {{ transform: translate(-3px, 1px); }}
      93% {{ transform: translate(1px, 0) skewX(4deg); }}
    }}
    @keyframes glitch1 {{
      0%, 88%, 95%, 100% {{ opacity: 0; transform: none; }}
      89% {{ opacity: .85; transform: translate(-5px, 1px) skewX(8deg); }}
      91% {{ opacity: .7; transform: translate(4px, -2px); }}
      93% {{ opacity: .85; transform: translate(-2px, 0) skewX(-5deg); }}
    }}
    @keyframes glitch2 {{
      0%, 88%, 95%, 100% {{ opacity: 0; transform: none; }}
      89% {{ opacity: .85; transform: translate(5px, -1px) skewX(-8deg); }}
      91% {{ opacity: .7; transform: translate(-4px, 2px); }}
      93% {{ opacity: .85; transform: translate(3px, 1px) skewX(5deg); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, .in, .pop {{ animation: none !important; opacity: 1; }}
      .gl, .scan, .typer {{ display: none; }}
    }}"""

    defs = f"""<defs>
    <linearGradient id="grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{t['g1']}"/><stop offset=".55" stop-color="{t['g2']}"/>
      <stop offset="1" stop-color="{t['g3']}"/>
    </linearGradient>
    <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{t['scan']}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{t['scan']}" stop-opacity="1"/>
      <stop offset="1" stop-color="{t['scan']}" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur stdDeviation="{t['glow']}" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="frame"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="12"/></clipPath>
  </defs>"""

    body = "\n  ".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t">
  <title id="t">axd@github — neofetch-style profile card</title>
  <style>{css}
  </style>
  {defs}
  <g clip-path="url(#frame)">
  {body}
  </g>
</svg>
"""


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name in THEMES:
        path = OUT / f"terminal-{name}.svg"
        path.write_text(build(name), encoding="utf-8")
        print(f"wrote {path.relative_to(OUT.parent)}")

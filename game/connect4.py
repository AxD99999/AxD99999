#!/usr/bin/env python3
"""Issue-driven Connect Four for a GitHub profile README.

A friend clicks a column link in the README, which opens a pre-filled issue
titled ``c4|drop|<col>`` (or ``c4|reset``). The workflow in
.github/workflows/connect4.yml calls this script, which validates the move,
updates game/state.json, re-renders the board between the README markers and
writes the reply comment to a file. Plain stdlib Python, no dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROWS, COLS = 6, 7
EMPTY, RED, YELLOW = ".", "R", "Y"
NAMES = {RED: "🔴 Red", YELLOW: "🟡 Yellow"}
DISCS = {EMPTY: "⚪", RED: "🔴", YELLOW: "🟡"}
WIN_DISCS = {RED: "🟥", YELLOW: "🟨"}

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "game" / "state.json"
README_PATH = ROOT / "README.md"
START, END = "<!-- C4:START -->", "<!-- C4:END -->"
DEFAULT_REPO = "AxD99999/AxD99999"

DROP_RE = re.compile(r"^c4\|drop\|(\d+)$")
RESET_RE = re.compile(r"^c4\|reset$")


class IllegalMove(Exception):
    pass


# ---------------------------------------------------------------- pure logic

def new_board() -> list[list[str]]:
    return [[EMPTY] * COLS for _ in range(ROWS)]


def drop(board: list[list[str]], col: int, piece: str) -> int:
    """Drop ``piece`` into 0-based ``col``; return the row it lands in."""
    if not 0 <= col < COLS:
        raise IllegalMove(f"Column must be between 1 and {COLS}.")
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] == EMPTY:
            board[row][col] = piece
            return row
    raise IllegalMove(f"Column {col + 1} is full.")


def winning_cells(board: list[list[str]], row: int, col: int) -> list[list[int]]:
    """Cells of a 4+ line through (row, col), or [] if that disc didn't win."""
    piece = board[row][col]
    if piece == EMPTY:
        return []
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        line = [[row, col]]
        for sign in (1, -1):
            r, c = row + dr * sign, col + dc * sign
            while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == piece:
                line.append([r, c])
                r, c = r + dr * sign, c + dc * sign
        if len(line) >= 4:
            return sorted(line)
    return []


def is_full(board: list[list[str]]) -> bool:
    return all(cell != EMPTY for cell in board[0])


def new_state(previous: dict | None = None) -> dict:
    stats = (previous or {}).get("stats") or {
        "games": 0, "red_wins": 0, "yellow_wins": 0, "draws": 0, "players": {},
    }
    game_id = (previous or {}).get("game_id", 0) + 1
    return {
        "game_id": game_id,
        "board": new_board(),
        "turn": RED,
        "status": "playing",  # playing | won | draw
        "winner": None,
        "win_cells": [],
        "moves": [],
        "stats": stats,
    }


def play(state: dict, col: int, user: str, issue: int | None = None) -> str:
    """Apply a 0-based column move to ``state`` in place. Returns a reply."""
    if state["status"] != "playing":
        raise IllegalMove("This game is already over. Start a new one with a reset.")
    piece = state["turn"]
    row = drop(state["board"], col, piece)
    state["moves"].append({"user": user, "col": col + 1, "piece": piece, "issue": issue})
    players = state["stats"]["players"]
    players[user] = players.get(user, 0) + 1

    cells = winning_cells(state["board"], row, col)
    if cells:
        state.update(status="won", winner=piece, win_cells=cells)
        stats = state["stats"]
        stats["games"] += 1
        stats["red_wins" if piece == RED else "yellow_wins"] += 1
        return f"🏆 **{NAMES[piece]} wins!** @{user} sealed it in column {col + 1}. GG!"
    if is_full(state["board"]):
        state["status"] = "draw"
        state["stats"]["games"] += 1
        state["stats"]["draws"] += 1
        return f"🤝 Board's full — it's a **draw**. @{user} played the final disc."
    state["turn"] = YELLOW if piece == RED else RED
    return (f"✅ @{user} dropped {DISCS[piece]} into column {col + 1}. "
            f"{NAMES[state['turn']]} is up next!")


def handle(state: dict, title: str, user: str, owner: str,
           issue: int | None = None) -> tuple[dict, str, bool]:
    """Route an issue title. Returns (state, reply, changed)."""
    title = title.strip().lower().replace(" ", "")
    if m := DROP_RE.match(title):
        try:
            reply = play(state, int(m.group(1)) - 1, user, issue)
        except IllegalMove as e:
            return state, f"🚫 Illegal move: {e}", False
        return state, reply, True
    if RESET_RE.match(title):
        if state["status"] == "playing" and state["moves"] and user.lower() != owner.lower():
            return state, ("🚫 A game is still in progress — only the repo owner can "
                           "reset mid-game. Finish it off first!"), False
        fresh = new_state(state)
        return fresh, f"🔄 @{user} started game #{fresh['game_id']}. 🔴 Red goes first!", True
    return state, ("🤔 I didn't understand that. Use the column links in the README "
                   "(titles look like `c4|drop|4` or `c4|reset`)."), False


# ---------------------------------------------------------------- rendering

def issue_url(repo: str, title: str) -> str:
    body = "Just hit Create - a bot will play your move and close this issue."
    return (f"https://github.com/{repo}/issues/new"
            f"?title={quote(title, safe='')}&body={quote(body, safe='')}")


def render(state: dict, repo: str) -> str:
    board, playing = state["board"], state["status"] == "playing"
    win = {tuple(c) for c in state["win_cells"]}
    out = ['<div align="center">', "", "### 🎮 Connect Four — the internet vs. itself", ""]

    if playing:
        out.append(f"**Game #{state['game_id']} · move {len(state['moves']) + 1} · "
                   f"{NAMES[state['turn']]} to play** — click a column to drop a disc ⬇️")
    elif state["status"] == "won":
        out.append(f"**Game #{state['game_id']} · {NAMES[state['winner']]} wins! 🏆** "
                   f"— [start a new game]({issue_url(repo, 'c4|reset')})")
    else:
        out.append(f"**Game #{state['game_id']} · draw 🤝** "
                   f"— [start a new game]({issue_url(repo, 'c4|reset')})")
    out.append("")

    header = []
    for c in range(COLS):
        if playing and board[0][c] == EMPTY:
            header.append(f"[**{c + 1}**]({issue_url(repo, f'c4|drop|{c + 1}')})")
        else:
            header.append(f"{c + 1}")
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + ":-:|" * COLS)
    for r in range(ROWS):
        cells = [WIN_DISCS[board[r][c]] if (r, c) in win else DISCS[board[r][c]]
                 for c in range(COLS)]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    out.append("<sub>Clicking a column opens a pre-filled issue — just hit <b>Create</b>. "
               "A bot plays it in ~30s and refreshes this board. Anyone can play either colour.</sub>")
    out.append("")
    out.append("</div>")
    out.append("")

    stats = state["stats"]
    out.append("<details><summary><b>📜 Recent moves &amp; 🏆 hall of fame</b></summary>")
    out.append("")
    if state["moves"]:
        out.append("| # | Player | Disc | Column |")
        out.append("|:-:|:--|:-:|:-:|")
        total = len(state["moves"])
        for i, mv in enumerate(reversed(state["moves"][-5:])):
            out.append(f"| {total - i} | [@{mv['user']}](https://github.com/{mv['user']}) "
                       f"| {DISCS[mv['piece']]} | {mv['col']} |")
    else:
        out.append("_No moves yet this game — be the first!_")
    out.append("")
    out.append(f"**Games finished:** {stats['games']} · 🔴 {stats['red_wins']} · "
               f"🟡 {stats['yellow_wins']} · 🤝 {stats['draws']}")
    out.append("")
    top = sorted(stats["players"].items(), key=lambda kv: (-kv[1], kv[0].lower()))[:5]
    if top:
        out.append("**Most moves:** " + " · ".join(
            f"[@{u}](https://github.com/{u}) ({n})" for u, n in top))
        out.append("")
    out.append("</details>")
    return "\n".join(out)


def update_readme(state: dict, repo: str, path: Path = README_PATH) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit(f"README is missing the {START} / {END} markers")
    block = f"{START}\n{render(state, repo)}\n{END}"
    path.write_text(pattern.sub(lambda _: block, text), encoding="utf-8")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return new_state()


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- CLI

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    mv = sub.add_parser("move", help="apply an issue title as a move")
    mv.add_argument("--title", required=True)
    mv.add_argument("--user", required=True)
    mv.add_argument("--owner", required=True)
    mv.add_argument("--issue", type=int)
    mv.add_argument("--comment-out", type=Path, required=True)
    sub.add_parser("render", help="re-render the README from game/state.json")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)

    state = load_state()
    if args.cmd == "render":
        save_state(state)
        update_readme(state, repo)
        return

    state, reply, changed = handle(state, args.title, args.user, args.owner, args.issue)
    if changed:
        save_state(state)
        update_readme(state, repo)
    profile = f"https://github.com/{repo.split('/')[0]}"
    args.comment_out.write_text(f"{reply}\n\n[↩️ Back to the board]({profile})\n",
                                encoding="utf-8")
    print(reply)


if __name__ == "__main__":
    main()

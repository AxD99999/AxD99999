#!/usr/bin/env python3
"""Quick checks for the Connect Four engine. Run: python3 game/test_connect4.py"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import connect4 as c4  # noqa: E402

OWNER = "AxD99999"


def play_cols(cols, user="friend"):
    state = c4.new_state()
    reply = ""
    for col in cols:
        state, reply, changed = c4.handle(state, f"c4|drop|{col}", user, OWNER)
        assert changed, reply
    return state, reply


def test_horizontal_win():
    state, reply = play_cols([1, 1, 2, 2, 3, 3, 4])
    assert state["status"] == "won" and state["winner"] == c4.RED, state
    assert state["win_cells"] == [[5, 0], [5, 1], [5, 2], [5, 3]]
    assert "wins" in reply and state["stats"]["red_wins"] == 1


def test_vertical_win():
    state, _ = play_cols([1, 2, 1, 2, 1, 2, 1])
    assert state["winner"] == c4.RED and len(state["win_cells"]) == 4


def test_diagonal_wins():
    def board_from(rows):
        return [list(r) for r in rows]

    # "/" diagonal: the final disc lands at (2,4) on top of filler.
    board = board_from([".......",
                        ".......",
                        ".......",
                        "...YR..",
                        "..YRY..",
                        ".YRRR.."])
    row = c4.drop(board, 4, c4.YELLOW)
    assert row == 2
    assert c4.winning_cells(board, row, 4) == [[2, 4], [3, 3], [4, 2], [5, 1]]

    # "\" diagonal, completed from the middle rather than an end.
    board = board_from([".......",
                        ".......",
                        "R......",
                        "YR.....",
                        "YY.R...",
                        "YYRRY.."])
    row = c4.drop(board, 2, c4.RED)
    assert row == 4
    assert c4.winning_cells(board, row, 2) == [[2, 0], [3, 1], [4, 2], [5, 3]]

    # And through the full game flow: Red wins on a "/" diagonal.
    state, _ = play_cols([1, 2, 2, 3, 3, 4, 3, 4, 4, 7, 4])
    assert state["winner"] == c4.RED, c4.render(state, "x/y")
    assert state["win_cells"] == [[2, 3], [3, 2], [4, 1], [5, 0]]


def test_illegal_moves():
    state = c4.new_state()
    for title in ("c4|drop|0", "c4|drop|8", "c4|drop|x", "hello", "c4|drop|"):
        state, reply, changed = c4.handle(state, title, "friend", OWNER)
        assert not changed and reply.startswith(("🚫", "🤔")), (title, reply)
    for _ in range(6):
        state, _, changed = c4.handle(state, "c4|drop|1", "friend", OWNER)
        assert changed
    state, reply, changed = c4.handle(state, "c4|drop|1", "friend", OWNER)
    assert not changed and "full" in reply
    assert len(state["moves"]) == 6


def test_no_moves_after_game_over():
    state, _ = play_cols([1, 1, 2, 2, 3, 3, 4])
    state, reply, changed = c4.handle(state, "c4|drop|5", "late", OWNER)
    assert not changed and "over" in reply


def test_draw():
    # Fills the board column-pair by column-pair without four in a row.
    order = [1, 2, 1, 2, 1, 2, 2, 1, 2, 1, 2, 1,
             3, 4, 3, 4, 3, 4, 4, 3, 4, 3, 4, 3,
             5, 6, 5, 6, 5, 6, 6, 5, 6, 5, 6, 5,
             7, 7, 7, 7, 7, 7]
    state, reply = play_cols(order)
    assert state["status"] == "draw", c4.render(state, "x/y")
    assert state["stats"]["draws"] == 1 and "draw" in reply


def test_reset_rules():
    state, _ = play_cols([4])
    state, reply, changed = c4.handle(state, "c4|reset", "randomfriend", OWNER)
    assert not changed and "owner" in reply
    state, _, changed = c4.handle(state, "c4|reset", "axd99999", OWNER)  # case-insensitive
    assert changed and state["game_id"] == 2 and not state["moves"]

    state, _ = play_cols([1, 1, 2, 2, 3, 3, 4])
    state, _, changed = c4.handle(state, "C4 | Reset", "anyone", OWNER)
    assert changed and state["status"] == "playing" and state["turn"] == c4.RED
    assert state["stats"]["games"] == 1, "stats survive a reset"


def test_render_and_readme_roundtrip():
    state, _ = play_cols([4, 4, 3])
    md = c4.render(state, "AxD99999/AxD99999")
    assert md.count("issues/new?title=c4%7Cdrop%7C") == 7
    assert "🟡 Yellow to play" in md
    state, _ = play_cols([1, 1, 2, 2, 3, 3, 4])
    md = c4.render(state, "AxD99999/AxD99999")
    assert "drop%7C" not in md and "c4%7Creset" in md and md.count("🟥") == 4

    with tempfile.TemporaryDirectory() as tmp:
        readme = Path(tmp) / "README.md"
        readme.write_text(f"top\n{c4.START}\nold\n{c4.END}\nbottom\n", encoding="utf-8")
        c4.update_readme(state, "AxD99999/AxD99999", readme)
        c4.update_readme(state, "AxD99999/AxD99999", readme)  # idempotent
        text = readme.read_text(encoding="utf-8")
        assert text.startswith("top\n") and text.endswith("bottom\n")
        assert "old" not in text and text.count(c4.START) == 1


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\nall {len(tests)} tests passed")

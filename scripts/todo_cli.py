#!/usr/bin/env python3
"""Simple CLI to toggle tasks in ROADMAP.md by number.

Usage:
  python scripts/todo_cli.py list
  python scripts/todo_cli.py toggle 3
  python scripts/todo_cli.py set 3 done|undone
"""
from pathlib import Path
import sys

MD = (
    Path(__file__).resolve().parents[1]
    / "documentation"
    / "plan_complexity_metric"
    / "ROADMAP.md"
)


def load_lines():
    return MD.read_text(encoding="utf-8").splitlines()


def save_lines(lines):
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def list_items():
    lines = load_lines()
    items = []
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("- [") and line.count(".") > 0:
            items.append((i, line))
    for idx, line in items:
        print(f"{idx}: {line.strip()}")


def toggle_item(number, state=None):
    lines = load_lines()
    # find Nth checklist line
    checklist_idx = []
    for i, line in enumerate(lines):
        if line.strip().startswith("- [") and line.count(".") > 0:
            checklist_idx.append(i)
    if number < 1 or number > len(checklist_idx):
        print("Invalid item number")
        return
    line_i = checklist_idx[number - 1]
    line = lines[line_i]
    if state is None:
        state = "done" if "[ ]" in line else "undone"
    if state.lower() in ("done", "true", "1", "x"):
        new = line.replace("[ ]", "[x]")
    else:
        new = line.replace("[x]", "[ ]")
    lines[line_i] = new
    save_lines(lines)
    print(f"Updated item {number}: {new.strip()}")


def usage():
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        usage()
        return
    cmd = sys.argv[1]
    if cmd == "list":
        list_items()
        return
    if cmd == "toggle" and len(sys.argv) >= 3:
        try:
            n = int(sys.argv[2])
        except:
            print("Provide an integer item number")
            return
        toggle_item(n)
        return
    if cmd == "set" and len(sys.argv) >= 4:
        try:
            n = int(sys.argv[2])
        except:
            print("Provide an integer item number")
            return
        toggle_item(n, state=sys.argv[3])
        return
    usage()


if __name__ == "__main__":
    main()

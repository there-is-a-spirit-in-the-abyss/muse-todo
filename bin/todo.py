"""Run from any directory, with no pip installation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from muse_todo.cli import main

if __name__ == '__main__':
    raise SystemExit(main())

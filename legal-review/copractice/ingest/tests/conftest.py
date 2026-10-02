import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "tests"))
from dbfixtures import conn, db_url  # noqa: E402,F401  (shared throwaway database fixtures)

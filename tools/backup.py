"""SQLite online backup using the SQLite backup API (safe with WAL readers/writers)."""

from __future__ import annotations

import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vietgeo import db


def main():
    folder = db.ROOT / "backups"
    folder.mkdir(exist_ok=True)
    out = folder / ("vietgeo-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + ".sqlite3")
    with closing(db.connect()) as c:
        db.backup(c, out)
    import sqlite3

    with sqlite3.connect(out) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check FAILED")
    print("Backup OK:", out)


if __name__ == "__main__":
    main()

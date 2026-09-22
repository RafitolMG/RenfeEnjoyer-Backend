"""Import profiles from the legacy Tkinter SQLite database.

The legacy schema stored values under mismatched column names: `add_user` was called as
`add_user(user, mail, ctr, abono)` against `(username, password, email, abono)`, so the
`password` column holds the email and the `email` column holds the password. This import
swaps them back into the correctly named fields.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from sqlmodel import Session, select

from app.db.models import User
from app.db.session import engine, init_db

DEFAULT_LEGACY_DB = Path(__file__).resolve().parents[2] / "renfe_enjoyer_database.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-db", type=Path, default=DEFAULT_LEGACY_DB)
    args = parser.parse_args()

    if not args.legacy_db.exists():
        print(f"No legacy database at {args.legacy_db}", file=sys.stderr)
        return 1

    with sqlite3.connect(args.legacy_db) as legacy:
        rows = legacy.execute(
            "SELECT username, password, email, abono FROM users"
        ).fetchall()

    init_db()
    imported = skipped = 0
    with Session(engine) as session:
        for username, legacy_password, legacy_email, abono in rows:
            already_present = session.exec(
                select(User).where(User.username == username)
            ).first()
            if already_present is not None:
                skipped += 1
                continue

            session.add(
                User(
                    username=username,
                    email=legacy_password,
                    password=legacy_email,
                    abono=abono,
                )
            )
            imported += 1
        session.commit()

    print(f"Imported {imported} profile(s), skipped {skipped} already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

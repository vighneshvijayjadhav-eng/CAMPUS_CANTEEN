"""Owner-operated provisioning, never a public registration endpoint."""

import argparse
import getpass
import os

from sqlalchemy import select

from app.core.db import connect, session_for
from app.modules.identity.models import StaffAccount
from app.modules.identity.service import hasher
from app.modules.menu.models import Canteen, Station


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("canteen", choices=["coe", "ioit"])
    parser.add_argument("username")
    parser.add_argument("--station", help="Existing station UUID; omit for canteen admin")
    args = parser.parse_args()
    password = getpass.getpass("New password (at least 14 characters): ")
    if len(password) < 14 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Password too short or confirmation does not match")
    with session_for(connect(os.environ["DATABASE_URL"])) as db, db.begin():
        canteen = db.scalar(select(Canteen).where(Canteen.slug == args.canteen))
        if not canteen:
            raise SystemExit("Seed the canteen first")
        if args.station:
            station = db.get(Station, args.station)
            if not station or station.canteen_id != canteen.id or not station.active:
                raise SystemExit("Station does not belong to this canteen or is disabled")
        username = args.username.strip().lower()
        if not username or len(username) > 160:
            raise SystemExit("Invalid username")
        if db.scalar(select(StaffAccount.id).where(StaffAccount.username == username)):
            raise SystemExit("Account already exists; use credential rotation instead")
        db.add(
            StaffAccount(
                username=username,
                password_hash=hasher.hash(password),
                canteen_id=canteen.id,
                station_id=args.station,
                role="station" if args.station else "admin",
            )
        )
    print("Account provisioned. No credentials written to files.")


if __name__ == "__main__":
    main()

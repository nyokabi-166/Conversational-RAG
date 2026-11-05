"""Create a staff account locally without exposing a public staff signup route."""

import argparse
import getpass
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from src.core.database import SessionLocal, init_db  # noqa: E402
from src.core.security import hash_password  # noqa: E402
from src.models.entities import StaffAccount  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument(
        "--role",
        choices=("policy_admin", "super_admin"),
        default=None,
    )
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Change the password for an existing staff account instead of creating one.",
    )
    args = parser.parse_args()
    username = args.username.strip().lower()
    if not username:
        parser.error("--username cannot be blank")

    password = getpass.getpass("New staff password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm staff password: ")
    if len(password) < 12:
        parser.error("Staff passwords must be at least 12 characters long")
    if password != confirmation:
        parser.error("The passwords do not match")

    init_db()
    db = SessionLocal()
    try:
        account = db.query(StaffAccount).filter_by(username=username).first()
        if account and not args.reset_existing:
            parser.error(
                f"A staff account named '{username}' already exists. "
                "Use --reset-existing to rotate its password."
            )
        if account:
            account.password_hash = hash_password(password)
            if args.full_name:
                account.full_name = args.full_name
            if args.role:
                account.role = args.role
            action = "Updated"
        else:
            account = StaffAccount(
                username=username,
                password_hash=hash_password(password),
                full_name=args.full_name,
                role=args.role or "policy_admin",
            )
            db.add(account)
            action = "Created"
        db.commit()
        print(f"{action} staff account '{username}' with role '{account.role}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

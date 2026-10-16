"""CLI tool for managing administrative users in MahaSeva AI."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from backend.auth import hash_password
from backend.database import SessionLocal
from backend.models import AdminUser


def create_or_update_admin(username: str, email: str, password: str, role: str = "admin") -> None:
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        sys.exit(1)

    with SessionLocal() as session:
        user = session.scalar(select(AdminUser).where(AdminUser.username == username))
        if user:
            print(f"Updating existing user '{username}'...")
            user.email = email
            user.hashed_password = hash_password(password)
            user.role = role
            user.is_active = True
        else:
            print(f"Creating new admin user '{username}'...")
            new_user = AdminUser(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
            )
            session.add(new_user)
        session.commit()
        print(f"Success: Admin user '{username}' ({role}) is ready.")


def list_admins() -> None:
    with SessionLocal() as session:
        users = session.scalars(select(AdminUser)).all()
        print(f"Total admin users: {len(users)}")
        for u in users:
            print(f"- ID: {u.id} | Username: {u.username} | Email: {u.email} | Role: {u.role} | Active: {u.is_active}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MahaSeva AI Admin Management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create or update an admin user")
    create_parser.add_argument("--username", required=True, help="Admin username")
    create_parser.add_argument("--email", required=True, help="Admin email")
    create_parser.add_argument("--password", required=True, help="Admin password")
    create_parser.add_argument("--role", default="admin", choices=["admin", "reviewer"], help="User role")

    subparsers.add_parser("list", help="List all admin users")

    args = parser.parse_args()
    if args.command == "create":
        create_or_update_admin(args.username, args.email, args.password, args.role)
    elif args.command == "list":
        list_admins()


if __name__ == "__main__":
    main()

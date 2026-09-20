#!/usr/bin/env python3
"""CLI utility to manage unlimited access emails for CRACK.

Usage:
  python manage_unlimited.py add <email> [reason]
  python manage_unlimited.py remove <email>
  python manage_unlimited.py list
  python manage_unlimited.py check <email>
"""
import sys
import asyncio
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.settings import UNLIMITED_ACCESS_EMAILS
from database.mongodb import db, client


async def add_email(email: str, reason: str = ""):
    norm = email.strip().lower()
    if not norm or "@" not in norm:
        print(f"Error: '{email}' is not a valid email address.")
        return 1

    now = datetime.now(timezone.utc).isoformat()
    await db.unlimited_emails.update_one(
        {"email": norm},
        {
            "$set": {
                "email": norm,
                "reason": reason or "Granted via manage_unlimited CLI",
                "added_at": now,
            }
        },
        upsert=True,
    )

    # Also update existing user doc if present
    res = await db.users.update_one(
        {"email": norm},
        {"$set": {"is_unlimited": True, "updated_at": now}},
    )
    user_status = " (linked to existing user account)" if res.matched_count else " (user account not yet registered)"
    print(f"✓ Successfully granted unlimited access to: {norm}{user_status}")
    return 0


async def remove_email(email: str):
    norm = email.strip().lower()
    if not norm:
        print("Error: email must not be empty.")
        return 1

    r1 = await db.unlimited_emails.delete_one({"email": norm})
    r2 = await db.users.update_one(
        {"email": norm},
        {"$unset": {"is_unlimited": ""}},
    )

    if norm in UNLIMITED_ACCESS_EMAILS:
        print(f"⚠ Note: '{norm}' is still configured in UNLIMITED_ACCESS_EMAILS environment variable.")
        print("  To completely revoke, also remove it from your .env file.")

    if r1.deleted_count or r2.modified_count:
        print(f"✓ Removed '{norm}' from database unlimited access records.")
    else:
        print(f"ℹ No database unlimited record found for '{norm}'.")
    return 0


async def list_emails():
    print("=" * 60)
    print("CRACK Unlimited Access Accounts")
    print("=" * 60)

    # From environment
    print(f"\n1. From Environment (.env: UNLIMITED_ACCESS_EMAILS):")
    if UNLIMITED_ACCESS_EMAILS:
        for e in sorted(UNLIMITED_ACCESS_EMAILS):
            print(f"  • {e}")
    else:
        print("  (None configured in .env)")

    # From MongoDB unlimited_emails collection
    print(f"\n2. From Database ('unlimited_emails' collection):")
    cursor = db.unlimited_emails.find({}, {"_id": 0})
    db_emails = await cursor.to_list(length=500)
    if db_emails:
        for doc in sorted(db_emails, key=lambda x: x.get("email", "")):
            added = doc.get("added_at", "N/A")
            reason = doc.get("reason", "")
            print(f"  • {doc.get('email')}  (added: {added}, reason: {reason})")
    else:
        print("  (No database records)")

    # From db.users flag
    print(f"\n3. Users with is_unlimited=True flag in 'users' collection:")
    user_cursor = db.users.find({"is_unlimited": True}, {"_id": 0, "email": 1, "id": 1})
    users = await user_cursor.to_list(length=500)
    if users:
        for u in users:
            print(f"  • {u.get('email')} (id: {u.get('id')})")
    else:
        print("  (No users with direct flag)")
    print("=" * 60)
    return 0


async def check_email(email: str):
    norm = email.strip().lower()
    from utils.subscription import is_unlimited_email
    has_unlimited = await is_unlimited_email(norm)

    print(f"Email: {norm}")
    print(f"Unlimited Access: {'YES ✓' if has_unlimited else 'NO ✗'}")
    if has_unlimited:
        reasons = []
        if norm in UNLIMITED_ACCESS_EMAILS:
            reasons.append("Configured in UNLIMITED_ACCESS_EMAILS (.env)")
        db_doc = await db.unlimited_emails.find_one({"email": norm})
        if db_doc:
            reasons.append(f"Listed in db.unlimited_emails (reason: {db_doc.get('reason', 'N/A')})")
        user = await db.users.find_one({"email": norm})
        if user and user.get("is_unlimited"):
            reasons.append("User document has is_unlimited=True")
        for r in reasons:
            print(f"  Source: {r}")
    return 0


async def main():
    parser = argparse.ArgumentParser(description="Manage unlimited access emails for CRACK")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_p = subparsers.add_parser("add", help="Grant unlimited access to an email")
    add_p.add_argument("email", help="Email address to grant unlimited access")
    add_p.add_argument("reason", nargs="?", default="", help="Optional reason / note")

    rm_p = subparsers.add_parser("remove", help="Revoke unlimited access from an email in DB")
    rm_p.add_argument("email", help="Email address to revoke")

    subparsers.add_parser("list", help="List all emails with unlimited access")

    chk_p = subparsers.add_parser("check", help="Check if an email has unlimited access")
    chk_p.add_argument("email", help="Email address to check")

    args = parser.parse_args()

    try:
        if args.command == "add":
            return await add_email(args.email, args.reason)
        elif args.command == "remove":
            return await remove_email(args.email)
        elif args.command == "list":
            return await list_emails()
        elif args.command == "check":
            return await check_email(args.email)
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

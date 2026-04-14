"""
Password Migration Script
=========================
Run this ONCE to convert plain-text passwords in the admin_users table to bcrypt hashes.

Usage:
    python migrate_passwords.py

Safe to run multiple times — already-hashed passwords (starting with '$2b$') are skipped.
"""

import bcrypt
import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Monster",
    "database": "sign_language_db"
}

def migrate():
    db = mysql.connector.connect(**DB_CONFIG)
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id, username, password_hash FROM admin_users")
    users = cursor.fetchall()

    migrated = 0
    skipped = 0

    for user in users:
        plain = user["password_hash"]

        # Skip already hashed passwords
        if plain.startswith("$2b$") or plain.startswith("$2a$"):
            print(f"  [SKIP] {user['username']} — already hashed")
            skipped += 1
            continue

        hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "UPDATE admin_users SET password_hash = %s WHERE id = %s",
            (hashed, user["id"])
        )
        print(f"  [OK]   {user['username']} — password hashed")
        migrated += 1

    db.commit()
    cursor.close()
    db.close()

    print(f"\nDone. Migrated: {migrated} | Skipped (already hashed): {skipped}")

if __name__ == "__main__":
    print("Starting password migration...\n")
    migrate()

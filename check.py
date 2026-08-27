import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

from apex_api import ApexAPI, ApexAPIError

API_KEY = os.environ.get("APEX_API_KEY")
if not API_KEY:
    print("set APEX_API_KEY env var", file=sys.stderr)
    sys.exit(2)

CACHE_DIR = Path.home() / ".cache" / "apex-check"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = CACHE_DIR / "accounts.db"

VALID_PLATFORMS = {"PC", "PS4", "X1"}

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                platform TEXT NOT NULL,
                username TEXT NOT NULL,
                last_seen INTEGER,
                status TEXT DEFAULT 'unknown',
                checked_at INTEGER DEFAULT 0,
                PRIMARY KEY (platform, username)
            )
            """
        )
        conn.commit()

def add_account(platform: str, username: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO accounts (platform, username) VALUES (?, ?)",
            (platform, username),
        )
        conn.commit()
    print(f"added {platform}/{username}")

def remove_account(platform: str, username: str):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM accounts WHERE platform = ? AND username = ?",
            (platform, username),
        )
        conn.commit()
    if cur.rowcount:
        print(f"removed {platform}/{username}")
    else:
        print(f"not found: {platform}/{username}")

def list_accounts():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT platform, username, status, last_seen, checked_at FROM accounts ORDER BY platform, username"
        )
        rows = cur.fetchall()
    if not rows:
        print("no accounts tracked. add one with --add <platform>:<username>")
        return
    print(f"{'platform':8} {'username':20} {'status':12} {'last_seen':10} {'checked':10}")
    print("-" * 64)
    for platform, username, status, last_seen, checked_at in rows:
        seen = time.strftime("%Y-%m-%d", time.localtime(last_seen)) if last_seen else "never"
        checked = time.strftime("%Y-%m-%d", time.localtime(checked_at)) if checked_at else "never"
        print(f"{platform:8} {username:20} {status:12} {seen:10} {checked:10}")

def _resolve_status(data: dict) -> str:
    if data.get("Error"):
        return "not_found"
    return "active"

def check_single(platform: str, username: str, *, store: bool = False):
    api = ApexAPI(API_KEY)
    try:
        data = api.get_player(platform, username)
    except ApexAPIError as e:
        print(f"{platform}/{username}: {e.status}")
        status = e.status
    except Exception:
        print(f"{platform}/{username}: error")
        status = "error"
    else:
        status = _resolve_status(data)
        print(f"{platform}/{username}: {status}")

    if store:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO accounts (platform, username, status, checked_at, last_seen) VALUES (?, ?, ?, ?, ?)",
                (platform, username, status, int(time.time()), int(time.time())),
            )
            conn.commit()

def update_accounts():
    api = ApexAPI(API_KEY)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT platform, username FROM accounts")
        rows = cur.fetchall()

    if not rows:
        print("no accounts tracked. add one with --add <platform>:<username>")
        return

    for platform, username in rows:
        try:
            data = api.get_player(platform, username)
        except ApexAPIError as e:
            status = e.status
        except Exception:
            status = "error"
        else:
            status = _resolve_status(data)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE accounts SET status = ?, checked_at = ?, last_seen = ? WHERE platform = ? AND username = ?",
                (status, int(time.time()), int(time.time()), platform, username),
            )
            conn.commit()
        print(f"{platform}/{username}: {status}")

def main():
    parser = argparse.ArgumentParser(description="check apex account status")
    parser.add_argument("--add", dest="add", help="add account as PLATFORM:USERNAME")
    parser.add_argument("--remove", dest="remove", help="remove account as PLATFORM:USERNAME")
    parser.add_argument("--update", action="store_true", help="check all tracked accounts")
    parser.add_argument("--list", action="store_true", help="list tracked accounts")
    parser.add_argument("--check", dest="check", help="check single account as PLATFORM:USERNAME")
    args = parser.parse_args()

    init_db()

    if args.add:
        if ":" not in args.add:
            print("use PLATFORM:USERNAME", file=sys.stderr)
            sys.exit(2)
        platform, username = args.add.split(":", 1)
        platform = platform.upper()
        if platform not in VALID_PLATFORMS:
            print(f"invalid platform {platform}, expected one of {VALID_PLATFORMS}", file=sys.stderr)
            sys.exit(2)
        add_account(platform, username)
    elif args.remove:
        if ":" not in args.remove:
            print("use PLATFORM:USERNAME", file=sys.stderr)
            sys.exit(2)
        platform, username = args.remove.split(":", 1)
        remove_account(platform.upper(), username)
    elif args.check:
        if ":" not in args.check:
            print("use PLATFORM:USERNAME", file=sys.stderr)
            sys.exit(2)
        platform, username = args.check.split(":", 1)
        platform = platform.upper()
        if platform not in VALID_PLATFORMS:
            print(f"invalid platform {platform}, expected one of {VALID_PLATFORMS}", file=sys.stderr)
            sys.exit(2)
        check_single(platform, username, store=True)
    elif args.update:
        update_accounts()
    elif args.list:
        list_accounts()
    else:
        list_accounts()

if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        sys.exit(130)

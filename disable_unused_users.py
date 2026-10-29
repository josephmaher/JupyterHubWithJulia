#!/usr/bin/env python3
"""
Find TLJH/JupyterHub users who have never logged in, and (optionally)
disable them by deleting them from the hub and/or locking their Unix account.

Detection: GET /hub/api/users -> users with last_activity == null are
considered "never logged in". Admins and users with running servers are
always skipped. A minimum account age (--older-than-days) protects
recently-added users who just haven't logged in *yet*.

Default is a DRY RUN: it only prints what it would do.
Pass --apply to actually delete/lock.

Authentication (in order of precedence):
  1. --token / $JUPYTERHUB_TOKEN, if set
  2. the token file (default /etc/jupyterhub-cleanup-token)
  3. BOOTSTRAP: if the token file does not exist and we are root, the
     script generates a token, writes it to the token file (mode 0600),
     registers a 'user-cleanup' hub service with the 'admin:users' scope
     via a snippet in /opt/tljh/config/jupyterhub_config.d/, and runs
     'tljh-config reload' (this briefly restarts the hub process; running
     user servers and kernels are not affected).

Examples:
    # first run as root: bootstraps the token, then dry-runs
    sudo ./disable_unused_users.py

    # actually delete hub users never seen, created >= 14 days ago,
    # and lock any matching Unix accounts
    sudo ./disable_unused_users.py --older-than-days 14 --apply --lock-unix

Written by claude Fable 5 with minor edits by Joseph Maher
"""

import argparse
import datetime as dt
import json
import os
import pwd
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error

DEFAULT_TOKEN_FILE = "/etc/jupyterhub-cleanup-token"
SNIPPET_DIR = "/opt/tljh/config/jupyterhub_config.d"
SNIPPET_PATH = os.path.join(SNIPPET_DIR, "user-cleanup-service.py")

# The hub-side config snippet reads the token from the token file at hub
# startup, so rotating the token only requires rewriting the file + reload.
SNIPPET_TEMPLATE = '''\
# Registers an API token for the user-cleanup script (disable_unused_users.py).
# Written automatically by that script; safe to delete to revoke access
# (then run: tljh-config reload).
with open({token_file!r}) as _f:
    _cleanup_token = _f.read().strip()

_services = list(c.JupyterHub.services) if isinstance(c.JupyterHub.services, list) else []
if not any(s.get("name") == "user-cleanup" for s in _services):
    _services.append({{"name": "user-cleanup", "api_token": _cleanup_token}})
c.JupyterHub.services = _services

_roles = list(c.JupyterHub.load_roles) if isinstance(c.JupyterHub.load_roles, list) else []
if not any(r.get("name") == "user-cleanup" for r in _roles):
    _roles.append({{"name": "user-cleanup",
                    "scopes": ["admin:users"],
                    "services": ["user-cleanup"]}})
c.JupyterHub.load_roles = _roles
'''


def parse_iso(ts):
    """Parse JupyterHub ISO8601 timestamps (may end in Z, may have no tz)."""
    if not ts:
        return None
    ts = ts.replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(ts)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def api_request(url, token, method="GET", insecure=False):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {token}")
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx) as resp:
        body = resp.read().decode()
        return resp.status, (json.loads(body) if body.strip() else None)


def find_tljh_config():
    for cand in (shutil.which("tljh-config"),
                 "/opt/tljh/hub/bin/tljh-config",
                 "/usr/bin/tljh-config"):
        if cand and os.path.exists(cand):
            return cand
    return None


def bootstrap_token(token_file):
    """Create token file + hub service registration, reload hub. Root only."""
    if os.geteuid() != 0:
        sys.exit(f"No token found and {token_file} does not exist.\n"
                 "Run as root to bootstrap it automatically, or set "
                 "$JUPYTERHUB_TOKEN / --token.")

    tljh_config = find_tljh_config()
    if tljh_config is None:
        sys.exit("Cannot bootstrap: tljh-config not found — is this the "
                 "TLJH container? Set $JUPYTERHUB_TOKEN instead.")

    print(f"[bootstrap] generating new token in {token_file}")
    token = secrets.token_hex(32)
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")

    os.makedirs(SNIPPET_DIR, exist_ok=True)
    snippet = SNIPPET_TEMPLATE.format(token_file=token_file)
    rewrite = (not os.path.exists(SNIPPET_PATH)
               or open(SNIPPET_PATH).read() != snippet)
    if rewrite:
        print(f"[bootstrap] writing hub service registration {SNIPPET_PATH}")
        with open(SNIPPET_PATH, "w") as f:
            f.write(snippet)

    print("[bootstrap] reloading the hub (tljh-config reload) — this briefly "
          "restarts the hub process; user servers keep running")
    subprocess.run([tljh_config, "reload"], check=True)
    return token


def get_token(args):
    # 1. explicit
    if args.token:
        return args.token
    # 2. token file
    if os.path.exists(args.token_file):
        with open(args.token_file) as f:
            token = f.read().strip()
        if token:
            return token
        print(f"[warn] {args.token_file} is empty; regenerating.")
    # 3. bootstrap
    return bootstrap_token(args.token_file)


def api_request_retry(url, token, insecure, attempts=6, delay=3):
    """GET with retries — the hub may still be coming back after a reload."""
    for i in range(attempts):
        try:
            return api_request(url, token, insecure=insecure)
        except urllib.error.URLError as e:
            if i == attempts - 1:
                raise
            print(f"[wait] hub not reachable yet ({e.reason}); retrying...")
            time.sleep(delay)


def unix_account_for(hub_user):
    """Best-effort guess at the TLJH system username for a hub user.

    TLJH uses 'jupyter-<name>' (long/special names get mangled with a
    hash suffix, which this does not reproduce - those are reported as
    'not found' and left alone).
    """
    candidate = f"jupyter-{hub_user}"
    try:
        pwd.getpwnam(candidate)
        return candidate
    except KeyError:
        return None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost/" + os.uname()[1] + "/hub/api",
                   help="Hub API base URL (default: %(default)s). "
                        "Use https://<fqdn>/hub/api if the hub redirects to HTTPS.")
    p.add_argument("--token", default=os.environ.get("JUPYTERHUB_TOKEN"),
                   help="Admin API token (default: $JUPYTERHUB_TOKEN, then --token-file)")
    p.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                   help="Token file to use/create (default: %(default)s)")
    p.add_argument("--older-than-days", type=int, default=7,
                   help="Only touch accounts created at least this many days ago "
                        "(default: %(default)s; 0 disables the age check)")
    p.add_argument("--apply", action="store_true",
                   help="Actually delete hub users (default: dry run)")
    p.add_argument("--lock-unix", action="store_true",
                   help="Also lock the matching jupyter-<name> Unix account with usermod -L")
    p.add_argument("--keep", action="append", default=[], metavar="NAME",
                   help="Hub username to never touch (repeatable)")
    p.add_argument("--insecure", action="store_true",
                   help="Skip TLS certificate verification (self-signed HTTPS)")
    args = p.parse_args()

    token = get_token(args)

    try:
        status, users = api_request_retry(f"{args.url}/users", token,
                                          insecure=args.insecure)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        if e.code in (401, 403):
            sys.exit(f"API auth failed ({e.code}): {detail}\n"
                     f"The hub probably doesn't know the token in {args.token_file}.\n"
                     f"Check that {SNIPPET_PATH} exists and run: tljh-config reload\n"
                     f"(or delete {args.token_file} and re-run as root to re-bootstrap).")
        sys.exit(f"API error {e.code} from {args.url}/users: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach {args.url}: {e.reason}\n"
                 "If the hub forces HTTPS, pass --url https://<fqdn>/hub/api "
                 "(add --insecure for self-signed certs).")

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=args.older_than_days)

    candidates, skipped = [], []
    for u in users:
        name = u["name"]
        reason = None
        if name in args.keep:
            reason = "on --keep list"
        elif u.get("admin"):
            reason = "admin"
        elif u.get("servers") or u.get("server"):
            reason = "server running"
        elif u.get("last_activity"):
            reason = f"active (last_activity {u['last_activity']})"
        else:
            created = parse_iso(u.get("created"))
            if args.older_than_days > 0 and created and created > cutoff:
                reason = f"too new (created {u['created']})"
        if reason:
            skipped.append((name, reason))
        else:
            candidates.append(u)

    print(f"{len(users)} hub users total; {len(candidates)} never logged in "
          f"(created > {args.older_than_days} days ago), {len(skipped)} skipped.\n")

    if not candidates:
        print("Nothing to do.")
        return

    mode = "APPLYING" if args.apply else "DRY RUN (use --apply to act)"
    print(f"--- {mode} ---")
    for u in candidates:
        name = u["name"]
        unix = unix_account_for(name)
        unix_note = f"unix account: {unix}" if unix else "no unix account"
        print(f"  {name}  (created {u.get('created')}, {unix_note})")

        if not args.apply:
            continue

        # 1. delete from the hub (removes allowed-user entry; FirstUseAuthenticator
        #    also drops the stored password via its delete_user hook)
        st, _ = api_request(f"{args.url}/users/{name}", token,
                            method="DELETE", insecure=args.insecure)
        print(f"      deleted from hub (HTTP {st})")

        # 2. optionally lock the unix account (home dir and files are untouched)
        if args.lock_unix and unix:
            r = subprocess.run(["usermod", "-L", unix],
                               capture_output=True, text=True)
            if r.returncode == 0:
                print(f"      locked unix account {unix}")
            else:
                print(f"      FAILED to lock {unix}: {r.stderr.strip()}")

    if args.apply:
        print("\nDone. Note: Unix accounts/home dirs are not deleted, only "
              "locked (if --lock-unix); hub-side the users are gone.")


if __name__ == "__main__":
    main()

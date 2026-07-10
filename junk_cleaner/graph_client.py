"""Microsoft Graph API client: auth + email operations."""
import json, time, subprocess, ssl, urllib.request, urllib.parse
from junk_cleaner.config import (
    WORKSPACE, CLIENT_ID, AUTHORITY_URL, GRAPH_BASE, JUNK_FOLDER_ID,
    FETCH_BATCH, RETRY_LIMIT, log
)

# SSL context
try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_refresh_token() -> str:
    """Read the MSAL refresh token from macOS keychain via Node.js helper."""
    helper = WORKSPACE / "get_refresh_token.js"
    if helper.exists():
        try:
            r = subprocess.run(
                ["node", str(helper)],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
            log(f"[auth] Node helper failed (exit={r.returncode}), falling back to security")
        except Exception as e:
            log(f"[auth] Node helper error: {e}, falling back to security")

    # Fallback: direct security command
    try:
        r = subprocess.run(
            ["security", "find-generic-password",
             "-s", "ms-365-mcp-server", "-a", "msal-token-cache", "-w"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            raise RuntimeError("Keychain read failed: " + r.stderr.strip())
        outer = json.loads(r.stdout.strip())
        inner = json.loads(outer["data"])
        rt_map = inner.get("RefreshToken", {})
        if not rt_map:
            raise RuntimeError("No RefreshToken in MSAL cache")
        return list(rt_map.values())[0]["secret"]
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Keychain prompt timed out. The `security -w` command needs GUI approval.\n"
            "Try running the cleaner from Terminal directly to approve the keychain dialog."
        )

def get_access_token() -> str:
    rt = get_refresh_token()
    data = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "grant_type":    "refresh_token",
        "refresh_token": rt,
        "scope":         "https://graph.microsoft.com/Mail.ReadWrite offline_access",
    }).encode()
    req = urllib.request.Request(AUTHORITY_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as resp:
        body = json.loads(resp.read())
    if "access_token" not in body:
        raise RuntimeError("Token refresh failed: " + str(body))
    log(f"[auth] Access token obtained (expires {body.get('expires_in')}s)")
    return body["access_token"]

# ── Graph API ─────────────────────────────────────────────────────────────────
def graph_get(url: str, token: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30, context=_SSL) as resp:
        return json.loads(resp.read())

def graph_delete(msg_id: str, token: str) -> bool:
    """Soft-delete (moves to Deleted Items — recoverable)."""
    url = f"{GRAPH_BASE}/messages/{msg_id}"
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            req = urllib.request.Request(url, method="DELETE")
            req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=30, context=_SSL) as resp:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return True
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", "5"))
                log(f"  [rate-limit] 429 — waiting {wait}s...")
                time.sleep(wait)
            elif e.code in (401, 403):
                log(f"  [auth] Token expired ({e.code})")
                return False
            else:
                log(f"  [warn] HTTP {e.code} attempt {attempt}")
                time.sleep(2 * attempt)
        except Exception as e:
            log(f"  [error] attempt {attempt}: {e}")
            time.sleep(2 * attempt)
    return False

def fetch_junk_batch(token: str, skip: int) -> list:
    url = (
        f"{GRAPH_BASE}/mailFolders/{JUNK_FOLDER_ID}/messages"
        f"?$top={FETCH_BATCH}&$skip={skip}"
        f"&$select=id,subject,from"
        f"&$orderby=receivedDateTime+desc"
    )
    try:
        return graph_get(url, token).get("value", [])
    except urllib.error.HTTPError as e:
        log(f"[error] fetch failed HTTP {e.code}: {e.read().decode()[:100]}")
        return []
    except Exception as e:
        log(f"[error] fetch failed: {e}")
        return []

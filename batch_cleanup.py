#!/usr/bin/env python3
"""
AI-based junk mail filter for Outlook.

Flow:
  1. Fetch emails from Junk Email folder via Graph API
  2. Fast-path: delete known-brand spam by keyword match (no LLM)
  3. Slow-path: unknown emails batched to local LLM (qwen3:8b via Ollama)
  4. Delete LLM-confirmed spam straight from junk
  5. Log everything + write heartbeat JSON

Run standalone:
  python3 ~/code/outlook-junk-cleanup/batch_cleanup.py

Orchestrated by OpenClaw cron — see cron-setup.md
"""

import json, time, subprocess, sys, ssl, re
import urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime

# ── Config (load from config.json) ────────────────────────────────────────────
WORKSPACE = Path("/Users/song/.openclaw/projects/outlook-junk-cleanup")
CONFIG_FILE = WORKSPACE / "config.json"

def load_config():
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        print(f"FATAL: {CONFIG_FILE} not found")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)

CFG = load_config()

# Extract from config
LOG_FILE        = WORKSPACE / CFG["workspace"]["log_file"]
HEARTBEAT_FILE  = WORKSPACE / CFG["workspace"]["heartbeat_file"]

CLIENT_ID       = CFG["microsoft_graph"]["client_id"]
TENANT_ID       = CFG["microsoft_graph"]["tenant_id"]
AUTHORITY_URL   = CFG["microsoft_graph"]["authority_url"]
JUNK_FOLDER_ID  = CFG["microsoft_graph"]["junk_folder_id"]
GRAPH_BASE      = "https://graph.microsoft.com/v1.0/me"

OLLAMA_URL      = CFG["ollama"]["url"]
LLM_MODEL       = CFG["ollama"]["model"]
LLM_BATCH_SIZE  = CFG["ollama"]["batch_size"]

FETCH_BATCH     = CFG["tuning"]["fetch_batch"]
DELETE_DELAY    = CFG["tuning"]["delete_delay_seconds"]
BATCH_PAUSE     = CFG["tuning"]["batch_pause_seconds"]
HEARTBEAT_EVERY = CFG["tuning"]["heartbeat_every_seconds"]
HEALTH_LOG = WORKSPACE / "ollama-health.jsonl"
RETRY_LIMIT     = CFG["tuning"]["retry_limit"]
PATTERN_THRESHOLD = CFG["tuning"]["pattern_threshold"]

# ── Known spam patterns (fast-path, no LLM needed) ───────────────────────────
# Format: { "Category": ["keyword1", "keyword2", ...] }
# Matched against: "{subject} {sender_name}".lower()
KNOWN_PATTERNS = {
    "eharmony":             ["eharmony"],
    "CarShield":            ["carshield"],
    "TruGreen":             ["trugreen"],
    "Roof":                 ["metal roof", "roof replacement", "roofing"],
    "Renewal by Andersen":  ["renewal by andersen"],
    "Healthcare.com":       ["healthcare.com"],
    "Optima Tax":           ["optima tax"],
    "National Debt Relief": ["national debt relief", "nationaldebt"],
    "Easy Canvas":          ["easy canvas", "canvas prints"],
    "Warby Parker":         ["warby parker", "warbparker"],
    "LendingForAll":        ["lendingforall"],
    "LifeLine Screening":   ["life line screening", "lifeline screening"],
    "LaserAway":            ["laseraway"],
    "Endurance Auto":       ["endurance auto"],
    "Liberty Mutual":       ["liberty mutual"],
    "Hearing Aid":          ["hearing aid", "hear.com", "soundlift"],
    "American Home Shield": ["american home shield"],
    "PhotoStick":           ["photostick"],
    "Ethos Life":           ["ethos life"],
    "VSP Vision":           ["vsp vision", " vsp "],
    "Lexington Law":        ["lexington law"],
    "AARP":                 ["aarp"],
    "Orangetheory":         ["orangetheory"],
    "BioLife Plasma":       ["biolife plasma"],
    "Blissy":               ["blissy"],
    "Saatva":               ["saatva"],
    "Jacuzzi":              ["jacuzzi bath"],
    "BetterHelp":           ["betterhelp"],
    "Destiny Mastercard":   ["destiny mastercard", "cashback rewards"],
    "TRA Services":         ["tra services", "debtcarefree"],
    "Brinks Home":          ["brinks home", "home security"],
    "Rate Equity":          ["rate equity", "home equity", "home's equity", "heloc"],
    "TheCapitalWallet":     ["capitalwallet", "capital wallet"],
    "NorthStar-Loans":      ["northstar-loans", "northstar loans"],
    "UsaWildSeaFood":       ["usawildseafood", "wild seafood"],
    "Telstra":              ["telstra"],
    "ForkFulMeals":         ["forkfulmeal", "meal delivery"],
    "TorontoFood":          ["toronto", "canada food", "perishable", "food delivery"],
    "spectaclezone":        ["spectaclezone", "relwriting", "glasses frame", "eyeglass"],
    "Fidelity Life":        ["fidelity life", "fidelity", "fidelity.com"],
    "ArenaSupreme":         ["arenasupreme", "alzheimer", "toxic mineral"],
    "PositiveInvest":       ["positiveinvestigations", "exclusive deal"],
    "Lunart Opera":         ["lunart", "内海響子", "リゴレット", "サポーター倶楽部"],
}

# ── Logging ───────────────────────────────────────────────────────────────────
_last_heartbeat = 0.0

def log(msg: str):
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def heartbeat(stats: dict, force: bool = False):
    global _last_heartbeat
    now = time.time()
    if not force and now - _last_heartbeat < HEARTBEAT_EVERY:
        return
    _last_heartbeat = now
    payload = {**stats, "ts": datetime.now().isoformat(timespec="seconds")}
    with open(HEARTBEAT_FILE, "w") as f:
        json.dump(payload, f, indent=2)

def health_log(entry: dict):
    """Append a JSON line to the Ollama health log."""
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(HEALTH_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ── System helpers ────────────────────────────────────────────────────────────
def _get_free_mem_mb() -> float:
    """Return free + inactive memory in MB (macOS)."""
    try:
        import subprocess
        r = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
        page_size = 16384
        free = inactive = 0
        for line in r.stdout.split("\n"):
            if "Pages free" in line:
                free = int(line.split(":")[1].strip().rstrip("."))
            elif "Pages inactive" in line:
                inactive = int(line.split(":")[1].strip().rstrip("."))
        return (free + inactive) * page_size / 1024 / 1024
    except:
        return 0.0

def preflight_check() -> dict:
    """Check Ollama health + system resources. Returns status dict."""
    result = {"phase": "preflight", "ollama_reachable": False,
              "ollama_ping_s": 0, "model": LLM_MODEL,
              "model_loaded": None, "inference_s": 0,
              "free_mem_mb": _get_free_mem_mb()}

    # 1. Ping Ollama API
    t0 = time.time()
    try:
        r = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        result["ollama_ping_s"] = round(time.time() - t0, 3)
        result["ollama_reachable"] = True
    except Exception as e:
        result["ollama_error"] = str(e)
        health_log(result)
        return result

    # 2. Check if model exists
    try:
        req = urllib.request.Request(
            f"http://localhost:11434/api/show",
            data=json.dumps({"name": LLM_MODEL}).encode(),
            method="POST"
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            show = json.loads(resp.read())
        result["model_loaded"] = show.get("modelfile", "") != ""
    except:
        result["model_loaded"] = False

    # 3. Quick inference test
    t0 = time.time()
    try:
        test = json.dumps({
            "model": LLM_MODEL, "stream": False,
            "options": {"num_predict": 5}, "prompt": "ping"
        }).encode()
        req2 = urllib.request.Request(OLLAMA_URL, data=test, method="POST")
        req2.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req2, timeout=30) as resp:
            td = json.loads(resp.read())
        result["inference_s"] = round(time.time() - t0, 3)
        result["load_duration_s"] = round(td.get("load_duration", 0) / 1e9, 3)
        result["eval_duration_s"] = round(td.get("eval_duration", 0) / 1e9, 3)
        result["tok_s"] = round(
            td.get("eval_count", 0) / max(td.get("eval_duration", 1), 1) * 1e9, 1)
    except Exception as e:
        result["inference_error"] = str(e)

    health_log(result)
    return result

# ── SSL context ───────────────────────────────────────────────────────────────
try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_refresh_token() -> str:
    """Read the MSAL refresh token from macOS keychain via Node.js helper.
    Falls back to direct `security` command if helper is unavailable."""
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

    # Fallback: direct security command (may hang if TCC blocks -w flag)
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
            "Try running the cleaner from Terminal directly to approve the keychain dialog, or\n"
            f"run: node {helper}"
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
                return True   # 204 No Content = success
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

# ── Fast-path pattern match ───────────────────────────────────────────────────
def fast_match(subject: str, sender_name: str, sender_email: str = ""):
    """Returns (category, True) if known spam, else (None, False).
    
    Args:
        subject: Email subject line
        sender_name: Display name from sender
        sender_email: Email address (optional, for domain verification)
    """
    # Special case: Telstra (only spam if NOT from @telstra.com.au)
    if "telstra" in sender_name.lower():
        if sender_email and "@telstra.com.au" not in sender_email.lower():
            return "Telstra", True
        elif not sender_email:
            # If we can't verify domain, assume it's spam (safer default)
            return "Telstra", True
        else:
            # Legitimate Telstra domain — not spam
            return None, False
    
    # Standard pattern matching
    text = f"{subject} {sender_name}".lower()
    for cat, keywords in KNOWN_PATTERNS.items():
        if cat == "Telstra":
            # Already handled above
            continue
        for kw in keywords:
            if kw in text:
                return cat, True
    return None, False

# ── New pattern tracking & Outlook rule creation ──────────────────────────────
NEW_PATTERNS_FILE = WORKSPACE / CFG["workspace"]["new_patterns_file"]
NEW_PATTERNS_LOG = {}

def extract_brand_from_email(subject: str, sender: str, llm_category: str = None) -> dict:
    """
    Extract brand name and keywords from subject/sender for pattern creation.
    Returns: {"brand": "...", "keywords": [...], "category": "..."}
    """
    text = f"{subject} {sender}".lower()
    
    # Extract brand from sender (if it's a legitimate company name)
    brand_candidate = sender.strip()
    if brand_candidate and not any(relay in sender.lower() for relay in 
        ["@", "ilyclicker", "pulsecertain", "comebeach", "mytontrash", 
         "henryfluns", "votalisman", "byteheroic", "popcornjoast", "ovesizzling", 
         "arraylush", "tollstank", "listbless", "hardispute", "intensenode", 
         "ovelyonto", "netbootlace", "mishresilient", "tollharsh", "randomdeprive",
         "bitversatile", "lanitem", "brown.whowascalled"]):
        brand = brand_candidate
    else:
        brand = f"[Unknown {llm_category or 'Spam'}]"
    
    # Extract keywords (first 3 meaningful tokens from subject)
    keywords = [w.strip('.,;:!?') for w in subject.split()[:5] if len(w) > 3]
    
    return {
        "brand": brand,
        "keywords": keywords[:3],
        "category": llm_category or "unknown"
    }

def track_new_pattern(email: dict, verdict_category: str):
    """
    Track new spam patterns (LLM-detected, not in KNOWN_PATTERNS).
    Log to new-patterns.txt for later review & rule creation.
    """
    pattern = extract_brand_from_email(
        email.get("subject", ""),
        email.get("sender", ""),
        verdict_category
    )
    key = pattern["brand"]
    
    if key not in NEW_PATTERNS_LOG:
        NEW_PATTERNS_LOG[key] = {
            "count": 0,
            "keywords": pattern["keywords"],
            "category": pattern["category"],
            "examples": []
        }
    
    NEW_PATTERNS_LOG[key]["count"] += 1
    if len(NEW_PATTERNS_LOG[key]["examples"]) < 2:
        NEW_PATTERNS_LOG[key]["examples"].append({
            "subject": email.get("subject", "")[:60],
            "sender": email.get("sender", "")[:40]
        })

def log_new_patterns():
    """
    Write accumulated new patterns to file for review.
    """
    if not NEW_PATTERNS_LOG:
        return
    
    with open(NEW_PATTERNS_FILE, "a") as f:
        f.write(f"\n\n=== New patterns detected {datetime.now().isoformat()} ===\n")
        for brand, data in sorted(NEW_PATTERNS_LOG.items(), key=lambda x: -x[1]["count"]):
            f.write(f"\n[{data['count']}x] {brand} ({data['category']})\n")
            f.write(f"  Keywords: {', '.join(data['keywords'])}\n")
            for ex in data["examples"]:
                f.write(f"    - {ex['subject']}\n")
                f.write(f"      from: {ex['sender']}\n")

def create_outlook_rule(brand: str, keywords: list, token: str) -> bool:
    """
    Create Outlook Inbox Rule to automatically delete emails matching this pattern.
    Rule: If (subject contains keyword1 OR keyword2) → mark as read, delete, stop.
    Returns: True if created, False if failed.
    """
    if not CFG["rules"]["auto_create_rules"]:
        return False
    
    inbox_folder_id = "inbox"  # Use well-known name
    
    rule_body = {
        "displayName": f"[AUTO] Delete {brand}",
        "sequence": CFG["rules"]["rule_sequence"],
        "isEnabled": True,
        "conditions": {
            "bodyOrSubjectContains": keywords  # At least one keyword
        },
        "actions": {
            "markAsRead": CFG["rules"]["rule_actions"]["mark_as_read"],
            "delete": CFG["rules"]["rule_actions"]["delete"],
            "stopProcessingRules": CFG["rules"]["rule_actions"]["stop_processing"]
        }
    }
    
    url = f"{GRAPH_BASE}/mailFolders/{inbox_folder_id}/messageRules"
    payload = json.dumps(rule_body).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL) as resp:
            result = json.loads(resp.read())
            log(f"  [rule-create] ✓ {brand} (keywords: {', '.join(keywords[:2])})")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 429:
            log(f"  [rule-create] Rate limit — {brand}")
        else:
            log(f"  [rule-create] Failed HTTP {e.code} — {brand}")
        return False
    except Exception as e:
        log(f"  [rule-create] Error — {brand}: {e}")
        return False

# ── LLM classification (Ollama) ───────────────────────────────────────────────
LLM_SYSTEM = """You are an email spam classifier. For each email decide: DELETE (spam/junk) or KEEP (legitimate).
Spam: unsolicited US ads, debt/loan/tax relief, home services, legal solicitation,
prize/giveaway scams, phishing, health/wellness products, dating, insurance, cosmetic/laser.
Legitimate: known contacts, purchase receipts, newsletters user signed up for.

CRITICAL: Reply ONLY with valid JSON. No markdown, no code fences, no commentary.
Example: [{"id": 1, "verdict": "DELETE", "category": "debt"}, {"id": 2, "verdict": "KEEP", "category": "receipt"}]"""

# Strip control chars from LLM responses before JSON parsing
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

def llm_classify(emails: list) -> list:
    """
    emails: list of {"id": int, "subject": str, "sender": str}
    returns list of {"id": int, "verdict": "DELETE"|"KEEP", "category": str}
    """
    _call_start = time.time()
    prompt = (
        LLM_SYSTEM
        + "\n\nEmails to classify:\n"
        + json.dumps(emails, ensure_ascii=False)
    )
    payload = json.dumps({
        "model": LLM_MODEL,
        "stream": False,
        "options": {"num_predict": 4096},
        "prompt": prompt,
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
        raw = (body.get("response") or "").strip()
        if not raw:
            log(f"  [llm] Empty response")
            return []
        # Log the raw response for debugging
        if len(raw) < 200:
            log(f"  [llm] raw: {raw}")
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not m:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            log(f"  [llm] No JSON in response: {raw[:100]}")
            return []
        # Strip control characters before parsing (qwen3 emits raw control chars in strings)
        cleaned = _CONTROL_CHARS_RE.sub('', m.group())
        results = json.loads(cleaned)
        if isinstance(results, dict):
            results = [results]
        tps = round(body.get("eval_count", 0) / max(body.get("eval_duration", 1), 1) * 1e9, 1)
        duration = round(time.time() - _call_start, 2)
        log(f"  [llm] {len(results)} classified @ {tps} tok/s ({duration}s)")
        health_log({
            "phase": "llm_call",
            "model": LLM_MODEL,
            "batch_size": len(emails),
            "duration_s": duration,
            "load_duration_s": round(body.get("load_duration", 0) / 1e9, 3),
            "eval_duration_s": round(body.get("eval_duration", 0) / 1e9, 3),
            "tok_s": tps,
            "tokens_out": body.get("eval_count", 0),
            "success": True,
        })
        return results
    except Exception as e:
        duration = round(time.time() - _call_start, 2)
        log(f"  [llm] ERROR after {duration}s: {e}")
        health_log({
            "phase": "llm_call",
            "model": LLM_MODEL,
            "batch_size": len(emails),
            "duration_s": duration,
            "success": False,
            "error": str(e)[:200],
        })
        return []

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log("=" * 60)
    log("=== Junk Mail AI Filter — starting ===")
    log(f"=== LLM: {LLM_MODEL} | Batch: {FETCH_BATCH} fetch / {LLM_BATCH_SIZE} LLM ===")
    log("=" * 60)

    # ── Pre-flight: Ollama health + system resources ────────────────────────
    pf = preflight_check()
    log(f"[preflight] Ollama reachable={pf.get('ollama_reachable')} "
        f"ping={pf.get('ollama_ping_s','?')}s "
        f"infer={pf.get('inference_s','?')}s "
        f"free_mem={pf.get('free_mem_mb',0):.0f}MB")
    if not pf.get("ollama_reachable"):
        log(f"[preflight] FATAL: Ollama not responding — {pf.get('ollama_error','')}")
        log(f"[preflight] Skipping LLM classification; will only fast-delete.")
        # Fallback: still try to fetch and fast-delete without LLM

    try:
        token = get_access_token()
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)

    stats = {"deleted": 0, "kept": 0, "fast": 0, "llm": 0,
             "llm_calls": 0, "failed": 0, "batch": 0}
    skip = 0

    try:
        while True:
            stats["batch"] += 1
            log(f"\n{'─'*50}")
            log(f"Batch {stats['batch']} — fetching {FETCH_BATCH} emails (offset={skip})")
            heartbeat(stats)

            emails = fetch_junk_batch(token, skip)
            if not emails:
                log("No more emails — done.")
                break

            log(f"Fetched {len(emails)}")

            to_delete_fast  = []   # (id, subject, category)
            to_llm          = []   # {id: int, subject, sender} for LLM
            idx_map         = {}   # local_id → msg_id

            for i, e in enumerate(emails):
                msg_id  = e["id"]
                subject = (e.get("subject") or "").strip()
                sender_name = (e.get("from", {}).get("emailAddress", {}).get("name") or "").strip()
                sender_email = (e.get("from", {}).get("emailAddress", {}).get("address") or "").strip()

                cat, matched = fast_match(subject, sender_name, sender_email)
                if matched:
                    to_delete_fast.append((msg_id, subject, cat))
                else:
                    local_id = len(to_llm) + 1
                    idx_map[local_id] = (msg_id, subject)
                    to_llm.append({"id": local_id, "subject": subject, "sender": sender_name})

            # ── Fast-path deletes ────────────────────────────────────────────
            for msg_id, subject, cat in to_delete_fast:
                ok = graph_delete(msg_id, token)
                if ok:
                    stats["deleted"] += 1
                    stats["fast"]    += 1
                    log(f"  DEL[fast/{cat}] {subject[:65]}")
                else:
                    stats["failed"] += 1
                    log(f"  FAIL {subject[:65]}")
                time.sleep(DELETE_DELAY)
                heartbeat(stats)

            # ── LLM classification of unknowns ───────────────────────────────
            ollama_ok = pf.get("ollama_reachable", False)
            if not ollama_ok:
                log(f"  [llm] SKIP — Ollama unavailable; keeping {len(to_llm)} unknowns")
                stats["kept"] += len(to_llm)
            else:
                for chunk_start in range(0, len(to_llm), LLM_BATCH_SIZE):
                    chunk = to_llm[chunk_start:chunk_start + LLM_BATCH_SIZE]
                    if not chunk:
                        break
                    log(f"  [llm] classifying {len(chunk)} unknowns...")
                    results = llm_classify(chunk)
                    stats["llm_calls"] += 1

                    # Build verdict lookup
                    verdicts = {r["id"]: r for r in results}

                    for item in chunk:
                        local_id = item["id"]
                        msg_id, subject = idx_map[local_id]
                        result = verdicts.get(local_id)

                        if not result:
                            log(f"  [llm] no verdict for id={local_id}, keeping: {subject[:50]}")
                            stats["kept"] += 1
                            continue

                        verdict  = result.get("verdict", "KEEP").upper()
                        category = result.get("category", "unknown")

                        if verdict == "DELETE":
                            ok = graph_delete(msg_id, token)
                            if ok:
                                stats["deleted"] += 1
                                stats["llm"]     += 1
                                log(f"  DEL[llm/{category}] {subject[:65]}")
                                # Track new pattern for future rule creation
                                track_new_pattern({"subject": subject, "sender": item["sender"]}, category)
                            else:
                                stats["failed"] += 1
                                log(f"  FAIL {subject[:65]}")
                            time.sleep(DELETE_DELAY)
                        else:
                            stats["kept"] += 1
                            log(f"  KEEP[llm/{category}] {subject[:65]}")

                        heartbeat(stats)

            skip += FETCH_BATCH
            if len(emails) == FETCH_BATCH:
                log(f"Batch {stats['batch']} done — pausing {BATCH_PAUSE}s...")
                time.sleep(BATCH_PAUSE)

    except KeyboardInterrupt:
        log("\n[interrupted]")
    except Exception as e:
        import traceback
        log(f"\n[fatal] {e}\n{traceback.format_exc()}")

    # ── Summary ───────────────────────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("=== COMPLETE ===")
    log(f"Deleted:    {stats['deleted']}  (fast={stats['fast']}, llm={stats['llm']})")
    log(f"Kept:       {stats['kept']}")
    log(f"Failed:     {stats['failed']}")
    log(f"LLM calls:  {stats['llm_calls']}")
    log(f"Batches:    {stats['batch']}")
    log("=" * 60 + "\n")
    
    # Log new patterns discovered for future rule creation
    if NEW_PATTERNS_LOG:
        log(f"\n[new-patterns] {len(NEW_PATTERNS_LOG)} new patterns tracked")
        log_new_patterns()
        # Create Outlook rules for high-confidence patterns (threshold from config)
        for brand, data in NEW_PATTERNS_LOG.items():
            if data["count"] >= PATTERN_THRESHOLD:
                log(f"[new-patterns] Creating rule for {brand} ({data['count']} instances)")
                create_outlook_rule(brand, data["keywords"], token)
                time.sleep(0.5)  # Rate limit
    
    heartbeat(stats, force=True)

if __name__ == "__main__":
    main()

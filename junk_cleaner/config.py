"""Config loading, shared constants, and logging utilities."""
import json, time, sys
from pathlib import Path
from datetime import datetime

# CUSTOMIZE: Set your project path below
WORKSPACE = Path("/ABSOLUTE/PATH/TO/outlook-junk-cleanup")
CONFIG_FILE = WORKSPACE / "config.json"

def load_config():
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        print(f"FATAL: {CONFIG_FILE} not found")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)

CFG = load_config()

# Derived paths
LOG_FILE        = WORKSPACE / CFG["workspace"]["log_file"]
HEARTBEAT_FILE  = WORKSPACE / CFG["workspace"]["heartbeat_file"]
HEALTH_LOG      = WORKSPACE / "ollama-health.jsonl"
NEW_PATTERNS_FILE = WORKSPACE / CFG["workspace"]["new_patterns_file"]

# Microsoft Graph config
CLIENT_ID       = CFG["microsoft_graph"]["client_id"]
TENANT_ID       = CFG["microsoft_graph"]["tenant_id"]
AUTHORITY_URL   = CFG["microsoft_graph"]["authority_url"]
JUNK_FOLDER_ID  = CFG["microsoft_graph"]["junk_folder_id"]
GRAPH_BASE      = "https://graph.microsoft.com/v1.0/me"

# Ollama config
OLLAMA_URL      = CFG["ollama"]["url"]
LLM_MODEL       = CFG["ollama"]["model"]
LLM_BATCH_SIZE  = CFG["ollama"]["batch_size"]

# Tuning
FETCH_BATCH     = CFG["tuning"]["fetch_batch"]
DELETE_DELAY    = CFG["tuning"]["delete_delay_seconds"]
BATCH_PAUSE     = CFG["tuning"]["batch_pause_seconds"]
HEARTBEAT_EVERY = CFG["tuning"]["heartbeat_every_seconds"]
RETRY_LIMIT     = CFG["tuning"]["retry_limit"]
PATTERN_THRESHOLD = CFG["tuning"]["pattern_threshold"]

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

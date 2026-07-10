"""Known spam patterns (fast-path), pattern tracking, and Outlook rule creation."""
import json, urllib.request
from datetime import datetime
from junk_cleaner.config import (
    WORKSPACE, GRAPH_BASE, NEW_PATTERNS_FILE,
    PATTERN_THRESHOLD, CFG, log
)

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

def fast_match(subject: str, sender_name: str, sender_email: str = ""):
    """Returns (category, True) if known spam, else (None, False)."""
    # Special case: Telstra (only spam if NOT from @telstra.com.au)
    if "telstra" in sender_name.lower():
        if sender_email and "@telstra.com.au" not in sender_email.lower():
            return "Telstra", True
        elif not sender_email:
            return "Telstra", True
        else:
            return None, False

    text = f"{subject} {sender_name}".lower()
    for cat, keywords in KNOWN_PATTERNS.items():
        if cat == "Telstra":
            continue
        for kw in keywords:
            if kw in text:
                return cat, True
    return None, False

# ── New pattern tracking ──────────────────────────────────────────────────────
NEW_PATTERNS_LOG = {}

def extract_brand_from_email(subject: str, sender: str, llm_category: str = None) -> dict:
    text = f"{subject} {sender}".lower()
    relay_domains = {"@", "ilyclicker", "pulsecertain", "comebeach", "mytontrash",
        "henryfluns", "votalisman", "byteheroic", "popcornjoast", "ovesizzling",
        "arraylush", "tollstank", "listbless", "hardispute", "intensenode",
        "ovelyonto", "netbootlace", "mishresilient", "tollharsh", "randomdeprive",
        "bitversatile", "lanitem", "brown.whowascalled"}

    if sender.strip() and not any(r in sender.lower() for r in relay_domains):
        brand = sender.strip()
    else:
        brand = f"[Unknown {llm_category or 'Spam'}]"

    keywords = [w.strip('.,;:!?') for w in subject.split()[:5] if len(w) > 3]
    return {"brand": brand, "keywords": keywords[:3], "category": llm_category or "unknown"}

def track_new_pattern(email: dict, verdict_category: str):
    pattern = extract_brand_from_email(
        email.get("subject", ""), email.get("sender", ""), verdict_category
    )
    key = pattern["brand"]
    if key not in NEW_PATTERNS_LOG:
        NEW_PATTERNS_LOG[key] = {
            "count": 0, "keywords": pattern["keywords"],
            "category": pattern["category"], "examples": []
        }
    NEW_PATTERNS_LOG[key]["count"] += 1
    if len(NEW_PATTERNS_LOG[key]["examples"]) < 2:
        NEW_PATTERNS_LOG[key]["examples"].append({
            "subject": email.get("subject", "")[:60],
            "sender": email.get("sender", "")[:40]
        })

def log_new_patterns():
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
    if not CFG["rules"]["auto_create_rules"]:
        return False
    rule_body = {
        "displayName": f"[AUTO] Delete {brand}",
        "sequence": CFG["rules"]["rule_sequence"],
        "isEnabled": True,
        "conditions": {"bodyOrSubjectContains": keywords},
        "actions": {
            "markAsRead": CFG["rules"]["rule_actions"]["mark_as_read"],
            "delete": CFG["rules"]["rule_actions"]["delete"],
            "stopProcessingRules": CFG["rules"]["rule_actions"]["stop_processing"]
        }
    }
    url = f"{GRAPH_BASE}/mailFolders/inbox/messageRules"
    payload = json.dumps(rule_body).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log(f"  [rule-create] OK {brand}")
            return True
    except urllib.error.HTTPError as e:
        log(f"  [rule-create] HTTP {e.code} — {brand}")
        return False
    except Exception as e:
        log(f"  [rule-create] Error — {brand}: {e}")
        return False

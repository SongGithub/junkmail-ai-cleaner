"""Ollama API client for LLM-based spam classification."""
import json, re, time, urllib.request
from junk_cleaner.config import OLLAMA_URL, LLM_MODEL, log, health_log

LLM_SYSTEM = """You are an email spam classifier. For each email decide: DELETE (spam/junk) or KEEP (legitimate).
Spam: unsolicited US ads, debt/loan/tax relief, home services, legal solicitation,
prize/giveaway scams, phishing, health/wellness products, dating, insurance, cosmetic/laser.
Legitimate: known contacts, purchase receipts, newsletters user signed up for.

CRITICAL: Reply ONLY with valid JSON. No markdown, no code fences, no commentary.
Example: [{"id": 1, "verdict": "DELETE", "category": "debt"}, {"id": 2, "verdict": "KEEP", "category": "receipt"}]"""

_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

def classify(emails: list) -> list:
    """
    Classify emails via Ollama API.
    Args:
        emails: list of {"id": int, "subject": str, "sender": str}
    Returns:
        list of {"id": int, "verdict": "DELETE"|"KEEP", "category": str}
    """
    _call_start = time.time()
    prompt = LLM_SYSTEM + "\n\nEmails to classify:\n" + json.dumps(emails, ensure_ascii=False)
    payload = json.dumps({
        "model": LLM_MODEL, "stream": False,
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
            log("  [llm] Empty response")
            return []

        if len(raw) < 200:
            log(f"  [llm] raw: {raw}")

        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if not m:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            log(f"  [llm] No JSON in response: {raw[:100]}")
            return []

        cleaned = _CONTROL_CHARS_RE.sub('', m.group())
        results = json.loads(cleaned)
        if isinstance(results, dict):
            results = [results]

        tps = round(body.get("eval_count", 0) / max(body.get("eval_duration", 1), 1) * 1e9, 1)
        duration = round(time.time() - _call_start, 2)
        log(f"  [llm] {len(results)} classified @ {tps} tok/s ({duration}s)")
        health_log({
            "phase": "llm_call", "model": LLM_MODEL,
            "batch_size": len(emails), "duration_s": duration,
            "load_duration_s": round(body.get("load_duration", 0) / 1e9, 3),
            "eval_duration_s": round(body.get("eval_duration", 0) / 1e9, 3),
            "tok_s": tps, "tokens_out": body.get("eval_count", 0), "success": True,
        })
        return results

    except Exception as e:
        duration = round(time.time() - _call_start, 2)
        log(f"  [llm] ERROR after {duration}s: {e}")
        health_log({
            "phase": "llm_call", "model": LLM_MODEL,
            "batch_size": len(emails), "duration_s": duration,
            "success": False, "error": str(e)[:200],
        })
        return []

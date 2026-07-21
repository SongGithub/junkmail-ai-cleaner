"""Main cleanup orchestration."""
import time, sys, traceback
from junk_cleaner.config import LLM_MODEL, FETCH_BATCH, LLM_BATCH_SIZE, DELETE_DELAY, BATCH_PAUSE, PATTERN_THRESHOLD, log, heartbeat
from junk_cleaner.graph_client import get_access_token, fetch_junk_batch, graph_delete
from junk_cleaner.spam_patterns import fast_match, track_new_pattern, log_new_patterns, create_outlook_rule, NEW_PATTERNS_LOG
from junk_cleaner.ollama_client import classify as llm_classify
from junk_cleaner.health_check import preflight_check


def main():
    log("=" * 60)
    log("=== Junk Mail AI Filter — starting ===")
    log(f"=== LLM: {LLM_MODEL} | Batch: {FETCH_BATCH} fetch / {LLM_BATCH_SIZE} LLM ===")
    log("=" * 60)

    pf = preflight_check()
    log(f"[preflight] Ollama reachable={pf.get('ollama_reachable')} "
        f"ping={pf.get('ollama_ping_s','?')}s "
        f"infer={pf.get('inference_s','?')}s "
        f"free_mem={pf.get('free_mem_mb',0):.0f}MB")
    if not pf.get("ollama_reachable"):
        log(f"[preflight] FATAL: Ollama not responding — {pf.get('ollama_error','')}")
        log("[preflight] Skipping LLM classification; will only fast-delete.")

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

            to_delete_fast, to_llm, idx_map = [], [], {}
            for i, e in enumerate(emails):
                msg_id = e["id"]
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

            for msg_id, subject, cat in to_delete_fast:
                ok = graph_delete(msg_id, token)
                if ok:
                    stats["deleted"] += 1
                    stats["fast"] += 1
                    log(f"  DEL[fast/{cat}] {subject[:65]}")
                else:
                    stats["failed"] += 1
                    log(f"  FAIL {subject[:65]}")
                time.sleep(DELETE_DELAY)
                heartbeat(stats)

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
                    verdicts = {r["id"]: r for r in results}
                    for item in chunk:
                        local_id = item["id"]
                        msg_id, subject = idx_map[local_id]
                        result = verdicts.get(local_id)
                        if not result:
                            log(f"  [llm] no verdict for id={local_id}, keeping: {subject[:50]}")
                            stats["kept"] += 1
                            continue
                        verdict = result.get("verdict", "KEEP").upper()
                        category = result.get("category", "unknown")
                        if verdict == "DELETE":
                            ok = graph_delete(msg_id, token)
                            if ok:
                                stats["deleted"] += 1
                                stats["llm"] += 1
                                log(f"  DEL[llm/{category}] {subject[:65]}")
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
        log(f"\n[fatal] {e}\n{traceback.format_exc()}")

    log("\n" + "=" * 60)
    log("=== COMPLETE ===")
    log(f"Deleted:    {stats['deleted']}  (fast={stats['fast']}, llm={stats['llm']})")
    log(f"Kept:       {stats['kept']}")
    log(f"Failed:     {stats['failed']}")
    log(f"LLM calls:  {stats['llm_calls']}")
    log(f"Batches:    {stats['batch']}")
    log("=" * 60 + "\n")

    if NEW_PATTERNS_LOG:
        log(f"\n[new-patterns] {len(NEW_PATTERNS_LOG)} new patterns tracked")
        log_new_patterns()
        for brand, data in NEW_PATTERNS_LOG.items():
            if data["count"] >= PATTERN_THRESHOLD:
                log(f"[new-patterns] Creating rule for {brand} ({data['count']} instances)")
                create_outlook_rule(brand, data["keywords"], token)
                time.sleep(0.5)
    heartbeat(stats, force=True)

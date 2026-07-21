#!/usr/bin/env python3
"""Golden-set evaluation for both classification tiers.

    python3 eval/run_eval.py --rules   # fast-pattern tier, offline, runs in CI
    python3 eval/run_eval.py --llm     # LLM tier, needs local Ollama

The hard gate is DELETED HAM (a false positive destroys real mail; a missed
spam just waits for the next pattern update). Ham entries with a
"known_gap" field are reported but don't fail the run — they are the
documented backlog of over-broad patterns. Removing an entry's known_gap
marker (after tightening the pattern) turns it back into a regression gate.

Exit code: 0 = gates pass, 1 = a non-known-gap ham was deleted.
"""
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Bootstrap a workspace so junk_cleaner.config imports anywhere (incl. CI)
if not (REPO_ROOT / "config.json").exists() and "JUNK_CLEANER_HOME" not in os.environ:
    tmp = Path(tempfile.mkdtemp(prefix="junk-cleaner-eval-"))
    shutil.copy(REPO_ROOT / "config.json.example", tmp / "config.json")
    os.environ["JUNK_CLEANER_HOME"] = str(tmp)

GOLDEN = [json.loads(line) for line in (REPO_ROOT / "eval" / "golden.jsonl").read_text().splitlines() if line.strip()]


def eval_rules():
    from junk_cleaner.spam_patterns import fast_match

    tp = fn = 0
    false_positives, known_gaps = [], []
    for row in GOLDEN:
        cat, matched = fast_match(row["subject"], row["sender"], row.get("sender_email", ""))
        if row["label"] == "spam":
            tp += matched
            fn += not matched
        elif matched:
            (known_gaps if row.get("known_gap") == "rules" else false_positives).append((row, cat))

    spam_total = sum(r["label"] == "spam" for r in GOLDEN)
    print(f"rules tier: {tp}/{spam_total} spam caught (recall {tp/spam_total:.0%}); "
          f"misses go to the LLM tier, so recall is informational")
    for row, cat in known_gaps:
        print(f"  KNOWN GAP  ham deleted by pattern '{cat}': {row['subject']!r} — {row.get('note', '')}")
    for row, cat in false_positives:
        print(f"  FALSE POSITIVE  ham deleted by pattern '{cat}': {row['subject']!r}")
    print(f"rules gate: {len(false_positives)} unexpected ham deletions "
          f"({len(known_gaps)} known gaps tracked)")
    return len(false_positives) == 0


def eval_llm(max_ham_fp: int, min_spam_recall: float):
    from junk_cleaner.config import LLM_BATCH_SIZE, LLM_MODEL
    from junk_cleaner.ollama_client import classify

    emails = [{"id": i + 1, "subject": r["subject"], "sender": r["sender"]} for i, r in enumerate(GOLDEN)]
    verdicts = {}
    for start in range(0, len(emails), LLM_BATCH_SIZE):
        chunk = emails[start:start + LLM_BATCH_SIZE]
        for r in classify(chunk):
            verdicts[r.get("id")] = r.get("verdict", "KEEP").upper()

    ham_fp, spam_caught, unclassified = [], 0, 0
    for i, row in enumerate(GOLDEN):
        v = verdicts.get(i + 1)
        if v is None:
            unclassified += 1
            continue
        if row["label"] == "spam" and v == "DELETE":
            spam_caught += 1
        elif row["label"] == "ham" and v == "DELETE":
            ham_fp.append(row)

    spam_total = sum(r["label"] == "spam" for r in GOLDEN)
    recall = spam_caught / spam_total
    print(f"llm tier ({LLM_MODEL}): spam recall {spam_caught}/{spam_total} ({recall:.0%}), "
          f"ham false positives {len(ham_fp)}, unclassified {unclassified}")
    for row in ham_fp:
        print(f"  FALSE POSITIVE  ham deleted: {row['subject']!r} from {row['sender']}")

    ok = len(ham_fp) <= max_ham_fp and recall >= min_spam_recall
    print(f"llm gate ({'PASS' if ok else 'FAIL'}): "
          f"ham FP {len(ham_fp)} (max {max_ham_fp}), spam recall {recall:.0%} (min {min_spam_recall:.0%})")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", action="store_true", help="evaluate the fast-pattern tier (offline)")
    ap.add_argument("--llm", action="store_true", help="evaluate the LLM tier (needs Ollama)")
    ap.add_argument("--max-ham-fp", type=int, default=0, help="LLM gate: max ham false positives")
    ap.add_argument("--min-spam-recall", type=float, default=0.6, help="LLM gate: min spam recall")
    args = ap.parse_args()
    if not (args.rules or args.llm):
        ap.error("pick at least one of --rules / --llm")

    ok = True
    if args.rules:
        ok = eval_rules() and ok
    if args.llm:
        ok = eval_llm(args.max_ham_fp, args.min_spam_recall) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/bin/bash
# Junk cleaner wrapper - runs cleanup and outputs targeted summary only
# Agent should NOT read any files directly - all needed info is here

cd /ABSOLUTE/PATH/TO/outlook-junk-cleanup

# Pre-flight health check
bash ollama_health.sh > /dev/null 2>&1

# Run cleanup (output suppressed to save agent context)
python3 batch_cleanup.py > /dev/null 2>&1

# Post-flight health check
bash ollama_health.sh > /dev/null 2>&1

# Output targeted summary (not the full log)
echo "=== HEARTBEAT ==="
cat cleanup-heartbeat.txt

echo "=== LLM-CLASSIFIED (escaped fast rules) ==="
grep "DEL\[llm/" cleanup-log.txt | tail -30

echo "=== KEPT (not deleted by any rule) ==="
grep -E "Keeping|kept|\[llm\] SKIP" cleanup-log.txt | tail -10

echo "=== NEW PATTERNS ==="
grep -E "new-patterns|\[new-patterns\]" cleanup-log.txt | tail -3

echo "=== OLLAMA HEALTH ==="
tail -2 ollama-health.jsonl

echo "=== DONE ==="

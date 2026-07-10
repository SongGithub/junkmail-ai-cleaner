#!/bin/bash
# Ollama pre-flight health check — run before the junk cleaner job.
# Logs to ollama-health.jsonl alongside batch_cleanup.py logs.
# Exit code: 0 = healthy, 1 = degraded, 2 = down

set -uo pipefail

WORKSPACE="/ABSOLUTE/PATH/TO/outlook-junk-cleanup"
HEALTH_LOG="$WORKSPACE/ollama-health.jsonl"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log_health() {
    local entry=$1
    echo "$entry" >> "$HEALTH_LOG"
    echo "$entry"
}

# 1. Ping Ollama
t0=$(date +%s)
if ! curl -sf -o /dev/null --max-time 5 http://localhost:11434/api/tags 2>/dev/null; then
    t1=$(date +%s)
    log_health "{\"ts\":\"$TIMESTAMP\",\"phase\":\"preflight\",\"script\":\"ollama_health.sh\",\"ollama_reachable\":false,\"error\":\"API not responding\",\"elapsed_s\":$((t1-t0))"
    echo "OLLAMA_DOWN"
    exit 2
fi
t1=$(date +%s)
PING_S=$((t1-t0))

# 2. Check model loaded
MODEL_NAME=$(python3 -c "import json; print(json.load(open('$WORKSPACE/config.json'))['ollama']['model'])")
LOADED=$(curl -sf http://localhost:11434/api/show -d "{\"name\":\"$MODEL_NAME\"}" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('modelfile','') else 'no')" 2>/dev/null || echo "unknown")

# 3. Quick inference test
t0=$(date +%s%N)
INFER_RESULT=$(curl -sf -X POST http://localhost:11434/api/generate \
    -d "{\"model\":\"$MODEL_NAME\",\"stream\":false,\"options\":{\"num_predict\":5},\"prompt\":\"ping\"}" 2>/dev/null)
t1=$(date +%s%N)
INFER_MS=$(( (t1 - t0) / 1000000 ))

if [ -z "$INFER_RESULT" ]; then
    log_health "{\"ts\":\"$TIMESTAMP\",\"phase\":\"preflight\",\"script\":\"ollama_health.sh\",\"ollama_reachable\":true,\"ping_s\":$PING_S,\"model\":\"$MODEL_NAME\",\"inference_ms\":$INFER_MS,\"inference_error\":\"no response\"}"
    echo "OLLAMA_DEGRADED"
    exit 1
fi

TOK_S=$(echo "$INFER_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d.get('eval_count',0)/max(d.get('eval_duration',1),1)*1e9,1))" 2>/dev/null || echo "0")
LOAD_S=$(echo "$INFER_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d.get('load_duration',0)/1e9,3))" 2>/dev/null || echo "0")

# System memory
FREE_MEM=$(python3 -c "
import subprocess
r = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)
free = inactive = 0
for line in r.stdout.split('\n'):
    if 'Pages free' in line: free = int(line.split(':')[1].strip().rstrip('.'))
    elif 'Pages inactive' in line: inactive = int(line.split(':')[1].strip().rstrip('.'))
print(round((free + inactive) * 16384 / 1024 / 1024))
" 2>/dev/null || echo "0")

log_health "{\"ts\":\"$TIMESTAMP\",\"phase\":\"preflight\",\"script\":\"ollama_health.sh\",\"ollama_reachable\":true,\"ping_s\":$PING_S,\"model\":\"$MODEL_NAME\",\"model_loaded\":\"$LOADED\",\"inference_ms\":$INFER_MS,\"load_s\":$LOAD_S,\"tok_s\":$TOK_S,\"free_mem_mb\":$FREE_MEM}"
echo "OLLAMA_OK"
exit 0

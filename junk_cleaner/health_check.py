"""Ollama health check and system resource monitoring."""
import json, time, urllib.request
from junk_cleaner.config import LLM_MODEL, OLLAMA_URL, health_log

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
    except Exception:
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
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        result["ollama_ping_s"] = round(time.time() - t0, 3)
        result["ollama_reachable"] = True
    except Exception as e:
        result["ollama_error"] = str(e)
        health_log(result)
        return result

    # 2. Check if model exists
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/show",
            data=json.dumps({"name": LLM_MODEL}).encode(),
            method="POST"
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            show = json.loads(resp.read())
        result["model_loaded"] = show.get("modelfile", "") != ""
    except Exception:
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

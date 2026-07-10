# Junkmail AI Cleaner

Automated junk mail cleanup for Outlook using AI classification.

## Architecture

1. **launchd** (`com.song.junk-cleaner.plist`) — runs `run_junk_cleaner.sh` daily at 08:00 via macOS scheduler
2. **Wrapper** (`run_junk_cleaner.sh`) — orchestrates health check, cleanup, and summary extraction
3. **Cleanup** (`batch_cleanup.py`) — deletes known spam via fast rules, classifies unknowns with local LLM (qwen3:8b)
4. **Pattern learning** — new spam patterns are extracted from LLM classifications and added to `spam-patterns.md`

## Files

- `batch_cleanup.py` — main cleanup script (calls Ollama directly, bypassing Gateway)
- `ollama_health.sh` — checks Ollama availability
- `run_junk_cleaner.sh` — wrapper that runs cleanup and outputs targeted summary
- `com.song.junk-cleaner.plist` — macOS launchd configuration
- `spam-patterns.md` — evolving spam pattern rules
- `config.json` — cleanup configuration
- `cleanup-heartbeat.txt` — latest run heartbeat (auto-updated)

## Requirements

- macOS with Ollama running (qwen3:8b model)
- Outlook Graph API credentials (refresh token)
- Python 3 with required packages

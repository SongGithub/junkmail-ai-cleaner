# Junkmail AI Cleaner

Automated junk mail cleanup for Outlook using AI classification.

## Architecture

1. **launchd** (`com.song.junk-cleaner.plist`) — runs `run_junk_cleaner.sh` daily at 08:00 via macOS scheduler
2. **Wrapper** (`run_junk_cleaner.sh`) — orchestrates health check, cleanup, and summary extraction
3. **Cleanup** (`batch_cleanup.py`) — deletes known spam via fast rules, classifies unknowns with local LLM (qwen3:8b)
4. **Pattern learning** — new spam patterns are extracted from LLM classifications and added to `spam-patterns.md`

## OpenClaw dependency

**None.** The entire pipeline runs standalone via launchd + shell + Python.
`batch_cleanup.py` calls Ollama's API directly — it does not go through
OpenClaw Gateway. An optional Gateway cron job can read the results and
report to Discord, but the cleanup itself has no dependency on OpenClaw.

## Files

- `batch_cleanup.py` — main cleanup script (calls Ollama directly)
- `ollama_health.sh` — checks Ollama availability
- `run_junk_cleaner.sh` — wrapper that runs cleanup and outputs targeted summary
- `com.song.junk-cleaner.plist` — macOS launchd configuration
- `spam-patterns.md` — evolving spam pattern rules (placeholder; actual data local)
- `config.json` — cleanup configuration (not tracked in git; contains folder IDs)

## Requirements

### Hardware

- **RAM:** 16 GB minimum (qwen3:8b uses ~5.5 GB + 128K context overhead ~2-3 GB)
- **OS:** macOS (for launchd; can adapt to cron/systemd on Linux)
- **GPU:** Metal (Apple Silicon) recommended — 100% GPU inference gives ~45-50 tok/s

### Software

- [Ollama](https://ollama.com) running locally with `qwen3:8b` model
- Outlook Graph API credentials (refresh token via Microsoft Entra)
- Python 3 with `requests`, `msal`, `json` packages

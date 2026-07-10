# Junkmail AI Cleaner

Automated junk mail cleanup for Outlook using AI classification.

## Usage

Run standalone (from the project directory):
```bash
python3 batch_cleanup.py
```

Or set up automatic daily runs via launchd:
```bash
# Edit com.song.junk-cleaner.plist to set your paths, then:
cp com.song.junk-cleaner.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.song.junk-cleaner.plist
```

Before first run, configure `config.json` with your Outlook app credentials
and refresh token (see Authentication section).

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

- **RAM:** 24 GB minimum, 32 GB recommended (qwen3:8b uses ~9 GB GPU, macOS ~4-6 GB, other apps ~2-4 GB)
- **OS:** macOS (for launchd; can adapt to cron/systemd on Linux)
- **GPU:** Metal (Apple Silicon) recommended — 100% GPU inference gives ~45-50 tok/s

### Software

- [Ollama](https://ollama.com) running locally with `qwen3:8b` model
- Outlook Graph API credentials (refresh token via Microsoft Entra)
- Python 3 with `requests`, `msal`, `json` packages
- Node.js (for get_refresh_token.js helper)
## Authentication (Outlook / Microsoft Graph)

The script uses OAuth 2.0 device code flow to access Outlook mail folders:

1. Register an app in Microsoft Entra with:
   - Redirect URI: `http://localhost` (mobile/desktop)
   - API permission: `Mail.ReadWrite` (delegated)
2. Put the `client_id` (and tenant if not `consumers`) in `config.json`
3. Store the refresh token in macOS keychain:
   ```
   security add-generic-password -a "$USER" -s outlook-refresh -w "YOUR_REFRESH_TOKEN"
   ```
4. The script uses a Node.js helper (`get_refresh_token.js`) to read the token from keychain and obtain an access token via MSAL

The refresh token is not stored in config.json - only the `client_id` and `tenant_id` are.


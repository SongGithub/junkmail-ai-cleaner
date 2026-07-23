# Junkmail AI Cleaner

Automated junk mail cleanup for Outlook using AI classification. Two-tier
design: known spam is deleted by fast keyword rules; unknowns are classified
by a **local** LLM (Ollama), so mail content never leaves your machine except
to Microsoft Graph itself.

## Quick start (turnkey)

```bash
git clone https://github.com/SongGithub/junkmail-ai-cleaner
cd junkmail-ai-cleaner
npm install                              # keytar, for the Keychain token helper
cp config.json.example config.json

# 1. One-time Outlook login (device code — see Authentication below)
MS365_MCP_TENANT_ID=consumers npx -y @softeria/ms-365-mcp-server --login

# 2. Find your junk folder ID and put it in config.json
python3 -m junk_cleaner.preflight --list-folders --skip-llm

# 3. Verify everything end-to-end (auth, Graph, Ollama)
python3 -m junk_cleaner.preflight

# 4. Run it
python3 batch_cleanup.py
```

To schedule daily runs, edit the paths in `com.song.junk-cleaner.plist`, then:

```bash
cp com.song.junk-cleaner.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.song.junk-cleaner.plist
```

> **Launchd Keychain gotcha:** run `python3 -m junk_cleaner.preflight` once
> from Terminal *before* the first scheduled run and click "Always Allow" on
> the Keychain prompt. Without that approval, the token read hangs silently
> when launchd runs it headless at 8am.

## Authentication (Outlook / Microsoft Graph)

The cleaner does **not** implement its own OAuth flow. It reuses the MSAL
token cache that [`@softeria/ms-365-mcp-server`](https://github.com/softeria/ms-365-mcp-server)
writes to the macOS Keychain (service `ms-365-mcp-server`). That's why step 1
of the quick start is that server's device-code login — it's the credential
bootstrap for this repo:

1. `MS365_MCP_TENANT_ID=consumers npx -y @softeria/ms-365-mcp-server --login`
   stores a ~90-day sliding refresh token in the Keychain.
2. At each run, `get_refresh_token.js` reads that token via keytar
   (`junk_cleaner/graph_client.py` falls back to the `security` CLI if Node
   is unavailable — but that path needs a GUI approval, see the gotcha above).
3. The token is exchanged for a Graph access token against the `consumers`
   authority using the same public client ID the MCP server uses (the
   default `client_id` in `config.json.example`).

Two rules that keep this working — both learned the hard way
(see [docs/outlook-auth-troubleshooting.md](docs/outlook-auth-troubleshooting.md)):

- **`tenant_id` must be `consumers`** for personal accounts. Under the
  default `common` authority, Microsoft rejects MSA refresh tokens on
  renewal and sessions die within about an hour.
- **Don't use the MCP server's `--auth-browser` flag** — personal-account
  logins are proxied to login.live.com, which rejects the bundled client
  ID's localhost redirect. Device code is the flow that works.

If the token ever expires (roughly 90 days without a run), re-run step 1.
Nothing secret is stored in this repo: `config.json` (gitignored) holds only
the public client ID and your folder IDs; tokens live in the Keychain.

## Architecture

1. **launchd** (`com.song.junk-cleaner.plist`) — runs `run_junk_cleaner.sh` daily at 08:00 via macOS scheduler
2. **Preflight** (`junk_cleaner/preflight.py`) — verifies config, Keychain token, Graph access, and Ollama *before* the mailbox is touched; a failure aborts the run loudly
3. **Cleanup** (`batch_cleanup.py`) — deletes known spam via fast rules, classifies unknowns with a local LLM (qwen3:8b)
4. **Pattern learning** — new spam patterns are extracted from LLM classifications and logged to `new-patterns.txt`; repeat offenders get an Outlook server-side rule (opt-in via `rules.auto_create_rules`)

Deletes are soft (Graph `DELETE` moves mail to Deleted Items), so mistakes
are recoverable from the mailbox.

## OpenClaw dependency

**None at runtime.** The pipeline runs standalone via launchd + shell +
Python and calls Ollama's API directly. The only shared piece is the
Keychain token cache described under Authentication. An optional OpenClaw
cron job can read the run summary and report to Discord, but the cleanup
itself has no OpenClaw dependency.

## Testing & evals

The failure mode that matters here is silent: a cron job at 8am with nobody
watching, deleting email. Three layers guard it — run all of them with
`make test lint eval` (CI runs the same):

- **Unit tests** (`tests/`) — the fast-pattern matcher (including the
  Telstra legit-domain carve-out) and a schema-drift gate that fails when
  `config.json.example` stops matching what the code reads.
- **LLM output-contract tests** (`tests/test_ollama_client.py`) — local
  models return markdown fences, chatter, control characters, bare dicts,
  or nothing; these tests pin down that `classify()` degrades to "keep the
  mail" instead of crashing, for every malformed shape we've seen.
- **Golden-set eval** (`eval/`) — a labeled spam/ham set run through both
  tiers. The hard gate is **zero deleted ham**: a false positive destroys
  real mail, while a missed spam just waits for the next run. Over-broad
  legacy patterns (e.g. `fidelity`, `toronto`, `home security`) are tracked
  in the golden set as `known_gap` entries — reported on every run,
  excluded from the gate, and re-armed as regression gates the moment the
  pattern is tightened. `make eval` is offline; `make eval-llm` also
  exercises the real model via Ollama (spam recall ≥ 60%, deleted ham = 0).
- **Preflight** (`make preflight`) — the runtime gotchas that unit tests
  can't see (expired token, revoked consent, Ollama not running, model not
  pulled) are caught by `run_junk_cleaner.sh` running the preflight before
  every scheduled cleanup and aborting with the mailbox untouched. Run it
  manually after any config or dependency change instead of waiting for
  tomorrow's cron.

## Security & supply chain

- **Runtime is Python stdlib-only** (urllib, json) — no third-party Python
  packages to compromise. Dev tooling (`requirements-dev.txt`) is
  pinned-minimum and audited with `pip-audit` in CI; the single npm
  dependency (keytar) is audited with `npm audit`. Dependabot watches pip,
  npm, and GitHub Actions weekly.
- **No secrets in the repo.** Tokens live in the macOS Keychain;
  `config.json` is gitignored and contains only a public client ID and
  folder IDs.
- **Mail content stays local.** Classification runs on a local Ollama
  model; the only external calls are to Microsoft Graph and the Microsoft
  token endpoint.
- **Known accepted risk:** auth rides on the ms-365-mcp-server public
  client ID and its Keychain cache format, both fetched via `npx` at login
  time. Registering your own Entra app and implementing device-code login
  natively (Python `msal`) would remove that trust edge — tracked as
  roadmap.

## Scalability

Deliberately a single-user, single-mailbox local tool — privacy is the
point. What scales, and how:

- **Mailbox volume:** paged fetches (`tuning.fetch_batch`), throttled
  deletes, and Graph 429 `Retry-After` backoff are already in place;
  thousands of junk messages per run is routine.
- **LLM throughput:** `ollama.batch_size` emails per call; on Apple Silicon
  qwen3:8b sustains ~45-50 tok/s. Swap `ollama.model` for a bigger model
  for accuracy or a smaller one for speed — then re-run `make eval-llm`,
  which is the whole reason the eval exists.
- **Multiple accounts:** one workspace per account — point
  `JUNK_CLEANER_HOME` at a directory with its own `config.json`, duplicate
  the plist under a new label, and use `MS365_KEYCHAIN_SERVICE` to separate
  token caches.
- **Beyond that** (multi-tenant service, shared queue) is out of scope by
  design: it would mean routing other people's mail through shared
  infrastructure, which this project exists to avoid.

## Files

- `batch_cleanup.py` — entry point (calls Ollama directly)
- `junk_cleaner/` — config, Graph client, pattern matcher, Ollama client, preflight, runner
- `get_refresh_token.js` — Keychain token helper (Node + keytar)
- `run_junk_cleaner.sh` — wrapper: preflight → cleanup → targeted summary
- `ollama_health.sh` — standalone Ollama health probe
- `com.song.junk-cleaner.plist` — macOS launchd schedule
- `config.json.example` — copy to `config.json` and edit
- `spam-patterns.md` — evolving spam pattern notes (placeholder; live data stays local)
- `eval/` — golden set + eval harness; `tests/` — unit tests
- `docs/outlook-auth-troubleshooting.md` — auth failure modes and fixes

## Requirements

### Hardware

- **RAM:** 24 GB minimum, 32 GB recommended (qwen3:8b uses ~9 GB GPU, macOS ~4-6 GB, other apps ~2-4 GB)
- **OS:** macOS (launchd + Keychain; adapting to Linux means replacing both)
- **GPU:** Metal (Apple Silicon) recommended — 100% GPU inference gives ~45-50 tok/s

### Software

- [Ollama](https://ollama.com) with `qwen3:8b` pulled (`ollama pull qwen3:8b`)
- Python 3.10+ (stdlib only at runtime; `pip install -r requirements-dev.txt` for tests)
- Node.js + `npm install` (keytar Keychain helper)
- A personal Microsoft account (@live.com / @outlook.com) — work/school
  tenants have different auth constraints not covered here

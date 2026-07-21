# Outlook auth troubleshooting (personal Microsoft accounts)

Notes from debugging the `@softeria/ms-365-mcp-server` login used by the
OpenClaw `outlook-personal` MCP server (2026-07-21). The same rules apply to
any MSAL-based auth against a personal account (@live.com / @outlook.com),
including this repo's own device-code flow.

## Symptom 1: browser login fails with `invalid_request: redirect_uri not valid`

```
npx @softeria/ms-365-mcp-server --login --auth-browser --preset mail
→ We're unable to complete your request
  invalid_request: The provided value for the input parameter 'redirect_uri' is not valid.
```

**Root cause:** personal-account logins get proxied from the converged
`login.microsoftonline.com` endpoint to the legacy consumer endpoint
`login.live.com`, which requires an *exact* match on the registered redirect
URIs. MSAL's browser flow listens on `http://localhost:<random port>`, and the
MCP server's bundled client ID does not have that loopback URI registered on
the consumer side. Not fixable from the client — the flag simply cannot work
for MSA accounts with the bundled app.

**Fix:** use device code flow instead (no redirect URI involved):

```bash
MS365_MCP_TENANT_ID=consumers npx -y @softeria/ms-365-mcp-server --login --preset mail
```

(Browser flow only works if you register your *own* Entra app — "Personal
Microsoft accounts" account type, platform "Mobile and desktop applications",
redirect URI `http://localhost` — and pass it via `MS365_MCP_CLIENT_ID`.
That is what this repo's standalone pipeline does; see the README
Authentication section.)

## Symptom 2: session dies ~1 hour after login

**Root cause:** the tenant/authority, not the login flow. With the default
`common` authority, Microsoft issues MSA tokens at login but **rejects the
refresh token on renewal**, so you are left with only the initial access
token's lifetime.

**Fix:** always use the `consumers` authority for personal accounts
(`MS365_MCP_TENANT_ID=consumers`, or `"tenant_id": "consumers"` in this
repo's `config.json`). With `consumers`, refresh works and the session slides
for ~90 days, renewing on every use.

**Note:** token lifetime does *not* depend on device-code vs. browser flow.
Both request `offline_access` and get the same refresh token. The tenant is
what matters.

## Where tokens live (ms-365-mcp-server)

- Tokens are stored in the **macOS Keychain** (via keytar), shared between
  the login CLI and the running MCP server — a CLI login is immediately
  visible to the server.
- The `MS365_MCP_TOKEN_CACHE_PATH` file is never created while the Keychain
  is available. That is normal, not a failure.
- Check auth state with `--verify-login` using the same env vars as the
  server:

  ```bash
  MS365_MCP_TENANT_ID=consumers npx -y @softeria/ms-365-mcp-server --verify-login
  ```

## Config changes applied to OpenClaw (2026-07-21)

- Removed `--auth-browser` from the `outlook-personal` server args in
  `openclaw.json` so interactive re-auth defaults to device code.
- `MS365_MCP_TENANT_ID=consumers` kept in the server env so refresh happens
  under the same authority the login used.

#!/usr/bin/env node
/**
 * Read the MSAL refresh token from the macOS Keychain.
 *
 * The token cache is seeded by a one-time device-code login:
 *   MS365_MCP_TENANT_ID=consumers npx -y @softeria/ms-365-mcp-server --login
 * (see README "Authentication"). This helper reads that cache via keytar —
 * the same library the MCP server uses — which avoids the GUI approval
 * prompt that `security find-generic-password -w` triggers under launchd.
 *
 * The keychain often has two refresh tokens for the same MSA account.
 * We must pick the valid one (the other is expired but still listed).
 *
 * Output: the refresh token on stdout.
 * Exit codes: 2 = no keychain entry, 3 = no refresh token in cache,
 *             4 = keytar not installed (run `npm install`).
 */
let keytar;
try {
  keytar = require('keytar');
} catch (e) {
  console.error('keytar not found — run `npm install` in the repo root first');
  process.exit(4);
}

const SERVICE = process.env.MS365_KEYCHAIN_SERVICE || 'ms-365-mcp-server';
const ACCOUNT = process.env.MS365_KEYCHAIN_ACCOUNT || 'msal-token-cache';

async function main() {
  const raw = await keytar.getPassword(SERVICE, ACCOUNT);
  if (!raw) {
    console.error(`No Keychain entry for ${SERVICE}/${ACCOUNT} — run the device-code login first`);
    process.exit(2);
  }

  const parsed = JSON.parse(raw);
  const data = JSON.parse(parsed.data);
  const tokens = Object.values(data.RefreshToken || {});
  if (tokens.length === 0) {
    console.error('MSAL cache has no refresh token — re-run the device-code login');
    process.exit(3);
  }

  // The keychain may contain stale/expired tokens alongside valid ones.
  // The valid MSA artifact token contains "MsaArtifacts" in its secret value.
  // Try that first, then fall back to the last token in the list (newest).
  const msa = tokens.find(t => (t.secret || '').includes('MsaArtifacts'));
  console.log((msa || tokens[tokens.length - 1]).secret);
}

main().catch(err => {
  console.error(String(err));
  process.exit(1);
});

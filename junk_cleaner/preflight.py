"""End-to-end preflight: verify every dependency the 8am cron run needs.

Run after install or any change, and automatically before each scheduled
cleanup (see run_junk_cleaner.sh):

    python3 -m junk_cleaner.preflight                # full check
    python3 -m junk_cleaner.preflight --skip-llm     # without Ollama
    python3 -m junk_cleaner.preflight --list-folders # print mail folder IDs

Checks, in order:
  1. config.json parses and has every key the code reads
  2. refresh token is readable from the Keychain (node helper or fallback)
  3. token refresh succeeds against the Microsoft authority
  4. Graph API is reachable and the configured junk folder exists
  5. Ollama is up, the model is present, and a test inference returns

Exits non-zero on any failure so launchd logs (or a wrapper) surface it.
"""
import argparse, sys, urllib.request, urllib.error


def _ok(name, detail=""):
    print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))
    return True


def _fail(name, detail=""):
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
    return False


def check_config():
    try:
        from junk_cleaner import config  # noqa: F401  (import validates all keys)
        return _ok("config", f"loaded {config.CONFIG_FILE}")
    except SystemExit:
        return _fail("config", "config.json not found — copy config.json.example and edit it")
    except KeyError as e:
        return _fail("config", f"missing key {e} — compare against config.json.example")
    except Exception as e:
        return _fail("config", str(e))


def check_token():
    try:
        from junk_cleaner.graph_client import get_access_token
        return get_access_token(), _ok("auth", "refresh token exchanged for access token")
    except Exception as e:
        _fail("auth", str(e))
        print("        hint: seed the Keychain with a device-code login (README 'Authentication'),")
        print("        then run this preflight once from Terminal to approve Keychain access.")
        return None, False


def check_graph(token):
    from junk_cleaner.config import GRAPH_BASE, JUNK_FOLDER_ID
    try:
        from junk_cleaner.graph_client import graph_get
        me = graph_get(f"{GRAPH_BASE.rsplit('/me', 1)[0]}/me?$select=userPrincipalName", token)
        _ok("graph api", f"signed in as {me.get('userPrincipalName', '?')}")
    except Exception as e:
        return _fail("graph api", str(e))
    try:
        from junk_cleaner.graph_client import graph_get
        folder = graph_get(f"{GRAPH_BASE}/mailFolders/{JUNK_FOLDER_ID}?$select=displayName,totalItemCount", token)
        return _ok("junk folder", f"'{folder.get('displayName')}' ({folder.get('totalItemCount')} messages)")
    except urllib.error.HTTPError as e:
        return _fail("junk folder", f"HTTP {e.code} — check junk_folder_id (try --list-folders)")
    except Exception as e:
        return _fail("junk folder", str(e))


def check_ollama():
    from junk_cleaner.health_check import preflight_check
    pf = preflight_check()
    if not pf.get("ollama_reachable"):
        _fail("ollama", pf.get("ollama_error", "not reachable"))
        print("        note: cleanup would still run fast-pattern deletes, but no LLM classification.")
        return False
    if not pf.get("model_loaded"):
        from junk_cleaner.config import LLM_MODEL
        return _fail("ollama model", f"{LLM_MODEL} not found — run: ollama pull {LLM_MODEL}")
    if "inference_error" in pf:
        return _fail("ollama inference", pf["inference_error"])
    return _ok("ollama", f"model ready, test inference {pf.get('inference_s')}s @ {pf.get('tok_s', '?')} tok/s")


def list_folders(token):
    from junk_cleaner.config import GRAPH_BASE
    from junk_cleaner.graph_client import graph_get
    data = graph_get(f"{GRAPH_BASE}/mailFolders?$top=50&$select=id,displayName,totalItemCount", token)
    print(f"{'displayName':30} {'items':>7}  id")
    for f in data.get("value", []):
        print(f"{f['displayName']:30} {f.get('totalItemCount', 0):>7}  {f['id']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-llm", action="store_true", help="skip the Ollama checks")
    ap.add_argument("--skip-auth", action="store_true", help="skip Keychain/Graph checks (config + Ollama only)")
    ap.add_argument("--list-folders", action="store_true", help="print mail folder IDs and exit")
    args = ap.parse_args()

    print("junk_cleaner preflight:")
    passed = check_config()
    if not passed:
        sys.exit(1)

    if not args.skip_auth:
        token, auth_ok = check_token()
        passed = auth_ok and passed
        if auth_ok:
            if args.list_folders:
                list_folders(token)
                sys.exit(0)
            passed = check_graph(token) and passed
    elif args.list_folders:
        print("  --list-folders requires auth; drop --skip-auth")
        sys.exit(1)

    if not args.skip_llm:
        passed = check_ollama() and passed

    print("preflight:", "ALL CHECKS PASSED" if passed else "FAILED — fix before the next scheduled run")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

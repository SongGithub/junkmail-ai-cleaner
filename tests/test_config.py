"""config.json.example must stay in sync with every key the code reads.

This is the schema-drift gate: if config.py starts reading a new key,
this import fails until config.json.example documents it.
"""


def test_example_config_satisfies_code():
    import junk_cleaner.config as c

    assert c.CLIENT_ID
    assert c.TENANT_ID == "consumers"
    assert c.AUTHORITY_URL.startswith("https://login.microsoftonline.com/")
    assert c.OLLAMA_URL and c.LLM_MODEL
    assert c.FETCH_BATCH > 0 and c.RETRY_LIMIT > 0


def test_tenant_matches_authority():
    """A common-tenant authority with consumers tenant (or vice versa) is the
    bug that kills sessions after ~1h — see docs/outlook-auth-troubleshooting.md."""
    import junk_cleaner.config as c

    assert f"/{c.TENANT_ID}/" in c.AUTHORITY_URL

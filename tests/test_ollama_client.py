"""LLM output-contract tests: classify() must survive every malformed shape
a local model actually produces (markdown fences, commentary, control chars,
bare dicts, garbage) without crashing the 8am run.

No Ollama needed — the HTTP layer is stubbed.
"""
import io, json

import junk_cleaner.ollama_client as oc

EMAILS = [{"id": 1, "subject": "hi", "sender": "x"}]


def _stub_response(monkeypatch, response_text):
    body = json.dumps({"response": response_text, "eval_count": 10, "eval_duration": 10**9})

    def fake_urlopen(req, timeout=None):
        return io.BytesIO(body.encode())

    monkeypatch.setattr(oc.urllib.request, "urlopen", fake_urlopen)


def test_clean_json_array(monkeypatch):
    _stub_response(monkeypatch, '[{"id": 1, "verdict": "DELETE", "category": "ads"}]')
    assert oc.classify(EMAILS) == [{"id": 1, "verdict": "DELETE", "category": "ads"}]


def test_json_wrapped_in_markdown_fence_and_chatter(monkeypatch):
    _stub_response(monkeypatch,
        'Sure! Here is the classification:\n```json\n[{"id": 1, "verdict": "KEEP", "category": "receipt"}]\n```')
    assert oc.classify(EMAILS)[0]["verdict"] == "KEEP"


def test_bare_dict_is_normalised_to_list(monkeypatch):
    _stub_response(monkeypatch, '{"id": 1, "verdict": "DELETE", "category": "phish"}')
    result = oc.classify(EMAILS)
    assert isinstance(result, list) and result[0]["id"] == 1


def test_control_chars_are_stripped(monkeypatch):
    _stub_response(monkeypatch, '[{"id": 1, "verdict": "DELETE", "category": "ads\x01"}]')
    assert oc.classify(EMAILS)[0]["verdict"] == "DELETE"


def test_no_json_returns_empty_not_crash(monkeypatch):
    _stub_response(monkeypatch, "I cannot classify these emails, sorry.")
    assert oc.classify(EMAILS) == []


def test_empty_response_returns_empty(monkeypatch):
    _stub_response(monkeypatch, "")
    assert oc.classify(EMAILS) == []


def test_network_error_returns_empty_not_crash(monkeypatch):
    def boom(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(oc.urllib.request, "urlopen", boom)
    assert oc.classify(EMAILS) == []

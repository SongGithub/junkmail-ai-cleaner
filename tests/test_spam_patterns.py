"""Unit tests for the fast-path pattern matcher."""
from junk_cleaner.spam_patterns import fast_match, extract_brand_from_email


def test_known_spam_matches():
    cat, matched = fast_match("Find your match today!", "eHarmony")
    assert matched and cat == "eharmony"


def test_match_is_case_insensitive_and_spans_subject_and_sender():
    cat, matched = fast_match("URGENT: your CARSHIELD quote", "Auto Dept")
    assert matched and cat == "CarShield"


def test_clean_email_passes_through():
    cat, matched = fast_match("Dinner on Saturday?", "Alice Chen", "alice@gmail.com")
    assert not matched and cat is None


def test_telstra_spoof_is_spam():
    cat, matched = fast_match("Your Telstra bill", "Telstra", "billing@telstra-payments.xyz")
    assert matched and cat == "Telstra"


def test_telstra_real_domain_is_kept():
    cat, matched = fast_match("Your Telstra bill", "Telstra", "noreply@telstra.com.au")
    assert not matched


def test_telstra_missing_sender_email_treated_as_spam():
    cat, matched = fast_match("Your Telstra bill", "Telstra", "")
    assert matched


def test_extract_brand_uses_sender_when_not_a_relay():
    p = extract_brand_from_email("50% off everything", "MegaStore Deals", "ads")
    assert p["brand"] == "MegaStore Deals"
    assert p["category"] == "ads"


def test_extract_brand_falls_back_on_relay_domains():
    p = extract_brand_from_email("You won a prize", "noreply@ilyclicker.example", "prize")
    assert p["brand"].startswith("[Unknown")

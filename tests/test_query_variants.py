"""footage_library.query_variants(): expanding a scene's search phrase into
provider-query attempts. Real repetition case (2026-08-14): the same handful
of cached clips (moon, meditation, forest categories) kept getting reused up
to 7x in 3 days despite a 30-day same-channel cooldown penalty, because the
generated phrase's exact word ("moonlit") never matched the synonym
dictionary's key ("moon"), and the two lowest-value variants (widened,
first-word) crowded the real synonyms/broad fallbacks out of the caller's
bounded per-segment query budget."""
import sys

import pytest

import footage_library as fl
from tests.test_private_admin import _fresh_app


@pytest.fixture()
def app_module(tmp_path):
    for m in ("footage_library",):
        sys.modules.pop(m, None)
    return _fresh_app(tmp_path)


def test_inflected_word_still_matches_its_synonym_stem():
    variants = fl.query_variants("moonlit night sky")
    # exact-match-only would have missed these entirely (real bug: "moonlit" != "moon")
    assert "full moon" in variants
    assert "moonlight night" in variants


def test_stem_key_matches_multiple_inflections():
    for phrase in ("meditation calm mind", "person meditating peacefully", "meditate daily"):
        variants = fl.query_variants(phrase)
        assert "person meditating nature" in variants, phrase


def test_short_common_word_does_not_spuriously_match_a_longer_key():
    # "for" must not match the "forest" key via the reverse (key.startswith)
    # direction -- only word.startswith(key) or word len>=4 is allowed to
    # trigger the reverse match.
    variants = fl.query_variants("waiting for an answer")
    assert "misty forest morning" not in variants[:2]  # only as the shared broad fallback, not a synonym hit


def test_synonyms_land_within_the_real_per_segment_budget():
    # PEXELS_MAX_SEARCH_QUERIES_PER_SEGMENT budget (6) must actually reach
    # the relevant synonyms, not just theoretically list them further down.
    from app_settings import settings
    budget = settings.PEXELS_MAX_SEARCH_QUERIES_PER_SEGMENT
    variants = fl.query_variants("moonlit night sky")[:budget]
    assert any(v in variants for v in ("full moon", "moonlight night"))


def test_synonyms_precede_the_low_value_widened_and_first_word_variants():
    variants = fl.query_variants("runes ancient symbols")
    syn_idx = variants.index("carved runes stone")
    widened_idx = variants.index("runes ancient")
    first_word_idx = variants.index("runes")
    assert syn_idx < widened_idx
    assert syn_idx < first_word_idx


def test_original_phrase_always_first():
    variants = fl.query_variants("full moon ritual")
    assert variants[0] == "full moon ritual"


def test_broad_fallbacks_always_present_and_deduped():
    variants = fl.query_variants("crystal healing energy")
    assert "starry night sky" in variants
    assert len(variants) == len(set(v.lower() for v in variants))


def test_all_new_niche_synonym_stems_resolve_from_realistic_phrasing():
    # Each stem key added for the categories observed repeating (2026-08-14)
    # must actually fire on a plausible AI-generated scene phrase -- a typo
    # in the stem (e.g. "zodiak" instead of "zodiac") would silently make
    # that whole category fall through to the generic broad fallbacks again,
    # exactly the failure mode this fix targets.
    cases = {
        "zodiac symbols aesthetic in the night sky": "constellations",
        "ancient rune carved in stone": "carved runes stone",
        "person balancing their chakra energy": "hands energy closeup",
        "a vivid dream about flying": "surreal dreamy scene",
        "old buddhist temple at sunrise": "old temple ruins",
        "digital clock showing repeating numbers": "digital clock numbers",
        "feeling drained of energy today": "person alone thoughtful",
    }
    for phrase, expected_synonym in cases.items():
        variants = fl.query_variants(phrase)
        assert expected_synonym in variants, f"{phrase!r} -> missing {expected_synonym!r} in {variants}"


def test_acquire_segment_asset_sends_the_reordered_variants_to_providers(app_module, monkeypatch):
    # Integration-level check at the real call site of the bug (not just
    # query_variants() in isolation): with an empty local library, the
    # network stage must try the synonym-bearing queries before the
    # low-value widened/first-word ones, within the real configured budget.
    import footage_library as fl_mod
    from database import SessionLocal
    from app_settings import settings

    attempted_queries: list[str] = []

    def fake_search_both_providers(query, **kwargs):
        attempted_queries.append(query)
        return []  # force exhaustion so the loop keeps advancing through variants

    monkeypatch.setattr(fl_mod, "search_both_providers", fake_search_both_providers)

    db = SessionLocal()
    try:
        chosen, stats = fl_mod.acquire_segment_asset(
            db, query="moonlit night sky", channel_id=999999, project_id=999999,
            job_id=999999, min_duration=3.0, used_asset_ids=set(), used_hashes=set(),
            allow_network=True,
        )
    finally:
        db.close()

    assert chosen is None  # every candidate was force-exhausted, as intended
    budget = settings.PEXELS_MAX_SEARCH_QUERIES_PER_SEGMENT
    expected_variants = fl_mod.query_variants("moonlit night sky")[:budget]
    # dedupe attempted_queries to variant identity, preserving first-seen order
    seen_order = list(dict.fromkeys(attempted_queries))
    assert seen_order == expected_variants
    assert "full moon" in seen_order[:3]  # reaches the real synonym early, not buried past budget

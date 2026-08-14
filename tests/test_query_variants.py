"""footage_library.query_variants(): expanding a scene's search phrase into
provider-query attempts. Real repetition case (2026-08-14): the same handful
of cached clips (moon, meditation, forest categories) kept getting reused up
to 7x in 3 days despite a 30-day same-channel cooldown penalty, because the
generated phrase's exact word ("moonlit") never matched the synonym
dictionary's key ("moon"), and the two lowest-value variants (widened,
first-word) crowded the real synonyms/broad fallbacks out of the caller's
bounded per-segment query budget."""
import footage_library as fl


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

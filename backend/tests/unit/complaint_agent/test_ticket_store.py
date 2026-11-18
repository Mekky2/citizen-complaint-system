"""Duplicate detection for the in-memory ticket store.

These tests cover the cases the team cares about:

* an identical complaint in a new session is flagged;
* a near-duplicate with a filler prefix ("في مشكلة ...") is still flagged, because Arabic
  token normalization drops the filler and the overlap coefficient ignores the extra words;
* identical wording in another category is not a duplicate;
* a ticket that already reached a terminal status is not offered for linking;
* one shared word alone is not enough, and the threshold stays configurable.
"""

from app.services.ticket_store import (
    DEFAULT_DUPLICATE_THRESHOLD,
    InMemoryTicketStore,
    duplicate_similarity,
)

LOCATION = {"governorate": "الجيزة", "city": "", "street": "النيل", "landmark": ""}


def _create(
    store: InMemoryTicketStore,
    description: str = "ماسورة مياه مكسورة في شارع النيل",
    category: str = "Water",
):
    return store.create(
        title=description,
        description=description,
        category=category,
        authority="مديرية المياه",
        location=LOCATION,
    )


def test_exact_duplicate_is_detected():
    store = InMemoryTicketStore()
    ticket = _create(store)

    found = store.find_similar(
        category="Water",
        description="ماسورة مياه مكسورة في شارع النيل",
        location=LOCATION,
    )

    assert found is not None
    assert found[0].ticket_id == ticket.ticket_id
    assert found[1] == 1.0


def test_duplicate_with_filler_prefix_is_detected():
    """Regression: "في مشكلة ..." must not hide an otherwise identical complaint."""
    store = InMemoryTicketStore()
    ticket = _create(store, description="في مشكلة ماسورة مياه مكسورة في شارع النيل")

    found = store.find_similar(
        category="Water",
        description="ماسورة مياه مكسورة في شارع النيل",
        location=LOCATION,
    )

    assert found is not None
    assert found[0].ticket_id == ticket.ticket_id
    # Overlap coefficient wins over Jaccard here, so the filler prefix costs nothing.
    assert found[1] == 1.0


def test_same_words_in_another_category_do_not_match():
    store = InMemoryTicketStore()
    _create(store, description="ماسورة مياه مكسورة في شارع النيل", category="Water")

    found = store.find_similar(
        category="Roads",
        description="ماسورة مياه مكسورة في شارع النيل",
        location=LOCATION,
    )

    assert found is None


def test_closed_ticket_is_not_a_duplicate_candidate():
    store = InMemoryTicketStore()
    ticket = _create(store)
    for status in ("Approved", "In Progress", "Verifying", "Done"):
        store.update_status(ticket.ticket_id, status)
    assert store.get(ticket.ticket_id).status == "Done"

    found = store.find_similar(
        category="Water",
        description="ماسورة مياه مكسورة في شارع النيل",
        location=LOCATION,
    )

    assert found is None


def test_single_shared_word_is_not_enough():
    store = InMemoryTicketStore()
    _create(store, description="ماسورة مياه مكسورة في شارع النيل")

    found = store.find_similar(
        category="Water",
        description="مياه",
        location=LOCATION,
    )

    assert found is None


def test_threshold_is_configurable():
    store = InMemoryTicketStore()
    _create(store, description="ماسورة مياه مكسورة في شارع النيل")

    strict = store.find_similar(
        category="Water",
        description="ماسورة مياه مكسورة في شارع النيل",
        location=LOCATION,
        threshold=1.01,
    )
    lenient = store.find_similar(
        category="Water",
        description="ماسورة مياه مكسورة قرب شارع النيل",
        location=LOCATION,
        threshold=0.3,
    )

    assert strict is None
    assert lenient is not None


def test_default_threshold_is_documented_value():
    assert DEFAULT_DUPLICATE_THRESHOLD == 0.45


def test_similarity_prefers_overlap_for_extra_words():
    base = {"مياه", "كسر", "نيل"}
    longer = {"مشكله", "مياه", "كسر", "نيل"}

    # Jaccard would be 0.75; the overlap coefficient is 1.0 and wins.
    assert duplicate_similarity(base, longer) == 1.0
    assert duplicate_similarity(set(), base) == 0.0
    assert duplicate_similarity({"مياه"}, {"طرق"}) == 0.0

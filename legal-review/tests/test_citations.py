"""Citation verification: fabricated quotes must be rejected."""

import pytest

from lexreview.citations import MIN_QUOTE_CHARS, Rejected, VerifiedQuote, normalize, verify_quote


@pytest.fixture
def env(ingested):
    w = ingested
    ctx = w.ctx("alice", w.case_a)
    return w, ctx, w.app.store(ctx)


def test_exact_quote_verifies_with_offsets(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    q = "Meridian shall maintain product between 2 and 8 degrees Celsius at all times."
    r = verify_quote(store, ctx, msa, 4, q)
    assert isinstance(r, VerifiedQuote) and r.page_no == 4
    page = store.get_page(ctx, msa, 4).text
    assert normalize(page[r.char_start:r.char_end]) == normalize(q)


def test_fabricated_quote_rejected(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    r = verify_quote(store, ctx, msa, 4, "Meridian has no liability for temperature excursions.")
    assert r == Rejected("quote_not_on_page")


def test_subtly_altered_quote_rejected(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    for q in ("Meridian shall maintain product between 2 and 9 degrees Celsius at all times.",
              "Meridian may maintain product between 2 and 8 degrees Celsius at all times.",
              "meridian shall maintain product between 2 and 8 degrees celsius at all times."):
        assert isinstance(verify_quote(store, ctx, msa, 4, q), Rejected), q


def test_right_quote_wrong_page_rejected(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    q = "Meridian shall maintain product between 2 and 8 degrees Celsius"
    assert isinstance(verify_quote(store, ctx, msa, 4, q), VerifiedQuote)
    assert verify_quote(store, ctx, msa, 5, q) == Rejected("quote_not_on_page")


def test_nonexistent_doc_or_page_rejected(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    q = "Meridian shall maintain product between 2 and 8 degrees Celsius"
    assert verify_quote(store, ctx, "d_000000", 1, q) == Rejected("doc_or_page_not_found")
    assert verify_quote(store, ctx, msa, 99, q) == Rejected("doc_or_page_not_found")


def test_quote_from_other_case_rejected(env):
    w, ctx, store = env
    ctx_b = w.ctx("carol", w.case_b)
    b_msa = [d for d in w.app.store(ctx_b).list_documents(ctx_b) if d["source_name"].endswith("agreement.pdf")][0]
    q = "Meridian shall maintain product between 2 and 8 degrees Celsius"
    assert verify_quote(store, ctx, b_msa["doc_id"], 4, q) == Rejected("doc_or_page_not_found")


def test_restricted_doc_quote_rejected_for_unprivileged(env):
    w, _, _ = env
    ctx = w.ctx("bob", w.case_a)
    amend = w.docs["docs/contracts/amendment_1.docx"]["doc_id"]
    r = verify_quote(w.app.store(ctx), ctx, amend, 1, "require notice of any Temperature Excursion within one hour")
    assert r == Rejected("doc_or_page_not_found")


def test_too_short_quote_rejected(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    assert verify_quote(store, ctx, msa, 4, "x" * (MIN_QUOTE_CHARS - 1)) == Rejected("quote_too_short")


def test_whitespace_and_typography_normalized(env):
    w, ctx, store = env
    msa = w.docs["docs/contracts/master_services_agreement.pdf"]["doc_id"]
    q = "Meridian   shall maintain\nproduct between 2 and 8 degrees Celsius"
    assert isinstance(verify_quote(store, ctx, msa, 4, q), VerifiedQuote)


def test_normalization_rules():
    assert normalize("“quoted” — text") == '"quoted" - text'
    assert normalize("exam-\nple  of\tspace") == "example of space"
    assert normalize("ﬁnal") == "final"
